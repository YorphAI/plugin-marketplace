"""
Base profiler — abstract class all warehouse profilers inherit from.

Handles:
  - Phase 1: Schema discovery (information_schema)
  - Phase 2: Rich data profiling (dialect-aware SQL, parallel execution)
  - 100-table context batching
  - Writing results to ~/.yorph/profiles/
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Context budget ─────────────────────────────────────────────────────────────
TABLES_PER_CONTEXT_BATCH = 100   # max tables loaded into Claude's context at once

# ── PII exclusions ─────────────────────────────────────────────────────────────
EXCLUDED_COLUMN_PATTERNS = [
    "password", "passwd", "ssn", "social_security",
    "credit_card", "card_number", "cvv", "secret",
    "private_key", "api_key", "api_secret",
    "token", "access_token", "refresh_token",
    "hash", "salt", "encrypted",
]

def is_excluded(column_name: str) -> bool:
    lower = column_name.lower()
    return any(p in lower for p in EXCLUDED_COLUMN_PATTERNS)


def _flag_skew(col_profiles: list) -> None:
    """
    Flag numeric columns with skewed distributions using Pass 1 stats.
    No extra SQL — just heuristics on existing percentile/avg/median values.
    Agents can then use @skew_analysis skill to run deeper queries on the fly.
    """
    for col in col_profiles:
        if col.median_numeric is None or col.avg_numeric is None:
            continue
        if col.median_numeric == 0 and col.avg_numeric == 0:
            continue

        skewed = False
        # Mean far from median (right-skewed revenue, amounts)
        if col.median_numeric != 0 and abs(col.avg_numeric / col.median_numeric) > 3:
            skewed = True
        # Heavy right tail
        if col.p95 is not None and col.median_numeric != 0:
            if col.p95 / col.median_numeric > 10:
                skewed = True
        # Extreme outliers beyond P95
        if col.p95 is not None and col.max_numeric is not None and col.p95 != 0:
            if col.max_numeric / col.p95 > 5:
                skewed = True

        col.skew_detected = skewed


# ── Column profile dataclass ───────────────────────────────────────────────────

@dataclass
class ColumnProfile:
    name: str
    data_type: str

    # Core stats
    total_rows: int = 0
    pct_null: float = 0.0
    approx_distinct: int = 0

    # Numeric stats
    min_numeric: float | None = None
    max_numeric: float | None = None
    avg_numeric: float | None = None
    p05: float | None = None
    p25: float | None = None
    median_numeric: float | None = None
    p75: float | None = None
    p95: float | None = None

    # String length stats
    avg_len: float | None = None
    max_len: int | None = None
    min_string: str | None = None
    max_string: str | None = None

    # Content type hints (% of non-null rows matching pattern)
    pct_numeric_like: float | None = None
    pct_integer_like: float | None = None
    pct_contains_percent: float | None = None
    pct_contains_currency_symbol: float | None = None

    # Date / timestamp format detection
    pct_date_iso_yyyy_mm_dd: float | None = None      # 2024-01-31
    pct_date_ymd_slash: float | None = None            # 2024/01/31
    pct_date_mdy_slash: float | None = None            # 01/31/2024
    pct_date_dmy_slash: float | None = None            # 31/01/2024
    pct_date_mdy_hyphen: float | None = None           # 01-31-2024
    pct_date_dmy_hyphen: float | None = None           # 31-01-2024
    pct_timestamp_iso_like: float | None = None        # 2024-01-31T00:00:00
    pct_timestamp_basic: float | None = None           # 2024-01-31 00:00:00
    pct_timestamp_mdy_12h: float | None = None         # 01/31/2024 12:00 AM
    pct_timestamp_mdy_24h: float | None = None         # 01/31/2024 00:00
    pct_timestamp_mdy_12h_hyphen: float | None = None  # 01-31-2024 12:00 AM
    pct_timestamp_mdy_24h_hyphen: float | None = None  # 01-31-2024 00:00
    pct_timestamp_dmy_12h_hyphen: float | None = None  # 31-01-2024 12:00 AM
    pct_timestamp_dmy_24h_hyphen: float | None = None  # 31-01-2024 00:00

    # Null-like string patterns (encoded nulls disguised as strings)
    pct_empty_string: float | None = None
    pct_blank: float | None = None
    pct_na: float | None = None
    pct_n_slash_a: float | None = None
    pct_null_string: float | None = None
    pct_none: float | None = None
    pct_unknown: float | None = None
    pct_missing: float | None = None
    pct_undefined: float | None = None
    pct_dash: float | None = None
    pct_dot: float | None = None
    pct_question_mark: float | None = None
    pct_hash_n_slash_a: float | None = None
    pct_hash_null_exclamation: float | None = None
    pct_hash_div_zero: float | None = None
    pct_hash_value_exclamation: float | None = None
    pct_hash_ref_exclamation: float | None = None
    pct_hash_name_question: float | None = None
    pct_hash_num_exclamation: float | None = None
    pct_no_like: float | None = None
    pct_yes_like: float | None = None

    # Sample values (for context)
    sample_values: list[Any] = field(default_factory=list)

    # Skew detection flag (computed from Pass 1 stats — no extra SQL)
    skew_detected: bool = False

    def __post_init__(self):
        """Coerce fields to their declared types regardless of data source."""
        for f in fields(self):
            val = getattr(self, f.name)
            if val is None:
                continue
            # float | None fields (all pct_* and numeric stats)
            if f.name.startswith("pct_") or f.name in (
                "min_numeric", "max_numeric", "avg_numeric",
                "p05", "p25", "median_numeric", "p75", "p95", "avg_len",
            ):
                try:
                    setattr(self, f.name, float(val))
                except (ValueError, TypeError):
                    setattr(self, f.name, None)
            # int fields
            elif f.name in ("total_rows", "approx_distinct", "max_len"):
                try:
                    setattr(self, f.name, int(val))
                except (ValueError, TypeError):
                    pass


@dataclass
class TableProfile:
    table_name: str
    schema_name: str
    warehouse_type: str
    total_rows: int
    size_bytes: int | None
    last_modified: str | None
    profiled_at: str
    columns: list[ColumnProfile]

    def to_dict(self) -> dict:
        return asdict(self)

    def to_context_summary(self) -> str:
        """
        Compact markdown table loaded into Claude's context.
        Includes all rich metadata so Claude can reason about data quality,
        type detection, null patterns, and semantic meaning.
        """
        lines = [
            f"## {self.schema_name}.{self.table_name}",
            f"Rows: {self.total_rows:,} | Profiled: {self.profiled_at[:10]}",
            "",
            "| Column | Type | Null% | ~Distinct | Sample Values |",
            "|--------|------|-------|-----------|---------------|",
        ]
        for col in self.columns:
            sample = ", ".join(str(v) for v in (col.sample_values or [])[:3])
            lines.append(
                f"| {col.name} | {col.data_type} | {col.pct_null:.1f}% "
                f"| {col.approx_distinct:,} | {sample} |"
            )

            extras = []

            # Numeric stats
            if col.min_numeric is not None:
                extras.append(
                    f"  - Numeric: min={col.min_numeric} avg={col.avg_numeric:.2f} "
                    f"max={col.max_numeric} | p05={col.p05} p25={col.p25} "
                    f"p50={col.median_numeric} p75={col.p75} p95={col.p95}"
                )
                if col.skew_detected:
                    extras.append("  - ⚠ Skewed distribution — use @skew_analysis for deeper stats")

            # String stats
            if col.avg_len is not None:
                extras.append(f"  - String: avg_len={col.avg_len:.1f} max_len={col.max_len}")

            # Content type hints
            hints = []
            if col.pct_numeric_like and col.pct_numeric_like > 5:
                hints.append(f"{col.pct_numeric_like:.0f}% numeric-like")
            if col.pct_integer_like and col.pct_integer_like > 5:
                hints.append(f"{col.pct_integer_like:.0f}% integer-like")
            if col.pct_contains_currency_symbol and col.pct_contains_currency_symbol > 5:
                hints.append(f"{col.pct_contains_currency_symbol:.0f}% has currency symbol")
            if col.pct_contains_percent and col.pct_contains_percent > 5:
                hints.append(f"{col.pct_contains_percent:.0f}% has %")
            if hints:
                extras.append(f"  - Content hints: {', '.join(hints)}")

            # Date format detection (only show dominant format)
            date_fields = {
                "ISO date (YYYY-MM-DD)": col.pct_date_iso_yyyy_mm_dd,
                "Timestamp ISO": col.pct_timestamp_iso_like,
                "Timestamp basic": col.pct_timestamp_basic,
                "MDY slash": col.pct_date_mdy_slash,
                "DMY slash": col.pct_date_dmy_slash,
                "MDY hyphen": col.pct_date_mdy_hyphen,
            }
            dominant_date = max(
                ((k, v) for k, v in date_fields.items() if v and v > 50),
                key=lambda x: x[1], default=None
            )
            if dominant_date:
                extras.append(f"  - Date format: {dominant_date[0]} ({dominant_date[1]:.0f}%)")

            # Null-like string patterns (flag any >1%)
            null_like = {
                "empty string": col.pct_empty_string,
                "blank": col.pct_blank,
                "NA/N/A": col.pct_na or col.pct_n_slash_a,
                "None/null (string)": col.pct_null_string or col.pct_none,
                "Unknown/Missing": col.pct_unknown or col.pct_missing,
                "#N/A / #NULL!": col.pct_hash_n_slash_a or col.pct_hash_null_exclamation,
                "#DIV/0!": col.pct_hash_div_zero,
                "dash/dot/?": (col.pct_dash or 0) + (col.pct_dot or 0) + (col.pct_question_mark or 0),
            }
            flagged = [(k, v) for k, v in null_like.items() if v and v > 1.0]
            if flagged:
                patterns = ", ".join(f"{k}={v:.1f}%" for k, v in flagged)
                extras.append(f"  - ⚠ Null-like strings: {patterns}")

            lines.extend(extras)

        return "\n".join(lines)


# ── Abstract base profiler ─────────────────────────────────────────────────────

class BaseProfiler(ABC):

    WAREHOUSE_TYPE: str = "base"
    SAMPLE_PCT: int = 10
    SAMPLE_VALUES_COUNT: int = 5

    def __init__(self, credentials: dict):
        self.credentials = credentials
        self.connection = None
        self._profiles_dir = Path.home() / ".yorph" / "profiles"
        self._profiles_dir.mkdir(parents=True, exist_ok=True)

    # ── Connection (implement per warehouse) ──────────────────────────────────

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def execute(self, sql: str) -> list[dict]: ...

    # ── Phase 1: Schema discovery ─────────────────────────────────────────────

    @abstractmethod
    def get_schemas_sql(self) -> str: ...

    @abstractmethod
    def get_tables_sql(self, schema: str) -> str: ...

    @abstractmethod
    def get_columns_sql(self, schema: str, table: str) -> str: ...

    # ── Sample SQL (override per warehouse for TABLESAMPLE) ──────────────────

    def fetch_sample_sql(self, schema: str, table: str, limit: int = 5000) -> str:
        """
        Return SQL to fetch a random sample of rows.
        Default uses TABLESAMPLE BERNOULLI (works for Postgres, Snowflake,
        Redshift, Supabase). Override for BigQuery/SQL Server syntax.
        """
        return f"SELECT * FROM {schema}.{table} TABLESAMPLE BERNOULLI ({self.SAMPLE_PCT}) LIMIT {limit}"

    def fetch_plain_sql(self, schema: str, table: str, limit: int = 5000) -> str:
        """Fallback: fetch rows without TABLESAMPLE (for small tables)."""
        return f"SELECT * FROM {schema}.{table} LIMIT {limit}"

    # ── DataFrame profiler (source-agnostic — replaces SQL-based stats) ────

    # Date format regex patterns (strings stored as dates)
    _DATE_PATTERNS = {
        "pct_date_iso_yyyy_mm_dd":      r"^\d{4}-\d{2}-\d{2}$",
        "pct_date_ymd_slash":           r"^\d{4}/\d{2}/\d{2}$",
        "pct_date_mdy_slash":           r"^\d{1,2}/\d{1,2}/\d{4}$",
        "pct_date_dmy_slash":           r"^\d{1,2}/\d{1,2}/\d{4}$",
        "pct_date_mdy_hyphen":          r"^\d{1,2}-\d{1,2}-\d{4}$",
        "pct_date_dmy_hyphen":          r"^\d{1,2}-\d{1,2}-\d{4}$",
        "pct_timestamp_iso_like":       r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}",
        "pct_timestamp_basic":          r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}",
        "pct_timestamp_mdy_12h":        r"^\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2} [APap][Mm]$",
        "pct_timestamp_mdy_24h":        r"^\d{1,2}/\d{1,2}/\d{4} \d{2}:\d{2}$",
        "pct_timestamp_mdy_12h_hyphen": r"^\d{1,2}-\d{1,2}-\d{4} \d{1,2}:\d{2} [APap][Mm]$",
        "pct_timestamp_mdy_24h_hyphen": r"^\d{1,2}-\d{1,2}-\d{4} \d{2}:\d{2}$",
        "pct_timestamp_dmy_12h_hyphen": r"^\d{1,2}-\d{1,2}-\d{4} \d{1,2}:\d{2} [APap][Mm]$",
        "pct_timestamp_dmy_24h_hyphen": r"^\d{1,2}-\d{1,2}-\d{4} \d{2}:\d{2}$",
    }

    # Null-like string values to detect
    _NULL_LIKE_VALUES = {
        "pct_empty_string":          {""},
        "pct_blank":                 {""},
        "pct_na":                    {"NA", "N A"},
        "pct_n_slash_a":             {"N/A"},
        "pct_null_string":           {"NULL"},
        "pct_none":                  {"NONE"},
        "pct_unknown":               {"UNKNOWN"},
        "pct_missing":               {"MISSING"},
        "pct_undefined":             {"UNDEFINED"},
        "pct_dash":                  {"-"},
        "pct_dot":                   {"."},
        "pct_question_mark":         {"?"},
        "pct_hash_n_slash_a":        {"#N/A"},
        "pct_hash_null_exclamation": {"#NULL!"},
        "pct_hash_div_zero":         {"#DIV/0!"},
        "pct_hash_value_exclamation":{"#VALUE!"},
        "pct_hash_ref_exclamation":  {"#REF!"},
        "pct_hash_name_question":    {"#NAME?"},
        "pct_hash_num_exclamation":  {"#NUM!"},
    }

    def _profile_df(
        self,
        df,
        table_name: str,
        schema_name: str,
        size_bytes: int | None,
        last_modified: str | None,
        column_metadata: dict[str, str] | None = None,
    ) -> TableProfile:
        """
        Compute per-column statistics from a pandas DataFrame.
        Source-agnostic: works identically for SQL warehouses, S3, and GCS.

        Args:
            column_metadata: maps column_name → SQL data_type string from
                information_schema. When provided, uses the SQL type string
                for ColumnProfile.data_type. When None, falls back to pandas dtype.
        """
        import pandas as pd

        col_profiles = []
        total_rows = len(df)

        for col_name in df.columns:
            if is_excluded(col_name):
                continue

            series = df[col_name]
            non_null = series.dropna()
            non_null_count = len(non_null)

            # ── Core stats ────────────────────────────────────────────
            pct_null = round(100.0 * series.isna().sum() / total_rows, 4) if total_rows > 0 else 0.0
            approx_distinct = int(series.nunique())

            # ── Numeric stats ─────────────────────────────────────────
            min_numeric = max_numeric = avg_numeric = None
            p05 = p25 = median_numeric = p75 = p95 = None

            is_bool = pd.api.types.is_bool_dtype(series)
            if pd.api.types.is_numeric_dtype(series) and not is_bool and non_null_count > 0:
                min_numeric = float(non_null.min())
                max_numeric = float(non_null.max())
                avg_numeric = round(float(non_null.mean()), 6)
                quantiles = non_null.quantile([0.05, 0.25, 0.50, 0.75, 0.95])
                p05 = float(quantiles.iloc[0])
                p25 = float(quantiles.iloc[1])
                median_numeric = float(quantiles.iloc[2])
                p75 = float(quantiles.iloc[3])
                p95 = float(quantiles.iloc[4])

            # ── Detect column type ────────────────────────────────────
            is_string = (
                pd.api.types.is_string_dtype(series)
                or series.dtype == object
            )
            is_datetime = pd.api.types.is_datetime64_any_dtype(series)

            # ── String stats ──────────────────────────────────────────
            avg_len = max_len = min_string = max_string = None
            if is_string and non_null_count > 0:
                strs = non_null.astype(str)
                lengths = strs.str.len()
                avg_len = round(float(lengths.mean()), 2)
                max_len = int(lengths.max())
                min_string = str(strs.min())
                max_string = str(strs.max())

            # ── Content type hints (string columns only) ──────────────
            pct_numeric_like = pct_integer_like = None
            pct_contains_percent = pct_contains_currency_symbol = None

            if is_string and non_null_count > 0:
                strs = non_null.astype(str)
                pct_numeric_like = round(
                    100.0 * strs.str.match(r'^-?[0-9]+\.?[0-9]*$', na=False).sum() / total_rows, 4
                )
                pct_integer_like = round(
                    100.0 * strs.str.match(r'^-?[0-9]+$', na=False).sum() / total_rows, 4
                )
                pct_contains_currency_symbol = round(
                    100.0 * strs.str.contains('[$€£¥]', regex=True, na=False).sum() / total_rows, 4
                )
                pct_contains_percent = round(
                    100.0 * strs.str.contains('%', na=False).sum() / total_rows, 4
                )

            # ── Date format detection (string columns only) ───────────
            date_stats: dict[str, float | None] = {}
            if is_string and non_null_count > 0:
                strs = non_null.astype(str)
                for field_name, pattern in self._DATE_PATTERNS.items():
                    matched = strs.str.match(pattern, na=False).sum()
                    date_stats[field_name] = round(100.0 * matched / total_rows, 4)
            else:
                for field_name in self._DATE_PATTERNS:
                    date_stats[field_name] = None

            # ── Null-like string detection ────────────────────────────
            null_like_stats: dict[str, float | None] = {}
            if is_string and non_null_count > 0:
                strs = non_null.astype(str)
                # Pre-compute trimmed + uppercased once for efficiency
                trimmed_upper = strs.str.strip().str.upper()
                trimmed = strs.str.strip()
                for field_name, match_set in self._NULL_LIKE_VALUES.items():
                    # Some patterns compare raw trimmed (dash, dot, empty),
                    # most compare uppercased
                    if match_set == {""}:
                        matched = (trimmed == "").sum()
                    elif all(v == v.upper() and v.isascii() for v in match_set):
                        matched = trimmed_upper.isin(match_set).sum()
                    else:
                        matched = trimmed.isin(match_set).sum()
                    null_like_stats[field_name] = round(100.0 * matched / total_rows, 4)
            else:
                for field_name in self._NULL_LIKE_VALUES:
                    null_like_stats[field_name] = None

            # ── Boolean-like detection ────────────────────────────────
            pct_no_like = pct_yes_like = None
            if is_string and non_null_count > 0:
                trimmed_upper = non_null.astype(str).str.strip().str.upper()
                pct_no_like = round(
                    100.0 * trimmed_upper.isin({"NO", "N", "FALSE", "F", "0"}).sum() / total_rows, 4
                )
                pct_yes_like = round(
                    100.0 * trimmed_upper.isin({"YES", "Y", "TRUE", "T", "1"}).sum() / total_rows, 4
                )

            # ── Sample values ─────────────────────────────────────────
            if is_string:
                sample_values = [str(v) for v in non_null.unique()[:5]]
            elif is_datetime and non_null_count > 0:
                sample_values = [str(non_null.min()), str(non_null.max())]
            elif pd.api.types.is_numeric_dtype(series) and min_numeric is not None:
                sample_values = [str(min_numeric), str(max_numeric)]
            else:
                sample_values = [str(v) for v in non_null.unique()[:5]]

            # ── Data type: prefer SQL type from info_schema if available
            data_type = (column_metadata or {}).get(col_name, str(series.dtype))

            # ── Build ColumnProfile ───────────────────────────────────
            col_profiles.append(ColumnProfile(
                name=col_name,
                data_type=data_type,
                total_rows=total_rows,
                pct_null=pct_null,
                approx_distinct=approx_distinct,
                min_numeric=min_numeric,
                max_numeric=max_numeric,
                avg_numeric=avg_numeric,
                p05=p05, p25=p25,
                median_numeric=median_numeric,
                p75=p75, p95=p95,
                avg_len=avg_len,
                max_len=max_len,
                min_string=min_string,
                max_string=max_string,
                pct_numeric_like=pct_numeric_like,
                pct_integer_like=pct_integer_like,
                pct_contains_percent=pct_contains_percent,
                pct_contains_currency_symbol=pct_contains_currency_symbol,
                pct_no_like=pct_no_like,
                pct_yes_like=pct_yes_like,
                sample_values=sample_values,
                **date_stats,
                **null_like_stats,
            ))

        _flag_skew(col_profiles)

        return TableProfile(
            table_name=table_name,
            schema_name=schema_name,
            warehouse_type=self.WAREHOUSE_TYPE,
            total_rows=total_rows,
            size_bytes=size_bytes,
            last_modified=last_modified,
            profiled_at=datetime.utcnow().isoformat(),
            columns=col_profiles,
        )

    # ── Async profiling ────────────────────────────────────────────────────────

    async def profile_table_async(
        self, schema: str, table: str, columns: list[dict], table_meta: dict,
        sample_limit: int = 5000,
    ) -> tuple:
        """
        Fetch sample rows, profile with pandas, return (TableProfile, DataFrame).
        Single query per table — no dialect-specific stats SQL.
        """
        import pandas as pd

        loop = asyncio.get_event_loop()
        total_rows = table_meta.get("row_count") or table_meta.get("total_rows") or 0

        # Fetch sample rows
        sample_sql = self.fetch_sample_sql(schema, table, limit=sample_limit)
        try:
            raw_rows = await loop.run_in_executor(None, self.execute, sample_sql)
        except Exception as e:
            logger.error("Error fetching sample from %s.%s: %s", schema, table, e)
            raw_rows = []

        # TABLESAMPLE can return 0 rows on small tables — retry without it
        if not raw_rows and total_rows and int(total_rows) > 0:
            try:
                fallback_sql = self.fetch_plain_sql(schema, table, limit=sample_limit)
                raw_rows = await loop.run_in_executor(None, self.execute, fallback_sql)
            except Exception:
                raw_rows = []

        # Convert to DataFrame
        if raw_rows:
            df = pd.DataFrame(raw_rows)
        else:
            df = pd.DataFrame(columns=[c["column_name"] for c in columns])

        # Build column metadata map (SQL type strings from information_schema)
        column_metadata = {c["column_name"]: c["data_type"] for c in columns}

        # Profile using pandas
        profile = self._profile_df(
            df,
            table_name=table,
            schema_name=schema,
            size_bytes=table_meta.get("size_bytes"),
            last_modified=str(table_meta.get("last_modified")) if table_meta.get("last_modified") else None,
            column_metadata=column_metadata,
        )

        # Override total_rows from table_meta (sample only has ≤sample_limit rows)
        if total_rows and int(total_rows) > 0:
            profile.total_rows = int(total_rows)
            for col in profile.columns:
                col.total_rows = int(total_rows)

        return profile, df

    async def profile_all(
        self, schemas: list[str] | None = None, sample_limit: int = 5000,
    ) -> list[tuple]:
        """
        Phase 1 (schema discovery) + Phase 2 (pandas profiling), fully parallel.
        Returns list of (TableProfile, DataFrame) tuples AND writes profiles to disk.

        Errors encountered during profiling are collected in self._profiling_errors
        so callers (e.g. run_profiler in tools.py) can surface them.
        """
        loop = asyncio.get_event_loop()
        self._profiling_errors: list[str] = []

        # ── Phase 1: Schema & table discovery ────────────────────────────────
        # Call self.execute() directly (not via run_in_executor).
        # For MCP-backed profilers, execute() uses run_coroutine_threadsafe to
        # schedule on the MCP client's background loop — this blocks the current
        # thread but does NOT deadlock because the two event loops are independent.
        # Direct calls are proven reliable for all transports (stdio, streamable_http).
        # run_in_executor is only used in Phase 2 (per-table profiling) where we
        # need parallelism via asyncio.gather.

        if schemas is None:
            schema_rows = self.execute(self.get_schemas_sql())
            schemas = [r["schema_name"] for r in schema_rows]
            if not schemas:
                logger.warning(
                    "No schemas discovered. "
                    "Make sure your database credentials are correct, "
                    "or pass 'schemas' explicitly to run_profiler."
                )
                return []

        profiler_type = type(self).__name__
        logger.info("Using %s, schemas=%s", profiler_type, schemas)

        tasks = []
        for schema in schemas:
            sql = self.get_tables_sql(schema)
            logger.info("Discovering tables in '%s' — SQL:\n%s", schema, sql[:500])
            try:
                table_rows = self.execute(sql)
            except Exception as e:
                err_msg = f"ERROR discovering tables in '{schema}': {type(e).__name__}: {e}"
                logger.error(err_msg)
                self._profiling_errors.append(err_msg)
                table_rows = []
            logger.info(
                "execute() returned %d rows for '%s', type=%s",
                len(table_rows), schema, type(table_rows).__name__,
            )
            if table_rows:
                first = table_rows[0]
                logger.info(
                    "First row keys: %s, values: %s",
                    list(first.keys()) if isinstance(first, dict) else type(first),
                    {k: v for k, v in first.items()} if isinstance(first, dict) else first,
                )
            else:
                # Log the raw return for debugging empty results
                logger.warning(
                    "Table discovery returned empty for '%s'. table_rows=%r",
                    schema, table_rows[:3] if table_rows else table_rows,
                )
            for t in table_rows:
                if not isinstance(t, dict) or "table_name" not in t:
                    err_msg = f"Skipping non-dict or missing table_name: {t}"
                    logger.warning(err_msg)
                    self._profiling_errors.append(err_msg)
                    continue
                table = t["table_name"]
                try:
                    col_rows = self.execute(self.get_columns_sql(schema, table))
                except Exception as e:
                    err_msg = f"ERROR getting columns for {schema}.{table}: {type(e).__name__}: {e}"
                    logger.error(err_msg)
                    self._profiling_errors.append(err_msg)
                    continue
                logger.info("%s.%s: %d columns", schema, table, len(col_rows))
                tasks.append(
                    self.profile_table_async(schema, table, col_rows, t, sample_limit)
                )

        # ── Phase 2: Per-table profiling (parallel) ──────────────────────────
        logger.info("Created %d profiling tasks", len(tasks))

        semaphore = asyncio.Semaphore(10)

        async def bounded(coro):
            async with semaphore:
                return await coro

        results_raw = await asyncio.gather(
            *[bounded(t) for t in tasks], return_exceptions=True
        )

        results = []
        profiles_only = []
        for r in results_raw:
            if isinstance(r, Exception):
                err_msg = f"Profiling task FAILED: {type(r).__name__}: {r}"
                logger.error(err_msg)
                self._profiling_errors.append(err_msg)
            else:
                results.append(r)
                profiles_only.append(r[0])

        logger.info(
            "Completed: %d succeeded, %d failed",
            len(results), len(results_raw) - len(results),
        )

        self._save_profiles(profiles_only)
        return results

    # ── Context batching (100 tables per batch) ───────────────────────────────

    def context_batches(self) -> list[list[TableProfile]]:
        """
        Returns profiles in batches of TABLES_PER_CONTEXT_BATCH (100).
        Each batch fits comfortably in Claude's context window.
        """
        profiles = self.load_profiles()
        return [
            profiles[i: i + TABLES_PER_CONTEXT_BATCH]
            for i in range(0, len(profiles), TABLES_PER_CONTEXT_BATCH)
        ]

    def context_summary(self, batch_index: int = 0) -> str:
        """
        Returns compact profile text for one batch of 100 tables.
        Call with increasing batch_index to page through all tables.
        """
        batches = self.context_batches()
        if not batches:
            return "No profiles found. Run run_profiler first."

        batch = batches[batch_index] if batch_index < len(batches) else []
        total_batches = len(batches)
        header = (
            f"# Schema Profiles — Batch {batch_index + 1} of {total_batches} "
            f"({len(batch)} tables)\n\n"
        )
        if total_batches > 1:
            header += (
                f"> ℹ️ This warehouse has {sum(len(b) for b in batches)} tables total. "
                f"Call get_context_summary(batch_index={batch_index + 1}) to see next batch.\n\n"
            )
        return header + "\n\n".join(p.to_context_summary() for p in batch)

    # ── Disk I/O ──────────────────────────────────────────────────────────────

    def _save_profiles(self, profiles: list[TableProfile]) -> None:
        wh_dir = self._profiles_dir / self.WAREHOUSE_TYPE
        wh_dir.mkdir(parents=True, exist_ok=True)
        for p in profiles:
            fname = wh_dir / f"{p.schema_name}.{p.table_name}.json"
            with open(fname, "w") as f:
                json.dump(p.to_dict(), f, indent=2, default=str)

    def load_profiles(self) -> list[TableProfile]:
        wh_dir = self._profiles_dir / self.WAREHOUSE_TYPE
        if not wh_dir.exists():
            return []
        profiles = []
        for f in sorted(wh_dir.glob("*.json")):
            with open(f) as fh:
                data = json.load(fh)
                cols = [ColumnProfile(**c) for c in data.pop("columns")]
                profiles.append(TableProfile(**data, columns=cols))
        return profiles
