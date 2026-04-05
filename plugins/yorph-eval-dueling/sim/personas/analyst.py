"""
Analyst persona: Business analyst who knows the domain but not the technical details.

Behaviour:
- Knows what the business does but not SQL/data architecture
- Confused by terms like 'grain', 'cardinality', 'additivity'
- Asks clarifying questions in response to agent prompts
- No data dictionary — going from memory
- Wants Conservative (rec 1) — simpler is better
- Will mis-state some things (e.g., say "total sales" when they mean revenue)
"""

from .base import Persona, ConversationTurn

ANALYST = Persona(
    name="analyst",
    title="Business Analyst",
    description=(
        "A business analyst who works closely with the sales and operations teams. "
        "Understands the business domain deeply but has limited SQL knowledge. "
        "Uses business terms like 'total sales', 'customer count', 'conversion'. "
        "Will struggle with technical concepts like 'grain' or 'cardinality' and "
        "will ask for plain-language explanations. No data dictionary — relies on memory."
    ),
    uploads_docs=False,
    challenges_joins=False,
    skips_questions=False,
    preferred_recommendation=1,
    data_dictionary=None,
    turns=[
        ConversationTurn(
            phase="connect",
            label="Connect and profile",
            message=(
                "Hi! I want to build a semantic layer for our {domain} data. "
                "Can we get started? I'm not sure exactly what all our tables are called "
                "but I think the main one is something like {primary_table}."
            ),
            notes=(
                "Agent should ask for warehouse connection details. "
                "Watch for whether it guides the user helpfully through the connection process."
            ),
        ),
        ConversationTurn(
            phase="connect",
            label="Confirm simulation warehouse",
            message=(
                "Let's use the simulation warehouse for now."
            ),
            notes="Agent should call connect_warehouse(warehouse_type='simulation').",
        ),
        ConversationTurn(
            phase="clarify",
            label="Answer clarifying questions — business language",
            message=(
                "This data is about {description}. "
                "We mostly care about total sales, customer numbers, "
                "and how many orders we get each month. "
                "I'm not sure which tables are 'fact' vs 'dimension' — what does that mean? "
                "Oh, and we have some data quality issues — I know some orders have 'N/A' "
                "as a status but I don't know why."
            ),
            notes=(
                "Agent should explain fact vs dimension in plain English. "
                "It should pick up on 'N/A status' as a data quality issue (encoded null). "
                "Watch for whether it asks follow-up questions clearly."
            ),
        ),
        ConversationTurn(
            phase="build",
            label="Ask a confused question about grain",
            message=(
                "When you asked about 'grain' earlier — what does that mean exactly? "
                "Is it like... the level of detail in the data? "
                "Also, can we track 'customer lifetime value'? "
                "I'm not sure if that's in the data or if we'd need to calculate it."
            ),
            notes=(
                "Agent should explain grain in plain language with a concrete example. "
                "For CLV: it should check if there's a column, "
                "or explain how to derive it from orders."
            ),
        ),
        ConversationTurn(
            phase="review",
            label="Accept Conservative recommendation",
            message=(
                "The Conservative one sounds right for us — we don't need too many metrics, "
                "just the basics. "
                "Can you make sure 'total sales' is included? "
                "And what's the difference between 'total revenue' and 'total sales' — "
                "are those the same thing?"
            ),
            notes=(
                "Agent should confirm rec 1 is selected. "
                "It should clarify the revenue vs sales terminology and align to what's in the schema. "
                "Watch for whether it handles the business-language confusion well."
            ),
        ),
        ConversationTurn(
            phase="save",
            label="Save in a simple format",
            message=(
                "Can you save this? I don't know what dbt is — "
                "is there a simpler format I can share with my team? "
                "Maybe JSON or just a document explaining everything?"
            ),
            notes=(
                "Agent should recommend JSON or plain YAML + the readme. "
                "It should save with format='json' (or 'all') "
                "and point the user to the companion readme."
            ),
        ),
    ],
)
