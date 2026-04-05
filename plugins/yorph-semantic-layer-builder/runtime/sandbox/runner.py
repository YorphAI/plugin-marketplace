"""
SandboxRunner — executes user-provided Python code in a subprocess sandbox.

Architecture:
  1. Pre-flight validation: scan code for blocked patterns (defense in depth)
  2. Data staging: decrypt cached Parquet files into a temp directory
     (lazy — only tables referenced in the code are staged)
  3. Subprocess launch: run bootstrap.py as a child process with minimal env
  4. Capture: collect stdout + last expression result from JSON on subprocess stdout
  5. Cleanup: remove temp directory

The subprocess has:
  - No network access (no approved network libraries, no socket module)
  - No filesystem access beyond the staged temp dir
  - CPU timeout (RLIMIT_CPU on Unix, asyncio timeout as fallback)
  - Memory cap (RLIMIT_AS on Unix)
  - Only approved libraries importable (custom import hook in bootstrap.py)
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.sampler.cache import SamplerCache, _decrypt_file
from runtime.sandbox._policy import (
    TIMEOUT_SECONDS,
    MAX_OUTPUT_CHARS,
    CODE_BLOCKLIST_PATTERNS,
)


@dataclass
class SandboxResult:
    """Result from a sandbox execution."""
    success: bool
    stdout: str                # captured print() output
    result: str | None         # repr of last expression (if any)
    error: str | None          # stderr / exception traceback
    execution_time_ms: int     # wall-clock time


class SandboxRunner:
    """
    Execute Python code in a sandboxed subprocess with access to cached sample data.

    The sandbox provides:
      - load_sample(schema, table) -> pd.DataFrame
      - available_tables() -> list[str]
      - Pre-imported: pd, np, scipy_stats, nx, difflib

    Usage:
        runner = SandboxRunner(caches={"snowflake": cache_instance})
        result = await runner.execute(
            code="df = load_sample('PUBLIC', 'orders'); print(df.shape)",
            description="Check orders table shape"
        )
    """

    def __init__(self, caches: dict[str, SamplerCache]):
        """
        Args:
            caches: mapping of warehouse_type -> SamplerCache instance
                    (from _sessions in tools.py)
        """
        self._caches = caches

    async def execute(self, code: str, description: str = "") -> SandboxResult:
        """
        Execute Python code in a subprocess sandbox.

        Returns SandboxResult with stdout, last expression result, and/or error.
        The MCP server process is never at risk — all execution happens in a child.
        """
        start = time.monotonic()

        # Step 1: Pre-flight validation
        violation = self._check_code(code)
        if violation:
            return SandboxResult(
                success=False,
                stdout="",
                result=None,
                error=f"Code rejected (pre-flight): {violation}",
                execution_time_ms=0,
            )

        # Step 2-6: Stage data, launch subprocess, capture output, cleanup
        tmp_dir = None
        try:
            tmp_dir = Path(tempfile.mkdtemp(prefix="yorph_sandbox_"))

            # Stage only tables referenced in the code (lazy staging)
            manifest = self._stage_data(tmp_dir, code)

            # Write user code to file (avoids shell escaping issues)
            code_file = tmp_dir / "_user_code.py"
            code_file.write_text(code, encoding="utf-8")

            # Launch subprocess
            bootstrap_path = str(Path(__file__).parent / "bootstrap.py")

            proc = await asyncio.create_subprocess_exec(
                sys.executable, bootstrap_path,
                str(tmp_dir), json.dumps(manifest),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._build_env(tmp_dir),
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                elapsed = int((time.monotonic() - start) * 1000)
                return SandboxResult(
                    success=False,
                    stdout="",
                    result=None,
                    error=f"Execution timed out after {TIMEOUT_SECONDS}s.",
                    execution_time_ms=elapsed,
                )

            # Parse output
            elapsed = int((time.monotonic() - start) * 1000)
            stdout_str = stdout_bytes.decode("utf-8", errors="replace")[:MAX_OUTPUT_CHARS]
            stderr_str = stderr_bytes.decode("utf-8", errors="replace")[:MAX_OUTPUT_CHARS]

            if proc.returncode != 0:
                return SandboxResult(
                    success=False,
                    stdout=stdout_str,
                    result=None,
                    error=stderr_str or f"Process exited with code {proc.returncode}",
                    execution_time_ms=elapsed,
                )

            # Bootstrap writes a JSON envelope as the last line of stdout
            return self._parse_output(stdout_str, elapsed)

        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            return SandboxResult(
                success=False,
                stdout="",
                result=None,
                error=f"Sandbox runner error: {e}",
                execution_time_ms=elapsed,
            )
        finally:
            # Cleanup temp directory
            if tmp_dir and tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _check_code(self, code: str) -> str | None:
        """
        Scan code for blocked patterns. Returns error message or None.

        This is defense-in-depth — the subprocess import hook is the primary
        security boundary. This catches obvious attacks before even spawning.
        """
        for pattern in CODE_BLOCKLIST_PATTERNS:
            if re.search(pattern, code):
                return f"Blocked pattern detected: '{pattern}'"
        return None

    def _stage_data(self, tmp_dir: Path, code: str) -> dict[str, str]:
        """
        Decrypt cached Parquet files to temp dir, return a manifest
        mapping "SCHEMA.TABLE" -> file path.

        Lazy staging: only decrypts tables that appear in load_sample() calls
        in the user's code. If no specific tables are detected, stages all.
        """
        # Find tables referenced in load_sample() calls
        referenced = self._find_referenced_tables(code)

        manifest: dict[str, str] = {}
        for _wh_type, cache in self._caches.items():
            for ref in cache.list_cached():
                # ref is like "PUBLIC.orders"
                # If we found specific references, only stage those
                if referenced and ref not in referenced:
                    continue

                enc_path = cache._base / f"{ref}.parquet.enc"
                if not enc_path.exists():
                    continue

                # Decrypt to temp dir as plain Parquet
                import pandas as _pd
                raw = _decrypt_file(enc_path)
                df = _pd.read_parquet(io.BytesIO(raw), engine="pyarrow")
                out_path = tmp_dir / f"{ref}.parquet"
                df.to_parquet(out_path, index=False, engine="pyarrow")
                manifest[ref] = str(out_path)

        return manifest

    def _find_referenced_tables(self, code: str) -> set[str]:
        """
        Scan code for load_sample() calls and extract table references.

        Matches patterns like:
          load_sample("PUBLIC", "orders")
          load_sample('PUBLIC.orders')
          load_sample("PUBLIC", "ORDERS")

        Returns set of "SCHEMA.TABLE" references, or empty set if none found
        (which means: stage everything).
        """
        refs: set[str] = set()

        # Pattern 1: load_sample("schema", "table")
        two_arg = re.findall(
            r'load_sample\s*\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']\s*\)',
            code,
        )
        for schema, table in two_arg:
            refs.add(f"{schema}.{table}")

        # Pattern 2: load_sample("schema.table")
        one_arg = re.findall(
            r'load_sample\s*\(\s*["\']([^"\']+\.[^"\']+)["\']\s*\)',
            code,
        )
        for ref in one_arg:
            refs.add(ref)

        return refs

    def _build_env(self, tmp_dir: Path) -> dict[str, str]:
        """
        Build a minimal environment for the subprocess.

        Inherits PATH and PYTHONPATH (so the Python binary and libraries
        are accessible) but strips sensitive env vars.
        """
        env: dict[str, str] = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(tmp_dir),       # prevent ~/.* file reads
            "TMPDIR": str(tmp_dir),
            "YORPH_SANDBOX": "1",       # signal to bootstrap.py
        }

        # Inherit PYTHONPATH so numpy/pandas/etc. are importable
        if "PYTHONPATH" in os.environ:
            env["PYTHONPATH"] = os.environ["PYTHONPATH"]

        # On macOS, numpy/scipy need dynamic library paths
        if "DYLD_LIBRARY_PATH" in os.environ:
            env["DYLD_LIBRARY_PATH"] = os.environ["DYLD_LIBRARY_PATH"]
        if "DYLD_FALLBACK_LIBRARY_PATH" in os.environ:
            env["DYLD_FALLBACK_LIBRARY_PATH"] = os.environ["DYLD_FALLBACK_LIBRARY_PATH"]

        # On Linux, similar for LD_LIBRARY_PATH
        if "LD_LIBRARY_PATH" in os.environ:
            env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]

        # Virtual environment support
        if "VIRTUAL_ENV" in os.environ:
            env["VIRTUAL_ENV"] = os.environ["VIRTUAL_ENV"]

        # Conda environment support
        if "CONDA_PREFIX" in os.environ:
            env["CONDA_PREFIX"] = os.environ["CONDA_PREFIX"]

        return env

    def _parse_output(self, stdout: str, elapsed_ms: int) -> SandboxResult:
        """
        Parse the JSON envelope the bootstrap script writes as the last line.

        The bootstrap writes all print() output to a captured StringIO,
        then writes the final JSON envelope to real stdout. So stdout
        contains only the JSON envelope.

        Format: {"stdout": "...", "result": "...", "error": null}
        """
        stdout = stdout.strip()
        if not stdout:
            return SandboxResult(
                success=True,
                stdout="",
                result=None,
                error=None,
                execution_time_ms=elapsed_ms,
            )

        # The entire stdout should be the JSON envelope
        # (bootstrap captures user prints to StringIO, not to real stdout)
        try:
            envelope = json.loads(stdout)
            return SandboxResult(
                success=envelope.get("error") is None,
                stdout=envelope.get("stdout", ""),
                result=envelope.get("result"),
                error=envelope.get("error"),
                execution_time_ms=elapsed_ms,
            )
        except json.JSONDecodeError:
            # Bootstrap didn't write valid JSON — return raw stdout
            return SandboxResult(
                success=True,
                stdout=stdout,
                result=None,
                error=None,
                execution_time_ms=elapsed_ms,
            )
