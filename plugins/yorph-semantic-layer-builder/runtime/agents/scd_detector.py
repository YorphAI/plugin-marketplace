"""
SCD / Temporal Pattern Detector — identifies slowly-changing dimensions.

Tier 0 agent — runs early so SCD warnings feed Join Validator.

Scans for SCD patterns:
  - valid_from/valid_to column pairs
  - effective_date / is_current columns
  - _version / _seq suffixes
  - start_date/end_date pairs
  - Multiple rows per entity key with validity period columns

Output: scd_tables[] — {table, scd_type, validity_columns[], safe_join_pattern, warning}
"""

from __future__ import annotations

import re
from typing import Any

from runtime.agents.base import BaseAgent, AgentContext, AgentOutput


# Column name patterns that indicate SCD type-2
_VALIDITY_PATTERNS = [
    (r"valid_from|effective_from|start_date|eff_date|begin_date", "start"),
    (r"valid_to|effective_to|end_date|expiry_date|expire_date", "end"),
    (r"is_current|is_active|current_flag|active_flag", "current_flag"),
    (r"_version$|_ver$|_seq$|_revision$", "version"),
    (r"effective_date|eff_date", "effective"),
    (r"dw_created|dw_updated|etl_loaded|loaded_at", "etl_metadata"),
]


class SCDDetector(BaseAgent):
    """Scans table profiles for slowly-changing dimension patterns."""

    name = "scd_detector"
    requires = ["profiles"]
    produces = ["scd_tables"]

    async def run(self, ctx: AgentContext) -> AgentOutput:
        profiles = ctx.profiles
        scd_tables: list[dict[str, Any]] = []
        issues = []

        tables = profiles.get("tables", {})
        for table_name, table_profile in tables.items():
            result = _detect_scd(table_name, table_profile)
            if result:
                scd_tables.append(result)

                # Always surface a warning for type-2 SCDs
                if result["scd_type"] == 2:
                    issues.append(self._issue(
                        severity="warning",
                        category="scd",
                        title=f"Type-2 SCD detected: {table_name}",
                        description=(
                            f"Table '{table_name}' appears to be a Type-2 slowly-changing "
                            f"dimension with validity columns: {result['validity_columns']}. "
                            f"If joined without filtering on {result.get('safe_join_pattern', 'is_current')}, "
                            f"historical rows will inflate metrics."
                        ),
                        evidence={"validity_columns": result["validity_columns"]},
                        options=[
                            f"Apply filter: {result.get('safe_join_pattern', 'WHERE is_current = TRUE')}",
                            "Keep all historical rows (I need point-in-time analysis)",
                            "This table is not an SCD — ignore",
                        ],
                        recommendation=result.get("safe_join_pattern", "Filter on is_current = TRUE"),
                    ))

        return self._make_output(
            data={"scd_tables": scd_tables},
            issues=issues,
        )


def _detect_scd(table_name: str, profile: dict) -> dict[str, Any] | None:
    """Check if a table has SCD patterns."""
    columns = profile.get("columns", [])
    col_names = [c.get("column_name", c.get("name", "")).lower() for c in columns]

    found: dict[str, list[str]] = {"start": [], "end": [], "current_flag": [], "version": [], "effective": [], "etl_metadata": []}

    for col_name in col_names:
        for pattern, category in _VALIDITY_PATTERNS:
            if re.search(pattern, col_name, re.IGNORECASE):
                found[category].append(col_name)

    # Type-2 SCD: has start+end date pair OR current flag
    has_validity_pair = bool(found["start"] and found["end"])
    has_current_flag = bool(found["current_flag"])
    has_version = bool(found["version"])

    if not (has_validity_pair or has_current_flag or has_version):
        return None

    # Determine SCD type
    if has_validity_pair or has_current_flag:
        scd_type = 2
    elif has_version:
        scd_type = 2  # versioned rows are type-2
    else:
        scd_type = 1  # only ETL metadata, likely type-1

    # Build validity columns list
    validity_cols = []
    for cat in ("start", "end", "current_flag", "version"):
        validity_cols.extend(found[cat])

    # Determine safe join pattern
    if has_current_flag:
        flag_col = found["current_flag"][0]
        safe_pattern = f"WHERE {flag_col} = TRUE"
    elif has_validity_pair:
        start_col = found["start"][0]
        end_col = found["end"][0]
        safe_pattern = f"WHERE CURRENT_DATE BETWEEN {start_col} AND COALESCE({end_col}, '9999-12-31')"
    elif has_version:
        ver_col = found["version"][0]
        safe_pattern = f"WHERE {ver_col} = (SELECT MAX({ver_col}) FROM {table_name})"
    else:
        safe_pattern = "Filter to current records only"

    return {
        "table": table_name,
        "scd_type": scd_type,
        "validity_columns": validity_cols,
        "safe_join_pattern": safe_pattern,
        "warning": (
            f"Type-{scd_type} SCD detected. Joining without temporal filter will "
            f"include historical rows and inflate metrics."
            if scd_type == 2 else
            f"Type-{scd_type} SCD — overwrites in place, no historical rows."
        ),
    }
