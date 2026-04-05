"""
Validate a candidate measure column by running aggregation checks.

Used by: Measures Builder (MB-1/2/3), Grain Detector
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Awaitable


@dataclass
class MeasureValidation:
    """Result of validating a candidate measure column."""
    table: str
    column: str
    is_valid: bool
    total_rows: int
    non_null_rows: int
    null_pct: float
    min_value: float | None
    max_value: float | None
    sum_value: float | None
    avg_value: float | None
    distinct_count: int
    has_negatives: bool
    is_constant: bool          # all values identical
    rejection_reason: str | None = None
    evidence_sql: str = ""


async def validate_measure(
    table: str,
    column: str,
    schema: str,
    execute_sql: Callable[..., Awaitable[Any]],
) -> MeasureValidation:
    """
    Run aggregation checks on a candidate measure column.

    Rejects if: >20% null, constant value, or clearly nonsensical aggregate.
    """
    sql = f"""
    SELECT
        COUNT(*)                       AS total_rows,
        COUNT({column})                AS non_null_rows,
        COUNT(DISTINCT {column})       AS distinct_count,
        MIN({column})                  AS min_val,
        MAX({column})                  AS max_val,
        SUM(CAST({column} AS DOUBLE))  AS sum_val,
        AVG(CAST({column} AS DOUBLE))  AS avg_val
    FROM {schema}.{table}
    """

    result = await execute_sql(sql=sql, description=f"Measure validation: {table}.{column}")

    row = result[0] if result else {}
    total = row.get("total_rows", 0) or 0
    non_null = row.get("non_null_rows", 0) or 0
    distinct = row.get("distinct_count", 0) or 0
    min_v = row.get("min_val")
    max_v = row.get("max_val")
    sum_v = row.get("sum_val")
    avg_v = row.get("avg_val")

    null_pct = (total - non_null) / total if total > 0 else 0.0
    has_neg = min_v is not None and float(min_v) < 0
    is_const = distinct <= 1

    # Determine validity
    rejection = None
    if null_pct > 0.20:
        rejection = f"High null rate ({null_pct:.1%})"
    elif is_const:
        rejection = f"Constant column (only {distinct} distinct value(s))"

    return MeasureValidation(
        table=table, column=column,
        is_valid=rejection is None,
        total_rows=total, non_null_rows=non_null,
        null_pct=null_pct,
        min_value=float(min_v) if min_v is not None else None,
        max_value=float(max_v) if max_v is not None else None,
        sum_value=float(sum_v) if sum_v is not None else None,
        avg_value=float(avg_v) if avg_v is not None else None,
        distinct_count=distinct,
        has_negatives=has_neg,
        is_constant=is_const,
        rejection_reason=rejection,
        evidence_sql=sql.strip(),
    )
