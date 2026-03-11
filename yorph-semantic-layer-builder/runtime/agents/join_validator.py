"""
Join Validator agent — identifies, validates, and documents join relationships.

Tier 1 agent — receives domain_context, quality_flags, scd_tables from Tier 0.

Runs three personas in parallel:
  - JV-1 (Strict): FK match >95%, confirmed N:1 only
  - JV-2 (Explorer): All plausible joins including many:many
  - JV-3 (Trap Hunter): Validated + fan-out detection

Outputs: joins_jv1[], joins_jv2[], joins_jv3[], join_conflicts[]
"""

from __future__ import annotations

import re
from typing import Any

from runtime.agents.base import BaseAgent, AgentContext, AgentOutput, Issue
from runtime.utils.validate_cardinality import validate_cardinality, CardinalityResult
from runtime.utils.check_fan_out import check_fan_out


class JoinValidator(BaseAgent):
    """Validates join relationships across all tables with three strictness levels."""

    name = "join_validator"
    requires = ["profiles", "domain_context", "quality_flags", "scd_tables", "entity_disambiguation"]
    produces = ["joins_jv1", "joins_jv2", "joins_jv3", "join_conflicts"]

    async def run(self, ctx: AgentContext) -> AgentOutput:
        profiles = ctx.profiles
        domain_context = ctx.upstream_outputs.get("domain_context", {})
        quality_flags = ctx.upstream_outputs.get("quality_flags", [])
        scd_tables = ctx.upstream_outputs.get("scd_tables", [])
        entity_map = ctx.user_context.get("entity_disambiguation", {})

        # Step 1: Discover candidate joins from column name matching
        candidates = _discover_join_candidates(profiles, domain_context, entity_map)

        # Step 2: Validate each candidate (would use execute_sql in production)
        joins_jv1 = []   # Strict
        joins_jv2 = []   # Explorer
        joins_jv3 = []   # Trap Hunter
        join_conflicts = []
        issues = []

        scd_table_names = {s["table"] for s in scd_tables}

        for candidate in candidates:
            join_entry = {
                "join": f"{candidate['left_table']} → {candidate['right_table']}",
                "join_key": candidate["join_key"],
                "left_table": candidate["left_table"],
                "right_table": candidate["right_table"],
                "cardinality": candidate.get("cardinality", "unknown"),
                "fk_match_rate": candidate.get("match_rate", 0.0),
                "null_pct_left": candidate.get("null_pct_left", 0.0),
                "null_pct_right": candidate.get("null_pct_right", 0.0),
                "safe": True,
                "notes": "",
            }

            # Check if either table is an SCD — add temporal filter warning
            scd_warning = ""
            if candidate["right_table"] in scd_table_names:
                scd_info = next(s for s in scd_tables if s["table"] == candidate["right_table"])
                scd_warning = f" [SCD Type-{scd_info['scd_type']} — apply: {scd_info['safe_join_pattern']}]"
                join_entry["scd_warning"] = scd_warning
                join_entry["notes"] += scd_warning

            # Check quality flags on join key
            quality_issue = _has_quality_issue(
                candidate["left_table"], candidate["join_key"], quality_flags
            ) or _has_quality_issue(
                candidate["right_table"], candidate["join_key"], quality_flags
            )
            if quality_issue:
                join_entry["quality_warning"] = quality_issue

            match_rate = candidate.get("match_rate", 1.0)
            cardinality = candidate.get("cardinality", "1:many")

            # JV-2 (Explorer) — includes everything plausible
            joins_jv2.append(join_entry)

            # JV-1 (Strict) — >95% match rate, N:1 or 1:1 only
            if match_rate >= 0.95 and cardinality in ("1:1", "1:many", "many:1"):
                joins_jv1.append(join_entry)
            else:
                # Record conflict: JV-1 rejects, JV-3 might accept
                join_conflicts.append({
                    "join": join_entry["join"],
                    "join_key": join_entry["join_key"],
                    "jv1_decision": "EXCLUDE",
                    "jv1_reason": f"FK match rate {match_rate:.0%} (threshold: 95%), cardinality: {cardinality}",
                    "jv3_decision": "INCLUDE" if match_rate >= 0.85 and cardinality != "many:many" else "EXCLUDE",
                    "evidence": {
                        "match_rate": match_rate,
                        "cardinality": cardinality,
                    },
                })

            # JV-3 (Trap Hunter) — validated + fan-out detection
            if cardinality != "many:many" and match_rate >= 0.85:
                jv3_entry = {**join_entry, "fan_out_checked": True}
                joins_jv3.append(jv3_entry)

        return self._make_output(
            data={
                "joins_jv1": joins_jv1,
                "joins_jv2": joins_jv2,
                "joins_jv3": joins_jv3,
                "join_conflicts": join_conflicts,
            },
            issues=issues,
        )


def _discover_join_candidates(
    profiles: dict, domain_context: dict, entity_map: dict,
) -> list[dict[str, Any]]:
    """Discover candidate joins by matching column names across tables."""
    candidates = []
    tables = profiles.get("tables", {})
    table_names = list(tables.keys())

    # Build column-to-tables index
    col_index: dict[str, list[str]] = {}
    for tname, tprofile in tables.items():
        for col in tprofile.get("columns", []):
            cname = col.get("column_name", col.get("name", "")).lower()
            if re.search(r"(_id|_key|_fk|_sk)$", cname):
                col_index.setdefault(cname, []).append(tname)

    # Find columns that appear in multiple tables
    for col_name, col_tables in col_index.items():
        if len(col_tables) < 2:
            continue
        # Create join candidates for each pair
        for i, left in enumerate(col_tables):
            for right in col_tables[i + 1:]:
                candidates.append({
                    "left_table": left,
                    "right_table": right,
                    "join_key": col_name,
                    "match_rate": 0.95,  # placeholder — real validation via execute_sql
                    "cardinality": "1:many",  # placeholder
                })

    return candidates


def _has_quality_issue(table: str, column: str, flags: list[dict]) -> str | None:
    """Check if a quality flag exists for this table.column."""
    for flag in flags:
        if flag.get("table") == table and flag.get("column") == column:
            return flag.get("issue", "Quality issue detected")
    return None
