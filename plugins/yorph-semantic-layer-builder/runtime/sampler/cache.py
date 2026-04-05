"""
Sampler cache — pulls raw rows from a warehouse and stores them locally
as encrypted Parquet files in ~/.yorph/samples/.

These are NEVER loaded into Claude's context by default.
Agents request specific slices on demand via get_slice().
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from cryptography.fernet import Fernet


# ── Encryption helpers ────────────────────────────────────────────────────────

def _get_or_create_key() -> bytes:
    """Load or generate a session-scoped encryption key stored in ~/.yorph."""
    key_path = Path.home() / ".yorph" / ".session_key"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        return key_path.read_bytes()
    key = Fernet.generate_key()
    key_path.write_bytes(key)
    key_path.chmod(0o600)  # owner read/write only
    return key


def _encrypt_file(path: Path) -> None:
    f = Fernet(_get_or_create_key())
    path.write_bytes(f.encrypt(path.read_bytes()))


def _decrypt_file(path: Path) -> bytes:
    f = Fernet(_get_or_create_key())
    return f.decrypt(path.read_bytes())


# ── Excluded PII columns ──────────────────────────────────────────────────────

EXCLUDED_PATTERNS = [
    "password", "passwd", "ssn", "social_security",
    "credit_card", "card_number", "cvv",
    "secret", "private_key", "api_key", "api_secret",
    "token", "access_token", "refresh_token",
    "hash", "salt", "encrypted",
]

def _is_excluded(col: str) -> bool:
    lower = col.lower()
    return any(p in lower for p in EXCLUDED_PATTERNS)


# ── SamplerCache ──────────────────────────────────────────────────────────────

class SamplerCache:
    """
    Manages the local raw row cache for a warehouse session.

    Usage:
        cache = SamplerCache(warehouse_type="snowflake")
        cache.store(schema="sales", table="orders", rows=rows_list)
        slice_df = cache.get_slice("sales", "orders", filters={"status": "refunded"}, limit=50)
    """

    DEFAULT_ROW_LIMIT = 5_000
    MAX_ROW_LIMIT = 50_000
    AGENT_SLICE_LIMIT = 100

    def __init__(self, warehouse_type: str):
        self.warehouse_type = warehouse_type
        self._base = Path.home() / ".yorph" / "samples" / warehouse_type
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, schema: str, table: str) -> Path:
        return self._base / f"{schema}.{table}.parquet.enc"

    # ── Write ─────────────────────────────────────────────────────────────────

    def store(
        self,
        schema: str,
        table: str,
        rows: list[dict[str, Any]],
        row_limit: int = DEFAULT_ROW_LIMIT,
    ) -> int:
        """
        Store raw rows as an encrypted Parquet file.
        PII columns are dropped before writing.
        Returns the number of rows stored.
        """
        if not rows:
            return 0

        df = pd.DataFrame(rows[:row_limit])

        # Drop excluded columns
        excluded = [c for c in df.columns if _is_excluded(c)]
        if excluded:
            df = df.drop(columns=excluded)

        # Write to temp parquet, then encrypt in place
        path = self._path(schema, table)
        tmp = path.with_suffix(".tmp")
        df.to_parquet(tmp, index=False, engine="pyarrow", compression="snappy")

        # Encrypt and replace
        tmp.rename(path)  # move to final path first
        _encrypt_file(path)

        return len(df)

    def store_df(
        self,
        schema: str,
        table: str,
        df: "pd.DataFrame",
        row_limit: int = DEFAULT_ROW_LIMIT,
    ) -> int:
        """
        Store a DataFrame directly as an encrypted Parquet file.
        PII columns are dropped before writing.
        Returns the number of rows stored.
        """
        if df is None or len(df) == 0:
            return 0

        df = df.head(row_limit)

        # Drop excluded columns
        excluded = [c for c in df.columns if _is_excluded(c)]
        if excluded:
            df = df.drop(columns=excluded)

        # Write to temp parquet, then encrypt in place
        path = self._path(schema, table)
        tmp = path.with_suffix(".tmp")
        df.to_parquet(tmp, index=False, engine="pyarrow", compression="snappy")
        tmp.rename(path)
        _encrypt_file(path)

        return len(df)

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_slice(
        self,
        schema: str,
        table: str,
        filters: dict[str, Any] | None = None,
        columns: list[str] | None = None,
        limit: int = AGENT_SLICE_LIMIT,
    ) -> list[dict[str, Any]]:
        """
        Read a slice of cached rows. Used by agents during validation.

        Args:
            filters: simple equality filters e.g. {"status": "refunded"}
            columns: subset of columns to return
            limit: max rows (capped at AGENT_SLICE_LIMIT)
        """
        path = self._path(schema, table)
        if not path.exists():
            raise FileNotFoundError(f"No cached sample for {schema}.{table}. Run store() first.")

        # Decrypt to bytes → read parquet from buffer
        import io
        raw = _decrypt_file(path)
        df = pd.read_parquet(io.BytesIO(raw), engine="pyarrow")

        # Apply filters
        if filters:
            for col, val in filters.items():
                if col in df.columns:
                    df = df[df[col] == val]

        # Select columns
        if columns:
            existing = [c for c in columns if c in df.columns]
            df = df[existing]

        # Enforce limit
        limit = min(limit, self.AGENT_SLICE_LIMIT)
        return df.head(limit).to_dict(orient="records")

    def get_dataframe(self, schema: str, table: str) -> pd.DataFrame:
        """
        Return the full cached DataFrame for a table (up to DEFAULT_ROW_LIMIT rows).

        Unlike get_slice(), this returns a pandas DataFrame rather than
        list[dict], and does not apply the AGENT_SLICE_LIMIT cap.
        Used by the sandbox for data injection.
        """
        path = self._path(schema, table)
        if not path.exists():
            raise FileNotFoundError(
                f"No cached sample for {schema}.{table}. Run store() first."
            )
        import io
        raw = _decrypt_file(path)
        return pd.read_parquet(io.BytesIO(raw), engine="pyarrow")

    def list_cached(self) -> list[str]:
        """List all cached table references."""
        return [
            f.stem.replace(".parquet", "")
            for f in self._base.glob("*.parquet.enc")
        ]

    def clear(self) -> None:
        """Delete all cached samples (called at session end)."""
        for f in self._base.glob("*.parquet.enc"):
            f.unlink()
        # Also remove session key
        key_path = Path.home() / ".yorph" / ".session_key"
        if key_path.exists():
            key_path.unlink()
