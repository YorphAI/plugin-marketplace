"""
Measures Builder agent — defines metrics at three levels of comprehensiveness.

Tier 1 agent — receives candidate_measures, quality_flags, domain_context from Tier 0.

Runs three personas:
  - MB-1 (Minimalist): 5-15 core KPIs with obvious business meaning
  - MB-2 (Analyst): All derivable metrics including ratios and growth
  - MB-3 (Strategist): Core KPIs + most valuable derived metrics, grouped by domain

Outputs: measures_mb1[], measures_mb2[], measures_mb3[], measure_conflicts[]
"""

from __future__ import annotations

from typing import Any

from runtime.agents.base import BaseAgent, AgentContext, AgentOutput


class MeasuresBuilder(BaseAgent):
    """Builds measure definitions at three levels of comprehensiveness."""

    name = "measures_builder"
    requires = ["profiles", "domain_context", "candidate_measures", "quality_flags", "joins_jv3"]
    produces = ["measures_mb1", "measures_mb2", "measures_mb3", "measure_conflicts"]

    async def run(self, ctx: AgentContext) -> AgentOutput:
        candidates = ctx.upstream_outputs.get("candidate_measures", [])
        quality_flags = ctx.upstream_outputs.get("quality_flags", [])
        domain_context = ctx.upstream_outputs.get("domain_context", {})
        joins = ctx.upstream_outputs.get("joins_jv3", [])

        # Separate by confidence
        verified = [c for c in candidates if c.get("confidence") == "VERIFIED"]
        high = [c for c in candidates if c.get("confidence") == "HIGH"]
        medium = [c for c in candidates if c.get("confidence") == "MEDIUM"]
        low = [c for c in candidates if c.get("confidence") == "LOW"]

        # Annotate candidates with quality flags
        flagged_cols = {(f["table"], f["column"]) for f in quality_flags}

        # MB-1: Verified + High confidence only, 5-15 measures
        mb1 = []
        for c in verified + high:
            measure = _candidate_to_measure(c, domain_context, flagged_cols)
            if measure:
                mb1.append(measure)
        if len(mb1) > 15:
            mb1 = mb1[:15]  # Cap at 15 core KPIs

        # MB-2: Everything derivable
        mb2 = list(mb1)  # Start from MB-1
        for c in medium + low:
            measure = _candidate_to_measure(c, domain_context, flagged_cols)
            if measure:
                mb2.append(measure)
        # Add derived ratio metrics
        ratio_measures = _derive_ratio_metrics(mb2, domain_context)
        mb2.extend(ratio_measures)

        # MB-3: Core + most valuable medium-confidence, grouped by domain
        mb3 = list(mb1)  # Start from core
        for c in medium:
            measure = _candidate_to_measure(c, domain_context, flagged_cols)
            if measure and _is_strategically_valuable(measure, domain_context):
                mb3.append(measure)

        # Identify conflicts (what MB-3 adds over MB-1)
        mb1_ids = {m["measure_id"] for m in mb1}
        mb3_ids = {m["measure_id"] for m in mb3}
        conflicts = []
        for m in mb3:
            if m["measure_id"] not in mb1_ids:
                conflicts.append({
                    "measure_id": m["measure_id"],
                    "label": m.get("label", ""),
                    "confidence": m.get("confidence", ""),
                    "domain": m.get("domain", ""),
                    "reason": "MB-3 includes this borderline metric; MB-1 excludes it",
                })

        return self._make_output(
            data={
                "measures_mb1": mb1,
                "measures_mb2": mb2,
                "measures_mb3": mb3,
                "measure_conflicts": conflicts,
            },
        )


def _candidate_to_measure(
    candidate: dict, domain_context: dict, flagged_cols: set,
) -> dict | None:
    """Convert a candidate_measures entry into a measure definition."""
    table = candidate.get("table", "")
    column = candidate.get("column", "")

    # Skip if quality-flagged
    if (table, column) in flagged_cols:
        return None

    measure_id = f"{table}_{column}".lower().replace(" ", "_")
    label = _humanize(column)

    return {
        "measure_id": measure_id,
        "label": label,
        "description": f"{candidate.get('recommended_aggregation', 'SUM')} of {column} from {table}",
        "aggregation": candidate.get("recommended_aggregation", "SUM"),
        "source_table": table,
        "source_column": column,
        "filter": "",
        "additivity": "fully_additive" if candidate.get("measure_type") == "additive" else "non_additive",
        "domain": candidate.get("domain", "General"),
        "confidence": candidate.get("confidence", "LOW"),
        "source": candidate.get("source", "inferred"),
        "validated": candidate.get("source") == "user_provided",
        "notes": candidate.get("notes", ""),
    }


def _humanize(name: str) -> str:
    """Convert snake_case to Title Case label."""
    return name.replace("_", " ").title()


def _derive_ratio_metrics(measures: list[dict], domain_context: dict) -> list[dict]:
    """Derive ratio metrics from pairs of existing measures."""
    ratios = []
    # Look for natural ratio pairs
    sum_measures = [m for m in measures if m.get("aggregation") == "SUM"]
    count_measures = [m for m in measures if m.get("aggregation") in ("COUNT", "COUNT_DISTINCT")]

    # Average value = SUM / COUNT for same table
    for sm in sum_measures:
        for cm in count_measures:
            if sm["source_table"] == cm["source_table"]:
                ratio_id = f"avg_{sm['source_column']}"
                if not any(m["measure_id"] == ratio_id for m in measures + ratios):
                    ratios.append({
                        "measure_id": ratio_id,
                        "label": f"Average {_humanize(sm['source_column'])}",
                        "description": f"{sm['label']} / {cm['label']}",
                        "aggregation": "RATIO",
                        "source_table": sm["source_table"],
                        "source_column": sm["source_column"],
                        "filter": "",
                        "additivity": "non_additive",
                        "domain": sm.get("domain", "General"),
                        "confidence": "MEDIUM",
                        "source": "derived",
                        "validated": False,
                        "complexity": "moderate",
                        "numerator": f"SUM({sm['source_column']})",
                        "denominator": f"{cm['aggregation']}({cm['source_column']})",
                        "notes": "Derived ratio metric",
                    })

    return ratios


def _is_strategically_valuable(measure: dict, domain_context: dict) -> bool:
    """Check if a measure is strategically valuable for the MB-3 tier."""
    # Measures with user-provided source are always valuable
    if measure.get("source") == "user_provided":
        return True
    # Medium confidence measures in core domains
    if measure.get("confidence") == "MEDIUM" and measure.get("domain") in (
        "Revenue", "Customer", "Product", "Marketing"
    ):
        return True
    return False
