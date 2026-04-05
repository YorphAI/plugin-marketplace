"""
MCPBackedProfiler — BaseProfiler mixin that delegates connect/execute/disconnect
to a WarehouseMCPClient instead of managing a direct DB connection.

Usage via multiple inheritance
==============================
Concrete classes combine this mixin with a warehouse-specific profiler so that:
  - MCPBackedProfiler provides: connect(), disconnect(), execute(), is_available()
  - SnowflakeProfiler (etc.) provides: get_schemas_sql(), get_tables_sql(), ...

Example:
    class SnowflakeMCPProfiler(MCPBackedProfiler, SnowflakeProfiler):
        ADAPTER = SNOWFLAKE_ADAPTER
        WAREHOUSE_TYPE = "snowflake"   # must match the direct profiler's value

Python MRO ensures the leftmost base wins for overridden methods:
  SnowflakeMCPProfiler → MCPBackedProfiler → SnowflakeProfiler → BaseProfiler
So connect/disconnect/execute come from MCPBackedProfiler, SQL generation comes
from SnowflakeProfiler, and dataclass / disk I/O come from BaseProfiler.
"""

from __future__ import annotations

import shutil

from .base import BaseProfiler
from runtime.mcp_client.client import WarehouseMCPClient
from runtime.mcp_client.adapters import WarehouseAdapter


class MCPBackedProfiler(BaseProfiler):
    """
    Abstract mixin — subclasses MUST:
      1. Set ADAPTER = <a WarehouseAdapter instance>
      2. Also inherit a concrete profiler (e.g. SnowflakeProfiler) for SQL generation
    """

    ADAPTER: WarehouseAdapter  # set on each concrete subclass

    def __init__(self, credentials: dict) -> None:
        super().__init__(credentials)
        self._mcp: WarehouseMCPClient | None = None

    # ── Availability check ─────────────────────────────────────────────────────

    @classmethod
    def is_available(cls) -> bool:
        """
        Return True if this MCP server's launch binary is on PATH.
        Used by _get_profiler_class() in tools.py to decide whether to use
        the MCP path or fall back to the direct connector.
        """
        adapter = getattr(cls, "ADAPTER", None)
        if adapter is None:
            return False
        if not adapter.command:          # SSE transport (Supabase) — always try
            return True
        return shutil.which(adapter.command) is not None

    # ── Override connection methods ────────────────────────────────────────────

    def connect(self) -> None:
        self._mcp = WarehouseMCPClient()
        self._mcp.connect(self.ADAPTER, self.credentials)

    def disconnect(self) -> None:
        if self._mcp:
            self._mcp.disconnect()
            self._mcp = None

    def execute(self, sql: str) -> list[dict]:
        if not self._mcp:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._mcp.execute(sql)
