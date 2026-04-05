"""
Agent package — DAG-based agent architecture for semantic layer construction.

Agents are organized into tiers:
  Tier 0 (Foundation): Schema Annotator, Quality Sentinel, SCD Detector
  Tier 1 (Analysis):   Join Validator, Measures Builder, Grain Detector,
                        Business Rules, Glossary Builder, Time Intelligence,
                        Dimension Hierarchies

The Orchestrator runs tiers in order, passing upstream outputs downstream.
"""

from .base import BaseAgent, AgentContext, AgentOutput, Issue, AssumptionQuestion, CrossValidationFlag
from .schema_annotator import SchemaAnnotator
from .quality_sentinel import QualitySentinel
from .scd_detector import SCDDetector
from .join_validator import JoinValidator
from .measures_builder import MeasuresBuilder
from .grain_detector import GrainDetector
from .business_rules import BusinessRulesAgent
from .glossary import GlossaryBuilder
from .time_intelligence import TimeIntelligenceAgent
from .dimension_hierarchies import DimensionHierarchiesAgent
from .orchestrator import Orchestrator

__all__ = [
    # Base
    "BaseAgent", "AgentContext", "AgentOutput", "Issue",
    "AssumptionQuestion", "CrossValidationFlag",
    # Tier 0
    "SchemaAnnotator", "QualitySentinel", "SCDDetector",
    # Tier 1
    "JoinValidator", "MeasuresBuilder", "GrainDetector",
    "BusinessRulesAgent", "GlossaryBuilder",
    "TimeIntelligenceAgent", "DimensionHierarchiesAgent",
    # Orchestrator
    "Orchestrator",
]
