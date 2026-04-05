"""
Base classes for simulation scenarios.

A Scenario wraps:
  - DuckDB seed SQL (creates + populates tables)
  - Metadata describing what the agent should discover
  - Ground truth for scoring (expected joins, measures, business rules)
  - Data quality issues deliberately injected

Usage:
    scenario = ECOMMERCE_MEDIUM
    db_path = scenario.seed(Path("~/.yorph/sim/current.duckdb"))
    profiler = scenario.make_profiler(db_path)
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── Ground truth dataclasses ───────────────────────────────────────────────────

@dataclass
class ExpectedJoin:
    left: str
    right: str
    key: str
    cardinality: str              # "1:1" | "1:many" | "many:many"
    is_trap: bool = False
    trap_type: str | None = None  # "fan_out" | "chasm"


@dataclass
class ExpectedMeasure:
    measure_id: str
    label: str
    aggregation: str              # SUM, COUNT, AVG, RATIO
    source_table: str
    source_column: str | None = None
    filters: list[str] = field(default_factory=list)
    domain: str | None = None


@dataclass
class DataQualityIssue:
    """A deliberate data quality problem injected into the scenario."""
    table: str
    column: str
    issue_type: str               # "encoded_null" | "fan_out_trap" | "ambiguous_key" |
                                  #  "mixed_grain" | "high_null" | "negative_values" |
                                  #  "schema_drift" | "duplicate_metric"
    description: str
    prevalence: str               # "10% of rows" | "always" etc.


@dataclass
class GroundTruth:
    expected_joins: list[ExpectedJoin] = field(default_factory=list)
    expected_measures: list[ExpectedMeasure] = field(default_factory=list)
    business_rules: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    grain_per_table: dict[str, list[str]] = field(default_factory=dict)


# ── Scenario dataclass ─────────────────────────────────────────────────────────

@dataclass
class Scenario:
    """
    A complete simulation scenario.

    seed_sql: list of SQL statements to create + populate DuckDB tables.
    Tables can span multiple schemas (DuckDB supports ATTACH or schema prefixes).
    """
    name: str
    domain: str                   # "ecommerce" | "saas" | "marketing" | "finance"
    complexity: str               # "simple" | "medium" | "complex"
    description: str              # 1-2 sentence overview for the runner summary
    schemas: list[str]            # DuckDB schema names used (default: ["main"])
    seed_sql: list[str]           # DDL + DML statements, executed in order
    data_quality_issues: list[DataQualityIssue] = field(default_factory=list)
    ground_truth: GroundTruth = field(default_factory=GroundTruth)
    table_descriptions: dict[str, str] = field(default_factory=dict)  # table → business description

    def seed(self, db_path: Path) -> Path:
        """
        Seed a DuckDB database at db_path with this scenario's data.
        Returns the path to the created database file.
        """
        import duckdb

        db_path.parent.mkdir(parents=True, exist_ok=True)
        # Remove existing file to start fresh
        if db_path.exists():
            db_path.unlink()

        con = duckdb.connect(str(db_path))
        try:
            for sql in self.seed_sql:
                sql = sql.strip()
                if sql:
                    con.execute(sql)
        finally:
            con.close()

        return db_path

    def make_profiler(self, db_path: Path) -> "SimScenarioProfiler":
        """
        Return a BaseProfiler-compatible profiler backed by the seeded DuckDB.
        Used by the runner to generate profiles.
        """
        return SimScenarioProfiler(scenario=self, db_path=db_path)


# ── DuckDB-backed profiler for scenarios ──────────────────────────────────────

class SimScenarioProfiler:
    """
    A thin wrapper that satisfies BaseProfiler's interface using DuckDB.

    Used to run the real profiler pipeline against a simulated DuckDB database,
    producing genuine statistical profiles (not hand-crafted fixtures).
    """

    WAREHOUSE_TYPE = "simulation"

    def __init__(self, scenario: Scenario, db_path: Path):
        import sys
        sys.path.insert(0, str(Path(__file__).parents[3] / "yorph-semantic-layer-assistant" / "runtime"))

        from profiler.base import BaseProfiler

        class _DuckDBProfiler(BaseProfiler):
            WAREHOUSE_TYPE = "simulation"
            SAMPLE_PCT = 10

            def __init__(self_, sc: Scenario, path: Path):
                self_.scenario = sc
                self_.db_path = path
                self_.credentials = {}
                self_.connection = None
                self_._lock = threading.Lock()

            def connect(self_):
                import duckdb
                self_.connection = duckdb.connect(str(self_.db_path))

            def disconnect(self_):
                if self_.connection:
                    self_.connection.close()
                    self_.connection = None

            def execute(self_, sql: str) -> list[dict]:
                # Translate Snowflake-specific constructs to DuckDB equivalents
                sql = _translate_sql(sql)
                with self_._lock:
                    cursor = self_.connection.execute(sql)
                    cols = [desc[0].lower() for desc in cursor.description]
                    return [dict(zip(cols, row)) for row in cursor.fetchall()]

            def get_schemas_sql(self_) -> str:
                return (
                    "SELECT schema_name FROM information_schema.schemata "
                    "WHERE schema_name NOT IN ('information_schema', 'pg_catalog') "
                    "ORDER BY schema_name"
                )

            def get_tables_sql(self_, schema: str) -> str:
                return (
                    f"SELECT table_name, NULL AS row_count, "
                    f"NULL AS size_bytes, NULL AS last_modified "
                    f"FROM information_schema.tables "
                    f"WHERE table_schema = '{schema}' AND table_type = 'BASE TABLE' "
                    f"ORDER BY table_name"
                )

            def get_columns_sql(self_, schema: str, table: str) -> str:
                return (
                    f"SELECT column_name, data_type, is_nullable, ordinal_position "
                    f"FROM information_schema.columns "
                    f"WHERE table_schema = '{schema}' AND table_name = '{table}' "
                    f"ORDER BY ordinal_position"
                )

            def sample_clause(self_) -> str:
                return ""  # DuckDB TABLESAMPLE breaks aggregates — skip in simulation

            def approx_distinct_sql(self_, column: str) -> str:
                return f"APPROX_COUNT_DISTINCT({column})"

            def percentile_sql(self_, column: str, pct: float) -> str:
                return f"PERCENTILE_CONT({pct}) WITHIN GROUP (ORDER BY {column})"

            def regexp_like_sql(self_, column: str, pattern: str) -> str:
                safe = pattern.replace("'", "''")
                return f"regexp_matches(CAST({column} AS VARCHAR), '{safe}')"

        self._profiler = _DuckDBProfiler(scenario, db_path)
        self._profiler.connect()

    @property
    def profiler(self):
        return self._profiler


def _translate_sql(sql: str) -> str:
    """
    Translate Snowflake-specific SQL constructs to DuckDB equivalents.

    Handles the key differences the profiler emits.
    """
    import re

    # TABLESAMPLE BERNOULLI (N) → remove (DuckDB TABLESAMPLE breaks aggregates in CTEs)
    sql = re.sub(r'\s+TABLESAMPLE\s+BERNOULLI\s*\(\s*\d+\s*\)', '', sql, flags=re.IGNORECASE)

    # APPROX_COUNT_DISTINCT is supported in DuckDB — no translation needed

    # REGEXP_LIKE(col, 'pattern') → regexp_matches(col, 'pattern')
    sql = re.sub(
        r'REGEXP_LIKE\s*\(([^,]+),\s*([^)]+)\)',
        r'regexp_matches(\1, \2)',
        sql,
        flags=re.IGNORECASE
    )

    # Snowflake's INTERVAL syntax: INTERVAL (n) SECOND → INTERVAL (n SECOND)
    # DuckDB uses INTERVAL '5' SECOND or INTERVAL 5 SECOND
    # The profiler uses INTERVAL (i * 3600) SECOND form — DuckDB handles this
    # via MAKE_INTERVAL, but simpler to just leave as is since DuckDB supports
    # INTERVAL expressions in most contexts.

    return sql
