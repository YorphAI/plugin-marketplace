---
name: produce-pipeline
description: Use this skill to translate the approved architecture plan into executable Python/pandas code and run it against the sample. Triggered automatically after sampling completes.
---

# Skill: Produce Pipeline

Translate the Orchestrator's approved architecture plan into clean, executable code. Run against the sample.

## Code structure conventions
- One function per named architecture step
- Function names match the step names from the plan (e.g., `remove_duplicate_orders()`)
- Clear comments at the top of each function explaining what it does and why
- No magic numbers — thresholds, window sizes, etc. as named constants or parameters
- Capture intermediate outputs (row counts, column stats) after each step for validation

## Execution flow
1. Execute steps sequentially against the sample
2. After each step, log: row count in, row count out, any warnings
3. If a step fails, return a clear error summary to the Orchestrator — do not guess at a fix and silently retry
4. After all steps pass, hand off to the `validate` skill

## SQL recipes

When the architecture plan specifies an analytical methodology, use the appropriate SQL recipe as a reference for the Python/pandas implementation. When the pipeline will later be translated to SQL in `scale-execution`, write the Python version to be structurally similar for easier translation.

See `sql-recipes.md` for reference implementations.

## Semantic enrichment and joining

When the architecture plan includes a semantic enrichment or semantic join step, load `shared/semantic-join/SKILL.md` for the implementation pattern. The three-phase approach: sample → propose extraction schema → extract features at linear cost → use extracted columns for the downstream goal (join, group, filter, dedup). The LLM is used to generate concept mappings, not called per-row.

## Complex chart data requirements

Some chart types require the pipeline to produce a specific data shape. When the architecture plan calls for one of these charts, load the relevant shared skill and produce exactly the required output:

- **Waterfall / bridge / walk** → load `shared/charts/waterfall.md`. Must produce `[label, value, bar_type, sort_order]` and run `validate_waterfall()` before returning results. The `compute_waterfall_bars()` function runs at dashboard build time, not in the pipeline itself — the pipeline just needs to produce the clean input table.
- **Cohort retention / cohort revenue** → load `shared/charts/cohort-heatmap.md`. Must produce two tables: the long-format heatmap table and the absolute-time stacked bar table. Run `validate_cohort_table()` before returning. The `compute_cohort_retention()` function in the shared skill is the canonical implementation — use it directly.

## Handoff to validate
After execution, pass to `validate`:
- The transformed sample dataframe(s)
- Step-by-step execution log (row counts, warnings)
- The architecture plan (so validate can check each step's intent against its output)
