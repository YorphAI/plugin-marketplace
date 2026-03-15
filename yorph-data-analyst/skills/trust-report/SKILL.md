---
name: trust-report
description: Generate a transparency summary covering assumptions, caveats, secondary observations, and a pipeline recap. Load this skill every time you deliver analysis results — it is a required part of the delivery phase alongside insights and visualizations. Without it, the user has no way to judge the credibility of the output. Also load it when the user asks "what assumptions did you make", "show me the trust report", "full report", "I want to share this with my team", or any request for transparency about the analysis.
---

# Skill: Trust Report

A comprehensive transparency document the user can review or share with their team. It answers: "should I trust this output, and what should I know before acting on it?"

This is an opt-in deliverable — the user chose to see it, so be thorough. But every sentence must earn its place: state facts, never speculate, and be extremely economical with words.

---

## Inputs

1. **Pipeline Builder result summary** — step-by-step execution log, row counts, validation results (pass/warnings/caveats), assumptions made during execution
2. **Architecture plan** — the approved steps and any user-confirmed decisions
3. **Insights output** — the headline findings (so the trust report can surface secondary findings that didn't make the cut)
4. **Glimpse profile** — source data characteristics
5. **Validation summary** — overall status, warnings, fixes applied, caveats

---

## Report structure

### 1. Step-by-step summary

Translate each pipeline step into a plain-English description of what it did in business terms. The user should be able to read this and understand the entire analysis without any technical knowledge.

For each step:
- **What it did**: one sentence in business terms. "Combined your orders with your customer list, keeping only customers who placed at least one order."
- **Row count**: how many records going in, how many coming out. Only mention if the change is notable (e.g., "kept 12,400 of 15,000 orders after removing duplicates").

Do not describe SQL logic, join types, or column operations. Describe business actions.

### 2. Assumptions

Every business logic choice baked into the pipeline. Be exhaustive — if the pipeline made a choice, it belongs here. Each assumption is one concise sentence.

**Categories to cover:**

**Temporal definitions:**
- Week start day (Monday vs. Sunday)
- Month/quarter/fiscal year boundaries
- Time zones applied to timestamps
- Date range used for the analysis (and what was excluded)

**Dimension definitions:**
- How derived categories were defined (e.g., "churned" = no events in last 90 days, "enterprise" = ARR > $100K)
- How cohorts were assigned (signup date rounded to month/week/quarter)
- Geographic groupings (e.g., "APAC" includes Australia, Japan, Singapore, India)
- Any categorical mappings or consolidations (e.g., "Other" bucket for low-frequency values)

**Metric definitions:**
- How each computed metric was calculated (e.g., "retention rate = users active in period N / users in cohort at period 0")
- Aggregation method used (sum vs. mean vs. median) and why it matters
- Whether counts are distinct or non-distinct, and the implications
- Numerator and denominator definitions for any ratio

**Handling choices:**
- How nulls were treated (excluded, imputed, flagged) and for which columns
- How outliers were treated (capped, removed, kept) and what thresholds were used
- How duplicates were identified and resolved
- Any rows excluded by filters and the reason

### 3. Observations

Facts about the data and output the user should know. Not data bugs (validation caught those) — but coverage limitations, caveats, and secondary patterns.

**Surface data quality issues that cannot be fixed.** If validation found source data problems that the pipeline worked around but didn't resolve (e.g., 30% of orders have no region, an entire month is missing from the source), report them here. These are facts the user needs to weigh when interpreting the results.

**Categories:**
- **Coverage gaps**: missing time periods, missing segments, incomplete data for certain dimensions
- **Sample size warnings**: segments or cohorts with very few data points where trends may not be reliable. State the count.
- **Skew and concentration**: if results are dominated by a small number of entities (e.g., one customer drives 40% of revenue), note it
- **Secondary findings**: patterns noticed during the insights step that didn't make the top 5 but are still noteworthy. State the fact; do not interpret.
- **Validation warnings**: any checks that passed with caveats (from the validation summary)

### 4. Suggestions

Forward-looking recommendations. Not about what was done — about what could be done next.

- **Alternative approaches** the user could consider (e.g., "this analysis used sum; a median-based view would reduce outlier influence")
- **Deeper analysis** directions worth pursuing (e.g., "APAC drove most of the growth — a country-level breakdown within APAC could identify the specific driver")
- **Scope extensions** (e.g., "adding return data would allow net revenue analysis instead of gross")
- **Known limitations** of the current approach and what would fix them

Each suggestion is one sentence stating the recommendation and one sentence stating why.

### 5. Validation summary

Pull directly from the Pipeline Builder's validation output:
- Overall status (pass / pass with warnings)
- Any fixes that were applied during validation (what was wrong, what was corrected)
- Row count journey (source rows → final output rows, with major drop-off points named)
- Caveats the validation flagged for the user

---

## Output format

```
## Trust Report

### What we did
1. [Step 1 plain-English summary]
2. [Step 2 plain-English summary]
...

### Assumptions
- [One assumption per bullet. Be exhaustive.]
- ...

### Things to know
- [Coverage gaps, sample size warnings, secondary findings, data quality issues that couldn't be fixed]
- ...

### Suggestions for further analysis
- [Recommendation + why]
- ...

### Data quality
- Status: [Pass / Pass with warnings]
- Source rows: [N] → Final output rows: [N]
- [Any fixes applied or warnings]
```

---

## Principles

- **State facts, never speculate.** "30% of orders have no region assigned" — not "this might be because the region field was added later."
- **Be exhaustive on assumptions.** Every choice the pipeline made is an assumption. If the user's colleague asks "why did you define churn as 90 days?" — the answer should be in this report.
- **Be concise per item.** Thorough means many items, not long items. Each bullet is 1–2 sentences maximum.
- **No jargon.** Same communication rules as the rest of the Orchestrator: plain language, business terms, no SQL or code.
- **Do not repeat insights.** The insights skill already delivered the headline findings. The trust report surfaces what's underneath — assumptions, caveats, and secondary observations. Don't rehash the top 5.
