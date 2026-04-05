"""
PostgreSQL MCP profiler — delegates SQL execution to the official MCP postgres
server (npx @modelcontextprotocol/server-postgres) while inheriting PostgreSQL
SQL generation from PostgresProfiler.

Auth note
=========
The MCP server takes the full connection string as a positional CLI argument:
  npx @modelcontextprotocol/server-postgres postgresql://user:pass@host:port/db

We build PG_DSN from the individual PG_* credential keys before passing
credentials to the adapter so that the {PG_DSN} placeholder in POSTGRES_ADAPTER
resolves correctly.
"""

from __future__ import annotations

import urllib.parse

from .mcp_backed import MCPBackedProfiler
from .postgres import PostgresProfiler
from runtime.mcp_client.adapters import POSTGRES_ADAPTER


class PostgresMCPProfiler(MCPBackedProfiler, PostgresProfiler):
    ADAPTER = POSTGRES_ADAPTER
    WAREHOUSE_TYPE = "postgres"

    def connect(self) -> None:
        # Build the DSN and inject it so POSTGRES_ADAPTER.build_args() can
        # substitute the {PG_DSN} placeholder in the args list.
        creds = dict(self.credentials)
        creds.setdefault("PG_DSN", self._build_dsn(creds))
        self.credentials = creds
        super().connect()

    @staticmethod
    def _build_dsn(creds: dict) -> str:
        host = creds.get("PG_HOST", "localhost")
        port = creds.get("PG_PORT", 5432)
        db   = creds.get("PG_DATABASE", "postgres")
        user = urllib.parse.quote(str(creds.get("PG_USER", "postgres")), safe="")
        pwd  = urllib.parse.quote(str(creds.get("PG_PASSWORD", "")), safe="")
        return f"postgresql://{user}:{pwd}@{host}:{port}/{db}"
