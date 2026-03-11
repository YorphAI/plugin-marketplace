"""
Classify columns by semantic role.

Used by: Schema Annotator, Measures Builder
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ColumnClassification:
    """Semantic classification of a single column."""
    column_name: str
    table_name: str
    role: str              # "measure_candidate" | "foreign_key" | "dimension" |
                           # "time_column" | "flag" | "identifier" | "text_label"
    confidence: str        # "high" | "medium" | "low"
    measure_type: str | None = None  # "additive" | "ratio" | "count" for measure candidates
    recommended_agg: str | None = None  # "SUM" | "COUNT" | "AVG" | "COUNT_DISTINCT"
    notes: str | None = None


# ── Pattern matchers ─────────────────────────────────────────────────────────

_MEASURE_HIGH = re.compile(
    r"(_amount|_paid|_revenue|_cost|_price|_profit|_qty|_quantity|_count|_total|_sum|_units|"
    r"^revenue$|^sales$|^spend$|^profit$|^margin$|^cost$|^price$|^quantity$|^amount$)",
    re.IGNORECASE,
)

_MEASURE_MEDIUM = re.compile(
    r"(_rate|_score|_pct|_percent|_fraction|_ratio|_avg|_mean|_duration|_latency|_weight)",
    re.IGNORECASE,
)

_FK_PATTERN = re.compile(r"(_id|_key|_fk|_sk)$", re.IGNORECASE)

_TIME_PATTERN = re.compile(
    r"(_at|_date|_time|_ts|_timestamp|_datetime|created|updated|modified|deleted|"
    r"^date$|^timestamp$|^created_at$|^updated_at$)",
    re.IGNORECASE,
)

_FLAG_PATTERN = re.compile(
    r"(^is_|^has_|^was_|^can_|^should_|_flag$|_bool$|_indicator$)",
    re.IGNORECASE,
)

_IDENTIFIER_PATTERN = re.compile(
    r"(^id$|^uuid$|^guid$|_uuid$|_guid$|^pk$|_pk$)",
    re.IGNORECASE,
)


def classify_column(
    column_name: str,
    table_name: str,
    profile: dict[str, Any] | None = None,
    entity_map: dict[str, Any] | None = None,
) -> ColumnClassification:
    """
    Classify a single column by its semantic role using name patterns
    and optional profile statistics.

    Args:
        column_name: the column name
        table_name: the table this column belongs to
        profile: optional column profile dict (null_pct, distinct_count, min, max, etc.)
        entity_map: optional entity_disambiguation from user context
    """
    profile = profile or {}
    distinct = profile.get("distinct_count", None)
    null_pct = profile.get("null_pct", 0.0)
    dtype = profile.get("data_type", "").lower()

    # 1. Check if it's an identifier / primary key
    if _IDENTIFIER_PATTERN.search(column_name):
        return ColumnClassification(
            column_name=column_name, table_name=table_name,
            role="identifier", confidence="high",
        )

    # 2. Check if it's a time column
    if _TIME_PATTERN.search(column_name) or dtype in ("date", "timestamp", "datetime", "timestamptz"):
        return ColumnClassification(
            column_name=column_name, table_name=table_name,
            role="time_column", confidence="high",
        )

    # 3. Check if it's a flag/boolean
    if _FLAG_PATTERN.search(column_name) or dtype in ("boolean", "bool"):
        return ColumnClassification(
            column_name=column_name, table_name=table_name,
            role="flag", confidence="high",
        )

    # 4. Check if it's a foreign key (but not a primary key pattern)
    if _FK_PATTERN.search(column_name) and not _IDENTIFIER_PATTERN.search(column_name):
        conf = "high"
        # If entity_map says this entity exists, boost confidence
        if entity_map:
            base = column_name.replace("_id", "").replace("_key", "").replace("_fk", "").replace("_sk", "")
            if base in entity_map:
                conf = "high"
        return ColumnClassification(
            column_name=column_name, table_name=table_name,
            role="foreign_key", confidence=conf,
        )

    # 5. Check if it's a high-confidence measure
    if _MEASURE_HIGH.search(column_name):
        # Exclude surrogate keys disguised as counts
        if distinct is not None and distinct <= 2:
            return ColumnClassification(
                column_name=column_name, table_name=table_name,
                role="flag", confidence="medium",
                notes="Looks like a measure by name but has <=2 distinct values",
            )
        return ColumnClassification(
            column_name=column_name, table_name=table_name,
            role="measure_candidate", confidence="high",
            measure_type="additive", recommended_agg="SUM",
        )

    # 6. Check if it's a medium-confidence measure (ratio/score)
    if _MEASURE_MEDIUM.search(column_name):
        return ColumnClassification(
            column_name=column_name, table_name=table_name,
            role="measure_candidate", confidence="medium",
            measure_type="ratio", recommended_agg="AVG",
            notes="Likely a ratio or pre-computed metric — verify additivity",
        )

    # 7. If numeric type with many distinct values, could be a measure
    if dtype in ("number", "numeric", "float", "double", "decimal", "real", "int", "integer", "bigint"):
        if distinct is not None and distinct > 10:
            return ColumnClassification(
                column_name=column_name, table_name=table_name,
                role="measure_candidate", confidence="low",
                measure_type="additive", recommended_agg="SUM",
                notes="Numeric column — check if it's a measure or just a numeric dimension",
            )

    # 8. Check if it's a text label (low distinct count relative to rows)
    if dtype in ("varchar", "text", "string", "char"):
        return ColumnClassification(
            column_name=column_name, table_name=table_name,
            role="text_label" if (distinct and distinct < 1000) else "dimension",
            confidence="medium",
        )

    # 9. Default to dimension
    return ColumnClassification(
        column_name=column_name, table_name=table_name,
        role="dimension", confidence="low",
    )


def classify_columns(
    columns: list[dict[str, Any]],
    table_name: str,
    entity_map: dict[str, Any] | None = None,
) -> list[ColumnClassification]:
    """Classify all columns in a table."""
    return [
        classify_column(
            column_name=col.get("column_name", col.get("name", "")),
            table_name=table_name,
            profile=col,
            entity_map=entity_map,
        )
        for col in columns
    ]
