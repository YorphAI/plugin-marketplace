"""
Per-warehouse MCP server configuration.

Each WarehouseAdapter describes:
  - How to launch the MCP server subprocess (command, args)
  - Which credential keys to pass as env vars to the subprocess
  - Which MCP tool to call for SQL execution (query_tool, query_arg)
  - How to parse the MCP tool response into list[dict] rows

Tool names are verified from upstream docs / source:
  Snowflake:  https://github.com/Snowflake-Labs/mcp
  BigQuery:   https://github.com/googleapis/genai-toolbox (--prebuilt bigquery)
  Redshift:   https://github.com/awslabs/mcp/tree/main/src/redshift-mcp-server
  PostgreSQL: https://github.com/modelcontextprotocol/servers/tree/main/src/postgres
  Supabase:   https://github.com/supabase-community/supabase-mcp
  SQL Server: https://github.com/RichardHan/mssql_mcp_server  (community)
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WarehouseAdapter:
    """
    Configuration for one warehouse MCP server.

    Credential flow:
      build_env(credentials)  →  env vars injected into the subprocess
      build_args(credentials) →  resolved CLI args (handles {CRED_KEY} placeholders,
                                 e.g. the Postgres connection-string positional arg)
    """

    name: str
    command: str                       # binary to exec, e.g. "uvx" / "npx" / "toolbox"
    args: list[str]                    # CLI args; may contain {CRED_KEY} placeholders
    query_tool: str                    # MCP tool name used to execute SQL
    query_arg: str                     # argument key for the SQL string in that tool
    env_keys: list[str] = field(default_factory=list)
    # Credential keys whose names are identical in both the creds dict and the env.
    # e.g. "SNOWFLAKE_ACCOUNT" → env var SNOWFLAKE_ACCOUNT
    env_remap: dict[str, str] = field(default_factory=dict)
    # Credential keys with different env var names.
    # e.g. {"BIGQUERY_KEY_FILE": "GOOGLE_APPLICATION_CREDENTIALS"}
    transport: str = "stdio"           # "stdio" or "sse"

    # ── Availability check ─────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Return True if the MCP server launch binary is on PATH."""
        if not self.command:           # SSE transport (Supabase) — no local binary
            return True
        return shutil.which(self.command) is not None

    # ── Arg / env builders ─────────────────────────────────────────────────────

    def build_args(self, credentials: dict) -> list[str]:
        """
        Resolve {CRED_KEY} placeholders in the args list.
        Used for servers where a credential appears as a positional CLI arg
        rather than an env var (e.g. the Postgres DSN).
        """
        result = []
        for arg in self.args:
            for key, val in credentials.items():
                arg = arg.replace(f"{{{key}}}", str(val) if val is not None else "")
            result.append(arg)
        return result

    def build_env(self, credentials: dict) -> dict:
        """
        Build the env dict for the MCP subprocess.
        Inherits the parent process env (for PATH, HOME, etc.), then overlays
        warehouse credentials so the MCP server can authenticate.
        """
        env = dict(os.environ)

        # Same-name mappings
        for key in self.env_keys:
            if credentials.get(key) is not None:
                env[key] = str(credentials[key])

        # Renamed mappings
        for cred_key, env_var in self.env_remap.items():
            if credentials.get(cred_key) is not None:
                env[env_var] = str(credentials[cred_key])

        return env

    # ── Response parser ────────────────────────────────────────────────────────

    def parse_response(self, result: Any) -> list[dict]:
        """
        Convert an MCP tool-call result into list[dict] rows.

        MCP returns a list of Content objects (TextContent, ImageContent …).
        Most SQL query tools return a single TextContent with JSON.
        We handle the common response shapes used across different servers:

          Shape 1: bare list           [ {col: val, ...}, ... ]
          Shape 2: {"rows": [...]}     AWS Redshift MCP
          Shape 3: {"results": [...]}  Snowflake MCP
          Shape 4: {"data": [...]}     some BI / analytics MCP servers
          Shape 5: plain text          Supabase MCP (CSV-like or markdown table)
          Shape 6: {"result": "...<untrusted-data-UUID>[...]</untrusted-data-UUID>..."}
                   Supabase hosted MCP wraps JSON rows inside a string with
                   untrusted-data boundary tags
        """
        import logging
        import re
        log = logging.getLogger("yorph.adapters")

        for content in result.content or []:
            text = getattr(content, "text", None)
            if not text:
                continue
            try:
                data = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                # Not JSON — the text might be a raw Supabase response with
                # untrusted-data boundary tags (Shape 6 without the JSON wrapper),
                # or a CSV/TSV/markdown table (Shape 5).
                extracted = self._extract_untrusted_data(text)
                if extracted is not None:
                    return extracted
                rows = self._parse_text_table(text)
                if rows is not None:
                    return rows
                log.debug("parse_response: non-JSON, non-table text: %s", text[:500])
                continue

            # Shape 1 — bare list of row dicts
            if isinstance(data, list):
                if not data:
                    return []  # valid empty result set
                if isinstance(data[0], dict):
                    return [{k.lower(): v for k, v in row.items()} for row in data]

            if isinstance(data, dict):
                for key in ("rows", "results", "data"):
                    rows = data.get(key)
                    if isinstance(rows, list):
                        if not rows:
                            return []  # valid empty result set
                        if isinstance(rows[0], dict):
                            return [{k.lower(): v for k, v in row.items()} for row in rows]

                # Shape 6 — Supabase hosted MCP: {"result": "...<untrusted-data-UUID>JSON</untrusted-data-UUID>..."}
                result_val = data.get("result")
                if isinstance(result_val, str):
                    extracted = self._extract_untrusted_data(result_val)
                    if extracted is not None:
                        return extracted

            log.debug("parse_response: unrecognized JSON shape: %s", str(data)[:500])

        return []

    @staticmethod
    def _extract_untrusted_data(text: str) -> list[dict] | None:
        """
        Extract JSON rows from Supabase MCP's untrusted-data wrapper.

        The Supabase hosted MCP server wraps query results like:
          "Below is the result... <untrusted-data-UUID>[{...}]</untrusted-data-UUID> ..."
        This method extracts the JSON content between the boundary tags.

        The UUID portion can be any combination of hex chars (upper or lower),
        digits, and dashes, so we use a broad character class.

        Important: the Supabase response also MENTIONS the boundary tag in its
        explanatory text ("within the below <untrusted-data-UUID> boundaries")
        before the actual data boundary.  A leading greedy ``.*`` ensures the
        regex skips those mentions and matches the LAST opening tag before the
        closing tag — which is the real data boundary.
        """
        import re
        m = re.search(
            r".*<untrusted-data-[0-9a-fA-F-]+>\s*(.*?)\s*</untrusted-data-[0-9a-fA-F-]+>",
            text,
            re.DOTALL,
        )
        if not m:
            return None
        inner = m.group(1).strip()
        if not inner:
            return []
        try:
            data = json.loads(inner)
        except (json.JSONDecodeError, TypeError):
            return None
        if isinstance(data, list):
            if not data:
                return []
            if isinstance(data[0], dict):
                return [{k.lower(): v for k, v in row.items()} for row in data]
        # Single dict result (e.g. SELECT 1 → {"test": 1})
        if isinstance(data, dict):
            return [{k.lower(): v for k, v in data.items()}]
        return None

    @staticmethod
    def _parse_text_table(text: str) -> list[dict] | None:
        """
        Parse plain-text tabular output into list[dict].

        Handles:
          - Markdown tables: | col1 | col2 |  with a |---|---| separator line
          - CSV-like output: col1,col2\\nval1,val2
          - Pipe-delimited output (no markdown separator)

        Returns None if the text doesn't look like a table.
        """
        import csv
        import io

        lines = [l for l in text.strip().splitlines() if l.strip()]
        if not lines:
            return None

        # ── Markdown table: detect separator line like |---|---|
        if any(
            all(
                cell.strip().replace("-", "").replace(":", "") == ""
                for cell in line.split("|")
                if cell.strip() != ""
            )
            and "|" in line
            and "-" in line
            for line in lines[:3]
        ):
            # Find header, separator, and data rows
            header_line = None
            data_start = 0
            for i, line in enumerate(lines):
                stripped_cells = [c.strip() for c in line.split("|") if c.strip() != ""]
                is_sep = (
                    "|" in line
                    and "-" in line
                    and all(
                        cell.replace("-", "").replace(":", "") == ""
                        for cell in stripped_cells
                    )
                )
                if is_sep:
                    if i > 0 and header_line is None:
                        header_line = lines[i - 1]
                    data_start = i + 1
                    break

            if header_line is None:
                return None

            headers = [h.strip().lower() for h in header_line.split("|") if h.strip() != ""]
            rows = []
            for line in lines[data_start:]:
                if not line.strip():
                    continue
                cells = [c.strip() for c in line.split("|") if c.strip() != ""]
                if len(cells) == len(headers):
                    rows.append(dict(zip(headers, cells)))
            return rows if rows or data_start < len(lines) else None

        # ── CSV: try the csv sniffer
        try:
            sample = "\n".join(lines[:5])
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t|;")
            reader = csv.DictReader(io.StringIO(text.strip()), dialect=dialect)
            rows = [{k.lower(): v for k, v in row.items()} for row in reader]
            if rows:
                return rows
        except csv.Error:
            pass

        return None


# ── Per-warehouse adapter instances ───────────────────────────────────────────

SNOWFLAKE_ADAPTER = WarehouseAdapter(
    name="snowflake",
    command="uvx",
    args=["snowflake-mcp"],
    # The Snowflake MCP server exposes an "execute_query" tool under the
    # query_manager service group.  The full tool name as seen by the MCP client
    # is "execute_query".  Verify with: session.list_tools() after connect.
    query_tool="execute_query",
    query_arg="query",
    env_keys=[
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_WAREHOUSE",
        "SNOWFLAKE_ROLE",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_PRIVATE_KEY_PASSPHRASE",
    ],
    env_remap={
        # The Snowflake MCP server uses SNOWFLAKE_PRIVATE_KEY_PATH, not _FILE
        "SNOWFLAKE_PRIVATE_KEY_FILE": "SNOWFLAKE_PRIVATE_KEY_PATH",
    },
)

BIGQUERY_ADAPTER = WarehouseAdapter(
    name="bigquery",
    command="toolbox",
    args=["--prebuilt", "bigquery", "--stdio"],
    query_tool="execute_sql",
    query_arg="query",
    env_keys=["BIGQUERY_PROJECT", "BIGQUERY_LOCATION"],
    env_remap={
        "BIGQUERY_KEY_FILE": "GOOGLE_APPLICATION_CREDENTIALS",
    },
)

REDSHIFT_ADAPTER = WarehouseAdapter(
    name="redshift",
    command="uvx",
    args=["awslabs.redshift-mcp-server@latest"],
    query_tool="execute_query",
    query_arg="sql",
    env_keys=[
        "AWS_REGION",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_PROFILE",
        "REDSHIFT_HOST",
        "REDSHIFT_DATABASE",
        "REDSHIFT_USER",
        "REDSHIFT_PASSWORD",
        "REDSHIFT_PORT",
    ],
)

# PostgreSQL MCP passes the connection string as a positional CLI arg, not env var.
# The DSN placeholder {PG_DSN} is resolved by build_args() — see PostgresMCPProfiler
# which sets credentials["PG_DSN"] before calling the adapter.
POSTGRES_ADAPTER = WarehouseAdapter(
    name="postgres",
    command="npx",
    args=["-y", "@modelcontextprotocol/server-postgres", "{PG_DSN}"],
    query_tool="query",
    query_arg="sql",
    env_keys=[],          # no env vars — auth via DSN positional arg
)

# Supabase uses Streamable HTTP transport to the hosted endpoint (or local for
# self-hosted).  No local subprocess is launched — WarehouseMCPClient.connect()
# uses streamablehttp_client().
SUPABASE_ADAPTER = WarehouseAdapter(
    name="supabase",
    command="",           # empty = no local binary; HTTP transport
    args=[],
    query_tool="execute_sql",
    query_arg="query",
    env_keys=["SUPABASE_PROJECT_REF", "SUPABASE_DB_PASSWORD", "SUPABASE_ACCESS_TOKEN"],
    transport="streamable_http",
)

# SQL Server — community MCP server (Microsoft has no official server).
# Has only two tools: list_tables and execute_query.
SQLSERVER_ADAPTER = WarehouseAdapter(
    name="sql_server",
    command="uvx",
    args=["microsoft_sql_server_mcp"],
    query_tool="execute_query",
    query_arg="query",
    env_keys=["MSSQL_SERVER", "MSSQL_DATABASE", "MSSQL_USER", "MSSQL_PASSWORD", "MSSQL_PORT"],
)

# Registry: warehouse_type → adapter
ADAPTERS: dict[str, WarehouseAdapter] = {
    "snowflake":  SNOWFLAKE_ADAPTER,
    "bigquery":   BIGQUERY_ADAPTER,
    "redshift":   REDSHIFT_ADAPTER,
    "postgres":   POSTGRES_ADAPTER,
    "supabase":   SUPABASE_ADAPTER,
    "sql_server": SQLSERVER_ADAPTER,
}
