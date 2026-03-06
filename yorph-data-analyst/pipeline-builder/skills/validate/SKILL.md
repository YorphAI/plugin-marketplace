---
name: validate
description: Use this skill after every pipeline execution — both sample and full-scale — to rigorously check outputs before proceeding. Triggered automatically by the Pipeline Builder after produce-pipeline and again after scale-execution.
---

# Skill: Validate

Even if every step executes without errors, the transformation logic can still be wrong. This skill catches silent failures by comparing output profiles against source profiles and applying common-sense domain checks.

**Run this skill twice**: once on the sample output (after `produce-pipeline`), once on the full-scale output (after `scale-execution`). Do not return results to the Orchestrator until full-scale validation passes.

---

## Inputs

You need three things to validate:

1. **Source profile** — the glimpse output from the connect/sample step (schema, dtypes, row count, null rates, distinct counts, numeric ranges)
2. **Step outputs** — the transformed dataframe(s) after each pipeline step, plus the execution log (row counts in/out, warnings)
3. **Architecture plan** — the ordered steps with plain-English descriptions, so you can check each step's output against its stated intent

---

## Validation sequence

### 1. Re-profile the output

After execution, profile every output dataframe the same way the glimpse skill profiles source data. For each column, compute:
- `total_rows`
- `pct_null`
- `n_unique` (approx distinct)
- `data_type`
- For numerics: `min`, `max`, `mean`, `median`, `p25`, `p75`

This output profile is what you compare against the source profile.

### 2. Run per-step checks

Walk through each pipeline step in order. For each step, check whether the output is consistent with what the step was supposed to do (per the architecture plan). If a step was supposed to "remove duplicate orders," verify that the row count dropped and that the key column's distinct count equals the row count.

### 3. Run end-to-end checks

After per-step checks pass, run the full checklist below against the final output.

### 4. Run chart-specific validation

If the pipeline produces output for specialized chart types, run the relevant validation function:
- Waterfall → `validate_waterfall()` from `shared/charts/waterfall.md` (closure check: start + deltas = end)
- Cohort → `validate_cohort_table()` from `shared/charts/cohort-heatmap.md` (period 0 = 100%, no negatives, no missing p0 cohorts)

### 5. Check output tractability for insights

Verify that the final output is consumable by the Orchestrator's insights and visualization steps. See the "Tractability check" section below.

---

## Validation checklist

### A. Empty results
`total_rows = 0` on any output table.

- Compare against source row count — did the source have data?
- Most likely cause: an overly restrictive WHERE filter, an INNER JOIN on a mismatched key, or a date range that excludes all rows.
- **Action**: This is always a failure. Diagnose and fix before proceeding.

### B. Null inflation
`pct_null > 0.5` on a column that was not predominantly null in the source, or on a column that was computed/imputed by the pipeline.

- Check JOIN type — a LEFT JOIN on a mismatched key inflates nulls on the right-side columns.
- Check whether COALESCE or null handling was applied as planned.
- A computed column (ratio, difference, etc.) that is >50% null means the inputs are misaligned.
- **Action**: Investigate the step that introduced the nulls. If the null rate is expected (e.g., the column is legitimately sparse), document it in the validation summary. Otherwise, fix.

### C. Category collapse
A categorical column's `n_unique` in the output is significantly lower than in the source (e.g., dropped from 50 to 3).

- Likely causes: over-aggressive filtering, incorrect GROUP BY, wrong JOIN condition.
- Compare the unique values in the output to the source — which categories disappeared?
- **Action**: If the collapse is intentional (e.g., filtering to top 3 regions), document it. If unintentional, fix the step.

### D. Row count inflation
Output has significantly more rows than expected — often a sign of a many-to-many JOIN or a missing GROUP BY.

- Compare output row count to the expected grain. If the output should be one row per customer per month, verify: `n_rows ≈ n_customers × n_months`.
- A JOIN producing more rows than the left table is a strong signal of duplicated keys on the right table.
- **Action**: Fix the JOIN or add a deduplication step.

### E. Unreasonable numeric ranges
`min` or `max` values that violate common sense.

- Negative values where only positive are valid (e.g., `revenue < 0` when returns are excluded, `retention_rate < 0`).
- Values exceeding logical bounds (e.g., `retention_rate > 1.0`, `conversion_rate > 100%`).
- Extremely large values from division by near-zero denominators.
- **Action**: For division-by-zero outliers — cap, flag, or exclude. Add a column recording which rows were modified. If downstream aggregations are affected, prefer median over mean to resist skew. For domain violations, trace back to the step that produced the value.

### F. Realism of calculated outputs
Apply domain common sense to aggregate statistics. Reference `domain-rules.md` for domain-specific constraints.

Examples:
- Minimum profit should never exceed minimum revenue.
- Maximum discount rate should never exceed 100%.
- Sum of component parts should equal the total (if the pipeline computes both).
- Period-over-period change of >10× is almost always a bug unless the base is very small.

**Watch for ambiguously named columns.** If "sales" means units in the source but you're treating it as dollars, every downstream calculation is wrong. Cross-reference the glimpse output's value ranges to confirm interpretation.

- **Action**: If realism is violated, trace the calculation back step by step. The most common root cause is misinterpreting a column's meaning or unit.

### G. Schema completeness
Every column specified in the architecture plan exists in the output with the expected data type.

- Missing columns mean a step was skipped or silently failed.
- Wrong data types (e.g., a date column stored as a string) will break downstream charting.
- **Action**: Fix the step that was supposed to produce the missing/mistyped column.

### H. Duplicate key check
If the output should have a unique key (e.g., one row per order_id), verify uniqueness.

- `n_unique` on the key column should equal `total_rows`.
- If not, find which step introduced duplicates (usually a JOIN).
- **Action**: Deduplicate or fix the JOIN.

---

## Tractability check

The pipeline output must be consumable by the Orchestrator for insights and visualization. At least some final-step tables should be small enough to generate insights by inspection and chart-ready.

### What "tractable" means

- At least one output table should be a **summary table** — pre-aggregated, low-dimensionality, directly interpretable.
- A good summary table has:
  - An axis column suitable for charting: dates/categories with ≤100 values (≤24 if categorical), 100% unique, not raw numeric
  - One or more metric columns (numeric, aggregated)
  - Reasonable row count (≤500 rows for a summary; ideally ≤50 for a bar chart, ≤100 for a time series)

### When the output is not tractable

If every output table is high-dimensional (hundreds of columns, thousands of rows with no aggregation), the Orchestrator cannot produce useful insights or charts from it.

**Action**: Add aggregation steps to create summary tables. For each key dimension worth exploring (region, product category, time period, channel), produce a summary step that aggregates the primary metrics. These are additional pipeline steps — they do not replace the detailed output; they supplement it.

How many summary steps: enough to cover the user's goal. Typically 2–4. Each summary step should correspond to one potential chart or insight. Cap at ~6 — more than that means the pipeline is trying to do too much.

---

## Validation outcome

### Pass
All checks pass. Proceed to the next phase (scale-execution after sample validation; return results to Orchestrator after full-scale validation).

### Fail — fixable
One or more checks fail but the root cause is clear. Fix the offending step, re-execute from that step forward, and re-validate.

Do not silently fix and move on — log every fix in the execution log so the validation summary captures what was corrected.

### Fail — ambiguous
A check fails but the root cause is not clear, or the fix requires a business-logic decision (e.g., "should negative revenue rows be excluded or flagged?"). Return the issue to the Orchestrator with:
- Which check failed
- What the data shows (concrete numbers)
- What decision is needed

The Orchestrator will consult the user and return with a clarified instruction.

---

## Validation summary (returned to Orchestrator)

The validation section of the result summary must include:

| Field | Content |
|---|---|
| Overall status | Pass / Pass with warnings / Fail |
| Checks run | List of all checks performed |
| Warnings | Any soft issues (e.g., high but expected null rate, documented category collapse) |
| Fixes applied | Any steps that were corrected during validation, and what changed |
| Row counts | Per-step row count in/out |
| Output profile | Key column stats for the final output (null rates, distinct counts, numeric ranges) |
| Tractability | Which summary tables are available and their schemas |
| Caveats | Anything the Orchestrator should surface to the user (e.g., "12% of orders had no region; these were excluded from regional breakdowns") |
