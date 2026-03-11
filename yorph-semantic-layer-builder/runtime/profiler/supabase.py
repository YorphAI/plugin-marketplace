"""
Supabase profiler — implements BaseProfiler using PostgreSQL dialect via psycopg2.

Supabase is a hosted Postgres service. All Supabase databases are standard PostgreSQL
under the hood — this profiler connects directly to the Postgres wire protocol.

Auth methods supported:
  - project_ref  (Supabase hosted — connects via db.{project_ref}.supabase.co)
  - direct       (any Postgres connection — custom host/port/user/password)

Credential keys (project_ref auth):
  SUPABASE_PROJECT_REF  (required) — e.g. "abcdefghijklmnop" (from project Settings > API)
  SUPABASE_DB_PASSWORD  (required) — database password (Settings > Database > Connection string)
  SUPABASE_DB_USER      (optional) — default "postgres"

Credential keys (direct auth):
  SUPABASE_HOST      (required) — Postgres host
  SUPABASE_PORT      (optional) — default 5432
  SUPABASE_DATABASE  (optional) — default "postgres"
  SUPABASE_USER      (optional) — default "postgres"
  SUPABASE_PASSWORD  (required)

  auth_method        (optional) — "project_ref" | "direct" (default: "project_ref")

Notes:
  - PostgreSQL does not have a native approximate distinct count function without
    the hll extension. COUNT(DISTINCT col) is used instead (exact, but slightly
    slower on very large tables).
  - Percentile: uses PERCENTILE_CONT ordered-set aggregate (PostgreSQL 9.4+).
  - Regex: uses PostgreSQL's ~ operator for POSIX regex matching.
  - SSL is required for Supabase hosted connections.
"""

from __future__ import annotations

from .base import BaseProfiler


class SupabaseProfiler(BaseProfiler):

    WAREHOUSE_TYPE = "supabase"
    SAMPLE_PCT = 10   # TABLESAMPLE BERNOULLI percentage

    # ── Connection ─────────────────────────────────────────────────────────────

    def connect(self) -> None:
        import psycopg2
        import psycopg2.extras

        creds = self.credentials
        auth = creds.get("auth_method", "project_ref")

        if auth == "project_ref":
            ref = creds["SUPABASE_PROJECT_REF"]
            password = creds["SUPABASE_DB_PASSWORD"]
            user = creds.get("SUPABASE_DB_USER", "postgres")
            params = dict(
                host=f"db.{ref}.supabase.co",
                port=5432,
                database="postgres",
                user=user,
                password=password,
                sslmode="require",
                connect_timeout=30,
            )
        else:
            # Direct connection to any Postgres instance
            params = dict(
                host=creds["SUPABASE_HOST"],
                port=int(creds.get("SUPABASE_PORT", 5432)),
                database=creds.get("SUPABASE_DATABASE", "postgres"),
                user=creds.get("SUPABASE_USER", "postgres"),
                password=creds["SUPABASE_PASSWORD"],
                sslmode=creds.get("SUPABASE_SSLMODE", "prefer"),
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
        # Exclude pg internal schemas and Supabase internal schemas.
        return """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN (
                'information_schema', 'pg_catalog', 'pg_toast',
                'supabase_functions', 'supabase_migrations',
                'graphql', 'graphql_public', 'realtime',
                'storage', 'vault', 'extensions', 'auth', 'net', 'pgsodium'
            )
              AND schema_name NOT LIKE 'pg_%'
              AND schema_name NOT LIKE '_timescaledb_%'
            ORDER BY schema_name
        """

    def get_tables_sql(self, schema: str) -> str:
        # pg_stat_user_tables has accurate row estimates and last autovacuum timestamp.
        # pg_total_relation_size is omitted — Supabase hosted instances restrict
        # this function for non-superuser roles.
        return f"""
            SELECT
                t.table_name,
                COALESCE(s.n_live_tup, 0)            AS row_count,
                0                                    AS size_bytes,
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
    # Base class default (TABLESAMPLE BERNOULLI + LIMIT) works for Supabase/Postgres.
