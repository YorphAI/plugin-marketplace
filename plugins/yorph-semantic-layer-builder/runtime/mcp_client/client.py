"""
WarehouseMCPClient — manages a warehouse MCP server subprocess.

Architecture
============
The MCP server runs as a child subprocess (stdio transport) or connects to a
hosted SSE endpoint (Supabase).  Both require an async context manager to stay
alive for the session lifetime, which conflicts with the synchronous interface
expected by BaseProfiler.execute().

Solution: run a dedicated asyncio event loop in a background daemon thread.
Sync callers (e.g. profiler.execute()) schedule coroutines on that loop via
asyncio.run_coroutine_threadsafe() and block until the result is ready.

Thread safety
=============
connect() and disconnect() must be called from the same thread (the main thread
or whatever owns the profiler).  execute() is safe to call from any thread after
connect() returns — asyncio.run_coroutine_threadsafe() handles the handoff.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

from .adapters import WarehouseAdapter


class WarehouseMCPClient:

    def __init__(self) -> None:
        self._adapter: WarehouseAdapter | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._session: Any | None = None          # mcp.ClientSession
        self._ready = threading.Event()
        self._connect_error: Exception | None = None
        # asyncio.Event owned by the background loop; set by disconnect()
        self._shutdown_flag: asyncio.Event | None = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def connect(self, adapter: WarehouseAdapter, credentials: dict) -> None:
        """
        Launch the MCP server subprocess and initialise the MCP session.
        Blocks until the session is ready (up to 45 s) or raises on failure.
        """
        self._adapter = adapter
        self._loop = asyncio.new_event_loop()
        self._ready.clear()
        self._connect_error = None

        _runners = {
            "stdio": self._run_stdio,
            "sse": self._run_sse,
            "streamable_http": self._run_streamable_http,
        }
        target = _runners.get(adapter.transport, self._run_stdio)
        self._thread = threading.Thread(
            target=target,
            args=(credentials,),
            daemon=True,
            name=f"mcp-{adapter.name}",
        )
        self._thread.start()

        if not self._ready.wait(timeout=45):
            self._thread.join(timeout=2)
            raise TimeoutError(
                f"MCP server '{adapter.command}' did not respond within 45 s. "
                "Ensure the binary is installed:\n"
                f"  uvx: uv tool install ...\n"
                f"  npx: requires Node.js\n"
                f"  toolbox: pip install google-cloud-toolbox"
            )

        if self._connect_error:
            raise self._connect_error

    def execute(self, sql: str) -> list[dict]:
        """Execute SQL via the MCP server and return rows as list[dict]."""
        if not self._session or not self._loop:
            raise RuntimeError("MCP client not connected. Call connect() first.")
        future = asyncio.run_coroutine_threadsafe(
            self._call_query(sql), self._loop
        )
        try:
            return future.result(timeout=120)
        except TimeoutError:
            raise TimeoutError("MCP query timed out after 120 s.")

    def list_tools(self) -> list[str]:
        """Return the names of all tools the connected MCP server exposes."""
        if not self._session or not self._loop:
            raise RuntimeError("Not connected.")
        future = asyncio.run_coroutine_threadsafe(
            self._session.list_tools(), self._loop
        )
        result = future.result(timeout=30)
        return [t.name for t in (result.tools or [])]

    def disconnect(self) -> None:
        """Shut down the MCP session and join the background thread."""
        if self._loop and self._shutdown_flag is not None:
            self._loop.call_soon_threadsafe(self._shutdown_flag.set)
        if self._thread:
            self._thread.join(timeout=10)
        self._session = None
        self._loop = None
        self._thread = None
        self._shutdown_flag = None

    # ── Background thread entry points ─────────────────────────────────────────

    def _run_stdio(self, credentials: dict) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._async_stdio(credentials))

    def _run_sse(self, credentials: dict) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._async_sse(credentials))

    def _run_streamable_http(self, credentials: dict) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._async_streamable_http(credentials))

    # ── Async runners (stay alive while shutdown_flag is not set) ──────────────

    async def _async_stdio(self, credentials: dict) -> None:
        from mcp import ClientSession, StdioServerParameters  # type: ignore
        from mcp.client.stdio import stdio_client             # type: ignore

        adapter = self._adapter
        cmd_args = adapter.build_args(credentials)
        env = adapter.build_env(credentials)

        params = StdioServerParameters(
            command=adapter.command,
            args=cmd_args,
            env=env,
        )

        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self._session = session
                    self._shutdown_flag = asyncio.Event()
                    self._ready.set()          # unblock connect() in the main thread
                    await self._shutdown_flag.wait()
        except Exception as exc:
            self._connect_error = exc
            self._ready.set()              # unblock connect() so it can raise
        finally:
            self._session = None

    async def _async_sse(self, credentials: dict) -> None:
        from mcp import ClientSession                # type: ignore
        from mcp.client.sse import sse_client        # type: ignore

        # Supabase: hosted endpoint with Bearer auth, or local for self-hosted
        project_ref = credentials.get("SUPABASE_PROJECT_REF")
        access_token = credentials.get("SUPABASE_ACCESS_TOKEN")

        if project_ref:
            if not access_token:
                self._connect_error = ConnectionError(
                    "Supabase MCP hosted endpoint requires SUPABASE_ACCESS_TOKEN "
                    "(personal access token). project_ref + db_password credentials "
                    "are not supported by the hosted MCP server — falling back to "
                    "direct PostgreSQL connection."
                )
                self._ready.set()
                return

            url = f"https://mcp.supabase.com/sse?project_ref={project_ref}"
            headers: dict = {"Authorization": f"Bearer {access_token}"}
        else:
            # Self-hosted Supabase
            url = credentials.get("SUPABASE_MCP_URL", "http://localhost:54321/mcp")
            headers = {}

        try:
            async with sse_client(url, headers=headers) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self._session = session
                    self._shutdown_flag = asyncio.Event()
                    self._ready.set()
                    await self._shutdown_flag.wait()
        except Exception as exc:
            self._connect_error = exc
            self._ready.set()
        finally:
            self._session = None

    async def _async_streamable_http(self, credentials: dict) -> None:
        import httpx                                                     # type: ignore
        from mcp import ClientSession                                    # type: ignore
        from mcp.client.streamable_http import streamable_http_client    # type: ignore

        project_ref = credentials.get("SUPABASE_PROJECT_REF")
        access_token = credentials.get("SUPABASE_ACCESS_TOKEN")

        if project_ref:
            if not access_token:
                self._connect_error = ConnectionError(
                    "Supabase MCP hosted endpoint requires SUPABASE_ACCESS_TOKEN "
                    "(personal access token). project_ref + db_password credentials "
                    "are not supported by the hosted MCP server — falling back to "
                    "direct PostgreSQL connection."
                )
                self._ready.set()
                return

            url = f"https://mcp.supabase.com/mcp?project_ref={project_ref}"
            headers: dict = {"Authorization": f"Bearer {access_token}"}
        else:
            url = credentials.get("SUPABASE_MCP_URL", "http://localhost:54321/mcp")
            headers = {}

        try:
            # streamable_http_client does not accept headers directly;
            # pass a pre-configured httpx.AsyncClient instead.
            # Use a generous timeout — the default httpx timeout is 5s which
            # is too short for remote MCP endpoints (Supabase) running complex
            # queries like information_schema JOINs during profiling.
            http_client = httpx.AsyncClient(
                headers=headers,
                timeout=httpx.Timeout(120.0),
            ) if headers else None
            async with streamable_http_client(url, http_client=http_client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self._session = session
                    self._shutdown_flag = asyncio.Event()
                    self._ready.set()
                    await self._shutdown_flag.wait()
        except Exception as exc:
            self._connect_error = exc
            self._ready.set()
        finally:
            self._session = None

    # ── Private helpers ────────────────────────────────────────────────────────

    async def _call_query(self, sql: str) -> list[dict]:
        result = await self._session.call_tool(
            self._adapter.query_tool,
            {self._adapter.query_arg: sql},
        )

        # Check for MCP-level errors (isError flag on CallToolResult)
        if getattr(result, "isError", False):
            error_texts = []
            for content in (result.content or []):
                text = getattr(content, "text", None)
                if text:
                    error_texts.append(text)
            error_msg = "\n".join(error_texts) if error_texts else "Unknown MCP tool error"
            raise RuntimeError(f"MCP tool '{self._adapter.query_tool}' returned error: {error_msg}")

        parsed = self._adapter.parse_response(result)

        # If parsing returned empty but there WAS content, surface a diagnostic
        # row so the caller can see the raw MCP response format and debug.
        if not parsed:
            raw_texts = []
            for content in (result.content or []):
                text = getattr(content, "text", None)
                ctype = getattr(content, "type", "unknown")
                if text:
                    raw_texts.append({"type": ctype, "text_preview": text[:2000]})
            if raw_texts:
                return [{"_debug_unparsed": True, "_raw_content": raw_texts}]

        return parsed
