"""
Tests for the profiler — uses the DuckDB mock profiler (no real warehouse needed).
"""

import asyncio
import pytest
import pandas as pd


class TestDuckDBProfiler:
    """Test profiling end-to-end using DuckDB."""

    def test_connect_and_execute(self, mock_profiler):
        rows = mock_profiler.execute("SELECT 1 AS test")
        assert rows == [{"test": 1}]

    def test_schema_discovery(self, mock_profiler):
        rows = mock_profiler.execute(mock_profiler.get_schemas_sql())
        assert any(r["schema_name"] == "main" for r in rows)

    def test_table_discovery(self, mock_profiler):
        rows = mock_profiler.execute(mock_profiler.get_tables_sql("main"))
        table_names = [r["table_name"] for r in rows]
        assert "orders" in table_names
        assert "order_items" in table_names
        assert "customers" in table_names

    def test_column_discovery(self, mock_profiler):
        rows = mock_profiler.execute(mock_profiler.get_columns_sql("main", "orders"))
        col_names = [r["column_name"] for r in rows]
        assert "order_id" in col_names
        assert "revenue" in col_names
        assert "status" in col_names

    def test_profile_df_basic(self, mock_profiler):
        """_profile_df should produce a TableProfile with correct stats."""
        rows = mock_profiler.execute("SELECT * FROM main.orders LIMIT 500")
        df = pd.DataFrame(rows)
        profile = mock_profiler._profile_df(
            df,
            table_name="orders",
            schema_name="main",
            size_bytes=None,
            last_modified=None,
            column_metadata=None,
        )
        assert profile.table_name == "orders"
        assert profile.total_rows == 500
        assert len(profile.columns) > 0

    def test_profile_df_numeric_stats(self, mock_profiler):
        """Revenue column should have numeric stats populated."""
        rows = mock_profiler.execute("SELECT * FROM main.orders LIMIT 1000")
        df = pd.DataFrame(rows)
        profile = mock_profiler._profile_df(
            df, table_name="orders", schema_name="main",
            size_bytes=None, last_modified=None, column_metadata=None,
        )
        revenue = next((c for c in profile.columns if c.name == "revenue"), None)
        assert revenue is not None
        assert revenue.min_numeric is not None
        assert revenue.max_numeric is not None
        assert revenue.avg_numeric is not None
        assert revenue.min_numeric < revenue.max_numeric

    def test_profile_df_null_detection(self, mock_profiler):
        """Revenue column has ~10% nulls in the test data."""
        rows = mock_profiler.execute("SELECT * FROM main.orders LIMIT 1000")
        df = pd.DataFrame(rows)
        profile = mock_profiler._profile_df(
            df, table_name="orders", schema_name="main",
            size_bytes=None, last_modified=None, column_metadata=None,
        )
        revenue = next((c for c in profile.columns if c.name == "revenue"), None)
        assert revenue is not None
        assert revenue.pct_null > 0, "Expected some nulls in revenue column"
        assert revenue.pct_null < 20, "Expected <20% nulls in revenue"

    def test_profile_df_column_metadata_preserves_sql_types(self, mock_profiler):
        """When column_metadata is provided, SQL type strings should be used."""
        rows = mock_profiler.execute("SELECT * FROM main.orders LIMIT 100")
        df = pd.DataFrame(rows)
        col_meta = {"order_id": "INTEGER", "revenue": "DECIMAL(10,2)", "status": "VARCHAR(50)"}
        profile = mock_profiler._profile_df(
            df, table_name="orders", schema_name="main",
            size_bytes=None, last_modified=None, column_metadata=col_meta,
        )
        order_id_col = next((c for c in profile.columns if c.name == "order_id"), None)
        assert order_id_col is not None
        assert order_id_col.data_type == "INTEGER"

    def test_profile_table_async(self, mock_profiler):
        """Full async profile of a single table should return a (TableProfile, DataFrame) tuple."""
        cols = mock_profiler.execute(mock_profiler.get_columns_sql("main", "orders"))
        table_meta = {"size_bytes": None, "last_modified": None, "row_count": 1000}

        result = asyncio.run(
            mock_profiler.profile_table_async("main", "orders", cols, table_meta)
        )

        assert isinstance(result, tuple)
        profile, df = result
        assert profile.table_name == "orders"
        assert profile.total_rows > 0
        assert len(profile.columns) > 0
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

        # Check revenue column stats are populated
        revenue = next((c for c in profile.columns if c.name == "revenue"), None)
        assert revenue is not None
        assert revenue.pct_null > 0
        assert revenue.min_numeric is not None

    def test_pii_columns_excluded(self, mock_profiler):
        """PII-named columns should not appear in profiles."""
        mock_profiler.connection.execute(
            "CREATE TABLE IF NOT EXISTS test_pii (user_id INT, password VARCHAR)"
        )
        cols = mock_profiler.execute(mock_profiler.get_columns_sql("main", "test_pii"))
        result = asyncio.run(
            mock_profiler.profile_table_async("main", "test_pii", cols, {})
        )
        profile = result[0] if isinstance(result, tuple) else result
        col_names = [c.name for c in profile.columns]
        assert "password" not in col_names
        assert "user_id" in col_names

    def test_context_batching(self, mock_profiler):
        """context_batches returns lists of max 100 tables."""
        from runtime.profiler.base import TABLES_PER_CONTEXT_BATCH
        assert TABLES_PER_CONTEXT_BATCH == 100

    def test_fetch_sample_sql(self, mock_profiler):
        """Base class fetch_sample_sql should produce valid SQL."""
        sql = mock_profiler.fetch_sample_sql("main", "orders", limit=100)
        assert "main.orders" in sql
        assert "TABLESAMPLE" in sql or "LIMIT" in sql or "TOP" in sql

    def test_fetch_plain_sql(self, mock_profiler):
        """Base class fetch_plain_sql should produce valid SQL."""
        sql = mock_profiler.fetch_plain_sql("main", "orders", limit=100)
        assert "main.orders" in sql
        assert "100" in sql


class TestSamplingSQL:
    """Test warehouse-specific sampling SQL overrides."""

    def test_bigquery_fetch_sample_sql(self):
        from runtime.profiler.bigquery import BigQueryProfiler
        p = BigQueryProfiler.__new__(BigQueryProfiler)
        p.SAMPLE_PCT = 10
        sql = p.fetch_sample_sql("my_dataset", "my_table", limit=5000)
        assert "TABLESAMPLE SYSTEM" in sql
        assert "PERCENT" in sql
        assert "5000" in sql

    def test_sqlserver_fetch_sample_sql(self):
        from runtime.profiler.sqlserver import SQLServerProfiler
        p = SQLServerProfiler.__new__(SQLServerProfiler)
        p.SAMPLE_PCT = 10
        sql = p.fetch_sample_sql("dbo", "my_table", limit=5000)
        assert "TOP" in sql
        assert "TABLESAMPLE" in sql

    def test_sqlserver_fetch_plain_sql(self):
        from runtime.profiler.sqlserver import SQLServerProfiler
        p = SQLServerProfiler.__new__(SQLServerProfiler)
        sql = p.fetch_plain_sql("dbo", "my_table", limit=5000)
        assert "TOP" in sql
        assert "dbo.my_table" in sql
