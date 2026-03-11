"""
Time Intelligence agent — temporal pattern analysis and time calculation generation.

Tier 1 agent — receives domain_context and candidate_measures from Tier 0.

Detects date/timestamp columns, identifies primary time dimensions per fact table,
detects or recommends a date spine, and generates time-based calculation definitions
(period-over-period, rolling windows, YTD/QTD/MTD) for every candidate measure.

Output: time_intelligence{} — date spine info, fact time dimensions, time calculations
"""

from __future__ import annotations

from typing import Any

from runtime.agents.base import BaseAgent, AgentContext, AgentOutput


class TimeIntelligenceAgent(BaseAgent):
    """Analyzes temporal patterns and generates time-based calculation definitions."""

    name = "time_intelligence"
    requires = ["profiles", "domain_context", "candidate_measures"]
    produces = ["time_intelligence"]

    async def run(self, ctx: AgentContext) -> AgentOutput:
        # Prompt-driven: Claude reads .claude-plugin/agents/time_intelligence.md
        # and generates the analysis on the fly using execute_validation_sql
        # and get_sample_slice. This stub provides the structural wiring.
        #
        # The prompt instructs Claude to:
        # 1. Identify date columns from profiles
        # 2. Determine primary time dimension per fact table
        # 3. Detect/recommend date spine
        # 4. Generate time calculation definitions for each measure
        # 5. Ask about fiscal calendar alignment
        return self._make_output(data={"time_intelligence": {}})
