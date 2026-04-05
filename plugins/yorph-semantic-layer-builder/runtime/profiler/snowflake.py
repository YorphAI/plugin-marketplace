"""
Snowflake profiler — implements BaseProfiler with Snowflake-specific SQL dialect.

Auth methods supported:
  - Key pair (.p8 / .pem private key) — recommended default
  - Password (username + password, with optional MFA/TOTP)
  - SSO / browser auth (externalbrowser authenticator)
"""

from __future__ import annotations

from .base import BaseProfiler


class SnowflakeProfiler(BaseProfiler):

    WAREHOUSE_TYPE = "snowflake"
    SAMPLE_PCT = 10  # TABLESAMPLE BERNOULLI percentage

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self) -> None:
        creds = self.credentials
        auth = creds.get("auth_method", "key_pair")

        params = dict(
            account=creds["SNOWFLAKE_ACCOUNT"],
            user=creds["SNOWFLAKE_USER"],
            warehouse=creds.get("SNOWFLAKE_WAREHOUSE"),
            role=creds.get("SNOWFLAKE_ROLE"),
            database=creds.get("SNOWFLAKE_DATABASE"),
            # Explicit autocommit — Snowflake defaults to autocommit=True but we
            # set it explicitly so behaviour is clear and not reliant on defaults.
            autocommit=True,
        )

        if auth == "sso":
            params["authenticator"] = "externalbrowser"

        elif auth == "key_pair":
            import os
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.serialization import (
                load_pem_private_key, load_der_private_key, Encoding, PrivateFormat, NoEncryption
            )
            key_path = os.path.expanduser(creds["SNOWFLAKE_PRIVATE_KEY_FILE"])
            passphrase = creds.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")
            with open(key_path, "rb") as f:
                key_data = f.read()
            # Support both PEM and DER formats
            try:
                private_key = load_pem_private_key(
                    key_data,
                    password=passphrase.encode() if passphrase else None,
                    backend=default_backend()
                )
            except Exception:
                private_key = load_der_private_key(
                    key_data,
                    password=passphrase.encode() if passphrase else None,
                    backend=default_backend()
                )
            params["private_key"] = private_key.private_bytes(
                Encoding.DER, PrivateFormat.PKCS8, NoEncryption()
            )

        else:
            # Password auth — plain or MFA/TOTP
            params["password"] = creds["SNOWFLAKE_PASSWORD"]
            mfa_passcode = creds.get("SNOWFLAKE_MFA_PASSCODE")
            if mfa_passcode:
                # username_password_mfa sends password + current TOTP code together,
                # which is what Snowflake requires when MFA is enforced on the account.
                params["authenticator"] = "username_password_mfa"
                params["passcode"] = str(mfa_passcode).strip()

        import snowflake.connector
        self.connection = snowflake.connector.connect(**params)

    def disconnect(self) -> None:
        if self.connection:
            self.connection.close()
            self.connection = None

    def execute(self, sql: str) -> list[dict]:
        if not self.connection:
            raise RuntimeError("Not connected. Call connect() first.")
        from snowflake.connector import DictCursor
        with self.connection.cursor(DictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            # Snowflake DictCursor returns uppercase column names (SCHEMA_NAME, TABLE_NAME…).
            # Normalize all keys to lowercase so the rest of the codebase can use consistent
            # lowercase field names everywhere.
            return [{k.lower(): v for k, v in row.items()} for row in rows]

    # ── Phase 1: Schema discovery ─────────────────────────────────────────────

    def get_schemas_sql(self) -> str:
        # Exclude only INFORMATION_SCHEMA — PUBLIC and all user schemas are included.
        # Many Snowflake databases (especially trial/dev) keep all tables in PUBLIC.
        return """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name != 'INFORMATION_SCHEMA'
            ORDER BY schema_name
        """

    def get_tables_sql(self, schema: str) -> str:
        return f"""
            SELECT
                table_name,
                row_count,
                bytes          AS size_bytes,
                last_altered   AS last_modified
            FROM information_schema.tables
            WHERE table_schema = '{schema.upper()}'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """

    def get_columns_sql(self, schema: str, table: str) -> str:
        return f"""
            SELECT
                column_name,
                data_type,
                is_nullable,
                ordinal_position
            FROM information_schema.columns
            WHERE table_schema = '{schema.upper()}'
              AND table_name   = '{table.upper()}'
            ORDER BY ordinal_position
        """

    # ── Sampling SQL ──────────────────────────────────────────────────────────
    # Base class default (TABLESAMPLE BERNOULLI + LIMIT) works for Snowflake.
