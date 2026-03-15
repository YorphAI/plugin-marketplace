---
name: design-transformation-architecture
description: Design the transformation and analysis plan in plain English before any code is written. Load this skill any time you need to plan, architect, or design data transformation steps — even if the user doesn't explicitly ask for a "plan." If you're about to decide what transformations to apply, what order to run them in, or how to structure an analysis, you need this skill. It contains domain rules, cleaning patterns, and methodology templates that prevent common mistakes. Never design transformation steps without it.
---

# Skill: Architecture

Design the full transformation and analysis pipeline as named, ordered, plain-English steps. No code at this stage.

## Inputs required
- Glimpse summary from the `connect-data-source` skill (schema, dtypes, statistics, row count)
- User's goal in plain English
- Domain context (inferred or asked)

## Subskills — loading rules

**Always load:**
- `docs/architecture/data-cleaning.md` — every pipeline needs cleaning decisions
- `docs/architecture/domain-rules.md` — domain context shapes every decision

**Load when the user's goal involves explaining why a metric changed, comparing periods, or attribution:**
- `docs/architecture/attribution-analysis.md` — variance analysis, RCA, cohort/retention, funnel analysis, causal analysis

**Load when the data has messy text columns that need matching, grouping, filtering, or enrichment:**
- `skills/semantic-join/SKILL.md` — semantic feature extraction and joining. Load when the glimpse reveals high-cardinality text with near-duplicate values, when a JOIN between tables has no exact key match, when GROUP BY on raw text would produce splintered groups, or when the user asks to categorize, normalize, or deduplicate text fields. The architecture plan must specify which columns need semantic extraction and what the downstream use is (join, group, filter, dedup).

**Load when the pipeline will produce a waterfall, bridge, or walk visualization:**
- `docs/charts/waterfall.md` — required data shape, column definitions, and the closure validation check. The architecture plan must specify the correct pipeline output (label, value, bar_type, sort_order) for the Pipeline Builder to produce.

**Load when the pipeline will produce cohort retention or cohort revenue analysis:**
- `docs/charts/cohort-heatmap.md` — required output tables (long-format heatmap + absolute-time stacked bar), period definition, contractual vs non-contractual distinction. The architecture plan must specify the correct pipeline output shape and define the cohort period (week/month/quarter) and activity window before handing off.

## How to architect

1. **Classify the goal.** Is this: exploratory analysis, metric investigation (why did X change?), reporting/dashboarding, ML feature prep, or operational pipeline?

2. **Draft the step sequence.** Every pipeline follows this skeleton — skip steps that don't apply:
   - Cleaning & standardization
   - Joins & enrichment
   - Filtering & scoping
   - Aggregation & metric computation
   - Analysis-specific steps (PVM, RCA, cohort, funnel, etc.)

3. **Name each step plainly.** The user must be able to read the plan and understand what each step does without technical knowledge. Example: "Remove duplicate orders" not "Deduplicate on composite key (order_id, line_item_id)."

4. **Flag decision points.** Where the pipeline requires a choice (impute vs. flag nulls, gross vs. net revenue, fiscal vs. calendar year), surface the trade-off to the user. Batch all decision points into a **single round of questions**. For each, present your recommended approach and ask for confirmation — not open-ended "what do you want?" If the user doesn't answer a question, proceed with your recommendation and document the assumption.

5. **Present the plan for approval.** Show the user: the ordered steps, any decisions you need from them, and what the expected output looks like. Get explicit sign-off before handing off to the Pipeline Builder.

## Step design rules

### Consolidation
- Steps that are **independent and operate on the same source** → combine into one step. Example: imputing nulls across multiple columns in one table is one step, not one per column.
- Steps that are **sequentially dependent** (output of one feeds into the next) → keep separate. Granularity helps with debugging and validation.
- Steps that serve **different analytical purposes** → keep separate even if they could technically be combined. Each step should have one clear job.

### Step count
Target **4–8 steps**. Fewer than 4 usually means unrelated logic is lumped together. More than 8 usually means steps are split too finely — consolidate independent operations.

### Anticipate transformation side effects
Plan for nulls, outliers, and edge cases **created by the pipeline itself**, not just those in the source data:
- **LEFT JOINs** introduce NULLs in unmatched rows — plan a post-join null handling step if needed
- **Division** creates infinities and division-by-zero — specify how to handle (flag, cap, exclude)
- **Filtering** may create empty groups downstream — specify what happens to metrics when a segment has zero rows
- **Aggregation** may hide outliers or create misleading averages — consider whether median or trimmed mean is more appropriate

Flag these in the plan so the Pipeline Builder handles them explicitly rather than discovering them at runtime.

---

## Plan ambiguity — when to choose vs. when to ask

When multiple valid approaches exist, decide whether to pick one or surface the choice to the user.

### Pick the best plan when:
- The plans differ only in **implementation** (alias naming, join order, computation style) but produce the same business result
- One plan is clearly **more explainable** to the end user
- One plan handles **edge cases** that others miss
- The differences are **computational** (performance, memory) not analytical

### Do NOT pick — ask the user when:
- The plans would produce **materially different result data** (e.g., net vs. gross revenue, fiscal vs. calendar year, including vs. excluding returns)
- The choice depends on **domain assumptions** the user hasn't confirmed
- Any candidate approach explicitly flags an ambiguity or requests more information

Never return a plan when the choice hinges on business logic the user has not specified. Return a concise request for clarification instead — frame it as a trade-off, not a technical question.

### Evaluation criteria (when picking)
Rank candidate approaches by:
1. **Explainability** — can the user understand what each step does?
2. **Edge case handling** — does it account for nulls, outliers, and empty groups?
3. **Visualization readiness** — does the output shape support the charts the user will need?
4. **Computational efficiency** — will it run at full scale without memory or time issues?
5. **Auxiliary value** — does it provide useful side outputs (e.g., segment-level summaries) beyond the primary ask?

---

## Structuring output for visualization

The pipeline output will be visualized. The architecture plan must think about what the dashboard needs and structure final steps accordingly.

### General principles
- Final output steps should have **clear, descriptive column names** — the column name may become a chart axis label or legend entry.
- Pre-aggregate to the grain the chart needs. Do not leave aggregation to the visualization step.
- When multiple dimensions are worth exploring, consider producing **separate summary steps per key dimension** (e.g., one step for revenue by region, another for revenue by product category). Cap at ~6 summary steps — more than that overwhelms the dashboard.

### Specialized chart output shapes

For specialized chart types, the architecture plan must specify an output shape that matches what the chart expects. Load the relevant shared skill for full specifications:

| Chart type | Required output shape | Reference |
|---|---|---|
| Waterfall / bridge | `[label, value, bar_type, sort_order]` | Load `docs/charts/waterfall.md` |
| Cohort heatmap | Two tables: retention (cohort × period_elapsed × metric) + absolute time (cohort × calendar_period × metric) | Load `docs/charts/cohort-heatmap.md` |
| Funnel | One row per stage with a single metric (e.g., `[stage, user_count]`). Pre-aggregated to stage × metric grain — no extra dimensions. | Inline — simple shape |
| Tornado | Driver column + signed impact column (e.g., `[driver, impact]` or `[variable, low_impact, high_impact]`). Sort by absolute impact descending. | Inline — simple shape |

For standard charts (bar, line, scatter, etc.), no special output shape is needed — just ensure the data is pre-aggregated and column names are self-explanatory.

---

## What the handoff to Pipeline Builder must include
- Ordered list of named steps with plain-English descriptions
- Decisions the user confirmed (with their exact wording)
- Domain rules that apply (from `docs/architecture/domain-rules.md`)
- Which analytical methodology to use, if any (from `docs/architecture/attribution-analysis.md`)
- Expected output shape for visualization — for specialized charts, reference the loaded shared skill
- Known transformation side effects to handle (e.g., "Step 3 is a LEFT JOIN — handle NULLs in the unmatched column in Step 4")
