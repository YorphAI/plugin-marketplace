"""
Build SQL WHERE clause fragments from user-defined exclusion rules.

Used by: Business Rules agent, all Measure agents (to apply standard exclusions)
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ExclusionFilter:
    """A parsed exclusion filter ready for SQL generation."""
    table: str | None        # which table this applies to (None = all)
    column: str
    operator: str            # "=" | "!=" | "IN" | "NOT IN" | "IS NULL" | "IS NOT NULL"
    value: str | list[str]
    original_text: str       # the user's original description
    is_user_confirmed: bool


def build_exclusion_filter(
    exclusion_text: str,
    table_hint: str | None = None,
    is_user_confirmed: bool = True,
) -> ExclusionFilter | None:
    """
    Parse a plain-English exclusion string into a structured filter.

    Examples:
        "is_test = TRUE" → ExclusionFilter(column="is_test", operator="=", value="TRUE")
        "account_type = 'internal'" → ExclusionFilter(column="account_type", operator="=", value="internal")
        "status IN ('deleted', 'cancelled')" → ExclusionFilter(column="status", operator="IN", value=["deleted","cancelled"])
    """
    text = exclusion_text.strip()

    # Try pattern: column = value
    m = re.match(r"(\w+)\s*(=|!=|<>)\s*['\"]?(\w+)['\"]?", text)
    if m:
        return ExclusionFilter(
            table=table_hint, column=m.group(1), operator=m.group(2),
            value=m.group(3), original_text=text,
            is_user_confirmed=is_user_confirmed,
        )

    # Try pattern: column IN (...)
    m = re.match(r"(\w+)\s+(NOT\s+)?IN\s*\(([^)]+)\)", text, re.IGNORECASE)
    if m:
        vals = [v.strip().strip("'\"") for v in m.group(3).split(",")]
        op = "NOT IN" if m.group(2) else "IN"
        return ExclusionFilter(
            table=table_hint, column=m.group(1), operator=op,
            value=vals, original_text=text,
            is_user_confirmed=is_user_confirmed,
        )

    # Try pattern: column IS NULL / IS NOT NULL
    m = re.match(r"(\w+)\s+IS\s+(NOT\s+)?NULL", text, re.IGNORECASE)
    if m:
        op = "IS NOT NULL" if m.group(2) else "IS NULL"
        return ExclusionFilter(
            table=table_hint, column=m.group(1), operator=op,
            value="", original_text=text,
            is_user_confirmed=is_user_confirmed,
        )

    # Could not parse — return None so caller can handle raw text
    return None


def exclusion_to_sql(filt: ExclusionFilter) -> str:
    """Convert an ExclusionFilter to a SQL WHERE fragment."""
    if filt.operator in ("IS NULL", "IS NOT NULL"):
        return f"{filt.column} {filt.operator}"
    if filt.operator in ("IN", "NOT IN"):
        vals = ", ".join(f"'{v}'" for v in filt.value)
        return f"{filt.column} {filt.operator} ({vals})"
    return f"{filt.column} {filt.operator} '{filt.value}'"
