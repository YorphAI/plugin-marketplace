"""
Sandbox security policy — approved libraries, blocked builtins, resource limits.

All sandbox constraints are defined here so they can be audited in a single file.
Changes to the security boundary should only touch this file.
"""

# ── Resource limits ──────────────────────────────────────────────────────────

# Maximum wall-clock execution time before the subprocess is killed (seconds).
TIMEOUT_SECONDS = 30

# Maximum memory the subprocess is allowed to use (bytes).
# ~512 MB — enough for pandas/numpy on 5,000-row sample data.
MAX_MEMORY_BYTES = 512 * 1024 * 1024

# Maximum combined output size from stdout/stderr (characters).
MAX_OUTPUT_CHARS = 100_000

# ── Approved modules (whitelist) ─────────────────────────────────────────────

# Standard library modules the sandbox allows.
APPROVED_STDLIB = frozenset({
    "math", "statistics", "collections", "itertools", "functools",
    "json", "datetime", "re", "decimal", "fractions",
    "operator", "string", "textwrap", "copy", "pprint",
    "dataclasses", "typing", "enum", "abc",
})

# Third-party libraries the sandbox allows.
# Must already be installed in the Python environment.
APPROVED_THIRD_PARTY = frozenset({
    "pandas", "numpy", "scipy", "networkx", "difflib",
})

# Top-level package names for the import hook.
# Submodules of approved packages are allowed implicitly
# (e.g. numpy.core, pandas.core.dtypes, scipy.stats).
APPROVED_TOP_LEVEL = APPROVED_STDLIB | APPROVED_THIRD_PARTY

# ── Blocked builtins ─────────────────────────────────────────────────────────

# Builtins that are replaced with a PermissionError-raising stub in the sandbox.
BLOCKED_BUILTINS = frozenset({
    "exec", "eval", "compile",
    "open", "input",
    "breakpoint", "exit", "quit",
})

# ── Pre-flight code blocklist ────────────────────────────────────────────────

# Regex patterns scanned against the raw code string BEFORE launching the
# subprocess. Defense in depth — even if the import hook fails, these catch
# the most dangerous escape vectors.
CODE_BLOCKLIST_PATTERNS = [
    r"subprocess",
    r"os\s*\.",
    r"sys\s*\.",
    r"shutil",
    r"pathlib",
    r"socket",
    r"\bhttp\b",
    r"urllib",
    r"requests",
    r"ctypes",
    r"importlib",
    r"__builtins__",
    r"__subclasses__",
    r"__class__",
    r"__bases__",
    r"__mro__",
    r"signal\s*\.",
    r"multiprocessing",
    r"threading",
    r"pickle",
    r"shelve",
    r"tempfile",
]
