"""
Rushed persona: Manager who wants results fast, skips everything optional.

Behaviour:
- Wants to skip clarifying questions ("just use defaults")
- No data dictionary
- Accepts whatever recommendation the agent proposes without debate
- Sends very short, terse messages
- Tests whether the agent handles minimal input gracefully and still produces
  a useful output (doesn't just break or produce empty recommendations)
- Preferred recommendation: whatever the agent defaults to (3)
"""

from .base import Persona, ConversationTurn

RUSHED = Persona(
    name="rushed",
    title="Data Manager (Rushed)",
    description=(
        "A data platform manager under deadline pressure. "
        "Has 15 minutes. Wants to get something working fast. "
        "Will skip every optional step. Tests whether the agent can "
        "produce a reasonable semantic layer with minimal user input."
    ),
    uploads_docs=False,
    challenges_joins=False,
    skips_questions=True,
    preferred_recommendation=3,
    data_dictionary=None,
    turns=[
        ConversationTurn(
            phase="connect",
            label="Short connect request",
            message="Connect to simulation and profile everything.",
            notes=(
                "Agent should handle the terse request gracefully and proceed. "
                "Watch for whether it asks unnecessary questions."
            ),
        ),
        ConversationTurn(
            phase="clarify",
            label="Skip all clarifying questions",
            message=(
                "It's {domain} data. Just use whatever defaults make sense. "
                "I don't have time for questions right now."
            ),
            notes=(
                "Agent should note what assumptions it's making and proceed. "
                "It should NOT refuse to continue or demand answers. "
                "Watch for whether it documents its assumptions in open_questions."
            ),
        ),
        ConversationTurn(
            phase="review",
            label="Accept default recommendation",
            message="Whatever you recommend is fine. Go with it.",
            notes=(
                "Agent should default to Balanced (rec 3) and explain briefly why. "
                "Watch for whether it still surfaces the most critical open questions "
                "even when the user tries to skip them."
            ),
        ),
        ConversationTurn(
            phase="save",
            label="Save quickly",
            message="Save it. All formats. Done.",
            notes=(
                "Agent should save format='all' with defaults. "
                "Should NOT ask additional questions about filename or project name — "
                "use sensible defaults."
            ),
        ),
    ],
)
