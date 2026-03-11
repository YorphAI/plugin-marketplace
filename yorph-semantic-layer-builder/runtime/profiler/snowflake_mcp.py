"""
Snowflake MCP profiler — delegates SQL execution to the official Snowflake MCP
server (uvx snowflake-mcp) while inheriting all Snowflake SQL generation from
SnowflakeProfiler.

Auth note
=========
The Snowflake MCP server handles auth entirely — it reads SNOWFLAKE_ACCOUNT,
SNOWFLAKE_USER, and either SNOWFLAKE_PRIVATE_KEY_PATH (key-pair) or
SNOWFLAKE_PASSWORD (password) from its env vars, and manages token refresh
internally.  This means MFA/TOTP flows are handled by the MCP server, not by
Yorph.  Key-pair auth is still recommended (no codes to re-enter between runs).
"""

from .mcp_backed import MCPBackedProfiler
from .snowflake import SnowflakeProfiler
from runtime.mcp_client.adapters import SNOWFLAKE_ADAPTER


class SnowflakeMCPProfiler(MCPBackedProfiler, SnowflakeProfiler):
    ADAPTER = SNOWFLAKE_ADAPTER
    WAREHOUSE_TYPE = "snowflake"
