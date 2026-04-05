"""
Shared test fixtures and the DuckDB mock profiler.

Testing strategy:
  - No real warehouse connection needed for any test
  - DuckDB stands in for Snowflake — it speaks a very similar SQL dialect
    and supports TABLESAMPLE, APPROX_COUNT_DISTINCT (via approx_count_distinct()),
    and window functions
  - Pre-baked column profiles (JSON fixtures) for document/enricher/renderer tests
  - Mock agent_outputs fixture reused from cli.py's _builtin_fixture()
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ── DuckDB mock profiler ───────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def duckdb_conn():
    """
    In-memory DuckDB database seeded with test tables that mirror
    a minimal e-commerce schema.

    Tables:
      orders        — 1,000 rows, various statuses, some nulls, encoded nulls
      order_items   — 3,500 rows, one-to-many with orders
      customers     — 250 rows, dimension table
      products      — 80 rows, dimension table
    """
    import duckdb
    con = duckdb.connect(":memory:")

    con.execute("""
        CREATE TABLE customers (
            customer_id  INTEGER PRIMARY KEY,
            name         VARCHAR,
            email        VARCHAR,
            region       VARCHAR,
            created_at   DATE
        )
    """)
    con.execute("""
        INSERT INTO customers
        SELECT
            i AS customer_id,
            'Customer ' || i AS name,
            'user' || i || '@example.com' AS email,
            CASE WHEN i % 3 = 0 THEN 'EMEA'
                 WHEN i % 3 = 1 THEN 'AMER'
                 ELSE 'APAC' END AS region,
            DATE '2022-01-01' + INTERVAL (i) DAY AS created_at
        FROM generate_series(1, 250) t(i)
    """)

    con.execute("""
        CREATE TABLE products (
            product_id    INTEGER PRIMARY KEY,
            name          VARCHAR,
            category      VARCHAR,
            price         DECIMAL(10, 2)
        )
    """)
    con.execute("""
        INSERT INTO products
        SELECT
            i AS product_id,
            'Product ' || i AS name,
            CASE WHEN i % 4 = 0 THEN 'Electronics'
                 WHEN i % 4 = 1 THEN 'Apparel'
                 WHEN i % 4 = 2 THEN 'Home'
                 ELSE 'Books' END AS category,
            ROUND(9.99 + (i * 7.5) % 200, 2) AS price
        FROM generate_series(1, 80) t(i)
    """)

    con.execute("""
        CREATE TABLE orders (
            order_id       INTEGER PRIMARY KEY,
            customer_id    INTEGER,
            order_date     DATE,
            status         VARCHAR,
            revenue        DECIMAL(12, 2),
            discount       DECIMAL(12, 2),
            created_at     TIMESTAMP
        )
    """)
    con.execute("""
        INSERT INTO orders
        SELECT
            i AS order_id,
            (i % 250) + 1 AS customer_id,
            DATE '2023-01-01' + INTERVAL (i % 365) DAY AS order_date,
            CASE WHEN i % 10 = 0 THEN 'N/A'       -- encoded null (10%)
                 WHEN i % 7  = 0 THEN 'refunded'
                 WHEN i % 3  = 0 THEN 'pending'
                 ELSE 'completed' END AS status,
            CASE WHEN i % 10 = 0 THEN NULL          -- 10% null revenue
                 ELSE ROUND(10.0 + (i * 13.7) % 500, 2) END AS revenue,
            ROUND((i % 50) * 1.0, 2) AS discount,
            TIMESTAMP '2023-01-01 00:00:00' + INTERVAL (i * 3600) SECOND AS created_at
        FROM generate_series(1, 1000) t(i)
    """)

    con.execute("""
        CREATE TABLE order_items (
            order_id     INTEGER,
            line_item_id INTEGER,
            product_id   INTEGER,
            quantity     INTEGER,
            unit_price   DECIMAL(10, 2),
            PRIMARY KEY (order_id, line_item_id)
        )
    """)
    con.execute("""
        INSERT INTO order_items
        SELECT
            (i % 1000) + 1                       AS order_id,
            CAST(FLOOR(i / 1000) AS INTEGER) + 1 AS line_item_id,
            (i % 80) + 1                         AS product_id,
            (i % 5) + 1                          AS quantity,
            ROUND(9.99 + (i % 100), 2)           AS unit_price
        FROM generate_series(0, 3499) t(i)
    """)

    yield con
    con.close()


@pytest.fixture(scope="session")
def mock_profiler(duckdb_conn, tmp_path_factory):
    """
    A MockProfiler that wraps DuckDB and satisfies the BaseProfiler interface.
    Used to test profiling logic without a real warehouse.
    """
    from runtime.profiler.base import BaseProfiler

    class DuckDBProfiler(BaseProfiler):
        WAREHOUSE_TYPE = "duckdb_test"

        def __init__(self, conn, profiles_dir):
            self.connection = conn
            self._profiles_dir = profiles_dir
            self._profiles_dir.mkdir(parents=True, exist_ok=True)
            self.credentials = {}
            self._lock = threading.Lock()  # DuckDB connections are not thread-safe

        def connect(self): pass
        def disconnect(self): pass

        def execute(self, sql: str) -> list[dict]:
            with self._lock:
                cursor = self.connection.execute(sql)
                cols = [desc[0] for desc in cursor.description]
                return [dict(zip(cols, row)) for row in cursor.fetchall()]

        def get_schemas_sql(self) -> str:
            return "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'main'"

        def get_tables_sql(self, schema: str) -> str:
            return (
                "SELECT table_name, NULL AS size_bytes, NULL AS last_modified "
                "FROM information_schema.tables WHERE table_schema = 'main'"
            )

        def get_columns_sql(self, schema: str, table: str) -> str:
            return (
                f"SELECT column_name, data_type, 'YES' AS is_nullable, ordinal_position "
                f"FROM information_schema.columns "
                f"WHERE table_schema = 'main' AND table_name = '{table}' "
                f"ORDER BY ordinal_position"
            )

    tmp = tmp_path_factory.mktemp("profiles")
    return DuckDBProfiler(duckdb_conn, tmp)


# ── Pre-baked profile fixture ──────────────────────────────────────────────────

@pytest.fixture(scope="session")
def sample_table_profiles():
    """
    Pre-baked TableProfile objects without needing to run profiling queries.
    Used for renderer and enricher tests.
    """
    from runtime.profiler.base import ColumnProfile, TableProfile
    from datetime import datetime

    orders_cols = [
        ColumnProfile(
            name="order_id", data_type="INTEGER",
            total_rows=1000, pct_null=0.0, approx_distinct=1000,
            sample_values=[1, 2, 3],
        ),
        ColumnProfile(
            name="revenue", data_type="DECIMAL",
            total_rows=1000, pct_null=10.0, approx_distinct=850,
            min_numeric=10.0, max_numeric=509.7, avg_numeric=255.4,
            p05=25.0, p25=120.0, median_numeric=255.0, p75=390.0, p95=490.0,
            sample_values=[249.99, 109.50, 389.00],
        ),
        ColumnProfile(
            name="status", data_type="VARCHAR",
            total_rows=1000, pct_null=0.0, approx_distinct=5,
            avg_len=8.2, max_len=9,
            pct_na=10.0,   # 10% are "N/A"
            sample_values=["completed", "pending", "refunded", "N/A"],
        ),
        ColumnProfile(
            name="order_date", data_type="DATE",
            total_rows=1000, pct_null=0.0, approx_distinct=365,
            sample_values=["2023-01-01", "2023-12-31"],
        ),
    ]

    return [
        TableProfile(
            table_name="orders",
            schema_name="PUBLIC",
            warehouse_type="snowflake",
            total_rows=1000,
            size_bytes=204800,
            last_modified="2024-01-15",
            profiled_at=datetime.utcnow().isoformat(),
            columns=orders_cols,
        )
    ]


# ── Document context fixture ───────────────────────────────────────────────────

@pytest.fixture
def sample_document_context():
    """A DocumentContext with column and metric definitions."""
    from runtime.documents.context import (
        DocumentContext, TableDefinition, ColumnDefinition,
        MetricDefinition, BusinessRule,
    )
    return DocumentContext(
        source_path="/tmp/test_data_dictionary.csv",
        source_type="csv",
        document_type="data_dictionary",
        extraction_confidence="high",
        table_definitions=[
            TableDefinition(
                table_name="orders",
                description="Purchase orders from the Shopify storefront.",
                source_system="Shopify",
                grain_description="one row per order",
            )
        ],
        column_definitions=[
            ColumnDefinition(
                table_name="orders",
                column_name="revenue",
                business_name="Gross Revenue",
                description="Pre-tax invoice amount in USD. Excludes shipping.",
                data_type_note="USD, 2 decimal places",
            ),
            ColumnDefinition(
                table_name="orders",
                column_name="status",
                business_name="Order Status",
                description="Fulfilment status of the order.",
                valid_values=["pending", "completed", "refunded", "cancelled"],
            ),
        ],
        metric_definitions=[
            MetricDefinition(
                name="total_revenue",
                business_name="Total Revenue",
                description="Sum of revenue on completed orders.",
                formula="SUM(revenue) WHERE status = 'completed'",
                source_table="orders",
                source_column="revenue",
                aggregation="SUM",
                filters=["status = 'completed'"],
                domain="Revenue & Growth",
                is_certified=True,
            )
        ],
        business_rules=[
            BusinessRule(
                rule="Revenue is only recognised when status = 'completed'",
                affects_tables=["orders"],
                affects_columns=["revenue"],
                affects_metrics=["total_revenue"],
            )
        ],
    )


# ── Agent outputs fixture ──────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def mock_agent_outputs():
    """Reuse the built-in fixture from cli.py."""
    from runtime.cli import _builtin_fixture
    return _builtin_fixture()
