"""
Redshift MCP profiler — delegates SQL execution to the official AWS Labs Redshift
MCP server (uvx awslabs.redshift-mcp-server@latest) while inheriting Redshift
SQL generation from RedshiftProfiler.

Auth note
=========
The Redshift MCP server reads AWS credentials (AWS_REGION, AWS_ACCESS_KEY_ID,
AWS_SECRET_ACCESS_KEY, or AWS_PROFILE) from its env and handles Redshift
authentication internally.
"""

from .mcp_backed import MCPBackedProfiler
from .redshift import RedshiftProfiler
from runtime.mcp_client.adapters import REDSHIFT_ADAPTER


class RedshiftMCPProfiler(MCPBackedProfiler, RedshiftProfiler):
    ADAPTER = REDSHIFT_ADAPTER
    WAREHOUSE_TYPE = "redshift"
