"""
BigQuery profiler — implements BaseProfiler with BigQuery Standard SQL dialect.

Auth methods supported:
  - gcloud_adc    (Application Default Credentials — gcloud auth application-default login)
  - service_account_json (.json key file path or inline JSON string)

Credential keys:
  BIGQUERY_PROJECT   (required) — GCP project ID
  BIGQUERY_KEY_FILE  (optional) — path to service account JSON key file
  BIGQUERY_LOCATION  (optional) — default dataset location, e.g. "US", "EU"
  auth_method        (optional) — "adc" | "service_account_json" (default: "adc")
"""

from __future__ import annotations

from .base import BaseProfiler


class BigQueryProfiler(BaseProfiler):

    WAREHOUSE_TYPE = "bigquery"
    SAMPLE_PCT = 10   # TABLESAMPLE SYSTEM percentage

    # ── Connection ─────────────────────────────────────────────────────────────

    def connect(self) -> None:
        from google.cloud import bigquery
        from google.oauth2 import service_account

        creds = self.credentials
        project = creds["BIGQUERY_PROJECT"]
        auth = creds.get("auth_method", "adc")
        location = creds.get("BIGQUERY_LOCATION", "US")

        if auth == "service_account_json":
            key_file = creds.get("BIGQUERY_KEY_FILE")
            if not key_file:
                raise ValueError("BIGQUERY_KEY_FILE is required for service_account_json auth.")

            import json, os
            key_file = os.path.expanduser(key_file)
            if os.path.isfile(key_file):
                with open(key_file) as f:
                    key_info = json.load(f)
            else:
                # Allow inline JSON string as fallback
                key_info = json.loads(key_file)

            credentials = service_account.Credentials.from_service_account_info(
                key_info,
                scopes=["https://www.googleapis.com/auth/bigquery"],
            )
            self.connection = bigquery.Client(
                project=project,
                credentials=credentials,
                location=location,
            )
        else:
            # ADC — uses GOOGLE_APPLICATION_CREDENTIALS env var or gcloud CLI auth
            self.connection = bigquery.Client(project=project, location=location)

    def disconnect(self) -> None:
        if self.connection:
            self.connection.close()
            self.connection = None

    def execute(self, sql: str) -> list[dict]:
        if not self.connection:
            raise RuntimeError("Not connected. Call connect() first.")
        rows = self.connection.query(sql).result()
        # BigQuery Row objects behave like mappings; normalise keys to lowercase.
        return [{k.lower(): v for k, v in dict(row).items()} for row in rows]

    # ── Phase 1: Schema discovery ─────────────────────────────────────────────

    def get_schemas_sql(self) -> str:
        # Returns all datasets in the project as schema_name rows.
        return """
            SELECT schema_name
            FROM INFORMATION_SCHEMA.SCHEMATA
            ORDER BY schema_name
        """

    def get_tables_sql(self, schema: str) -> str:
        # BigQuery INFORMATION_SCHEMA is dataset-scoped and must be project-qualified:
        # `project.dataset`.INFORMATION_SCHEMA.TABLES
        project = self.credentials["BIGQUERY_PROJECT"]
        return f"""
            SELECT
                t.table_name,
                CAST(s.total_rows AS INT64)          AS row_count,
                s.total_logical_bytes                 AS size_bytes,
                CAST(t.last_modified_time AS STRING)  AS last_modified
            FROM `{project}.{schema}`.INFORMATION_SCHEMA.TABLES t
            LEFT JOIN `{project}.{schema}`.INFORMATION_SCHEMA.TABLE_STORAGE s
                   ON t.table_name = s.table_name
            WHERE t.table_type = 'BASE TABLE'
            ORDER BY t.table_name
        """

    def get_columns_sql(self, schema: str, table: str) -> str:
        project = self.credentials["BIGQUERY_PROJECT"]
        return f"""
            SELECT
                column_name,
                data_type,
                is_nullable,
                ordinal_position
            FROM `{project}.{schema}`.INFORMATION_SCHEMA.COLUMNS
            WHERE table_name = '{table}'
            ORDER BY ordinal_position
        """

    # ── Sampling SQL ──────────────────────────────────────────────────────────

    def fetch_sample_sql(self, schema: str, table: str, limit: int = 5000) -> str:
        # BigQuery uses TABLESAMPLE SYSTEM (block-based, PERCENT keyword required).
        project = self.credentials["BIGQUERY_PROJECT"]
        return f"SELECT * FROM `{project}.{schema}`.{table} TABLESAMPLE SYSTEM ({self.SAMPLE_PCT} PERCENT) LIMIT {limit}"

    def fetch_plain_sql(self, schema: str, table: str, limit: int = 5000) -> str:
        project = self.credentials["BIGQUERY_PROJECT"]
        return f"SELECT * FROM `{project}.{schema}`.{table} LIMIT {limit}"
