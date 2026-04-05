"""
Supabase MCP profiler — connects to the official Supabase MCP server via SSE
transport (https://mcp.supabase.com/sse for hosted, or localhost for self-hosted)
while inheriting Supabase SQL generation from SupabaseProfiler.

Auth note
=========
Unlike the stdio-based profilers, no subprocess is launched.  WarehouseMCPClient
opens an SSE connection to the Supabase-hosted endpoint and authenticates via:
  - SUPABASE_ACCESS_TOKEN (OAuth Bearer token) — for hosted projects
  - SUPABASE_PROJECT_REF + SUPABASE_DB_PASSWORD — project-scoped auth
  - SUPABASE_MCP_URL env var — for self-hosted Supabase pointing at localhost

is_available() always returns True for SSE transport since there is no local
binary to check.
"""

from .mcp_backed import MCPBackedProfiler
from .supabase import SupabaseProfiler
from runtime.mcp_client.adapters import SUPABASE_ADAPTER


class SupabaseMCPProfiler(MCPBackedProfiler, SupabaseProfiler):
    ADAPTER = SUPABASE_ADAPTER
    WAREHOUSE_TYPE = "supabase"
