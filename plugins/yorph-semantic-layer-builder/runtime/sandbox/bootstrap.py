"""
Sandbox bootstrap — runs INSIDE the subprocess.

This script is the security boundary. It:
  1. Sets resource limits (CPU, memory) via resource.setrlimit on Unix
  2. Pre-imports approved third-party libraries (with full builtins access)
  3. THEN installs import hook to restrict what user code can import
  4. Builds a restricted __builtins__ dict for user code (blocks open/exec/eval)
  5. Defines load_sample(schema, table) -> pd.DataFrame
  6. Executes the user's code in a restricted namespace
  7. Captures stdout + last expression result
  8. Writes a JSON envelope to stdout as the final line

Key insight: The import hook is installed AFTER library imports, not before.
Libraries (numpy, pandas, scipy) need unrestricted imports (os, sys, threading,
etc.) to initialize. The hook only needs to restrict what the USER's code can
import — by the time user code runs, all library modules are already loaded.

Usage (called by SandboxRunner, never directly):
    python bootstrap.py <tmp_dir> <manifest_json>
"""

import sys
import json
import io
import ast
import traceback
import builtins

# ── Step 1: Resource limits (Unix only) ──────────────────────────────────────

def _set_resource_limits():
    """Set CPU and memory limits. No-op on Windows."""
    try:
        import resource
        # Memory: 512 MB
        mem = 512 * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        # CPU: 30 seconds
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    except (ImportError, ValueError, OSError):
        pass  # Windows, or container without permission

_set_resource_limits()

# ── Step 2: Pre-import libraries WITH FULL BUILTINS ──────────────────────────
# Libraries need unrestricted imports (os, sys, threading, etc.) to initialize.
# We import them first, then lock down the import hook for user code.

import pandas as pd
import numpy as np

try:
    from scipy import stats as scipy_stats
except ImportError:
    scipy_stats = None

try:
    import networkx as nx
except ImportError:
    nx = None

import difflib

# ── Step 3: Parse arguments + read user code (before locking down) ───────────

_tmp_dir = sys.argv[1]
_manifest = json.loads(sys.argv[2])

_code_path = _tmp_dir + "/_user_code.py"
with open(_code_path, "r") as _f:
    _user_code = _f.read()

# ── Step 4: Install import hook (AFTER library imports) ──────────────────────
# Now that all libraries are loaded, we can restrict what new imports are
# allowed. User code can only import from the approved whitelist.

_original_import = builtins.__import__

_APPROVED_TOP_LEVEL = {
    # stdlib (safe for user code)
    "math", "statistics", "collections", "itertools", "functools",
    "json", "datetime", "re", "decimal", "fractions",
    "operator", "string", "textwrap", "copy", "pprint",
    "dataclasses", "typing", "enum", "abc",
    "typing_extensions",
    # third party (already loaded above, but user code may re-import)
    "pandas", "numpy", "scipy", "networkx", "difflib",
    # dependencies of approved libraries (may need lazy sub-imports)
    "pyarrow", "pytz", "dateutil",
}

# Modules that must NEVER be importable by user code
_HARD_BLOCKED = {
    "os", "sys",  # filesystem and interpreter access
    "subprocess", "socket", "http", "urllib", "requests",
    "ctypes", "shutil", "pathlib", "signal", "multiprocessing",
    "threading", "pickle", "shelve", "tempfile", "importlib",
}

def _safe_import(name, *args, **kwargs):
    """Import hook: allow only approved modules and their submodules."""
    top_level = name.split(".")[0]

    # Hard-block dangerous modules
    if top_level in _HARD_BLOCKED:
        raise ImportError(
            f"Module '{name}' is not available in the sandbox."
        )

    # Allow CPython internal modules (underscore-prefixed C extensions)
    if top_level.startswith("_"):
        return _original_import(name, *args, **kwargs)

    # Allow approved modules and their submodules
    if top_level in _APPROVED_TOP_LEVEL:
        return _original_import(name, *args, **kwargs)

    raise ImportError(
        f"Module '{name}' is not available in the sandbox. "
        f"Approved: pandas, numpy, scipy.stats, networkx, difflib, "
        f"and standard library modules (math, json, datetime, re, etc.)."
    )

builtins.__import__ = _safe_import

# ── Step 5: Define load_sample() + available_tables() ────────────────────────

def load_sample(schema_or_ref: str, table: str = None):
    """
    Load cached sample data as a pandas DataFrame.

    Usage:
        df = load_sample("PUBLIC", "orders")     # schema + table
        df = load_sample("PUBLIC.orders")          # dotted reference

    Call available_tables() to see what's available.
    """
    if table is not None:
        ref = f"{schema_or_ref}.{table}"
    else:
        ref = schema_or_ref

    if ref not in _manifest:
        available = sorted(_manifest.keys())
        raise FileNotFoundError(
            f"No cached data for '{ref}'. Available tables: {available}"
        )

    return pd.read_parquet(_manifest[ref], engine="pyarrow")


def available_tables():
    """Return list of table references available in the sandbox."""
    return sorted(_manifest.keys())

# ── Step 6: Build restricted __builtins__ for user code ──────────────────────
# User code gets a copy of builtins with dangerous functions replaced.
# Libraries (already imported above) retain access to real builtins.

def _blocked_fn(*_args, **_kwargs):
    raise PermissionError("This function is not available in the sandbox.")

_restricted_builtins = dict(vars(builtins))
for _name in ("open", "exec", "eval", "compile", "breakpoint", "exit", "quit", "input"):
    _restricted_builtins[_name] = _blocked_fn
_restricted_builtins["__import__"] = _safe_import

# ── Step 7: Execute user code + capture output ───────────────────────────────

_captured_stdout = io.StringIO()
_old_stdout = sys.stdout
sys.stdout = _captured_stdout

_result = None
_error = None

try:
    _compiled = compile(_user_code, "<sandbox>", "exec")

    _namespace = {
        # Pre-imported libraries
        "pd": pd,
        "np": np,
        "scipy_stats": scipy_stats,
        "nx": nx,
        "difflib": difflib,
        # Data loading helpers
        "load_sample": load_sample,
        "available_tables": available_tables,
        # Restricted builtins (open/exec/eval blocked, import hook active)
        "__builtins__": _restricted_builtins,
    }

    exec(_compiled, _namespace)

    # ── Step 8: Capture last expression value ────────────────────────────
    # If the last statement is a pure expression (not a function call like
    # print()), evaluate it and capture repr — like a Jupyter cell.
    # Skip if the last statement is a Call (to avoid re-executing print, etc.)
    try:
        _tree = ast.parse(_user_code)
        if _tree.body and isinstance(_tree.body[-1], ast.Expr):
            _last_value = _tree.body[-1].value
            # Skip Call expressions (print(), load_sample(), etc.)
            # — they have side effects and would execute twice
            if not isinstance(_last_value, ast.Call):
                _last_expr = ast.Expression(_last_value)
                ast.fix_missing_locations(_last_expr)
                _last_compiled = compile(_last_expr, "<sandbox>", "eval")
                _result = repr(eval(_last_compiled, _namespace))
    except Exception:
        pass  # Not critical — stdout output is always available

except Exception:
    _error = traceback.format_exc()

finally:
    sys.stdout = _old_stdout

# ── Step 9: Write JSON envelope to stdout ────────────────────────────────────

_envelope = {
    "stdout": _captured_stdout.getvalue()[:100_000],
    "result": _result,
    "error": _error,
}

print(json.dumps(_envelope))
