"""
Base agent infrastructure for the semantic layer builder.

Every agent (Schema Annotator, Join Validator, etc.) subclasses BaseAgent
and declares:
  - requires: list of output keys it needs from upstream agents
  - produces: list of output keys it generates

The Orchestrator uses these declarations to build a DAG, topologically sort
agents into tiers, and run each tier in parallel.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class Issue:
    """An escalation item surfaced by an agent for user resolution."""
    agent: str
    severity: str          # "critical" | "warning" | "info"
    category: str          # "join_conflict" | "measure_conflict" | "quality" | "scd" | "ambiguity"
    title: str
    description: str
    evidence: dict[str, Any] = field(default_factory=dict)
    options: list[str] = field(default_factory=list)
    recommendation: str | None = None


@dataclass
class AssumptionQuestion:
    """A question the agent needs answered before finalising output."""
    agent: str
    question: str
    why_it_matters: str
    options: list[str]
    assumption: str | None = None    # agent's default if user doesn't answer


@dataclass
class AgentOutput:
    """Structured result from a single agent run."""
    agent_name: str
    data: dict[str, Any]                              # keyed by produces[] names
    issues: list[Issue] = field(default_factory=list)
    questions: list[AssumptionQuestion] = field(default_factory=list)


@dataclass
class AgentContext:
    """
    Shared state passed to each agent at run time.

    - profiles: column/table profiles from the profiler (enriched with doc context)
    - user_context: domain_type, entity_disambiguation, standard_exclusions,
                    user_provided_metrics — everything from Phase 2
    - upstream_outputs: merged dict of all outputs from agents in earlier tiers,
                        keyed by output name (e.g. "domain_context", "quality_flags")
    - execute_sql: async callable to run validation SQL against the warehouse
    - get_sample: async callable to fetch sample rows from the cache
    - execute_python: async callable to run Python code in the sandbox
    """
    profiles: dict[str, Any]
    user_context: dict[str, Any]
    upstream_outputs: dict[str, Any] = field(default_factory=dict)
    execute_sql: Callable[..., Awaitable[Any]] | None = None
    get_sample: Callable[..., Awaitable[Any]] | None = None
    execute_python: Callable[..., Awaitable[Any]] | None = None


# ── Cross-validation result ──────────────────────────────────────────────────

@dataclass
class CrossValidationFlag:
    """A flag raised during the cross-validation phase (Tier 2)."""
    source_agent: str      # which agent's output triggered this
    target_agent: str      # which agent's output is affected
    flag_type: str         # "scd_join_warning" | "quality_measure_warning" | "broken_dependency"
    detail: str
    affected_items: list[str] = field(default_factory=list)  # IDs of affected joins/measures


# ── Base agent ───────────────────────────────────────────────────────────────

class BaseAgent(ABC):
    """
    Abstract base for all semantic layer agents.

    Subclasses must set `name`, `requires`, `produces` and implement `run()`.
    Optionally override `validate()` for post-run self-checks.
    """

    name: str = ""
    requires: list[str] = []
    produces: list[str] = []

    @abstractmethod
    async def run(self, ctx: AgentContext) -> AgentOutput:
        """Execute the agent's analysis and return structured output."""
        ...

    async def validate(self, output: AgentOutput, ctx: AgentContext) -> list[Issue]:
        """
        Optional self-validation after run().

        Override to add checks like "did I produce at least N measures?"
        or "are all my join keys present in the profiles?".
        Returns additional issues to surface.
        """
        return []

    def _make_output(self, data: dict[str, Any], **kwargs) -> AgentOutput:
        """Helper to build an AgentOutput with this agent's name pre-filled."""
        return AgentOutput(agent_name=self.name, data=data, **kwargs)

    def _issue(self, severity: str, category: str, title: str,
               description: str, **kwargs) -> Issue:
        """Helper to build an Issue with this agent's name pre-filled."""
        return Issue(agent=self.name, severity=severity, category=category,
                     title=title, description=description, **kwargs)

    def _question(self, question: str, why: str, options: list[str],
                  assumption: str | None = None) -> AssumptionQuestion:
        """Helper to build an AssumptionQuestion."""
        return AssumptionQuestion(
            agent=self.name, question=question, why_it_matters=why,
            options=options, assumption=assumption,
        )
