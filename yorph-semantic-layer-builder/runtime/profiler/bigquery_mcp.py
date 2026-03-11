"""
BigQuery MCP profiler — delegates SQL execution to google/genai-toolbox
(toolbox --prebuilt bigquery --stdio) while inheriting BigQuery SQL generation
from BigQueryProfiler.

Auth note
=========
The toolbox process reads BIGQUERY_PROJECT and GOOGLE_APPLICATION_CREDENTIALS
from its env.  ADC (gcloud auth application-default login) is the recommended
auth method — no key file needed if already authenticated via gcloud.
"""

from .mcp_backed import MCPBackedProfiler
from .bigquery import BigQueryProfiler
from runtime.mcp_client.adapters import BIGQUERY_ADAPTER


class BigQueryMCPProfiler(MCPBackedProfiler, BigQueryProfiler):
    ADAPTER = BIGQUERY_ADAPTER
    WAREHOUSE_TYPE = "bigquery"
