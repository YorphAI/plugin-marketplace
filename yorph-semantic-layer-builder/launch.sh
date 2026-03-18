#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# FIX: Use a writable location for the venv instead of the plugin directory.
# In Cowork (desktop app sandbox), the plugin directory is mounted via bindfs
# with --delete-deny, which means:
#   - [ -w dir ] returns true (create works)
#   - but pip install fails because it can't overwrite/delete temp files
# We test for ACTUAL full write capability by creating AND deleting a temp file.
# If that fails, fall back to /tmp which is a normal writable filesystem.
# (We skip ~/.yorph/ because it also uses --delete-deny in Cowork.)
_test_writable() {
    local dir="$1"
    local tmp="$dir/.yorph-write-test-$$"
    touch "$tmp" 2>/dev/null && rm "$tmp" 2>/dev/null
}

if _test_writable "$SCRIPT_DIR"; then
    VENV_DIR="$SCRIPT_DIR/.venv"
else
    # Plugin dir doesn't support full read/write/delete — use /tmp or override
    VENV_DIR="${YORPH_VENV_DIR:-/tmp/yorph-venv}"
fi

VENV_PYTHON="$VENV_DIR/bin/python3"
STAMP_FILE="$VENV_DIR/.deps-installed"

# Bootstrap on first run (or if venv is missing)
if [ ! -f "$STAMP_FILE" ]; then
    # Find Python >= 3.10
    PYTHON=""
    for cmd in python3 python3.13 python3.12 python3.11 python3.10; do
        if command -v "$cmd" &>/dev/null; then
            if "$cmd" -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
                PYTHON="$(command -v "$cmd")"
                break
            fi
        fi
    done

    if [ -z "$PYTHON" ]; then
        echo "Error: Python >= 3.10 is required but not found." >&2
        echo "Install it with: brew install python@3.12  (macOS)" >&2
        echo "                 sudo apt install python3.12 (Ubuntu/Debian)" >&2
        exit 1
    fi

    # Create venv if needed
    if [ ! -d "$VENV_DIR" ]; then
        "$PYTHON" -m venv "$VENV_DIR" >&2
    fi

    # Install dependencies
    "$VENV_DIR/bin/pip" install --quiet -e "$SCRIPT_DIR/runtime/" >&2

    # Stamp so we skip next time
    date > "$STAMP_FILE"
fi

# Start the MCP server
exec "$VENV_PYTHON" -m runtime.cli serve
