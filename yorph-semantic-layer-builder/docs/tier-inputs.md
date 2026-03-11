# Tier Inputs

This document describes the outputs produced by Tier 0 agents. Referenced by any Tier 1 agent that consumes upstream outputs.

---

## Available Tier 0 outputs

### From Schema Annotator

- **`domain_context`** — table domain classifications (Revenue, Customer, Product, etc.) and entity types (fact vs dimension). Each table entry includes `annotated_columns[]` with semantic roles (measure_candidate, foreign_key, dimension, time_column, flag, identifier, text_label).

- **`candidate_measures`** — pre-ranked list of measure candidates with confidence scores (VERIFIED > HIGH > MEDIUM > LOW). User-provided metrics are marked `source=user_provided` with `confidence=VERIFIED` — these **MUST** appear in every output tier without exception.

### From Quality Sentinel

- **`quality_flags`** — columns with data quality issues. Each flag has `{table, column, issue, severity, recommendation}`.
  - **CRITICAL** severity: do NOT define measures or validate joins on these columns. They will produce wrong numbers.
  - **WARNING** severity: add a warning annotation to any output that depends on this column.
  - **INFO** severity: noteworthy but non-blocking.

### From SCD Detector

- **`scd_tables`** — Type-2 slowly-changing dimensions. Each entry has `{table, scd_type, validity_columns[], safe_join_pattern, warning}`.
  - For any join targeting an SCD table, you **MUST** add the recommended temporal filter (e.g. `WHERE is_current = TRUE`).
  - Joins to SCD tables without temporal filters are flagged as unsafe.

## How to access

Tier 0 outputs are available in your `AgentContext.upstream_outputs` dict, keyed by the output name (e.g. `upstream_outputs["domain_context"]`).
