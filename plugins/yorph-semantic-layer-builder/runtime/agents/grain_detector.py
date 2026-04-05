"""
Grain Detector agent — defines grain at three levels.

Tier 1 agent — receives domain_context, quality_flags from Tier 0.

Runs three personas:
  - GD-1 (Purist): Atomic grain only — one row per source event
  - GD-2 (Pragmatist): Reporting grain — pre-aggregated for dashboards
  - GD-3 (Architect): Hybrid — atomic fact + pre-aggregated reporting mart

Outputs: grain_gd1[], grain_gd2[], grain_gd3[], grain_conflicts[]
"""

from __future__ import annotations

from typing import Any

from runtime.agents.base import BaseAgent, AgentContext, AgentOutput


class GrainDetector(BaseAgent):
    """Defines table grain at three levels of abstraction."""

    name = "grain_detector"
    requires = ["profiles", "domain_context", "quality_flags"]
    produces = ["grain_gd1", "grain_gd2", "grain_gd3", "grain_conflicts"]

    async def run(self, ctx: AgentContext) -> AgentOutput:
        profiles = ctx.profiles
        domain_context = ctx.upstream_outputs.get("domain_context", {})
        quality_flags = ctx.upstream_outputs.get("quality_flags", [])

        gd1 = []  # Atomic
        gd2 = []  # Reporting
        gd3 = []  # Hybrid
        grain_conflicts = []
        questions = []

        tables = profiles.get("tables", {})
        for table_name, table_profile in tables.items():
            table_domain = domain_context.get(table_name, {})
            entity_type = table_domain.get("likely_entity_type", "dimension")

            # Only define grain for fact tables (dimensions have implicit 1:1 grain)
            if entity_type != "fact":
                continue

            # GD-1: Find atomic grain
            grain_cols = _find_grain_columns(table_name, table_profile)
            row_count = table_profile.get("row_count", 0)

            gd1_entry = {
                "table": table_name,
                "grain": grain_cols,
                "grain_description": f"One row per {' + '.join(grain_cols)}" if grain_cols else "Unknown",
                "uniqueness_validated": len(grain_cols) > 0,
                "safe_dimensions": _find_safe_dimensions(table_profile, domain_context),
                "row_count": row_count,
            }
            gd1.append(gd1_entry)

            # GD-2: Reporting grain (if table is large enough to warrant rollup)
            if row_count and row_count > 1_000_000:
                time_cols = _find_time_columns(table_profile)
                dim_cols = _find_grouping_dimensions(table_profile, domain_context)
                if time_cols:
                    gd2_entry = {
                        "table": table_name,
                        "reporting_grain": [time_cols[0]] + dim_cols[:2],
                        "grain_description": f"Daily by {', '.join(dim_cols[:2])}" if dim_cols else "Daily",
                        "rollup_from": table_name,
                        "rollup_justified": True,
                        "justification": f"Table has {row_count:,} rows — pre-aggregation improves query performance",
                        "drill_down_table": table_name,
                    }
                    gd2.append(gd2_entry)

                    # GD-3: Both atomic + reporting
                    gd3_entry = {
                        "atomic_layer": gd1_entry,
                        "summary_layer": {
                            "table": f"daily_{table_name}_summary",
                            "grain": gd2_entry["reporting_grain"],
                            "source": table_name,
                            "materialisation": "dbt incremental / Dynamic Table",
                            "refresh": "daily",
                            "role": "reporting_performance",
                        },
                        "conformed_dimensions": _find_safe_dimensions(table_profile, domain_context),
                    }
                    gd3.append(gd3_entry)

                    # Record conflict
                    grain_conflicts.append({
                        "table": table_name,
                        "gd1": f"Atomic: {gd1_entry['grain_description']}",
                        "gd3_adds": f"Pre-aggregated: {gd2_entry['grain_description']}",
                        "reason": f"Table has {row_count:,} rows — reporting mart improves dashboard performance",
                    })

            # Generate assumption questions for ambiguous grains
            if not grain_cols:
                questions.append(self._question(
                    question=f"What does one row represent in '{table_name}'?",
                    why=f"I couldn't determine the atomic grain automatically. "
                        f"The table has {row_count:,} rows but no obvious unique key.",
                    options=[
                        f"One row per transaction/event",
                        f"One row per entity (e.g. customer, product)",
                        f"Pre-aggregated (daily/weekly summary)",
                        f"Other — I'll describe it",
                    ],
                ))

        return self._make_output(
            data={
                "grain_gd1": gd1,
                "grain_gd2": gd2,
                "grain_gd3": gd3,
                "grain_conflicts": grain_conflicts,
            },
            questions=questions,
        )


def _find_grain_columns(table_name: str, profile: dict) -> list[str]:
    """Find columns that likely form the grain (unique key) of a table."""
    columns = profile.get("columns", [])
    candidates = []

    for col in columns:
        col_name = col.get("column_name", col.get("name", "")).lower()
        distinct = col.get("distinct_count")
        row_count = profile.get("row_count", 0)

        # Primary key patterns
        if col_name in ("id", "pk") or col_name == f"{table_name}_id":
            candidates.append((col_name, 1.0))  # highest priority
        elif col_name.endswith("_id") or col_name.endswith("_key"):
            # Check if this column is near-unique (might be part of grain)
            if distinct and row_count and distinct / row_count > 0.9:
                candidates.append((col_name, distinct / row_count))

    if not candidates:
        return []

    # Sort by uniqueness ratio descending
    candidates.sort(key=lambda x: x[1], reverse=True)

    # If top candidate is near-unique alone, use it
    if candidates[0][1] > 0.95:
        return [candidates[0][0]]

    # Otherwise return top 2 as composite grain
    return [c[0] for c in candidates[:2]]


def _find_time_columns(profile: dict) -> list[str]:
    """Find date/timestamp columns suitable for time-based grain."""
    time_cols = []
    for col in profile.get("columns", []):
        dtype = col.get("data_type", "").lower()
        col_name = col.get("column_name", col.get("name", "")).lower()
        if dtype in ("date", "timestamp", "datetime", "timestamptz"):
            time_cols.append(col_name)
        elif any(kw in col_name for kw in ("_date", "_at", "_time", "created", "updated")):
            time_cols.append(col_name)
    return time_cols


def _find_safe_dimensions(profile: dict, domain_context: dict) -> list[str]:
    """Find dimension tables that can safely join to this fact table."""
    dims = []
    for col in profile.get("columns", []):
        col_name = col.get("column_name", col.get("name", "")).lower()
        if col_name.endswith(("_id", "_key", "_fk")):
            # Derive dimension table name from FK column
            dim_name = col_name.replace("_id", "").replace("_key", "").replace("_fk", "")
            if dim_name and dim_name + "s" not in dims and dim_name not in dims:
                dims.append(dim_name)
    return dims


def _find_grouping_dimensions(profile: dict, domain_context: dict) -> list[str]:
    """Find categorical columns suitable for reporting grain grouping."""
    dims = []
    for col in profile.get("columns", []):
        dtype = col.get("data_type", "").lower()
        distinct = col.get("distinct_count")
        col_name = col.get("column_name", col.get("name", "")).lower()

        if dtype in ("varchar", "text", "string", "char"):
            if distinct and 2 <= distinct <= 100:
                dims.append(col_name)
    return dims[:3]  # Cap at 3 grouping dimensions for reporting grain
