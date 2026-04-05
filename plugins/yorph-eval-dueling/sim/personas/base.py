"""
Persona base class.

A Persona is a scripted user archetype with:
  - A description (who this person is, what they know)
  - A sequence of ConversationTurns (what they say at each phase)
  - Behavioural flags (do they upload docs? do they challenge recommendations?)
  - A data_dictionary fixture (CSV content) to upload, if applicable

The runner uses the persona to output a conversation script the tester can
paste into Claude. Each turn is tagged with the agent workflow phase it
corresponds to, so testers know when to send each message.

Turns are templates — {scenario_description}, {primary_table}, etc. are
filled in by the runner based on the loaded scenario.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ConversationTurn:
    """One user message in the scripted conversation."""
    phase: str          # "connect" | "clarify" | "build" | "review" | "save"
    label: str          # Short description of this turn (for the script header)
    message: str        # The exact message to paste into Claude
    notes: str = ""     # Tester notes — what to watch for in the agent's response


@dataclass
class Persona:
    """A scripted user archetype."""
    name: str
    title: str          # e.g. "Data Architect"
    description: str    # Who this person is
    uploads_docs: bool  # Does this persona upload a data dictionary?
    data_dictionary: str | None  # CSV content of the data dictionary, if any
    challenges_joins: bool       # Does this persona push back on join recommendations?
    skips_questions: bool        # Does this persona try to skip clarifying questions?
    preferred_recommendation: int  # 1=Conservative, 2=Comprehensive, 3=Balanced
    turns: list[ConversationTurn] = field(default_factory=list)

    def render_script(self, scenario_context: dict) -> str:
        """
        Render a human-readable conversation script by substituting
        scenario_context variables into turn messages.

        scenario_context keys:
          scenario_name, domain, complexity, description,
          primary_table, table_list (comma-sep), data_quality_issues (bullet list)
        """
        lines = [
            f"# Persona Script: {self.title} ({self.name})",
            f"",
            f"> **Scenario:** {scenario_context.get('scenario_name', 'unknown')}  ",
            f"> **Domain:** {scenario_context.get('domain', '')}  ",
            f"> **Complexity:** {scenario_context.get('complexity', '')}",
            f"",
            f"---",
            f"",
            f"## Who this persona is",
            f"",
            f"{self.description}",
            f"",
            f"## Behavioural flags",
            f"- Uploads data dictionary: {'Yes' if self.uploads_docs else 'No'}",
            f"- Challenges join recommendations: {'Yes' if self.challenges_joins else 'No'}",
            f"- Tries to skip clarifying questions: {'Yes' if self.skips_questions else 'No'}",
            f"- Preferred recommendation: {['Conservative', 'Comprehensive', 'Balanced'][self.preferred_recommendation - 1]}",
            f"",
            f"---",
            f"",
            f"## Conversation Script",
            f"",
            f"Paste each turn into Claude **in order**. Wait for the full response before sending the next.",
            f"",
        ]

        for i, turn in enumerate(self.turns, 1):
            try:
                message = turn.message.format(**scenario_context)
            except KeyError:
                message = turn.message  # leave unformatted if key missing

            lines += [
                f"### Turn {i} — {turn.label}",
                f"**Phase:** `{turn.phase}`",
                f"",
                f"```",
                message,
                f"```",
            ]
            if turn.notes:
                lines += [f"", f"> **Watch for:** {turn.notes}"]
            lines.append("")

        if self.uploads_docs and self.data_dictionary:
            lines += [
                "---",
                "",
                "## Data Dictionary to Upload",
                "",
                "Save the following as `data_dictionary.csv` and upload it when the agent asks for documents:",
                "",
                "```csv",
                self.data_dictionary.strip(),
                "```",
                "",
            ]

        return "\n".join(lines)
