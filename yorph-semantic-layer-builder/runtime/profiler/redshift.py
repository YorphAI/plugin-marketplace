"""
Redshift profiler — implements BaseProfiler with Amazon Redshift SQL dialect.

Auth methods supported:
  - password   (direct database credentials — username + password)
  - iam        (IAM-based auth — requires AWS access key or profile + Redshift cluster)

Credential keys:
  REDSHIFT_HOST      (required) — cluster endpoint, e.g. my-cluster.abc.us-east-1.redshift.amazonaws.com
  REDSHIFT_DATABASE  (required) — database name
  REDSHIFT_USER      (required for password auth) — database username
  REDSHIFT_PASSWORD  (required for password auth) — database password
  REDSHIFT_PORT      (optional) — default 5439
  AWS_REGION         (optional) — AWS region for IAM auth, e.g. "us-east-1"
  AWS_ACCESS_KEY_ID  (optional) — for IAM auth
  AWS_SECRET_ACCESS_KEY (optional) — for IAM auth
  AWS_PROFILE        (optional) — named AWS profile for IAM auth
  auth_method        (optional) — "password" | "iam" (default: "password")
"""

from __future__ import annotations

from .base import BaseProfiler


class RedshiftProfiler(BaseProfiler):

    WAREHOUSE_TYPE = "redshift"
    SAMPLE_PCT = 10   # TABLESAMPLE BERNOULLI percentage

    # ── Connection ─────────────────────────────────────────────────────────────

    def connect(self) -> None:
        import redshift_connector

        creds = self.credentials
        auth = creds.get("auth_method", "password")
        host = creds["REDSHIFT_HOST"]
        database = creds["REDSHIFT_DATABASE"]
        port = int(creds.get("REDSHIFT_PORT", 5439))

        if auth == "iam":
            # IAM auth: redshift_connector handles token exchange automatically.
            params = dict(
                iam=True,
                host=host,
                database=database,
                port=port,
                db_user=creds.get("REDSHIFT_USER", ""),
                cluster_identifier=host.split(".")[0],  # extract cluster ID from endpoint
            )
            region = creds.get("AWS_REGION")
            if region:
                params["region"] = region
            access_key = creds.get("AWS_ACCESS_KEY_ID")
            secret_key = creds.get("AWS_SECRET_ACCESS_KEY")
            if access_key and secret_key:
                params["access_key_id"] = access_key
                params["secret_access_key"] = secret_key
            profile = creds.get("AWS_PROFILE")
            if profile:
                params["profile"] = profile
        else:
            # Password auth
            params = dict(
                host=host,
                database=database,
                port=port,
                user=creds["REDSHIFT_USER"],
                password=creds["REDSHIFT_PASSWORD"],
            )

        self.connection = redshift_connector.connect(**params)
        self.connection.autocommit = True

    def disconnect(self) -> None:
        if self.connection:
            self.connection.close()
            self.connection = None

    def execute(self, sql: str) -> list[dict]:
        if not self.connection:
            raise RuntimeError("Not connected. Call connect() first.")
        with self.connection.cursor() as cur:
            cur.execute(sql)
            if cur.description is None:
                return []
            cols = [desc[0].lower() for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    # ── Phase 1: Schema discovery ─────────────────────────────────────────────

    def get_schemas_sql(self) -> str:
        # Exclude internal Redshift schemas.
        return """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN (
                'information_schema', 'pg_catalog', 'pg_toast',
                'pg_temp_1', 'pg_toast_temp_1'
            )
              AND schema_name NOT LIKE 'pg_temp_%'
            ORDER BY schema_name
        """

    def get_tables_sql(self, schema: str) -> str:
        # SVV_TABLE_INFO has Redshift-specific stats (row count, size in MB).
        return f"""
            SELECT
                t.table_name,
                i.tbl_rows                       AS row_count,
                i.size * 1024 * 1024             AS size_bytes,
                NULL                             AS last_modified
            FROM information_schema.tables t
            LEFT JOIN svv_table_info i
                   ON i.schema = t.table_schema
                  AND i.table  = t.table_name
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
    # Base class default (TABLESAMPLE BERNOULLI + LIMIT) works for Redshift.
