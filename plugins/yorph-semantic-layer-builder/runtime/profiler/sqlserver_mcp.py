"""
SQL Server MCP profiler — delegates SQL execution to the community SQL Server MCP
server (uvx microsoft_sql_server_mcp) while inheriting SQL generation from
SQLServerProfiler.

Community server note
=====================
Microsoft has no official SQL Server MCP server.  We use the community server
at https://github.com/RichardHan/mssql_mcp_server which exposes only two tools:
  - list_tables
  - execute_query

is_available() checks whether 'uvx' is on PATH.  If not (or if the server fails
to start), _get_profiler_class() falls back to the direct SQLServerProfiler which
uses pyodbc.
"""

from .mcp_backed import MCPBackedProfiler
from .sqlserver import SQLServerProfiler
from runtime.mcp_client.adapters import SQLSERVER_ADAPTER


class SQLServerMCPProfiler(MCPBackedProfiler, SQLServerProfiler):
    ADAPTER = SQLSERVER_ADAPTER
    WAREHOUSE_TYPE = "sql_server"
