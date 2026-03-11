"""
Business Rules Agent — extracts and structures business rules.

Tier 1 agent — receives domain_context from Schema Annotator.

Starts from user-provided standard_exclusions (hard rules, marked [USER CONFIRMED]).
Adds domain-specific defaults and rules inferred from data patterns.

Output: business_rules[] — list of plain-English rule strings
"""

from __future__ import annotations

from typing import Any

from runtime.agents.base import BaseAgent, AgentContext, AgentOutput
from runtime.utils.build_exclusion_filter import build_exclusion_filter, exclusion_to_sql


# Domain-specific default business rules
_DOMAIN_DEFAULTS: dict[str, list[str]] = {
    "E-commerce": [
        "Revenue calculations exclude rows where net_paid <= 0 or return_amount > 0",
        "Order counts only include orders with status = 'completed' or 'delivered'",
        "Exclude test orders (order_id starting with 'TEST' or flagged as test)",
    ],
    "SaaS": [
        "MRR calculations only include subscriptions with status = 'active'",
        "Churn is calculated as cancellations divided by start-of-period active subscriptions",
        "Trial accounts are excluded from revenue metrics unless converted",
    ],
    "Marketing": [
        "Conversion attribution uses last-touch model by default",
        "Internal traffic (from company IP ranges) is excluded from session metrics",
        "Bot traffic (identified by user_agent patterns) is excluded",
    ],
    "Finance": [
        "Revenue excludes intercompany transactions",
        "Distinguish between realized and unrealized revenue",
        "GL entries must balance (debits = credits per journal entry)",
    ],
    "Healthcare": [
        "PHI columns are excluded from the semantic layer",
        "Patient counts use COUNT(DISTINCT patient_id), not row counts",
        "Exclude voided or cancelled claims from financial metrics",
    ],
}


class BusinessRulesAgent(BaseAgent):
    """Extracts and structures business rules from user input and data patterns."""

    name = "business_rules"
    requires = ["profiles", "domain_context", "standard_exclusions"]
    produces = ["business_rules"]

    async def run(self, ctx: AgentContext) -> AgentOutput:
        user_ctx = ctx.user_context
        domain_context = ctx.upstream_outputs.get("domain_context", {})
        standard_exclusions = user_ctx.get("standard_exclusions", [])
        domain_type = user_ctx.get("domain_type", "")

        rules: list[str] = []

        # 1. User-provided exclusions are hard rules (highest priority)
        for exclusion in standard_exclusions:
            rules.append(f"[USER CONFIRMED] {exclusion}")

        # 2. Add domain-specific defaults
        for domain_key, defaults in _DOMAIN_DEFAULTS.items():
            if domain_key.lower() in domain_type.lower():
                for default_rule in defaults:
                    # Don't duplicate if user already stated something similar
                    if not _is_duplicate_rule(default_rule, rules):
                        rules.append(default_rule)

        # 3. Infer rules from data patterns
        profiles = ctx.profiles
        tables = profiles.get("tables", {})
        for table_name, table_profile in tables.items():
            inferred = _infer_rules_from_profile(table_name, table_profile, domain_context)
            for rule in inferred:
                if not _is_duplicate_rule(rule, rules):
                    rules.append(rule)

        return self._make_output(data={"business_rules": rules})


def _infer_rules_from_profile(
    table_name: str,
    profile: dict,
    domain_context: dict,
) -> list[str]:
    """Infer business rules from column profiles."""
    rules = []
    columns = profile.get("columns", [])

    for col in columns:
        col_name = col.get("column_name", col.get("name", "")).lower()
        sample_values = col.get("sample_values", [])

        # Status columns with specific values
        if "status" in col_name:
            if sample_values:
                vals = [str(v) for v in sample_values if v is not None]
                if any(v.lower() in ("deleted", "cancelled", "voided", "archived", "inactive")
                       for v in vals):
                    rules.append(
                        f"Consider filtering {table_name}.{col_name} to exclude "
                        f"inactive statuses (deleted, cancelled, etc.) in metric calculations"
                    )

        # Boolean flag columns that might indicate test/internal data
        if col_name in ("is_test", "is_internal", "is_sandbox", "is_demo"):
            rules.append(
                f"Filter out rows where {table_name}.{col_name} = TRUE "
                f"from all metric calculations"
            )

    return rules


def _is_duplicate_rule(new_rule: str, existing: list[str]) -> bool:
    """Simple duplicate check — looks for significant word overlap."""
    new_words = set(new_rule.lower().split())
    for existing_rule in existing:
        existing_words = set(existing_rule.lower().split())
        overlap = len(new_words & existing_words)
        if overlap > len(new_words) * 0.6:
            return True
    return False
