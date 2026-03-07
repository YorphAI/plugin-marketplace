---
name: data-analysis-multi-approach
description: Use this skill whenever the user asks Claude to analyze data, calculate metrics, summarize a dataset, run a data transformation, or answer a question from data. This includes requests like "analyze this CSV", "what are the trends in this data", "calculate revenue", "how many X", "build a pipeline for Y", or any task involving numerical or tabular data. Even if the request seems simple, ALWAYS use this skill — it ensures multiple analytical approaches are run and compared so the user gets a trustworthy result rather than a single opinionated answer. Also use this skill when the user mentions a "semantic layer" or wants to define business rules, metric definitions, or join logic.
---

# Data Analysis: Multi-Approach Skill

## Core Philosophy

Don't make a single opinionated analytical choice. Instead:
1. **Identify all dimensions of ambiguity** in the question and data
2. **Run all reasonable approaches** across those dimensions
3. **Compare results** and surface divergences
4. **Recommend** the best approach (ranked), but let the user decide
5. **Update the semantic layer** with any resolved decisions

---

## Step 1: Load Context

Before writing any analysis code, check:
- Is there a `semantic_layer.md` file in the working directory or uploads? If yes, read it and use its definitions to constrain your approaches (don't re-explore already-resolved ambiguities).
- What is the data source? (CSV, Excel, SQL, DataFrame, etc.) Load it and do a quick structural scan: shape, column names, dtypes, null rates, sample rows.

---

## Step 2: Identify Dimensions of Ambiguity

Look at the user's question and the data. List every place where a reasonable analyst could make a different choice. Common dimensions:

**Metric definition**
- What exactly counts? (e.g. gross vs net revenue, completed vs all orders)
- How to handle nulls? (exclude, treat as zero, impute)
- What time window? (calendar vs rolling, inclusive/exclusive bounds)

**Aggregation**
- Mean vs median vs mode
- Sum vs count vs ratio
- Weighted vs unweighted

**Filtering / scope**
- Include or exclude outliers?
- What threshold defines an outlier? (IQR, z-score, domain rule)
- Which segments/cohorts to include?

**Joins**
- Which key to join on if multiple options exist?
- Inner vs left vs outer join?
- How to handle duplicates / fan-out?

**Granularity**
- Per user, per transaction, per day?
- Roll up or keep atomic?

Only enumerate dimensions that are actually present and materially affect the result. Don't manufacture noise.

---

## Step 3: Run All Approaches in Parallel

For each dimension with ≥2 reasonable choices, implement all variants. Use code (Python/pandas, SQL, or whatever fits the data source). Run them and capture the results.

Structure your code so it's easy to see which variant produced which result. Use clear variable/function names like `revenue_gross`, `revenue_net`, `agg_mean`, `agg_median`.

For N dimensions with K options each, you may get K^N combinations — use judgment to prune combinations that are clearly redundant or nonsensical, keeping the set **diverse and meaningful** rather than exhaustive.

---

## Step 4: Compare and Find Divergences

After running all approaches, compare results. A divergence is meaningful when:
- The numeric results differ by more than ~10% (use judgment based on context)
- Or the qualitative conclusion would change (e.g. "trend is up" vs "trend is down")
- Or the ranking of items changes

Ignore trivial differences (e.g. 1001 vs 1000 rows due to one null).

---

## Step 5: Output — Concise Divergence Report

Present a **concise summary** structured as follows:

```
## Analysis: [Question]

**Approaches run:** [brief list, e.g. "3 metric definitions × 2 aggregation methods = 6 variants"]

---

### Divergences Found

**[Dimension name]** ← most impactful first
- Option A (recommended): [description] → result: X
- Option B: [description] → result: Y
- Option C: [description] → result: Z
*Why it matters: [one sentence on impact]*

**[Next dimension]**
...

---

### Where approaches agreed
[One sentence summary of what was consistent across all variants — gives user confidence in those parts]

---

### Your decisions needed
For each divergence above, please confirm which approach to use. I'll update your semantic layer accordingly.
```

Rank options within each divergence by your best-guess recommendation (most defensible analytically), but make clear the user decides.

If there are **no meaningful divergences**, say so clearly and give the result directly.

---

## Step 6: Update the Semantic Layer

Once the user confirms their choices (or if some decisions are already resolved in an existing semantic layer), update or create `semantic_layer.md`.

If the file exists: append new decisions under the appropriate section. Do not remove or overwrite existing entries unless the user explicitly corrects one.

If the file doesn't exist: create it with this structure:

```markdown
# Semantic Layer
*LLM-readable definitions and business rules for data analysis. Load this file at the start of any analysis.*

## Metric Definitions
<!-- How to calculate specific metrics -->

## Join Logic
<!-- What joins what, on which keys, and with what type -->

## Data Quality Rules
<!-- What counts as an outlier vs. anomalous data, how to handle nulls, etc. -->

## Business Rules
<!-- Inclusions, exclusions, segment definitions, time window conventions -->

## Resolved Ambiguities
<!-- One-off decisions made during past analyses -->
```

Each entry should be a short, precise, LLM-readable statement. Example:
> **Revenue**: Sum of `order_total` where `status = 'completed'`, excluding refunded orders (`refund_amount > 0`). Does not include tax. Time-attributed to `created_at`.

---

## Notes

- Always load the semantic layer first — it's the source of truth for prior decisions.
- If the user's question is fully resolved by the semantic layer (no ambiguity), skip the multi-approach phase and just run the analysis directly.
- For very large datasets, sample intelligently rather than running all approaches on full data (but note the sampling).
- Keep code outputs visible so the user can audit.
