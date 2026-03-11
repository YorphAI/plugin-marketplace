"""
Schema Annotator — merged Pre-Agent A (Domain Classifier) + Pre-Agent B (Metric Discovery).

Tier 0 agent — runs before all main agents, no upstream dependencies.

Performs a single pass over all profiled tables and columns to:
  1. Classify each table into a business domain (Revenue, Customer, Product, etc.)
  2. Tag each column's semantic role (measure_candidate, foreign_key, dimension, etc.)
  3. Rank measure candidates by confidence (VERIFIED > HIGH > MEDIUM > LOW)
  4. Apply entity disambiguation from user context to correctly label FK columns

Outputs:
  - domain_context: {table → {domain, likely_entity_type, annotated_columns[]}}
  - candidate_measures: [{column, table, confidence, recommended_aggregation, domain, source}]
"""

from __future__ import annotations

from typing import Any

from runtime.agents.base import BaseAgent, AgentContext, AgentOutput
from runtime.utils.classify_column import classify_column, ColumnClassification


# ── Domain classification heuristics ─────────────────────────────────────────

# Table name patterns → likely domain
_DOMAIN_PATTERNS: dict[str, list[str]] = {
    "Revenue": ["order", "sale", "transaction", "invoice", "payment", "billing", "charge", "refund", "return"],
    "Customer": ["customer", "user", "account", "member", "subscriber", "contact", "person", "profile"],
    "Product": ["product", "item", "sku", "catalog", "category", "brand", "inventory"],
    "Date/Time": ["date", "calendar", "time", "period", "fiscal"],
    "Marketing": ["campaign", "channel", "attribution", "conversion", "session", "event", "click", "impression"],
    "HR": ["employee", "department", "position", "salary", "headcount", "attrition"],
    "Logistics": ["shipment", "warehouse", "fulfillment", "delivery", "carrier", "tracking"],
    "Finance": ["ledger", "journal", "gl_", "account_balance", "receivable", "payable"],
}

# Entity type classification based on table characteristics
_FACT_INDICATORS = {"order", "sale", "transaction", "event", "session", "shipment", "payment", "log"}
_DIM_INDICATORS = {"customer", "user", "product", "category", "region", "store", "channel", "date", "calendar"}


class SchemaAnnotator(BaseAgent):
    """
    Merged Domain Classifier + Metric Discovery.
    Single pass: classify domain → tag columns → rank measures → apply entity map.
    """

    name = "schema_annotator"
    requires = ["profiles", "user_context"]
    produces = ["domain_context", "candidate_measures"]

    async def run(self, ctx: AgentContext) -> AgentOutput:
        profiles = ctx.profiles
        user_ctx = ctx.user_context
        domain_type = user_ctx.get("domain_type", "")
        entity_map = user_ctx.get("entity_disambiguation", {})
        user_metrics = user_ctx.get("user_provided_metrics", [])

        domain_context: dict[str, Any] = {}
        candidate_measures: list[dict[str, Any]] = []
        issues = []
        questions = []

        # ── Step 1: Process user-provided metrics first (VERIFIED, highest confidence)
        for metric in user_metrics:
            candidate_measures.append({
                "column": metric.get("formula", ""),
                "table": ", ".join(metric.get("source_tables", [])),
                "confidence": "VERIFIED",
                "recommended_aggregation": _infer_agg_from_formula(metric.get("formula", "")),
                "domain": metric.get("domain", ""),
                "source": "user_provided",
                "name": metric.get("name", ""),
                "formula": metric.get("formula", ""),
                "filters": metric.get("filters", ""),
                "notes": metric.get("notes", ""),
            })

        # ── Step 2: Classify each table and its columns
        tables = profiles.get("tables", {})
        for table_name, table_profile in tables.items():
            # Classify table domain
            domain = _classify_table_domain(table_name, domain_type)
            entity_type = _classify_entity_type(table_name, table_profile)

            # Classify each column
            annotated_columns = []
            columns = table_profile.get("columns", [])
            for col in columns:
                col_name = col.get("column_name", col.get("name", ""))
                classification = classify_column(
                    column_name=col_name,
                    table_name=table_name,
                    profile=col,
                    entity_map=entity_map,
                )
                annotated_columns.append({
                    "column_name": col_name,
                    "role": classification.role,
                    "confidence": classification.confidence,
                    "measure_type": classification.measure_type,
                    "recommended_agg": classification.recommended_agg,
                    "notes": classification.notes,
                })

                # If it's a measure candidate, add to candidate_measures
                if classification.role == "measure_candidate":
                    # Check it's not already covered by user-provided metrics
                    if not _is_user_provided(col_name, table_name, user_metrics):
                        candidate_measures.append({
                            "column": col_name,
                            "table": table_name,
                            "confidence": classification.confidence.upper(),
                            "recommended_aggregation": classification.recommended_agg or "SUM",
                            "domain": domain,
                            "source": "inferred",
                            "measure_type": classification.measure_type,
                            "notes": classification.notes,
                        })

            domain_context[table_name] = {
                "domain": domain,
                "likely_entity_type": entity_type,
                "annotated_columns": annotated_columns,
            }

        return self._make_output(
            data={
                "domain_context": domain_context,
                "candidate_measures": candidate_measures,
            },
            issues=issues,
            questions=questions,
        )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _classify_table_domain(table_name: str, domain_type: str) -> str:
    """Classify a table into a business domain based on name patterns."""
    lower = table_name.lower()
    for domain, patterns in _DOMAIN_PATTERNS.items():
        for pattern in patterns:
            if pattern in lower:
                return domain
    return "General"


def _classify_entity_type(table_name: str, profile: dict) -> str:
    """Classify a table as fact, dimension, or bridge."""
    lower = table_name.lower()
    # Check name patterns
    for indicator in _FACT_INDICATORS:
        if indicator in lower:
            return "fact"
    for indicator in _DIM_INDICATORS:
        if indicator in lower:
            return "dimension"
    # Heuristic: tables with many numeric columns are more likely facts
    columns = profile.get("columns", [])
    numeric_count = sum(1 for c in columns if c.get("data_type", "").lower() in
                        ("number", "numeric", "float", "double", "decimal", "int", "integer", "bigint"))
    if len(columns) > 0 and numeric_count / len(columns) > 0.4:
        return "fact"
    return "dimension"


def _infer_agg_from_formula(formula: str) -> str:
    """Infer aggregation type from a metric formula string."""
    upper = formula.upper()
    if "COUNT(DISTINCT" in upper:
        return "COUNT_DISTINCT"
    if "COUNT(" in upper:
        return "COUNT"
    if "AVG(" in upper:
        return "AVG"
    if "SUM(" in upper:
        return "SUM"
    if "/" in formula:
        return "RATIO"
    return "SUM"


def _is_user_provided(col_name: str, table_name: str, user_metrics: list[dict]) -> bool:
    """Check if a column is already covered by a user-provided metric."""
    for m in user_metrics:
        sources = m.get("source_tables", [])
        formula = m.get("formula", "").lower()
        if table_name in sources and col_name.lower() in formula:
            return True
    return False
