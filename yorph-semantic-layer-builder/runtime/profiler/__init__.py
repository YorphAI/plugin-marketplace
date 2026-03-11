# Direct connectors (file-based for S3/GCS; direct DB for others)
from .snowflake import SnowflakeProfiler
from .bigquery import BigQueryProfiler
from .redshift import RedshiftProfiler
from .sqlserver import SQLServerProfiler
from .supabase import SupabaseProfiler
from .postgres import PostgresProfiler
from .s3 import S3Profiler
from .gcs import GCSProfiler

# MCP-backed connectors (delegate SQL execution to official MCP servers)
from .snowflake_mcp import SnowflakeMCPProfiler
from .bigquery_mcp import BigQueryMCPProfiler
from .redshift_mcp import RedshiftMCPProfiler
from .postgres_mcp import PostgresMCPProfiler
from .supabase_mcp import SupabaseMCPProfiler
from .sqlserver_mcp import SQLServerMCPProfiler

__all__ = [
    # Direct
    "SnowflakeProfiler",
    "BigQueryProfiler",
    "RedshiftProfiler",
    "SQLServerProfiler",
    "SupabaseProfiler",
    "PostgresProfiler",
    "S3Profiler",
    "GCSProfiler",
    # MCP-backed
    "SnowflakeMCPProfiler",
    "BigQueryMCPProfiler",
    "RedshiftMCPProfiler",
    "PostgresMCPProfiler",
    "SupabaseMCPProfiler",
    "SQLServerMCPProfiler",
]
