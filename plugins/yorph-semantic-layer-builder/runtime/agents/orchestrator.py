"""
DAG Orchestrator — runs agents in topological order with cross-validation.

Reads dag.yaml to determine execution tiers and dependencies.
Within each tier, agents run in parallel (asyncio.gather).
After all tiers complete, runs cross-validation checks.

Supports targeted re-runs: if user changes input (e.g. exclusions),
only affected agents and their downstream dependents re-run.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import yaml

from runtime.agents.base import (
    BaseAgent, AgentContext, AgentOutput, CrossValidationFlag, Issue,
)
from runtime.agents.schema_annotator import SchemaAnnotator
from runtime.agents.quality_sentinel import QualitySentinel
from runtime.agents.scd_detector import SCDDetector
from runtime.agents.join_validator import JoinValidator
from runtime.agents.measures_builder import MeasuresBuilder
from runtime.agents.grain_detector import GrainDetector
from runtime.agents.business_rules import BusinessRulesAgent
from runtime.agents.glossary import GlossaryBuilder
from runtime.agents.time_intelligence import TimeIntelligenceAgent
from runtime.agents.dimension_hierarchies import DimensionHierarchiesAgent


# ── Agent registry ───────────────────────────────────────────────────────────

_AGENT_CLASSES: dict[str, type[BaseAgent]] = {
    "SchemaAnnotator": SchemaAnnotator,
    "QualitySentinel": QualitySentinel,
    "SCDDetector": SCDDetector,
    "JoinValidator": JoinValidator,
    "MeasuresBuilder": MeasuresBuilder,
    "GrainDetector": GrainDetector,
    "BusinessRulesAgent": BusinessRulesAgent,
    "GlossaryBuilder": GlossaryBuilder,
    "TimeIntelligenceAgent": TimeIntelligenceAgent,
    "DimensionHierarchiesAgent": DimensionHierarchiesAgent,
}


class Orchestrator:
    """
    Runs the agent DAG: load config → execute tiers → cross-validate.

    Usage:
        orch = Orchestrator()
        result = await orch.run(profiles, user_context, execute_sql, get_sample)
        agent_outputs = result["agent_outputs"]
    """

    def __init__(self, dag_path: str | Path | None = None):
        if dag_path is None:
            dag_path = Path(__file__).parent / "dag.yaml"
        self.dag_path = Path(dag_path)
        self.dag_config = self._load_dag()
        self.outputs: dict[str, AgentOutput] = {}
        self.all_issues: list[Issue] = []
        self.all_questions: list[dict] = []
        self.cross_validation_flags: list[CrossValidationFlag] = []

    def _load_dag(self) -> dict:
        """Load and parse dag.yaml."""
        with open(self.dag_path) as f:
            return yaml.safe_load(f)

    def _get_tiers(self) -> dict[int, list[dict]]:
        """Group agents by tier number."""
        tiers: dict[int, list[dict]] = {}
        for agent_name, config in self.dag_config.get("agents", {}).items():
            tier = config.get("tier", 0)
            tiers.setdefault(tier, []).append({
                "name": agent_name,
                **config,
            })
        return dict(sorted(tiers.items()))

    async def run(
        self,
        profiles: dict[str, Any],
        user_context: dict[str, Any],
        execute_sql: Any = None,
        get_sample: Any = None,
        execute_python: Any = None,
    ) -> dict[str, Any]:
        """
        Execute the full agent DAG and return merged agent_outputs.

        Args:
            profiles: enriched column/table profiles from profiler
            user_context: domain_type, entity_disambiguation, standard_exclusions, etc.
            execute_sql: async callable for validation SQL
            get_sample: async callable for sample row fetching
            execute_python: async callable for sandboxed Python execution

        Returns:
            dict with keys:
                "agent_outputs": merged dict matching renderer expectations
                "issues": all escalation items
                "questions": all assumption questions
                "cross_validation_flags": flags from post-tier validation
        """
        tiers = self._get_tiers()
        merged_outputs: dict[str, Any] = {}

        # Inject user_context items that agents might require as "upstream" outputs
        merged_outputs["entity_disambiguation"] = user_context.get("entity_disambiguation", {})
        merged_outputs["standard_exclusions"] = user_context.get("standard_exclusions", [])

        for tier_num in sorted(tiers.keys()):
            tier_agents = tiers[tier_num]

            # Build context for this tier
            ctx = AgentContext(
                profiles=profiles,
                user_context=user_context,
                upstream_outputs=dict(merged_outputs),
                execute_sql=execute_sql,
                get_sample=get_sample,
                execute_python=execute_python,
            )

            # Run all agents in this tier in parallel
            tasks = []
            for agent_config in tier_agents:
                agent_cls = _AGENT_CLASSES.get(agent_config["class"])
                if agent_cls is None:
                    continue
                agent = agent_cls()
                tasks.append(self._run_agent(agent, ctx))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Collect outputs
            for result in results:
                if isinstance(result, Exception):
                    self.all_issues.append(Issue(
                        agent="orchestrator",
                        severity="critical",
                        category="agent_failure",
                        title=f"Agent failed: {result}",
                        description=str(result),
                    ))
                    continue
                if isinstance(result, AgentOutput):
                    self.outputs[result.agent_name] = result
                    self.all_issues.extend(result.issues)
                    self.all_questions.extend(
                        q.__dict__ if hasattr(q, "__dict__") else q
                        for q in result.questions
                    )
                    # Merge data into the shared outputs
                    merged_outputs.update(result.data)

        # Cross-validation phase
        self.cross_validation_flags = self._cross_validate(merged_outputs)

        # Build final agent_outputs dict (matches renderer expectations)
        agent_outputs = self._build_agent_outputs(merged_outputs)

        return {
            "agent_outputs": agent_outputs,
            "issues": self.all_issues,
            "questions": self.all_questions,
            "cross_validation_flags": self.cross_validation_flags,
        }

    async def _run_agent(self, agent: BaseAgent, ctx: AgentContext) -> AgentOutput:
        """Run a single agent with error handling."""
        output = await agent.run(ctx)

        # Run self-validation
        validation_issues = await agent.validate(output, ctx)
        output.issues.extend(validation_issues)

        return output

    def _cross_validate(self, outputs: dict[str, Any]) -> list[CrossValidationFlag]:
        """
        Cross-validation phase — check outputs against each other.

        Rules:
        1. SCD tables joined without temporal filter → warning on joins
        2. Quality-flagged columns used as measures → severity annotation
        3. Measures depending on JV-1 rejected joins → flagged
        """
        flags: list[CrossValidationFlag] = []

        scd_tables = outputs.get("scd_tables", [])
        quality_flags = outputs.get("quality_flags", [])
        join_conflicts = outputs.get("join_conflicts", [])
        measures_mb1 = outputs.get("measures_mb1", [])
        measures_mb2 = outputs.get("measures_mb2", [])
        measures_mb3 = outputs.get("measures_mb3", [])

        # Rule 1: SCD tables in joins without temporal filter
        scd_table_names = {s["table"] for s in scd_tables if s.get("scd_type") == 2}
        for jv_key in ("joins_jv1", "joins_jv2", "joins_jv3"):
            joins = outputs.get(jv_key, [])
            for join in joins:
                right = join.get("right_table", "")
                if right in scd_table_names and not join.get("scd_warning"):
                    scd_info = next(s for s in scd_tables if s["table"] == right)
                    flags.append(CrossValidationFlag(
                        source_agent="scd_detector",
                        target_agent="join_validator",
                        flag_type="scd_join_warning",
                        detail=(
                            f"Join to SCD type-2 table '{right}' lacks temporal filter. "
                            f"Apply: {scd_info.get('safe_join_pattern', 'WHERE is_current = TRUE')}"
                        ),
                        affected_items=[join.get("join_key", "")],
                    ))

        # Rule 2: Quality-flagged columns used as measures
        flagged_cols = {(f["table"], f["column"]) for f in quality_flags
                        if f.get("severity") in ("critical", "warning")}
        for measures in (measures_mb1, measures_mb2, measures_mb3):
            for m in measures:
                key = (m.get("source_table", ""), m.get("source_column", ""))
                if key in flagged_cols:
                    flags.append(CrossValidationFlag(
                        source_agent="quality_sentinel",
                        target_agent="measures_builder",
                        flag_type="quality_measure_warning",
                        detail=f"Measure '{m.get('measure_id')}' uses quality-flagged column {key}",
                        affected_items=[m.get("measure_id", "")],
                    ))

        # Rule 3: Measures depending on rejected joins
        rejected_tables = set()
        for conflict in join_conflicts:
            if conflict.get("jv1_decision") == "EXCLUDE":
                join_str = conflict.get("join", "")
                if "→" in join_str:
                    parts = join_str.split("→")
                    rejected_tables.update(p.strip() for p in parts)

        for m in measures_mb1:
            if m.get("source_table") in rejected_tables:
                flags.append(CrossValidationFlag(
                    source_agent="join_validator",
                    target_agent="measures_builder",
                    flag_type="broken_dependency",
                    detail=(
                        f"Measure '{m.get('measure_id')}' depends on table "
                        f"'{m.get('source_table')}' which has rejected joins at JV-1 level"
                    ),
                    affected_items=[m.get("measure_id", "")],
                ))

        return flags

    def _build_agent_outputs(self, outputs: dict[str, Any]) -> dict[str, Any]:
        """
        Build the agent_outputs dict matching the structure expected by
        runtime/output/renderer.py's build_semantic_layer_from_agent_outputs().
        """
        return {
            # Tier 0 outputs
            "domain_context": outputs.get("domain_context", {}),
            "candidate_measures": outputs.get("candidate_measures", []),
            "quality_flags": outputs.get("quality_flags", []),
            "scd_tables": outputs.get("scd_tables", []),
            # Tier 1 outputs
            "joins_jv1": outputs.get("joins_jv1", []),
            "joins_jv2": outputs.get("joins_jv2", []),
            "joins_jv3": outputs.get("joins_jv3", []),
            "join_conflicts": outputs.get("join_conflicts", []),
            "measures_mb1": outputs.get("measures_mb1", []),
            "measures_mb2": outputs.get("measures_mb2", []),
            "measures_mb3": outputs.get("measures_mb3", []),
            "measure_conflicts": outputs.get("measure_conflicts", []),
            "grain_gd1": outputs.get("grain_gd1", []),
            "grain_gd2": outputs.get("grain_gd2", []),
            "grain_gd3": outputs.get("grain_gd3", []),
            "grain_conflicts": outputs.get("grain_conflicts", []),
            "business_rules": outputs.get("business_rules", []),
            "open_questions": outputs.get("open_questions", []),
            "glossary": outputs.get("glossary", {}),
            # User context (passed through)
            "entity_disambiguation": outputs.get("entity_disambiguation", {}),
            "standard_exclusions": outputs.get("standard_exclusions", []),
        }

    async def rerun_affected(
        self,
        changed_inputs: list[str],
        profiles: dict[str, Any],
        user_context: dict[str, Any],
        execute_sql: Any = None,
        get_sample: Any = None,
        execute_python: Any = None,
    ) -> dict[str, Any]:
        """
        Targeted re-run: only re-run agents affected by changed inputs.

        Args:
            changed_inputs: list of output keys that changed
                           (e.g. ["standard_exclusions", "entity_disambiguation"])
        """
        tiers = self._get_tiers()

        # Find agents that depend on any changed input
        affected_agents: set[str] = set()
        for agent_name, config in self.dag_config.get("agents", {}).items():
            requires = config.get("requires", [])
            if any(inp in changed_inputs for inp in requires):
                affected_agents.add(agent_name)
                # Also add anything that depends on this agent's outputs
                for output_key in config.get("produces", []):
                    changed_inputs.append(output_key)

        # Re-run only affected agents, preserving existing outputs for unaffected ones
        merged_outputs = dict(self._build_agent_outputs(
            {k: v.data for v in self.outputs.values() for k, v2 in v.data.items()}
            if self.outputs else {}
        ))
        merged_outputs["entity_disambiguation"] = user_context.get("entity_disambiguation", {})
        merged_outputs["standard_exclusions"] = user_context.get("standard_exclusions", [])

        for tier_num in sorted(tiers.keys()):
            tier_agents = [a for a in tiers[tier_num] if a["name"] in affected_agents]
            if not tier_agents:
                continue

            ctx = AgentContext(
                profiles=profiles,
                user_context=user_context,
                upstream_outputs=dict(merged_outputs),
                execute_sql=execute_sql,
                get_sample=get_sample,
                execute_python=execute_python,
            )

            tasks = []
            for agent_config in tier_agents:
                agent_cls = _AGENT_CLASSES.get(agent_config["class"])
                if agent_cls:
                    tasks.append(self._run_agent(agent_cls(), ctx))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, AgentOutput):
                    self.outputs[result.agent_name] = result
                    merged_outputs.update(result.data)

        self.cross_validation_flags = self._cross_validate(merged_outputs)
        return {
            "agent_outputs": self._build_agent_outputs(merged_outputs),
            "issues": self.all_issues,
            "questions": self.all_questions,
            "cross_validation_flags": self.cross_validation_flags,
        }
