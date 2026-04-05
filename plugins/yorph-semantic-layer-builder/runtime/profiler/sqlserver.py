"""
SQL Server profiler — implements BaseProfiler with T-SQL dialect.

Auth methods supported:
  - sql_auth      (username + password)
  - windows_auth  (Windows/Active Directory integrated authentication)

Credential keys:
  MSSQL_SERVER    (required) — hostname or IP, e.g. "myserver.database.windows.net"
  MSSQL_DATABASE  (required) — database name
  MSSQL_USER      (required for sql_auth) — SQL login username
  MSSQL_PASSWORD  (required for sql_auth) — SQL login password
  MSSQL_PORT      (optional) — default 1433
  MSSQL_ENCRYPT   (optional) — "yes" | "no" (default: "yes" for Azure/cloud)
  auth_method     (optional) — "sql_auth" | "windows_auth" (default: "sql_auth")

Notes:
  - APPROX_COUNT_DISTINCT requires SQL Server 2019+ (or Azure SQL).
    Falls back to COUNT(DISTINCT col) on older versions.
  - PERCENTILE_CONT in T-SQL requires an OVER() clause (window function),
    which cannot be mixed with scalar aggregates. Percentile stats are
    omitted (returned as NULL) for SQL Server — use AVG/MIN/MAX instead.
  - Full regex is not natively supported in SQL Server without CLR. Pattern
    detection uses LIKE-based approximations instead.
  - Requires ODBC Driver 17 or 18 for SQL Server installed on the host machine.
"""

from __future__ import annotations

from .base import BaseProfiler


class SQLServerProfiler(BaseProfiler):

    WAREHOUSE_TYPE = "sql_server"
    SAMPLE_PCT = 10   # TABLESAMPLE SYSTEM percentage

    # ── Connection ─────────────────────────────────────────────────────────────

    def connect(self) -> None:
        import pyodbc

        creds = self.credentials
        auth = creds.get("auth_method", "sql_auth")
        server = creds["MSSQL_SERVER"]
        database = creds["MSSQL_DATABASE"]
        port = creds.get("MSSQL_PORT", 1433)
        encrypt = creds.get("MSSQL_ENCRYPT", "yes")

        # Try ODBC Driver 18 first, fall back to 17
        for driver in ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"]:
            if driver in pyodbc.drivers():
                break
        else:
            raise RuntimeError(
                "No compatible SQL Server ODBC driver found. "
                "Install 'ODBC Driver 18 for SQL Server' from Microsoft."
            )

        if auth == "windows_auth":
            conn_str = (
                f"DRIVER={{{driver}}};"
                f"SERVER={server},{port};"
                f"DATABASE={database};"
                f"Trusted_Connection=yes;"
                f"Encrypt={encrypt};"
            )
        else:
            # SQL authentication
            conn_str = (
                f"DRIVER={{{driver}}};"
                f"SERVER={server},{port};"
                f"DATABASE={database};"
                f"UID={creds['MSSQL_USER']};"
                f"PWD={creds['MSSQL_PASSWORD']};"
                f"Encrypt={encrypt};"
                f"TrustServerCertificate=yes;"
            )

        self.connection = pyodbc.connect(conn_str, autocommit=True)

    def disconnect(self) -> None:
        if self.connection:
            self.connection.close()
            self.connection = None

    def execute(self, sql: str) -> list[dict]:
        if not self.connection:
            raise RuntimeError("Not connected. Call connect() first.")
        cursor = self.connection.cursor()
        cursor.execute(sql)
        if cursor.description is None:
            return []
        cols = [col[0].lower() for col in cursor.description]
        rows = cursor.fetchall()
        cursor.close()
        return [dict(zip(cols, row)) for row in rows]

    # ── Phase 1: Schema discovery ─────────────────────────────────────────────

    def get_schemas_sql(self) -> str:
        # Exclude system schemas.
        return """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN (
                'information_schema', 'sys', 'db_owner', 'db_accessadmin',
                'db_securityadmin', 'db_ddladmin', 'db_backupoperator',
                'db_datareader', 'db_datawriter', 'db_denydatareader',
                'db_denydatawriter', 'guest'
            )
            ORDER BY schema_name
        """

    def get_tables_sql(self, schema: str) -> str:
        # sys.tables has row counts and size via sys.partitions / sys.allocation_units.
        return f"""
            SELECT
                t.name                          AS table_name,
                p.rows                          AS row_count,
                SUM(a.total_pages) * 8192       AS size_bytes,
                NULL                            AS last_modified
            FROM sys.tables t
            JOIN sys.schemas s      ON s.schema_id = t.schema_id
            JOIN sys.indexes i      ON i.object_id = t.object_id AND i.index_id IN (0, 1)
            JOIN sys.partitions p   ON p.object_id = t.object_id AND p.index_id = i.index_id
            JOIN sys.allocation_units a ON a.container_id = p.partition_id
            WHERE s.name = '{schema}'
            GROUP BY t.name, p.rows
            ORDER BY t.name
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

    def fetch_sample_sql(self, schema: str, table: str, limit: int = 5000) -> str:
        # SQL Server uses TOP instead of LIMIT; TABLESAMPLE is page-based.
        return f"SELECT TOP {limit} * FROM {schema}.{table} TABLESAMPLE ({self.SAMPLE_PCT} PERCENT)"

    def fetch_plain_sql(self, schema: str, table: str, limit: int = 5000) -> str:
        # SQL Server uses TOP instead of LIMIT.
        return f"SELECT TOP {limit} * FROM {schema}.{table}"
