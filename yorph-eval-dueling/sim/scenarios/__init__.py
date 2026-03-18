"""Simulation scenarios for stress-testing the semantic layer agent."""
from .base import Scenario, DataQualityIssue, GroundTruth
from .ecommerce import ECOMMERCE_SIMPLE, ECOMMERCE_MEDIUM, ECOMMERCE_COMPLEX
from .saas import SAAS_SIMPLE, SAAS_MEDIUM
from .marketing import MARKETING_SIMPLE, MARKETING_MEDIUM
from .finance import FINANCE_SIMPLE, FINANCE_MEDIUM

ALL_SCENARIOS: dict[str, "Scenario"] = {
    "ecommerce_simple":   ECOMMERCE_SIMPLE,
    "ecommerce_medium":   ECOMMERCE_MEDIUM,
    "ecommerce_complex":  ECOMMERCE_COMPLEX,
    "saas_simple":        SAAS_SIMPLE,
    "saas_medium":        SAAS_MEDIUM,
    "marketing_simple":   MARKETING_SIMPLE,
    "marketing_medium":   MARKETING_MEDIUM,
    "finance_simple":     FINANCE_SIMPLE,
    "finance_medium":     FINANCE_MEDIUM,
}
