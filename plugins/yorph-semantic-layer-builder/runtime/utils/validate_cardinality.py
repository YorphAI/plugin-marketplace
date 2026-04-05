"""
Validate join cardinality between two tables.

Used by: Join Validator (JV-1/2/3), Grain Detector (GD-1/2/3)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Awaitable


@dataclass
class CardinalityResult:
    """Result of a cardinality validation check."""
    left_table: str
    right_table: str
    join_key: str
    cardinality: str          # "1:1" | "1:many" | "many:1" | "many:many"
    left_count: int
    right_count: int
    left_distinct: int
    right_distinct: int
    match_rate: float         # % of left keys found in right (0.0-1.0)
    fan_out_ratio: float      # joined rows / left distinct keys
    null_pct_left: float
    null_pct_right: float
    is_safe: bool             # True if no fan-out risk detected
    evidence_sql: str         # the SQL that was run


async def validate_cardinality(
    left_table: str,
    right_table: str,
    join_key: str,
    schema: str,
    execute_sql: Callable[..., Awaitable[Any]],
) -> CardinalityResult:
    """
    Run a cardinality validation query and return structured results.

    Generates and executes SQL to check:
    - Distinct key counts on both sides
    - Match rate (FK coverage)
    - Fan-out ratio
    - Null rates
    """
    sql = f"""
    WITH left_keys AS (
        SELECT {join_key}, COUNT(*) AS row_count
        FROM {schema}.{left_table}
        GROUP BY {join_key}
    ),
    right_keys AS (
        SELECT {join_key}, COUNT(*) AS row_count
        FROM {schema}.{right_table}
        GROUP BY {join_key}
    ),
    stats AS (
        SELECT
            (SELECT COUNT(*) FROM {schema}.{left_table}) AS left_total,
            (SELECT COUNT(*) FROM {schema}.{right_table}) AS right_total,
            (SELECT COUNT(DISTINCT {join_key}) FROM {schema}.{left_table}) AS left_distinct,
            (SELECT COUNT(DISTINCT {join_key}) FROM {schema}.{right_table}) AS right_distinct,
            (SELECT COUNT(*) FROM {schema}.{left_table} WHERE {join_key} IS NULL) AS left_nulls,
            (SELECT COUNT(*) FROM {schema}.{right_table} WHERE {join_key} IS NULL) AS right_nulls
    ),
    match_check AS (
        SELECT COUNT(*) AS matched
        FROM left_keys l
        INNER JOIN right_keys r ON l.{join_key} = r.{join_key}
    )
    SELECT
        s.left_total, s.right_total,
        s.left_distinct, s.right_distinct,
        s.left_nulls, s.right_nulls,
        m.matched
    FROM stats s, match_check m
    """

    result = await execute_sql(sql=sql, description=f"Cardinality check: {left_table}.{join_key} → {right_table}")

    # Parse result
    row = result[0] if result else {}
    left_total = row.get("left_total", 0) or 0
    right_total = row.get("right_total", 0) or 0
    left_distinct = row.get("left_distinct", 0) or 0
    right_distinct = row.get("right_distinct", 0) or 0
    left_nulls = row.get("left_nulls", 0) or 0
    right_nulls = row.get("right_nulls", 0) or 0
    matched = row.get("matched", 0) or 0

    # Determine cardinality
    left_is_unique = (left_total == left_distinct)
    right_is_unique = (right_total == right_distinct)

    if left_is_unique and right_is_unique:
        cardinality = "1:1"
    elif left_is_unique and not right_is_unique:
        cardinality = "1:many"
    elif not left_is_unique and right_is_unique:
        cardinality = "many:1"
    else:
        cardinality = "many:many"

    match_rate = matched / left_distinct if left_distinct > 0 else 0.0
    null_pct_left = left_nulls / left_total if left_total > 0 else 0.0
    null_pct_right = right_nulls / right_total if right_total > 0 else 0.0

    # Fan-out: if joining inflates rows
    fan_out_ratio = right_total / right_distinct if right_distinct > 0 else 1.0

    is_safe = (
        cardinality in ("1:1", "1:many", "many:1")
        and match_rate >= 0.90
        and null_pct_left < 0.05
        and null_pct_right < 0.05
    )

    return CardinalityResult(
        left_table=left_table,
        right_table=right_table,
        join_key=join_key,
        cardinality=cardinality,
        left_count=left_total,
        right_count=right_total,
        left_distinct=left_distinct,
        right_distinct=right_distinct,
        match_rate=match_rate,
        fan_out_ratio=fan_out_ratio,
        null_pct_left=null_pct_left,
        null_pct_right=null_pct_right,
        is_safe=is_safe,
        evidence_sql=sql.strip(),
    )
