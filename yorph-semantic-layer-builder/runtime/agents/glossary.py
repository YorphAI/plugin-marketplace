"""
Glossary Builder agent — builds glossary and surfaces open questions.

Tier 1 agent — receives domain_context, candidate_measures from Tier 0.

Flags anything ambiguous or requiring user confirmation.
Builds a glossary of business terms found in column names and sample values.

Outputs: open_questions[], glossary{}
"""

from __future__ import annotations

import re
from typing import Any

from runtime.agents.base import BaseAgent, AgentContext, AgentOutput


class GlossaryBuilder(BaseAgent):
    """Builds a business glossary and surfaces unresolved questions."""

    name = "glossary"
    requires = ["profiles", "domain_context", "candidate_measures"]
    produces = ["open_questions", "glossary"]

    async def run(self, ctx: AgentContext) -> AgentOutput:
        profiles = ctx.profiles
        domain_context = ctx.upstream_outputs.get("domain_context", {})
        candidate_measures = ctx.upstream_outputs.get("candidate_measures", [])
        domain_type = ctx.user_context.get("domain_type", "")

        glossary: dict[str, str] = {}
        open_questions: list[dict[str, Any]] = []

        tables = profiles.get("tables", {})
        for table_name, table_profile in tables.items():
            table_info = domain_context.get(table_name, {})
            domain = table_info.get("domain", "General")

            # Add table to glossary
            glossary[table_name] = _describe_table(table_name, domain, table_profile)

            columns = table_profile.get("columns", [])
            for col in columns:
                col_name = col.get("column_name", col.get("name", ""))
                annotations = table_info.get("annotated_columns", [])
                col_annotation = next(
                    (a for a in annotations if a.get("column_name") == col_name), {}
                )

                # Add column terms to glossary
                term = _extract_business_term(col_name)
                if term and term not in glossary:
                    glossary[term] = _describe_column_term(
                        term, col_name, table_name, col, col_annotation, domain_type,
                    )

                # Surface ambiguities as open questions
                if col_annotation.get("confidence") == "low":
                    open_questions.append({
                        "question": f"What does '{col_name}' represent in '{table_name}'?",
                        "context": f"Column type: {col.get('data_type', 'unknown')}, "
                                   f"null rate: {col.get('null_pct', 0):.0%}, "
                                   f"distinct values: {col.get('distinct_count', 'unknown')}",
                        "agent": self.name,
                    })

        # Surface questions about ambiguous measure candidates
        for measure in candidate_measures:
            if measure.get("confidence") == "LOW" and measure.get("source") != "user_provided":
                open_questions.append({
                    "question": (
                        f"Is '{measure['column']}' in '{measure['table']}' a measure "
                        f"that should be aggregated, or a numeric dimension?"
                    ),
                    "context": f"Suggested aggregation: {measure.get('recommended_aggregation', 'SUM')}",
                    "agent": self.name,
                })

        return self._make_output(
            data={
                "open_questions": open_questions,
                "glossary": glossary,
            },
        )


def _describe_table(name: str, domain: str, profile: dict) -> str:
    """Generate a glossary description for a table."""
    row_count = profile.get("row_count", 0)
    col_count = len(profile.get("columns", []))
    return f"{domain} table with {col_count} columns and ~{row_count:,} rows"


def _extract_business_term(col_name: str) -> str | None:
    """Extract a business term from a column name."""
    # Strip common prefixes/suffixes
    term = re.sub(r"^(dim_|fact_|fk_|pk_|src_|stg_)", "", col_name, flags=re.IGNORECASE)
    term = re.sub(r"(_id|_key|_fk|_sk|_pk|_flag|_ind|_code)$", "", term, flags=re.IGNORECASE)
    term = term.strip("_")
    if len(term) < 2:
        return None
    return term.replace("_", " ").title()


def _describe_column_term(
    term: str, col_name: str, table_name: str,
    profile: dict, annotation: dict, domain_type: str,
) -> str:
    """Generate a glossary definition for a business term from a column."""
    role = annotation.get("role", "unknown")
    dtype = profile.get("data_type", "unknown")
    distinct = profile.get("distinct_count")

    parts = [f"Found as '{col_name}' in '{table_name}'"]
    if role != "unknown":
        parts.append(f"role: {role}")
    if distinct:
        parts.append(f"{distinct} distinct values")

    # Add domain-specific standard definitions
    domain_defs = _STANDARD_DEFINITIONS.get(term.lower(), "")
    if domain_defs:
        parts.append(f"Standard definition: {domain_defs}")

    return ". ".join(parts)


# Standard business term definitions
_STANDARD_DEFINITIONS: dict[str, str] = {
    "revenue": "Total monetary value of goods or services sold",
    "gross revenue": "Revenue before any deductions (returns, discounts, taxes)",
    "net revenue": "Revenue after returns, discounts, and allowances",
    "mrr": "Monthly Recurring Revenue — sum of active subscription values",
    "arr": "Annual Recurring Revenue — MRR × 12",
    "churn": "Rate at which customers cancel or do not renew",
    "conversion": "Rate at which users complete a desired action",
    "dau": "Daily Active Users — unique users who performed an action per day",
    "mau": "Monthly Active Users — unique users per month",
    "ltv": "Customer Lifetime Value — total expected revenue from a customer",
    "cac": "Customer Acquisition Cost — cost to acquire a new customer",
    "aov": "Average Order Value — total revenue / number of orders",
    "margin": "Difference between revenue and cost, typically expressed as a percentage",
    "retention": "Percentage of customers who continue using the product over time",
}
