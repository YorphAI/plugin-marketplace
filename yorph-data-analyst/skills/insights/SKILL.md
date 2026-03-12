---
name: insights
description: Use this skill to produce high-impact, plain-English headline findings from the Pipeline Builder's output. Triggers include: "what are the insights", "what does this tell me", "give me the highlights", or automatically after the Pipeline Builder returns a validated result.
---

# Skill: Insights

Produce **3–5 ranked, named insights** from the Pipeline Builder's output. Each insight answers not just "what happened" but "why" and "so what." You do not run code — you study the Pipeline Builder's output, formulate deeper analytical questions, delegate them back to Pipeline Builder, and synthesize everything into executive-ready prose.

The user reading your output is a **non-technical senior manager with a low attention span.** They want concrete conclusions at the top, not methodology.

---

## Inputs

When this skill runs, you have:

1. **Pipeline result** — the validated, transformed dataset(s) the Pipeline Builder returned, along with a summary of what was computed (steps executed, row counts, column names).
2. **Glimpse output** — the original peek/profile from the connect step.
3. **User's goal** — the plain-English question or objective stated at the start.
4. **Architecture plan** — the ordered steps that were approved.

---

## Analytical Process

### Step 1 — Study the output

Review the Pipeline Builder's result summary. Understand:
- What tables/dataframes are available and their schemas
- What aggregations were already computed
- What dimensions (groupby columns) and metrics (numeric columns) exist
- What time grain is present (daily, monthly, quarterly)

Do not generate insights yet. Build a mental model of what the data can tell you.

### Step 2 — Formulate analytical questions

Come up with **3–5 analytical questions** that would produce the highest-value insights for the user's stated goal. Write these out before proceeding.

Good analytical questions go beyond surface-level:

| Surface-level (avoid) | Deep (prefer) |
|---|---|
| What is total revenue? | Which segments drove the revenue change and by how much? |
| What is the average conversion rate? | Where in the funnel is the biggest drop-off and which cohort is most affected? |
| Which region has the highest sales? | Why does Region X outperform — is it volume, pricing, or mix? |
| What is the trend over time? | When did the trend inflect and what changed at that point? |

Prioritize questions where:
- The answer is **actionable** (the user could do something differently)
- The data to answer it **exists** in the pipeline output
- The finding would have **meaningful business impact** (not trivia)

### Step 3 — Delegate analytical queries

For each question, send a plain-English query to the Pipeline Builder describing what to compute. Be specific about:
- Which table/dataframe to analyze
- What grouping dimensions to use
- What metric to compute and how (sum vs. mean)
- What comparison to make (period-over-period, segment vs. segment, contribution to total)

**Example delegation queries:**

> "On the `monthly_revenue` table, compute revenue change from Q1 to Q2, broken down by `region`. For each region, show the absolute delta and the % contribution to the total change."

> "On the `funnel_stages` table, compute drop-off rate between each consecutive stage, segmented by `channel`. Flag any segment where the drop-off exceeds 2× the overall average."

> "On the `order_detail` table, decompose the total revenue change into volume effect, price effect, and mix effect using the PVM methodology. Group by `product_category`."

### Step 4 — Dig deeper (1–2 more rounds)

After receiving the first round of results, look for:

- **Surprising segments**: a region/channel/cohort that behaves very differently from others → ask Pipeline Builder to drill into it
- **Unexplained variance**: a metric moved but the initial breakdown doesn't fully explain it → ask for a finer-grained decomposition
- **Confirmation checks**: a finding seems too strong or too convenient → ask for a different cut of the data to confirm or contradict it
- **Temporal patterns**: a segment-level finding might be driven by a single time period → ask for the time series within that segment

This is where depth comes from. Do not stop at the first answer. Follow the trail until you can explain the "why" or explicitly acknowledge the uncertainty.

Cap at **2–3 total delegation rounds**. Beyond that, diminishing returns.

### Step 5 — Synthesize into ranked insights

Rank findings by **business impact** (magnitude × actionability), not by statistical impressiveness. A $50K revenue leak that can be plugged beats a statistically significant 0.3% lift that cannot.

For each insight, assemble:
- A **headline** — one sentence stating the finding as a fact
- **Supporting evidence** — concrete numbers (both % and absolute), date ranges, segment names
- **Data reference** — which table/dataframe and what query produced this finding
- **Implication** — what the user should consider doing (or investigating further)

---

## Analysis Patterns

These are the analytical lenses to consider for every dataset. Not all will apply. Pick the ones that match the user's goal and the available data.

### Segment comparison
Split a metric by a categorical dimension and compare groups. Look for:
- Outsized performers (segments contributing disproportionately to the total)
- Underperformers relative to their size (large segment, low metric)
- Lift: how does one segment compare to the overall average? `(segment_value - overall) / overall`

### Time-period decomposition
Compare a metric across two time periods. Break the change into:
- **What changed** — absolute and % delta
- **Where it changed** — which segments drove the change (contribution analysis)
- **When it changed** — was the change gradual or concentrated in a sub-period?

### Driver attribution (PVM / variance bridges)
When a financial metric changed, decompose into volume, price, and mix effects. This applies to any multiplicative relationship (revenue = units × price, cost = hours × rate, etc.). Reference `architecture/attribution-analysis.md` for methodology.

### Funnel / conversion analysis
Ordered stages with a metric that decreases. Look for:
- The biggest absolute drop-off (most users lost)
- The biggest rate drop-off (worst conversion step)
- Segment-specific bottlenecks (e.g., mobile drops harder at checkout)

### Concentration / Pareto
How concentrated is the metric? If 10% of customers drive 60% of revenue, that is an insight. Compute cumulative share of the metric sorted by the dimension.

### Distribution shape
When a metric has high variance, look at the distribution — not just the mean. Are there outliers? Is it bimodal? Skewed? The mean alone can be misleading.

### Cohort behavior
If cohort data is available, look for:
- Cohort-over-cohort improvement or degradation
- The "critical period" where most churn happens
- Whether recent cohorts are better or worse than older ones at the same elapsed time

---

## Insight Quality Rules

1. **Lead with value drivers.** Not "total revenue was $X" — that's a summary statistic the user already knows. Instead: "Revenue grew 12% but the entire gain came from one region (APAC +$3.2M); all other regions were flat or down."

2. **Always give both % and absolute.** A 200% lift on a $500 base is less important than a 5% lift on a $10M base. Give both so the reader can judge materiality.

3. **Reference actual column names.** Say "`region` = APAC" not "the Asia-Pacific region." The user should be able to trace your claim back to the data.

4. **No speculation.** State facts. Accept uncertainty. Never write "this is probably because..." unless you have direct evidence from the data. It is better to say "the data shows X but does not explain why — this may warrant further investigation" than to fabricate a causal story.

5. **Do not do mental math.** Report numbers directly from the Pipeline Builder's output. Never compute percentages, ratios, or aggregations in your head — you will get them wrong. If you need a derived number, delegate the computation.

6. **No contradictions.** Before finalizing, review all insights together. If Insight 2 says APAC is the growth driver and Insight 4 implies domestic markets drove growth, something is wrong. Resolve it or flag the tension explicitly.

7. **Pursue all leads.** If the data raises a question you can answer with one more delegation round, do it. Do not leave obvious threads unpulled.

---

## Output Format

```
## Executive Summary

[1–3 sentence overview of the single most important finding.
Concrete numbers. No filler.]

## Key Findings

### 1. [Insight headline as a factual sentence]
[2–4 bullet points with supporting evidence.
Include both % and absolute numbers.
Reference column names and date ranges.]

_Data: `table_name` — [brief description of what was computed]_

### 2. [Next insight headline]
...

### 3. [Next insight headline]
...

## Suggested Next Steps
- [Actionable recommendation or further investigation, if any]
- [Do NOT suggest visualizations — the viz skill handles that]
```

**Formatting rules:**
- Executive Summary is mandatory. It contains the #1 finding, not a summary of all findings.
- Key Findings are numbered by importance, not by the order they were discovered.
- Each insight has a `_Data:_` footer line referencing the source table and what was computed. The visualizations skill uses this to decide what to chart.
- Cap at **5 insights**. If you have 7 candidates, cut the two with the smallest business impact.
- Use markdown tables for small numeric comparisons (≤5 rows × 4 columns). Do not create large tables — they lose the reader.
- Be concrete: give date ranges ("Jan–Mar 2024"), not "the recent period." Give numbers ("$3.2M"), not "significant growth."

---

## Tone & Style

- **Short sentences.** Cut every word that does not carry information.
- **Bullet points over paragraphs.** The user scans, not reads.
- **Bold the key number** in each bullet so the eye catches it.
- **No jargon** unless the user used it first. Say "price went up" not "ASP exhibited upward pressure."
- **No hedging** on facts. If the data says APAC grew 23%, say it. Do not write "APAC appeared to grow by approximately 23%."
- **Hedge on causation.** "APAC grew 23%, coinciding with the new pricing rollout" — not "APAC grew 23% because of the new pricing rollout" (unless you have causal evidence).

---

## Anti-Patterns

- **Do not recommend visualizations.** The viz skill reads your insights and decides what to chart. Your job ends at the prose.
- **Do not restate the user's question.** Jump to the answer.
- **Do not list every metric in the dataset.** Only surface findings that are surprising, large, or actionable.
- **Do not lead with methodology.** The user does not care that you "ran a segment comparison on the `orders` table." Lead with the finding; cite the data source in the footer.
- **Do not give both good and bad news equal weight.** If the headline is bad news, say so. Do not soften it with offsetting positives buried in the same sentence.
