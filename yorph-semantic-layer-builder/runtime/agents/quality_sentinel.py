"""
Quality Sentinel — Data quality checks agent.

Tier 0 agent — runs early so quality flags feed downstream agents.

Scans all profiled tables and columns for quality issues:
  - >30% null rate on columns referenced as measures or join keys
  - Constant columns (all same value — likely broken ETL)
  - Stale date columns (MAX > 90 days ago)
  - Negative values on measure columns (check if refunds/credits)

Output: quality_flags[] — {table, column, issue, severity, recommendation}
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from runtime.agents.base import BaseAgent, AgentContext, AgentOutput


class QualitySentinel(BaseAgent):
    """Scans profiles for data quality issues that affect semantic layer accuracy."""

    name = "quality_sentinel"
    requires = ["profiles"]
    produces = ["quality_flags"]

    async def run(self, ctx: AgentContext) -> AgentOutput:
        profiles = ctx.profiles
        quality_flags: list[dict[str, Any]] = []

        tables = profiles.get("tables", {})
        for table_name, table_profile in tables.items():
            columns = table_profile.get("columns", [])
            for col in columns:
                col_name = col.get("column_name", col.get("name", ""))
                flags = _check_column_quality(table_name, col_name, col)
                quality_flags.extend(flags)

            # Check table-level staleness
            table_flags = _check_table_staleness(table_name, table_profile)
            quality_flags.extend(table_flags)

        return self._make_output(data={"quality_flags": quality_flags})


def _check_column_quality(table: str, column: str, profile: dict) -> list[dict]:
    """Check a single column for quality issues."""
    flags = []
    null_pct = profile.get("null_pct", 0.0) or 0.0
    distinct = profile.get("distinct_count", None)
    min_val = profile.get("min")
    dtype = profile.get("data_type", "").lower()

    # High null rate
    if null_pct > 0.30:
        severity = "critical" if null_pct > 0.50 else "warning"
        flags.append({
            "table": table,
            "column": column,
            "issue": f"High null rate ({null_pct:.0%})",
            "severity": severity,
            "recommendation": f"Verify this column is populated correctly. "
                              f"If used as a measure or join key, results will be incomplete.",
        })

    # Constant column
    if distinct is not None and distinct <= 1:
        flags.append({
            "table": table,
            "column": column,
            "issue": f"Constant column ({distinct} distinct value(s))",
            "severity": "warning",
            "recommendation": "This column has no variation — likely a filtering artifact or "
                              "broken ETL. Exclude from the semantic layer.",
        })

    # Negative values on numeric columns (potential measure issue)
    if dtype in ("number", "numeric", "float", "double", "decimal", "int", "integer", "bigint"):
        if min_val is not None:
            try:
                if float(min_val) < 0:
                    flags.append({
                        "table": table,
                        "column": column,
                        "issue": f"Negative values present (min: {min_val})",
                        "severity": "warning",
                        "recommendation": "If this is a revenue or amount column, negative values "
                                          "may indicate refunds/credits. Confirm whether the measure "
                                          "should be net-of-returns.",
                    })
            except (ValueError, TypeError):
                pass

    return flags


def _check_table_staleness(table: str, profile: dict) -> list[dict]:
    """Check if date columns in a table are stale."""
    flags = []
    columns = profile.get("columns", [])
    cutoff = datetime.utcnow() - timedelta(days=90)

    for col in columns:
        dtype = col.get("data_type", "").lower()
        if dtype not in ("date", "timestamp", "datetime", "timestamptz"):
            continue
        max_val = col.get("max")
        if max_val is None:
            continue
        try:
            if isinstance(max_val, str):
                # Try common date formats
                for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                    try:
                        max_date = datetime.strptime(max_val[:19], fmt)
                        break
                    except ValueError:
                        continue
                else:
                    continue
            elif isinstance(max_val, datetime):
                max_date = max_val
            else:
                continue

            if max_date < cutoff:
                days_stale = (datetime.utcnow() - max_date).days
                col_name = col.get("column_name", col.get("name", ""))
                flags.append({
                    "table": table,
                    "column": col_name,
                    "issue": f"Stale data — last value is {max_val} ({days_stale} days ago)",
                    "severity": "warning",
                    "recommendation": "This table may contain outdated data. Verify ETL pipeline "
                                      "is running. Semantic layer queries against this table may "
                                      "return misleading results.",
                })
        except (ValueError, TypeError):
            pass

    return flags
