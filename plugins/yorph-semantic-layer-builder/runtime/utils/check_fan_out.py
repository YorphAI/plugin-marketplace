"""
Detect fan-out traps in join relationships.

A fan-out occurs when joining two tables produces more rows than the base table,
causing measure double-counting.

Used by: Join Validator, Measures Builder
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Awaitable


@dataclass
class FanOutResult:
    """Result of a fan-out detection check."""
    left_table: str
    right_table: str
    join_key: str
    base_rows: int
    joined_rows: int
    fan_out_detected: bool
    fan_out_ratio: float     # joined_rows / base_rows
    evidence_sql: str


async def check_fan_out(
    left_table: str,
    right_table: str,
    join_key: str,
    schema: str,
    execute_sql: Callable[..., Awaitable[Any]],
    threshold: float = 1.05,
) -> FanOutResult:
    """
    Check if joining left_table to right_table on join_key produces fan-out.

    Fan-out is detected when the joined row count exceeds the left table
    row count by more than the threshold (default 5%).
    """
    sql = f"""
    SELECT
        (SELECT COUNT(*) FROM {schema}.{left_table}) AS base_rows,
        (SELECT COUNT(*)
         FROM {schema}.{left_table} a
         INNER JOIN {schema}.{right_table} b ON a.{join_key} = b.{join_key}
        ) AS joined_rows
    """

    result = await execute_sql(sql=sql, description=f"Fan-out check: {left_table} → {right_table} on {join_key}")

    row = result[0] if result else {}
    base = row.get("base_rows", 0) or 0
    joined = row.get("joined_rows", 0) or 0

    ratio = joined / base if base > 0 else 1.0
    detected = ratio > threshold

    return FanOutResult(
        left_table=left_table,
        right_table=right_table,
        join_key=join_key,
        base_rows=base,
        joined_rows=joined,
        fan_out_detected=detected,
        fan_out_ratio=ratio,
        evidence_sql=sql.strip(),
    )
