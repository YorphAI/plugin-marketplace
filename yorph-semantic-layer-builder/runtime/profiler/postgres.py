"""
PostgreSQL profiler — implements BaseProfiler with standard PostgreSQL dialect.

Auth methods supported:
  - password  (host + port + database + user + password)

Credential keys:
  PG_HOST      (required) — hostname, e.g. "localhost" or "mydb.example.com"
  PG_PORT      (optional) — default 5432
  PG_DATABASE  (required) — database name
  PG_USER      (required) — database username
  PG_PASSWORD  (required) — database password
  PG_SSLMODE   (optional) — "disable" | "prefer" | "require" (default: "prefer")
  auth_method  (optional) — "password" (only method supported)

Notes:
  - PostgreSQL has no built-in approximate distinct count without the hll extension.
    COUNT(DISTINCT col) is used instead — exact but slightly slower on large tables.
  - Percentile uses PERCENTILE_CONT ordered-set aggregate (PostgreSQL 9.4+).
  - Regex uses PostgreSQL's ~ operator for POSIX regex matching.
  - TABLESAMPLE BERNOULLI available since PostgreSQL 9.5.
"""

from __future__ import annotations

from .base import BaseProfiler


class PostgresProfiler(BaseProfiler):

    WAREHOUSE_TYPE = "postgres"
    SAMPLE_PCT = 10   # TABLESAMPLE BERNOULLI percentage

    # ── Connection ─────────────────────────────────────────────────────────────

    def connect(self) -> None:
        import psycopg2
        import psycopg2.extras

        creds = self.credentials
        params = dict(
            host=creds["PG_HOST"],
            port=int(creds.get("PG_PORT", 5432)),
            database=creds["PG_DATABASE"],
            user=creds["PG_USER"],
            password=creds["PG_PASSWORD"],
            sslmode=creds.get("PG_SSLMODE", "prefer"),
            connect_timeout=30,
            # Enforce read-only mode at the database session level.
            # Even if the code-level SQL guard is bypassed, Postgres itself will
            # reject any INSERT / UPDATE / DELETE / DDL on this connection.
            options="-c default_transaction_read_only=on",
        )
        self.connection = psycopg2.connect(**params)
        self.connection.autocommit = True

    def disconnect(self) -> None:
        if self.connection:
            self.connection.close()
            self.connection = None

    def execute(self, sql: str) -> list[dict]:
        if not self.connection:
            raise RuntimeError("Not connected. Call connect() first.")
        import psycopg2.extras
        with self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            if cur.description is None:
                return []
            return [dict(row) for row in cur.fetchall()]

    # ── Phase 1: Schema discovery ─────────────────────────────────────────────

    def get_schemas_sql(self) -> str:
        # Exclude PostgreSQL internal schemas.
        return """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
              AND schema_name NOT LIKE 'pg_temp_%'
              AND schema_name NOT LIKE 'pg_toast_temp_%'
            ORDER BY schema_name
        """

    def get_tables_sql(self, schema: str) -> str:
        # pg_stat_user_tables has live row estimates and last-analyse timestamp.
        return f"""
            SELECT
                t.table_name,
                s.n_live_tup                         AS row_count,
                pg_total_relation_size(
                    (t.table_schema || '.' || t.table_name)::regclass
                )                                    AS size_bytes,
                s.last_analyze::TEXT                 AS last_modified
            FROM information_schema.tables t
            LEFT JOIN pg_stat_user_tables s
                   ON s.schemaname = t.table_schema
                  AND s.relname    = t.table_name
            WHERE t.table_schema = '{schema}'
              AND t.table_type   = 'BASE TABLE'
            ORDER BY t.table_name
        """

    def get_columns_sql(self, schema: str, table: str) -> str:
        return f"""
            SELECT
                column_name,
                data_type,
                is_nullable,
                ordinal_position
            FROM information_schema.columns
            WHERE table_schema = '{schema}'
              AND table_name   = '{table}'
            ORDER BY ordinal_position
        """

    # ── Sampling SQL ──────────────────────────────────────────────────────────
    # Base class default (TABLESAMPLE BERNOULLI + LIMIT) works for PostgreSQL.

    async def test_connection(self) -> dict:
        """Test connection and return status dict (used by connect_warehouse tool)."""
        try:
            self.connect()
            self.execute("SELECT 1 AS test")
            return {"success": True, "warehouse_type": self.WAREHOUSE_TYPE}
        except Exception as e:
            return {"success": False, "error": str(e)}
