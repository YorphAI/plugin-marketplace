"""
MCP tool registrations — exposes Python functions as tools Claude can call.

Claude never runs Python directly. It calls these tools by name with
parameters, and the tool implementations handle execution and return
results as JSON-serialisable dicts.

Tools exposed:
  - connect_warehouse        → authenticate + test connection
  - run_profiler             → Phase 1 + Phase 2, write to ~/.yorph/profiles/
  - get_context_summary      → return enriched profile text for Claude's context
  - get_sample_slice         → fetch rows from local cache for agent validation
  - execute_validation_sql   → run a SQL query Claude generates for validation
  - process_document         → parse uploaded file into structured DocumentContext
  - fetch_url_context        → fetch a URL and extract DocumentContext from it
  - get_document_context     → return all loaded document context for agents
  - save_output              → write final semantic layer to ~/.yorph/output/
  - list_credentials         → show required credentials + how-to-get guide per warehouse
  - query                    → run any SELECT at any time; auto-reconnects from keychain
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import keyring
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from runtime.profiler.snowflake import SnowflakeProfiler
from runtime.profiler.bigquery import BigQueryProfiler
from runtime.profiler.redshift import RedshiftProfiler
from runtime.profiler.sqlserver import SQLServerProfiler
from runtime.profiler.supabase import SupabaseProfiler
from runtime.profiler.postgres import PostgresProfiler
from runtime.profiler.s3 import S3Profiler
from runtime.profiler.gcs import GCSProfiler
from runtime.profiler.snowflake_mcp import SnowflakeMCPProfiler
from runtime.profiler.bigquery_mcp import BigQueryMCPProfiler
from runtime.profiler.redshift_mcp import RedshiftMCPProfiler
from runtime.profiler.postgres_mcp import PostgresMCPProfiler
from runtime.profiler.supabase_mcp import SupabaseMCPProfiler
from runtime.profiler.sqlserver_mcp import SQLServerMCPProfiler
from runtime.sampler.cache import SamplerCache
from runtime.documents.processor import process_file, fetch_url
from runtime.documents.context import load_all_document_contexts, MergedDocumentContext
from runtime.documents.enricher import build_enriched_profiles, enriched_context_summary

# ── Server setup ──────────────────────────────────────────────────────────────

app = Server("yorph-semantic-layer")

# Active sessions — supports up to 2 simultaneous data sources.
# Keyed by warehouse_type, e.g. {"snowflake": {...}, "postgres": {...}}
MAX_SOURCES = 2
_sessions: dict[str, dict[str, Any]] = {}

# MCP-backed profilers (preferred) mapped to their direct fallbacks.
# S3 and GCS are file-based (pandas) and have no SQL MCP server, so they
# always use the direct profiler.
# Supabase: MCP profiler preferred (streamable HTTP to hosted endpoint).
# Falls back to direct psycopg2 if MCP connect/execute fails at runtime.
_MCP_PROFILERS: dict[str, type] = {
    "snowflake":  SnowflakeMCPProfiler,
    "bigquery":   BigQueryMCPProfiler,
    "redshift":   RedshiftMCPProfiler,
    "postgres":   PostgresMCPProfiler,
    "supabase":   SupabaseMCPProfiler,
    "sql_server": SQLServerMCPProfiler,
}

_DIRECT_PROFILERS: dict[str, type] = {
    "snowflake":  SnowflakeProfiler,
    "bigquery":   BigQueryProfiler,
    "redshift":   RedshiftProfiler,
    "sql_server": SQLServerProfiler,
    "supabase":   SupabaseProfiler,
    "postgres":   PostgresProfiler,
    "s3":         S3Profiler,
    "gcs":        GCSProfiler,
}


def _get_profiler_class(warehouse_type: str) -> type | None:
    """
    Return the best available profiler class for the given warehouse type.

    Preference order:
      1. MCP-backed profiler — if the MCP server binary is on PATH (uvx/npx/toolbox)
         or uses SSE transport (Supabase, no binary needed).
      2. Direct connector — fallback when the MCP binary is not installed.
      3. None — if the warehouse type is not supported at all.

    S3 and GCS always use the direct (file-based) profiler — there is no
    suitable MCP server for general S3/GCS object profiling.
    """
    mcp_cls = _MCP_PROFILERS.get(warehouse_type)
    if mcp_cls is not None and mcp_cls.is_available():
        return mcp_cls
    return _DIRECT_PROFILERS.get(warehouse_type)


def _get_session(warehouse_type: str | None = None) -> dict[str, Any] | None:
    """
    Return the session dict for the given warehouse_type, or the first active
    session if warehouse_type is None. Returns None if no sessions are active.
    """
    if not _sessions:
        return None
    if warehouse_type:
        return _sessions.get(warehouse_type)
    return next(iter(_sessions.values()))


# ── Credential reference guide ────────────────────────────────────────────────
# Extracted to runtime/credentials.py so the CLI can import it without pulling
# in MCP server dependencies. Re-exported here for backward compat.
from runtime.credentials import CREDENTIAL_GUIDE


_DOTENV_PATH = Path.home() / ".yorph" / ".env"


def _load_dotenv() -> dict[str, str]:
    """
    Read key=value pairs from ~/.yorph/.env (if it exists).

    Supports:
      - KEY=value
      - KEY="value"  and  KEY='value'  (quotes stripped)
      - # comments and blank lines (skipped)
      - export KEY=value (export prefix stripped)

    Returns a dict of the parsed values. Does NOT modify os.environ — the
    values are only used by _load_from_env so they don't leak into other
    processes.
    """
    if not _DOTENV_PATH.exists():
        return {}

    env: dict[str, str] = {}
    for line in _DOTENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        env[key] = value
    return env


def _diagnose_env_file(warehouse_type: str) -> str:
    """
    Check ~/.yorph/.env and return a human-readable diagnostic message:
      - If the file doesn't exist → suggest creating it with required keys
      - If the file exists → show which keys are present vs missing for the warehouse
    """
    guide = CREDENTIAL_GUIDE.get(warehouse_type)
    if not guide:
        return f"Warehouse type '{warehouse_type}' is not recognised."

    if not _DOTENV_PATH.exists():
        # Collect all required keys across auth methods for the example
        example_keys: list[str] = []
        for method in guide["auth_methods"].values():
            for key in method.get("required", {}):
                if key not in example_keys:
                    example_keys.append(key)
        example_lines = "\n".join(f"{k}=your-value-here" for k in example_keys[:4])
        return (
            f"No ~/.yorph/.env file found. Create one with your {guide['display']} credentials:\n"
            f"  mkdir -p ~/.yorph && cat > ~/.yorph/.env << 'EOF'\n"
            f"  {example_lines}\n"
            f"  EOF\n"
            "Call list_credentials to see exactly which fields are needed and where to find them."
        )

    # File exists — check which keys are present vs missing for each auth method
    dotenv = _load_dotenv()
    present_keys = set(dotenv.keys())
    lines = [f"Found ~/.yorph/.env with keys: {', '.join(sorted(present_keys)) or '(empty)'}"]

    for method_key, method in guide["auth_methods"].items():
        required = set(method.get("required", {}).keys())
        optional = set(method.get("optional", {}).keys())
        missing_required = required - present_keys
        present_required = required & present_keys
        present_optional = optional & present_keys

        if not missing_required:
            lines.append(
                f"  ✓ Auth method '{method_key}' ({method['label']}): "
                f"all required keys present ({', '.join(sorted(present_required))})"
            )
        else:
            lines.append(
                f"  ✗ Auth method '{method_key}' ({method['label']}): "
                f"missing required keys: {', '.join(sorted(missing_required))}"
            )
            if present_required:
                lines.append(f"    present: {', '.join(sorted(present_required))}")

    return "\n".join(lines)


def _load_from_env(warehouse_type: str) -> dict[str, Any] | None:
    """
    Attempt to build a credentials dict from environment variables.

    Checks two sources (in priority order for each variable):
      1. Process environment (os.environ)
      2. ~/.yorph/.env file (re-read on every call so changes take effect
         without restarting the MCP server)

    Uses the CREDENTIAL_GUIDE to discover which env var names are valid for each
    warehouse. Tries each auth_method in order and returns the first one where
    ALL required env vars are set. Optional env vars are included if present.

    Returns the credentials dict on success, or None if no complete auth method
    was found in the environment.
    """
    guide = CREDENTIAL_GUIDE.get(warehouse_type)
    if not guide:
        return None

    # Re-read the dotenv file on every call so the user can create/edit it
    # without restarting the MCP server.
    dotenv = _load_dotenv()

    def _get(name: str) -> str | None:
        """Look up a variable: process env first, then dotenv file."""
        return os.environ.get(name) or dotenv.get(name)

    # Collect all auth methods where ALL required vars are present,
    # then pick the one with the most required keys (most specific wins).
    # This prevents a broad method like "adc" (1 required key) from shadowing
    # a more specific method like "service_account_json" (2 required keys)
    # when the user has provided credentials for both.
    candidates: list[tuple[int, dict[str, Any]]] = []

    for method_key, method in guide["auth_methods"].items():
        required = method.get("required", {})
        optional = method.get("optional", {})

        # Check if all required env vars are present
        method_creds: dict[str, Any] = {"auth_method": method_key}
        all_present = True
        for env_name in required:
            val = _get(env_name)
            if val is None:
                all_present = False
                break
            method_creds[env_name] = val

        if not all_present:
            continue

        # All required vars present — pick up optional ones too
        for env_name in optional:
            val = _get(env_name)
            if val is not None:
                method_creds[env_name] = val

        candidates.append((len(required), method_creds))

    if not candidates:
        return None

    # Return the most specific match (most required keys)
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _assert_read_only(sql: str) -> str | None:
    """
    Return an error string if `sql` contains any write or DDL statement, otherwise None.

    Defence layers:
      1. Strip SQL line-comments (-- ...) and block-comments (/* ... */) so they can't
         be used to hide forbidden keywords.  Block-comment stripping is iterative to
         handle nested /* /* */ */ patterns; any remaining delimiters after exhaustive
         stripping cause the query to be rejected outright.
      2. Reject semicolons entirely — no multi-statement batches are allowed.
      3. Require the first real keyword to be SELECT or WITH (CTEs).
      4. Word-boundary scan the full SQL for any write/DDL keyword — this catches
         forbidden ops inside subqueries, CTEs, or RETURNING clauses.

    This is intentionally conservative: if something looks ambiguous, it is rejected.
    Column names like "created_at" are safe because the pattern requires a word boundary
    *before and after* the keyword.
    """
    # Strip line comments
    stripped = re.sub(r"--[^\n]*", " ", sql)
    # Strip block comments — iterate until stable to handle nested /* /* */ */ patterns.
    prev = None
    while prev != stripped:
        prev = stripped
        stripped = re.sub(r"/\*.*?\*/", " ", stripped, flags=re.DOTALL)
    # If any comment delimiters survive exhaustive stripping, the SQL contains malformed
    # or non-terminating block comments we cannot safely analyse — reject it.
    if "/*" in stripped or "*/" in stripped:
        return "Malformed or nested SQL block comments are not permitted."
    # Normalise whitespace
    stripped = stripped.strip()

    # 1. No semicolons — prevents multi-statement injection
    if ";" in stripped:
        return "Multi-statement SQL is not permitted. Remove the semicolon(s)."

    # 2. Must start with SELECT or WITH
    first_word = stripped.split()[0].upper() if stripped.split() else ""
    if first_word not in ("SELECT", "WITH"):
        return (
            f"Only SELECT queries are permitted. "
            f"Your query starts with '{first_word}'."
        )

    # 3. Full-text word-boundary scan for write/DDL keywords
    _FORBIDDEN = re.compile(
        r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|CREATE|ALTER|GRANT|REVOKE|"
        r"MERGE|UPSERT|REPLACE|EXECUTE|EXEC|CALL|COPY|LOAD|PUT|GET|REMOVE|"
        r"UNDROP|CLONE)\b",
        re.IGNORECASE,
    )
    match = _FORBIDDEN.search(stripped)
    if match:
        return (
            f"Write and DDL operations are not permitted. "
            f"Found forbidden keyword: '{match.group().upper()}'."
        )

    return None  # SQL is clean


def _format_credential_guide(warehouse_type: str | None = None) -> str:
    """
    Return a human-readable credential guide for one warehouse or all of them.
    Used by the list_credentials tool and connect_warehouse error messages.
    """
    warehouses = (
        [warehouse_type] if warehouse_type and warehouse_type in CREDENTIAL_GUIDE
        else list(CREDENTIAL_GUIDE.keys())
    )
    lines = []
    for wh in warehouses:
        info = CREDENTIAL_GUIDE[wh]
        lines.append(f"## {info['display']}")
        for method_key, method in info["auth_methods"].items():
            lines.append(f"\n### {method['label']}  (auth_method='{method_key}')")
            lines.append("\n**Required credentials:**")
            for key, desc in method["required"].items():
                lines.append(f"  • `{key}` — {desc}")
            if method.get("optional"):
                lines.append("\n**Optional:**")
                for key, desc in method["optional"].items():
                    lines.append(f"  • `{key}` — {desc}")
            lines.append(f"\n**How to get them:**\n{method['how_to_get']}")
        if info.get("readonly_tip"):
            lines.append(f"\n**🔒 Security recommendation (read-only role):**\n{info['readonly_tip']}")
        lines.append("")
    return "\n".join(lines)


def _ensure_connected(warehouse_type: str | None) -> dict[str, Any] | str:
    """
    Return an active session for warehouse_type, auto-reconnecting from keychain
    if the session has expired. Returns the session dict on success, or an
    error string describing what to do on failure.

    This allows any tool (query, execute_validation_sql, etc.) to work even
    if the user's conversation-level session was dropped.
    """
    session = _get_session(warehouse_type)
    if session:
        # Verify the connection is still alive
        try:
            session["profiler"].execute("SELECT 1 AS _ping")
            return session
        except Exception:
            # Connection is stale — drop it and reconnect below
            wh_key = warehouse_type or next(iter(_sessions.keys()), None)
            if wh_key and wh_key in _sessions:
                try:
                    _sessions[wh_key]["profiler"].disconnect()
                except Exception:
                    pass
                del _sessions[wh_key]

    # If no warehouse specified and multiple are saved, we can't auto-pick
    if not warehouse_type:
        return (
            "Not connected to any warehouse. "
            "Call connect_warehouse with a warehouse_type to connect. "
            "If you've connected before, your credentials are saved — "
            "just call connect_warehouse with the warehouse_type and no credentials."
        )

    # Try keychain auto-reconnect
    _keychain_key = f"yorph_{warehouse_type}"
    try:
        saved = keyring.get_password("yorph", _keychain_key)
    except Exception:
        saved = None
    if not saved:
        # Fall back to environment variables
        env_creds = _load_from_env(warehouse_type)
        if env_creds:
            saved = json.dumps(env_creds)
        else:
            diag = _diagnose_env_file(warehouse_type)
            return (
                f"Not connected to {warehouse_type} and no saved credentials found.\n\n"
                f"{diag}\n\n"
                f"Add the missing credentials to ~/.yorph/.env and call connect_warehouse again. "
                f"Call list_credentials to see full details."
            )

    creds = json.loads(saved)
    ProfilerClass = _get_profiler_class(warehouse_type)
    if not ProfilerClass:
        return f"Warehouse type '{warehouse_type}' is not supported."

    if len(_sessions) >= MAX_SOURCES:
        return (
            f"Cannot auto-reconnect to {warehouse_type}: "
            f"maximum of {MAX_SOURCES} simultaneous sources already connected "
            f"({list(_sessions.keys())}). Disconnect one first."
        )

    # Try MCP first, fall back to direct if it connects but returns no data
    is_mcp = ProfilerClass is _MCP_PROFILERS.get(warehouse_type)
    profiler = ProfilerClass(credentials=creds)
    try:
        profiler.connect()
        test_rows = profiler.execute("SELECT 1 AS test")
        if not test_rows or (
            test_rows
            and isinstance(test_rows[0], dict)
            and test_rows[0].get("_debug_unparsed")
        ):
            raise RuntimeError(
                "Connected but SELECT 1 returned no parseable data."
                + (
                    f" Raw: {test_rows[0].get('_raw_content', '')}"
                    if test_rows else ""
                )
            )
    except Exception as e:
        if is_mcp:
            direct_cls = _DIRECT_PROFILERS.get(warehouse_type)
            if direct_cls:
                try:
                    profiler = direct_cls(credentials=creds)
                    profiler.connect()
                    test_rows = profiler.execute("SELECT 1 AS test")
                    if not test_rows:
                        raise RuntimeError("Direct connector returned no data")
                except Exception as fallback_err:
                    return (
                        f"Auto-reconnect to {warehouse_type} failed.\n"
                        f"MCP: {e}\nDirect: {fallback_err}\n"
                        "Your saved credentials may have expired. "
                        "Call connect_warehouse with fresh credentials."
                    )
            else:
                return (
                    f"Auto-reconnect to {warehouse_type} failed: {e}\n"
                    "Your saved credentials may have expired. "
                    "Call connect_warehouse with fresh credentials."
                )
        else:
            return (
                f"Auto-reconnect to {warehouse_type} failed: {e}\n"
                "Your saved credentials may have expired. "
                "Call connect_warehouse with fresh credentials."
            )

    _sessions[warehouse_type] = {
        "profiler": profiler,
        "cache": SamplerCache(warehouse_type=warehouse_type),
    }
    return _sessions[warehouse_type]


# ── Tool: connect_warehouse ───────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="connect_warehouse",
            description=(
                "Connect to a data warehouse. Credentials are resolved automatically: "
                "OS keychain (from a previous session or plugin UI) → ~/.yorph/.env file → "
                "environment variables. Optionally pass 'credential_key' if the plugin UI "
                "stored credentials under a specific keychain key. "
                "Tests the connection and returns connection status. "
                "Must be called before run_profiler."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "warehouse_type": {
                        "type": "string",
                        "enum": ["snowflake", "bigquery", "redshift", "sql_server", "supabase", "postgres", "s3", "gcs"],
                        "description": "Which warehouse to connect to."
                    },
                    "credential_key": {
                        "type": "string",
                        "description": "OS keychain key where credentials are stored (set by the plugin UI modal). Omit to use auto-resolution."
                    }
                },
                "required": ["warehouse_type"]
            }
        ),
        Tool(
            name="run_profiler",
            description=(
                "Run schema discovery and data profiling across all tables. "
                "Profiling means scanning your warehouse to collect statistical metadata about every table and column — "
                "null rates, distinct counts, min/max/percentiles, sample values, and date format detection — "
                "without pulling raw data into the conversation. "
                "Uses TABLESAMPLE BERNOULLI(10%) for cost control (no full table scans). "
                "Runs all table profiles in parallel. "
                "Saves compact profiles to ~/.yorph/profiles/ and caches raw sample rows to ~/.yorph/samples/. "
                "Call this immediately after connect_warehouse."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "warehouse_type": {
                        "type": "string",
                        "enum": ["snowflake", "bigquery", "redshift", "sql_server", "supabase", "postgres", "s3", "gcs"],
                        "description": "Which connected source to profile. Required when 2 sources are connected; omit when only 1 is connected."
                    },
                    "schemas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific schemas to profile. If omitted, profiles all schemas."
                    },
                    "row_limit": {
                        "type": "integer",
                        "default": 5000,
                        "description": "Max raw rows to cache per table (for agent validation)."
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_context_summary",
            description=(
                "Returns a compact text summary of all table profiles, formatted for "
                "loading into Claude's context window. ~150-400 tokens per table. "
                "Call this after run_profiler to load data into context."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "schemas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter to specific schemas. Omit for all."
                    }
                },
                "required": [],
                "description": "Returns merged profiles from all connected sources when multiple are active."
            }
        ),
        Tool(
            name="get_sample_slice",
            description=(
                "Fetch a small slice of cached raw rows for a specific table. "
                "Use this during agent validation to verify join keys, check "
                "value distributions, or confirm measure logic. "
                "Max 100 rows returned per call."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "warehouse_type": {
                        "type": "string",
                        "enum": ["snowflake", "bigquery", "redshift", "sql_server", "supabase", "postgres", "s3", "gcs"],
                        "description": "Which source the table belongs to. Required when 2 sources are connected."
                    },
                    "schema": {"type": "string", "description": "Schema name."},
                    "table": {"type": "string", "description": "Table name."},
                    "filters": {
                        "type": "object",
                        "description": "Simple equality filters e.g. {\"status\": \"refunded\"}",
                        "additionalProperties": {"type": "string"}
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Columns to return. Omit for all columns."
                    },
                    "limit": {
                        "type": "integer",
                        "default": 20,
                        "description": "Number of rows to return (max 100)."
                    }
                },
                "required": ["schema", "table"]
            }
        ),
        Tool(
            name="execute_validation_sql",
            description=(
                "Execute a SQL query against the connected warehouse for validation purposes. "
                "Use this to verify join cardinality, check for nulls in key columns, "
                "validate measure calculations, or confirm granularity assumptions. "
                "Read-only queries only — no INSERT, UPDATE, DELETE, DROP."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "warehouse_type": {
                        "type": "string",
                        "enum": ["snowflake", "bigquery", "redshift", "sql_server", "supabase", "postgres", "s3", "gcs"],
                        "description": "Which source to run the query against. Required when 2 sources are connected."
                    },
                    "sql": {
                        "type": "string",
                        "description": "The SQL query to execute. Must be a SELECT statement."
                    },
                    "description": {
                        "type": "string",
                        "description": "What this query is validating (for logging)."
                    }
                },
                "required": ["sql", "description"]
            }
        ),
        Tool(
            name="process_document",
            description=(
                "Parse an uploaded file (PDF, DOCX, CSV, Excel, JSON, YAML, Markdown) into a "
                "structured DocumentContext — table descriptions, column definitions with business names, "
                "metric definitions, business rules, glossary, and join hints. "
                "The extracted context is saved to ~/.yorph/documents/ and automatically merged "
                "into all subsequent get_context_summary calls, enriching agent reasoning with "
                "documented semantics. Call this when the user uploads a data dictionary, "
                "SaaS context doc, business glossary, or existing semantic layer definition."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to the uploaded file."
                    },
                    "document_type": {
                        "type": "string",
                        "enum": [
                            "data_dictionary", "saas_context", "business_glossary",
                            "existing_semantic_layer", "schema_docs", "unknown"
                        ],
                        "description": "What kind of document this is. Helps guide extraction."
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="fetch_url_context",
            description=(
                "Fetch a URL (Confluence page, Notion doc, GitHub README/wiki, internal wiki, "
                "dbt manifest endpoint, or any documentation page) and extract structured "
                "DocumentContext from it — same output as process_document. "
                "Handles HTML pages (strips chrome, extracts content), raw JSON/YAML endpoints, "
                "and plain text. Extracted context is saved and merged into agent context. "
                "Call this when the user provides a link to documentation about their data."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch (must be HTTP/HTTPS)."
                    },
                    "document_type": {
                        "type": "string",
                        "enum": [
                            "data_dictionary", "saas_context", "business_glossary",
                            "existing_semantic_layer", "schema_docs", "unknown"
                        ],
                        "description": "What kind of content this URL contains."
                    }
                },
                "required": ["url"]
            }
        ),
        Tool(
            name="get_document_context",
            description=(
                "Return a compact summary of all loaded DocumentContexts — table descriptions, "
                "column business names, metric definitions, business rules, and glossary terms "
                "extracted from uploaded files and URLs. "
                "Agents call this at the start of the build phase to load documented semantics "
                "alongside column profiles. Also reports any conflicts found between documentation "
                "and the profiled data."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="save_output",
            description=(
                "Render and save the final semantic layer to ~/.yorph/output/. "
                "Always generates BOTH the technical format (dbt/Snowflake/JSON/YAML/OSI/DOCX) AND "
                "a companion _readme.md explaining every metric, join, and design decision in plain English. "
                "Preferred usage: pass agent_outputs (structured JSON from all 9 agents) + "
                "recommendation_number (1=Conservative, 2=Comprehensive, 3=Balanced) and the renderer "
                "builds everything. Fallback: pass raw content string if agent outputs aren't available. "
                "Use format='all' to generate every supported format at once. "
                "Supports mix-and-match: pass joins_grade, measures_grade, grain_grade independently "
                "(each 1/2/3) to override the bundled recommendation per dimension."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_outputs": {
                        "type": "object",
                        "description": (
                            "Structured outputs from all agents. Expected keys: "
                            # Phase 2 user inputs (passed through unchanged — ground truth)
                            "'entity_disambiguation' (dict: entity_name→{definition, primary_id, relationships}), "
                            "'user_provided_metrics' (list: {name, formula, source_tables, filters, notes} — VERIFIED HIGH-confidence), "
                            "'standard_exclusions' (list of plain-English filter strings from the user — always included in business_rules), "
                            # Pre-analysis agents
                            "'domain_context' (dict: table→{domain, annotated_columns}), "
                            "'candidate_measures' (list: {column, table, confidence, recommended_aggregation, domain, source} — "
                            "source='user_provided' for VERIFIED metrics, source='inferred' for column-scan candidates), "
                            # Join Validator (3 personas)
                            "'joins_jv1', 'joins_jv2', 'joins_jv3' (or fallback 'joins') for joins, "
                            "'join_conflicts' (list of joins where JV-1 rejects but JV-3 accepts), "
                            # Measures Builder (3 personas)
                            "'measures_mb1', 'measures_mb2', 'measures_mb3' (lists), "
                            "'measure_conflicts' (list: borderline measures MB-3 adds over MB-1), "
                            # Grain Detector (3 personas)
                            "'grain_gd1', 'grain_gd2', 'grain_gd3' (lists), "
                            "'grain_conflicts' (list: what GD-3 reporting marts add over GD-1), "
                            # Foundational agents
                            "'business_rules' (list of strings — user standard_exclusions marked [USER CONFIRMED]), "
                            "'open_questions' (list), 'glossary' (dict), "
                            # Sentinel agents
                            "'quality_flags' (list: {table, column, issue, severity, recommendation}), "
                            "'scd_tables' (list: {table, scd_type, validity_columns, safe_join_pattern, warning}). "
                            "If provided, the renderer builds all formats from this — preferred path."
                        )
                    },
                    "recommendation_number": {
                        "type": "integer",
                        "enum": [1, 2, 3],
                        "description": (
                            "Which recommendation to render: 1=Conservative, 2=Comprehensive, 3=Balanced. "
                            "Used as the default for any dimension not individually overridden."
                        )
                    },
                    "joins_grade": {
                        "type": "integer",
                        "enum": [1, 2, 3],
                        "description": (
                            "Join Validator grade to use independently of other dimensions. "
                            "1=JV-1 Strict (FK match >95%, N:1 confirmed only), "
                            "2=JV-2 Explorer (all plausible joins incl. many:many), "
                            "3=JV-3 Trap Hunter (validated + fan-out detection). "
                            "Overrides recommendation_number for the joins dimension."
                        )
                    },
                    "measures_grade": {
                        "type": "integer",
                        "enum": [1, 2, 3],
                        "description": (
                            "Measures Builder grade to use independently of other dimensions. "
                            "1=MB-1 Minimalist (5-15 core KPIs only), "
                            "2=MB-2 Analyst (all derivable metrics), "
                            "3=MB-3 Strategist (core KPIs + top derived metrics by domain). "
                            "Overrides recommendation_number for the measures dimension."
                        )
                    },
                    "grain_grade": {
                        "type": "integer",
                        "enum": [1, 2, 3],
                        "description": (
                            "Grain Detector grade to use independently of other dimensions. "
                            "1=GD-1 Purist (atomic grain only, no pre-aggregation), "
                            "2=GD-2 Pragmatist (reporting grain, pre-aggregated for dashboards), "
                            "3=GD-3 Architect (hybrid: atomic fact + pre-aggregated reporting mart). "
                            "Overrides recommendation_number for the grain dimension."
                        )
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Name of the project / company for the output file header."
                    },
                    "description": {
                        "type": "string",
                        "description": "One-sentence description of what this semantic layer covers."
                    },
                    "format": {
                        "type": "string",
                        "enum": ["dbt", "snowflake", "json", "yaml", "osi_spec", "docx", "custom", "all"],
                        "description": "Output format. Use 'all' to generate every format including .docx."
                    },
                    "filename": {
                        "type": "string",
                        "description": "Base filename (no extension). Default: 'semantic_layer'."
                    },
                    "content": {
                        "type": "string",
                        "description": "Fallback: raw content string if agent_outputs not available."
                    }
                },
                "required": ["format"]
            }
        ),
        Tool(
            name="list_credentials",
            description=(
                "Show exactly what credentials are required to connect to a data warehouse, "
                "including where to find them and how to generate them. "
                "Call this proactively when the user mentions a warehouse type so they know "
                "what to gather before connecting. "
                "Pass warehouse_type to get the guide for one warehouse, or omit it to see all."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "warehouse_type": {
                        "type": "string",
                        "enum": ["snowflake", "bigquery", "redshift", "sql_server", "supabase", "postgres", "s3", "gcs"],
                        "description": "Which warehouse to show credentials for. Omit to show all warehouses."
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="query",
            description=(
                "Run any SELECT query against the connected warehouse — at any time, "
                "not just during semantic layer build. "
                "If the warehouse session has expired, automatically reconnects using "
                "credentials saved in your OS keychain (set on first connect). "
                "Use this for ad-hoc data exploration, answering business questions, "
                "spot-checking values, or previewing tables. Read-only (SELECT only)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "The SQL SELECT query to run."
                    },
                    "warehouse_type": {
                        "type": "string",
                        "enum": ["snowflake", "bigquery", "redshift", "sql_server", "supabase", "postgres", "s3", "gcs"],
                        "description": (
                            "Which warehouse to query. Required if not currently connected, "
                            "or if multiple warehouses are connected."
                        )
                    },
                    "limit": {
                        "type": "integer",
                        "default": 100,
                        "description": "Cap the number of rows returned (default: 100, max: 1000)."
                    }
                },
                "required": ["sql"]
            }
        ),
        Tool(
            name="execute_python",
            description=(
                "Execute Python code in a sandboxed subprocess against cached sample data. "
                "Use this for data validation that is too complex for SQL — e.g., checking "
                "value distributions with pandas, computing statistical tests with scipy, "
                "building join graphs with networkx, or fuzzy-matching column values with difflib. "
                "The sandbox provides: load_sample(schema, table) -> DataFrame, plus pandas (pd), "
                "numpy (np), scipy.stats (scipy_stats), networkx (nx), and difflib. "
                "No network or filesystem access. Execution capped at 30s / 512 MB."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": (
                            "Python code to execute. Available functions:\n"
                            "  load_sample(schema, table) -> pd.DataFrame\n"
                            "  available_tables() -> list[str]\n"
                            "Pre-imported: pd (pandas), np (numpy), scipy_stats, nx (networkx), difflib.\n"
                            "Use print() for output. The last expression's value is also captured."
                        ),
                    },
                    "description": {
                        "type": "string",
                        "description": "What this code validates (for logging and audit).",
                    },
                },
                "required": ["code", "description"],
            },
        ),
    ]


# ── Tool call handler ─────────────────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:

    # ── connect_warehouse ─────────────────────────────────────────────────────
    if name == "connect_warehouse":
        wh = arguments["warehouse_type"]
        _keychain_key = f"yorph_{wh}"

        # Resolve credentials: plugin UI keychain → auto-saved keychain → env vars / .env
        if "credential_key" in arguments:
            cred_key = arguments["credential_key"]
            try:
                creds_json = keyring.get_password("yorph", cred_key)
            except Exception:
                creds_json = None
            if not creds_json:
                return [TextContent(type="text", text=json.dumps({
                    "success": False,
                    "error": f"No credentials found in keychain for key '{cred_key}'. "
                             "Connect via the plugin UI first, or add credentials to ~/.yorph/.env."
                }))]
            creds = json.loads(creds_json)
        else:
            # Try auto-saved keychain entry from a previous session
            try:
                saved = keyring.get_password("yorph", _keychain_key)
            except Exception:
                saved = None
            if saved:
                creds = json.loads(saved)
            else:
                # Fall back to environment variables / .env file
                env_creds = _load_from_env(wh)
                if env_creds:
                    creds = env_creds
                else:
                    diag = _diagnose_env_file(wh)
                    return [TextContent(type="text", text=json.dumps({
                        "success": False,
                        "error": (
                            f"No complete credentials found for '{wh}'.\n\n"
                            f"{diag}\n\n"
                            "Call list_credentials to see exactly what's needed. "
                            "Credentials will be saved to your OS keychain automatically for future sessions."
                        )
                    }))]

        if wh in _sessions:
            # Verify the existing connection is still alive
            try:
                _sessions[wh]["profiler"].execute("SELECT 1 AS _ping")
                return [TextContent(type="text", text=json.dumps({
                    "success": True,
                    "warehouse_type": wh,
                    "message": f"Already connected to {wh} — connection verified."
                }))]
            except Exception:
                # Stale connection — clean up and reconnect below
                try:
                    _sessions[wh]["profiler"].disconnect()
                except Exception:
                    pass
                del _sessions[wh]

        if len(_sessions) >= MAX_SOURCES:
            connected = list(_sessions.keys())
            return [TextContent(type="text", text=json.dumps({
                "success": False,
                "error": (
                    f"Maximum of {MAX_SOURCES} simultaneous data sources reached "
                    f"(currently connected: {connected}). "
                    "Ask the user which source to drop if they want to add a new one."
                )
            }))]


        ProfilerClass = _get_profiler_class(wh)
        if not ProfilerClass:
            return [TextContent(type="text", text=json.dumps({
                "success": False,
                "error": f"Warehouse type '{wh}' not yet supported."
            }))]

        # Try the chosen profiler class. If it's MCP-backed and fails at runtime
        # (e.g. subprocess error, empty results), fall back to the direct connector.
        is_mcp = ProfilerClass is _MCP_PROFILERS.get(wh)
        profiler = ProfilerClass(credentials=creds)
        connect_error: Exception | None = None
        try:
            profiler.connect()
            test_rows = profiler.execute("SELECT 1 AS test")
            # Verify we actually got data back — MCP servers may connect but
            # return empty/unparseable results (e.g. wrong response format).
            # Diagnostic rows (from _call_query debug) also indicate a parse
            # failure and should trigger fallback.
            if not test_rows or (
                test_rows
                and isinstance(test_rows[0], dict)
                and test_rows[0].get("_debug_unparsed")
            ):
                raise RuntimeError(
                    "Connection succeeded but SELECT 1 returned no parseable data. "
                    "The MCP server may be returning responses in an unrecognized format."
                    + (
                        f" Raw response: {test_rows[0].get('_raw_content', '')}"
                        if test_rows else ""
                    )
                )
        except Exception as e:
            connect_error = e
            if is_mcp:
                # MCP failed — try direct connector as fallback
                direct_cls = _DIRECT_PROFILERS.get(wh)
                if direct_cls:
                    try:
                        profiler = direct_cls(credentials=creds)
                        profiler.connect()
                        test_rows = profiler.execute("SELECT 1 AS test")
                        if not test_rows:
                            raise RuntimeError("Direct connector returned no data for SELECT 1")
                        is_mcp = False
                        connect_error = None   # fallback succeeded
                    except Exception as fallback_err:
                        # Both failed — show both errors so the user can debug
                        connect_error = ConnectionError(
                            f"MCP connection failed: {e}\n"
                            f"Direct connector also failed: {fallback_err}"
                        )

        if connect_error:
            return [TextContent(type="text", text=json.dumps({
                "success": False,
                "error": str(connect_error)
            }))]

        _sessions[wh] = {
            "profiler": profiler,
            "cache": SamplerCache(warehouse_type=wh),
        }

        # Persist credentials to OS keychain so future sessions reconnect without prompting
        try:
            keyring.set_password("yorph", _keychain_key, json.dumps(creds))
            creds_persisted = True
        except Exception:
            creds_persisted = False

        connection_mode = "MCP-backed" if is_mcp else "direct connector"
        connected_now = list(_sessions.keys())
        return [TextContent(type="text", text=json.dumps({
            "success": True,
            "warehouse_type": wh,
            "connection_mode": connection_mode,
            "active_sources": connected_now,
            "credentials_saved": creds_persisted,
            "message": (
                f"Connected to {wh} successfully ({connection_mode}). "
                f"Active sources: {connected_now}. "
                + (
                    "Credentials saved to your OS keychain — "
                    "future sessions will reconnect automatically without asking for them again. "
                    if creds_persisted else
                    "Note: credentials could not be saved to keychain — you will need to provide them again next session. "
                )
                + (
                    "You can connect one more data source if needed."
                    if len(connected_now) < MAX_SOURCES
                    else f"Maximum of {MAX_SOURCES} sources reached."
                )
            )
        }))]

    # ── run_profiler ──────────────────────────────────────────────────────────
    elif name == "run_profiler":
        wh = arguments.get("warehouse_type")
        session = _get_session(wh)
        if not session:
            return [TextContent(type="text", text=json.dumps({
                "error": (
                    "Not connected. Call connect_warehouse first."
                    if not wh else
                    f"No active session for '{wh}'. Call connect_warehouse first."
                )
            }))]
        if len(_sessions) > 1 and not wh:
            return [TextContent(type="text", text=json.dumps({
                "error": (
                    f"Multiple sources connected {list(_sessions.keys())}. "
                    "Specify warehouse_type to indicate which source to profile."
                )
            }))]
        profiler = session["profiler"]
        cache = session["cache"]

        schemas = arguments.get("schemas")
        row_limit = arguments.get("row_limit", 5000)

        # Run profiling (async, parallel across tables)
        # profile_all() returns list of (TableProfile, DataFrame) tuples.
        # Each table is profiled in pandas from a single sample query — no separate
        # stats SQL needed, and the DataFrame is cached directly (no second query).
        results = await profiler.profile_all(schemas=schemas, sample_limit=row_limit)

        # If nothing was profiled, return an actionable diagnostic instead of silent success
        if not results:
            # Surface any errors that profile_all captured
            profiling_errors = getattr(profiler, "_profiling_errors", [])

            # Try to give the user the actual schema list for debugging
            try:
                schema_rows = profiler.execute(profiler.get_schemas_sql())
                found_schemas = [r["schema_name"] for r in schema_rows]
            except Exception:
                found_schemas = []

            wh_label = wh.upper() if wh else "WAREHOUSE"
            hint = (
                "No tables were found. Common causes:\n"
                f"  1. The database/project credentials may be incomplete — check your {wh_label} "
                "credentials in ~/.yorph/.env.\n"
                "  2. The database exists but has no BASE TABLEs (only views, or is empty).\n"
                "  3. Your role doesn't have SELECT/USAGE on the schemas.\n"
            )
            if found_schemas:
                hint += (
                    f"\nSchemas visible to your role in this database: {found_schemas}\n"
                    f"Try calling run_profiler with {{\"schemas\": {json.dumps(found_schemas[:3])}}} "
                    "to target them explicitly."
                )
            else:
                hint += (
                    "\nNo schemas were returned by information_schema.schemata either. "
                    f"Check that your {wh_label} credentials point to the right database and that "
                    "your role has USAGE on it."
                )

            response = {
                "success": False,
                "tables_profiled": 0,
                "profiler_class": type(profiler).__name__,
                "hint": hint,
            }
            if profiling_errors:
                response["profiling_errors"] = profiling_errors

            return [TextContent(type="text", text=json.dumps(response))]

        # Cache sample DataFrames — profile_all() already fetched them, no second query needed
        cached_tables = []
        for profile, df in results:
            try:
                fqn = f"{profile.schema_name}.{profile.table_name}"
                n = cache.store_df(profile.schema_name, profile.table_name, df, row_limit=row_limit)
                cached_tables.append({"table": fqn, "rows_cached": n})
            except Exception as e:
                cached_tables.append({"table": f"{profile.schema_name}.{profile.table_name}", "error": str(e)})

        return [TextContent(type="text", text=json.dumps({
            "success": True,
            "tables_profiled": len(results),
            "sample_cache": cached_tables,
            "profiles_saved_to": str(Path.home() / ".yorph" / "profiles"),
            "message": (
                "Profiling complete. "
                "The profiler connected to your warehouse and scanned every table using a 10% random sample "
                "(TABLESAMPLE BERNOULLI) — no full table scans, so cost is minimal. "
                "For each table it computed per-column statistics in pandas: null rates, distinct counts, "
                "min/max/percentiles for numbers, sample values for text, date format detection, "
                "null-like string detection, currency/percent patterns, and boolean-like columns. "
                "It also cached up to 5,000 raw rows per table locally to ~/.yorph/samples/ for agent validation. "
                "The compact profiles (not raw data) are saved to ~/.yorph/profiles/ and are now ready to load. "
                "Call get_context_summary to load them into context."
            )
        }))]

    # ── get_context_summary ───────────────────────────────────────────────────
    elif name == "get_context_summary":
        if not _sessions:
            return [TextContent(type="text", text=json.dumps({
                "error": "Not connected. Call connect_warehouse first."
            }))]

        batch_index = arguments.get("batch_index", 0)

        # Merge raw profiles from ALL connected sources
        all_raw_profiles = []
        for session in _sessions.values():
            all_raw_profiles.extend(session["profiler"].load_profiles())

        if not all_raw_profiles:
            return [TextContent(type="text", text="No profiles found. Run run_profiler first.")]

        # Load document context and produce enriched profiles
        doc_contexts = load_all_document_contexts()
        from runtime.documents.context import MergedDocumentContext
        merged_docs = MergedDocumentContext(doc_contexts)

        enriched = build_enriched_profiles(all_raw_profiles)
        summary = enriched_context_summary(enriched, merged_docs, batch_index=batch_index)
        return [TextContent(type="text", text=summary)]

    # ── process_document ──────────────────────────────────────────────────────
    elif name == "process_document":
        file_path = arguments["file_path"]
        document_type = arguments.get("document_type", "unknown")
        try:
            ctx = process_file(file_path, document_type=document_type)
            return [TextContent(type="text", text=json.dumps({
                "success": True,
                "source": ctx.source_path,
                "document_type": ctx.document_type,
                "extraction_confidence": ctx.extraction_confidence,
                "extracted": {
                    "table_definitions": len(ctx.table_definitions),
                    "column_definitions": len(ctx.column_definitions),
                    "metric_definitions": len(ctx.metric_definitions),
                    "business_rules": len(ctx.business_rules),
                    "glossary_terms": len(ctx.glossary),
                    "join_hints": len(ctx.join_hints),
                },
                "extraction_notes": ctx.extraction_notes,
                "preview": ctx.to_context_summary()[:3000],
                "message": (
                    f"Document processed. Found {len(ctx.column_definitions)} column definitions, "
                    f"{len(ctx.metric_definitions)} metrics, {len(ctx.business_rules)} business rules. "
                    "This context will now automatically enrich all agent profiles. "
                    "Call get_context_summary to see the enriched profiles."
                )
            }))]
        except FileNotFoundError as e:
            return [TextContent(type="text", text=json.dumps({"success": False, "error": str(e)}))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"success": False, "error": str(e)}))]

    # ── fetch_url_context ─────────────────────────────────────────────────────
    elif name == "fetch_url_context":
        url = arguments["url"]
        document_type = arguments.get("document_type", "schema_docs")
        try:
            ctx = fetch_url(url, document_type=document_type)
            return [TextContent(type="text", text=json.dumps({
                "success": True,
                "source": ctx.source_path,
                "document_type": ctx.document_type,
                "extraction_confidence": ctx.extraction_confidence,
                "extracted": {
                    "table_definitions": len(ctx.table_definitions),
                    "column_definitions": len(ctx.column_definitions),
                    "metric_definitions": len(ctx.metric_definitions),
                    "business_rules": len(ctx.business_rules),
                    "glossary_terms": len(ctx.glossary),
                    "join_hints": len(ctx.join_hints),
                },
                "extraction_notes": ctx.extraction_notes,
                "preview": ctx.to_context_summary()[:3000],
                "message": (
                    f"URL fetched and parsed. Found {len(ctx.column_definitions)} column definitions, "
                    f"{len(ctx.metric_definitions)} metrics, {len(ctx.business_rules)} business rules. "
                    "This context is now merged into agent profiles. "
                    "Call get_context_summary to see the enriched view."
                )
            }))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"success": False, "error": str(e)}))]

    # ── get_document_context ──────────────────────────────────────────────────
    elif name == "get_document_context":
        contexts = load_all_document_contexts()
        if not contexts:
            return [TextContent(type="text", text=json.dumps({
                "documents_loaded": 0,
                "message": (
                    "No documents loaded yet. Use process_document to upload a file, "
                    "or fetch_url_context to read from a URL."
                )
            }))]
        from runtime.documents.context import MergedDocumentContext
        merged = MergedDocumentContext(contexts)
        return [TextContent(type="text", text=json.dumps({
            "documents_loaded": len(contexts),
            "sources": [ctx.source_path for ctx in contexts],
            "total_extracted": {
                "table_definitions": sum(len(c.table_definitions) for c in contexts),
                "column_definitions": sum(len(c.column_definitions) for c in contexts),
                "metric_definitions": sum(len(c.metric_definitions) for c in contexts),
                "business_rules": sum(len(c.business_rules) for c in contexts),
                "glossary_terms": sum(len(c.glossary) for c in contexts),
                "join_hints": sum(len(c.join_hints) for c in contexts),
            },
            "summary": merged.to_context_summary(),
        }))]

    # ── get_sample_slice ──────────────────────────────────────────────────────
    elif name == "get_sample_slice":
        wh = arguments.get("warehouse_type")
        session = _get_session(wh)
        if not session:
            return [TextContent(type="text", text=json.dumps({
                "error": "No active session. Run connect_warehouse and run_profiler first."
            }))]
        if len(_sessions) > 1 and not wh:
            return [TextContent(type="text", text=json.dumps({
                "error": (
                    f"Multiple sources connected {list(_sessions.keys())}. "
                    "Specify warehouse_type to indicate which source the table belongs to."
                )
            }))]
        cache: SamplerCache = session["cache"]

        try:
            rows = cache.get_slice(
                schema=arguments["schema"],
                table=arguments["table"],
                filters=arguments.get("filters"),
                columns=arguments.get("columns"),
                limit=arguments.get("limit", 20),
            )
            return [TextContent(type="text", text=json.dumps({
                "rows": rows,
                "count": len(rows)
            }, default=str))]
        except FileNotFoundError as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    # ── execute_validation_sql ────────────────────────────────────────────────
    elif name == "execute_validation_sql":
        wh = arguments.get("warehouse_type")
        if len(_sessions) > 1 and not wh:
            return [TextContent(type="text", text=json.dumps({
                "error": (
                    f"Multiple sources connected {list(_sessions.keys())}. "
                    "Specify warehouse_type to indicate which source to query."
                )
            }))]
        session_or_error = _ensure_connected(wh)
        if isinstance(session_or_error, str):
            return [TextContent(type="text", text=json.dumps({
                "error": session_or_error
            }))]
        session = session_or_error
        profiler = session["profiler"]

        sql = arguments["sql"].strip()

        # Safety guard — read-only only
        guard_error = _assert_read_only(sql)
        if guard_error:
            return [TextContent(type="text", text=json.dumps({
                "error": guard_error
            }))]

        try:
            rows = profiler.execute(sql)
            return [TextContent(type="text", text=json.dumps({
                "rows": rows[:100],  # cap at 100 rows
                "count": len(rows),
                "description": arguments.get("description", "")
            }, default=str))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    # ── save_output ───────────────────────────────────────────────────────────
    elif name == "save_output":
        from runtime.output.renderer import (
            OutputRenderer, build_semantic_layer_from_agent_outputs
        )
        output_dir = Path.home() / ".yorph" / "output"
        fmt = arguments["format"]
        filename_base = arguments.get("filename", "semantic_layer")
        warehouse_type = "+".join(_sessions.keys()) if _sessions else "unknown"

        # Path A: Claude passes structured agent_outputs JSON → renderer builds everything
        if "agent_outputs" in arguments:
            try:
                agent_outputs = (
                    arguments["agent_outputs"]
                    if isinstance(arguments["agent_outputs"], dict)
                    else json.loads(arguments["agent_outputs"])
                )
                rec_number = int(arguments.get("recommendation_number", 3))
                project_name = arguments.get("project_name", "Semantic Layer")
                description = arguments.get("description", "")

                # Per-dimension grade overrides (optional mix-and-match)
                joins_grade   = arguments.get("joins_grade")
                measures_grade = arguments.get("measures_grade")
                grain_grade   = arguments.get("grain_grade")

                layer = build_semantic_layer_from_agent_outputs(
                    agent_outputs=agent_outputs,
                    recommendation_number=rec_number,
                    warehouse_type=warehouse_type,
                    project_name=project_name,
                    description=description,
                    joins_grade=int(joins_grade) if joins_grade is not None else None,
                    measures_grade=int(measures_grade) if measures_grade is not None else None,
                    grain_grade=int(grain_grade) if grain_grade is not None else None,
                )

                renderer = OutputRenderer(layer, output_dir=output_dir)

                # "all" format generates every supported format
                formats_to_render = (
                    ["dbt", "snowflake", "json", "yaml", "osi_spec", "docx"]
                    if fmt == "all"
                    else [fmt]
                )

                all_written: dict[str, str] = {}
                for f in formats_to_render:
                    written = renderer.render(f, filename_base=filename_base)
                    all_written.update({k: str(v) for k, v in written.items()})

                files_list = "\n".join(f"  {k}: {v}" for k, v in all_written.items())
                return [TextContent(type="text", text=json.dumps({
                    "success": True,
                    "recommendation": layer.recommendation,
                    "files_written": all_written,
                    "summary": {
                        "entities": len(layer.entities),
                        "measures": len(layer.measures),
                        "joins": len(layer.joins),
                        "business_rules": len(layer.business_rules),
                        "open_questions": len(layer.open_questions),
                    },
                    "message": (
                        f"Semantic layer saved ({layer.recommendation} design).\n"
                        f"Files:\n{files_list}\n\n"
                        f"The _readme.md contains a plain-English explanation of every "
                        f"metric, join, and design decision."
                    ),
                }))]
            except Exception as e:
                return [TextContent(type="text", text=json.dumps({
                    "success": False,
                    "error": f"Renderer error: {e}",
                    "hint": "Check that agent_outputs contains 'joins', 'measures_mb*', 'grain_gd*' keys."
                }))]

        # Path B: Claude passes raw content string (fallback for partial outputs)
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
            ext_map = {
                "dbt": "yml", "snowflake": "yml", "json": "json",
                "yaml": "yaml", "osi_spec": "yaml", "document": "md", "custom": "txt"
            }
            ext = ext_map.get(fmt, "txt")
            tech_path = output_dir / f"{filename_base}.{ext}"
            tech_path.write_text(arguments["content"])

            # Always also write a minimal document
            doc_path = output_dir / f"{filename_base}_readme.md"
            doc_path.write_text(
                f"# Semantic Layer\n\nGenerated: {datetime.utcnow().isoformat()[:10]}\n\n"
                f"Format: {fmt}\n\n"
                f"> Full structured output was not available for this save. "
                f"Re-run with agent_outputs to get the enriched document."
            )

            return [TextContent(type="text", text=json.dumps({
                "success": True,
                "files_written": {fmt: str(tech_path), "document": str(doc_path)},
                "message": f"Saved to {tech_path}. Add agent_outputs next time for full rendering."
            }))]

    # ── list_credentials ──────────────────────────────────────────────────────
    elif name == "list_credentials":
        wh = arguments.get("warehouse_type")
        guide = _format_credential_guide(wh)
        display = CREDENTIAL_GUIDE[wh]["display"] if wh and wh in CREDENTIAL_GUIDE else "all warehouses"
        return [TextContent(type="text", text=json.dumps({
            "warehouse": wh or "all",
            "guide": guide,
            "message": (
                f"Credential guide for {display}. "
                "Once you have these, pass them as a JSON object to connect_warehouse. "
                "They will be saved to your OS keychain so future sessions reconnect automatically."
            )
        }))]

    # ── query ─────────────────────────────────────────────────────────────────
    elif name == "query":
        sql = arguments.get("sql", "").strip()
        wh = arguments.get("warehouse_type")
        row_limit = min(int(arguments.get("limit", 100)), 1000)

        # Read-only guard — shared strict validator
        guard_error = _assert_read_only(sql)
        if guard_error:
            return [TextContent(type="text", text=json.dumps({
                "error": guard_error
            }))]

        # Auto-reconnect if needed
        session_or_error = _ensure_connected(wh)
        if isinstance(session_or_error, str):
            return [TextContent(type="text", text=json.dumps({
                "error": session_or_error
            }))]

        session = session_or_error
        profiler = session["profiler"]
        auto_reconnected = wh not in _sessions if wh else False  # flag for transparency

        try:
            # Inject a LIMIT if the SQL doesn't already have one
            sql_with_limit = sql
            if "limit" not in sql.lower():
                sql_with_limit = f"SELECT * FROM ({sql}) AS _q LIMIT {row_limit}"
            rows = profiler.execute(sql_with_limit)
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

        active_wh = wh or next(iter(_sessions.keys()), "unknown")
        return [TextContent(type="text", text=json.dumps({
            "rows": rows[:row_limit],
            "row_count": len(rows),
            "warehouse": active_wh,
            "auto_reconnected": auto_reconnected,
            "note": (
                f"Showing up to {row_limit} rows. "
                "Pass a higher 'limit' value (max 1000) to see more."
                if len(rows) == row_limit else ""
            )
        }, default=str))]

    # ── execute_python ───────────────────────────────────────────────────────
    elif name == "execute_python":
        if not _sessions:
            return [TextContent(type="text", text=json.dumps({
                "error": (
                    "Not connected. Call connect_warehouse and run_profiler first "
                    "to populate the sample cache."
                )
            }))]

        code = arguments["code"]
        description = arguments.get("description", "")

        from runtime.sandbox.runner import SandboxRunner
        caches = {wh: session["cache"] for wh, session in _sessions.items()}
        runner = SandboxRunner(caches=caches)

        result = await runner.execute(code, description=description)

        response: dict[str, Any] = {
            "success": result.success,
            "execution_time_ms": result.execution_time_ms,
            "description": description,
        }
        if result.stdout:
            response["stdout"] = result.stdout
        if result.result:
            response["result"] = result.result
        if result.error:
            response["error"] = result.error

        return [TextContent(type="text", text=json.dumps(response, default=str))]

    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as streams:
        await app.run(*streams, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
