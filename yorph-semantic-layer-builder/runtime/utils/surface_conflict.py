"""
Surface conflicts between agent outputs or between data and documentation.

Used by: all agents during cross-validation and self-validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ConflictType(Enum):
    """Types of conflicts that can arise."""
    AGENT_DISAGREEMENT = "agent_disagreement"     # two agents disagree on same item
    DOC_DATA_MISMATCH = "doc_data_mismatch"       # documentation vs profiled data
    QUALITY_WARNING = "quality_warning"            # data quality issue affecting output
    SCD_JOIN_RISK = "scd_join_risk"                # SCD table joined without temporal filter
    BROKEN_DEPENDENCY = "broken_dependency"        # measure depends on rejected join
    GRAIN_MISMATCH = "grain_mismatch"              # measure at wrong grain


@dataclass
class Conflict:
    """A conflict surfaced for user resolution."""
    conflict_type: ConflictType
    item_id: str                 # e.g. join key, measure_id
    agent_a: str                 # first agent's perspective
    agent_b: str                 # second agent's perspective (or "data" / "documentation")
    position_a: str              # what agent A says
    position_b: str              # what agent B says
    evidence: dict[str, Any] = None
    recommendation: str | None = None
    resolved: bool = False
    resolution: str | None = None


def surface_conflict(
    conflict_type: ConflictType,
    item_id: str,
    agent_a: str,
    agent_b: str,
    position_a: str,
    position_b: str,
    evidence: dict[str, Any] | None = None,
    recommendation: str | None = None,
) -> Conflict:
    """Create a Conflict object for user resolution."""
    return Conflict(
        conflict_type=conflict_type,
        item_id=item_id,
        agent_a=agent_a,
        agent_b=agent_b,
        position_a=position_a,
        position_b=position_b,
        evidence=evidence or {},
        recommendation=recommendation,
    )
