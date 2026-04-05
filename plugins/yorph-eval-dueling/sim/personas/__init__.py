"""User personas for semantic layer agent stress tests."""
from .base import Persona, ConversationTurn
from .expert import EXPERT
from .analyst import ANALYST
from .skeptic import SKEPTIC
from .rushed import RUSHED

ALL_PERSONAS: dict[str, "Persona"] = {
    "expert":   EXPERT,
    "analyst":  ANALYST,
    "skeptic":  SKEPTIC,
    "rushed":   RUSHED,
}
