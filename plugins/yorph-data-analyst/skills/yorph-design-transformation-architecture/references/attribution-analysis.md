# Attribution, Variance & Root Cause Analysis

Load this subskill when the user's goal involves: explaining why a metric changed, comparing periods (budget vs actual, WoW, MoM, YoY), retention/churn analysis, funnel optimization, or causal impact estimation.

---

## Pre-Analysis Checklist (gate — confirm before proceeding)

- Metric definition has not changed between comparison periods (if unknown, ask the user)
- Data completeness is consistent across periods (if not, flag)
- Time alignment is correct (fiscal vs calendar, timezone consistency)
- No known outages, backfills, or schema changes

If any fail, resolve before running analysis. See Example 7 in worked examples.

## Core Analytical Principles

1. **Measurement validity first** — verify definitions, time windows, data freshness before analyzing
2. **Compare like with like** — same populations, calendars, currencies; adjust for seasonality
3. **Decompose before explaining** — break metrics into components before hypothesizing causes
4. **Correlation ≠ causation** — treat findings as hypotheses unless causal evidence exists
5. **Quantify impact** — attribute portions of change to identifiable drivers

---

## 1. Variance Analysis (Price-Volume-Mix)

### When to use
Explaining the gap between budgeted/forecasted and actual performance. Also called a sales bridge, margin bridge, or "walk."

### The PVM components

- **Price Effect:** `(Actual Price − Budget Price) × Actual Units` — sold at higher/lower prices than planned
- **Volume Effect:** change in total units assuming unchanged prices/margins
- **Mix Effect:** shift in which products/segments sold — the "silent thief"

**Mix analogy:** A smoothie shop sells more smoothies (volume up) but everyone switched from the $10 Super-Green to the $4 Simple-Orange. Revenue drops despite higher volume. Mix explains the gap.

### Advanced decomposition (add when data supports it)
- **Cost Effect:** variable costs, fixed costs, logistics, rebates separated
- **FX Effect:** isolate currency fluctuations from local performance
- **New / Non-Repeat:** items appearing in only one period get their own bucket

### Critical edge cases

**New/discontinued items:** When a product has zero budget quantity but appears in actuals → "New Effect" bucket. Budget-only → "Non-Repeat" bucket. Traditional PVM formulas incorrectly treat these as Price Effect when budget price is null. Use explicit CASE logic to route them.

**Non-additivity:** A product's volume can increase while its Volume Effect is negative — the Mix Effect absorbs the impact. If a customer buys large quantities of a low-priced item, it's positive volume but negative mix. This is counterintuitive but correct.

**Match criteria:** Comparison only works if you can 1:1 match items across periods. Without separating "matched business" from new/non-repeat, volume and mix effects become skewed.

### Data model requirements
- **Fact_Actuals** and **Fact_Budget_Forecast** at the same grain for 1:1 matching
- Rich dimensionality (25-100 dimensions: geo, channel, customer type, product attributes; 5-10 measures)
- **Dim_Product / Dim_Customer** for drill-through

### Caveats
- Missing list prices or unit costs invalidate the model
- More granular analysis = higher Mix impact. One level up the hierarchy often gives more stable comparison
- Separate controllable variances (discounts, sales volume) from non-controllable (FX, market inflation)

---

## 2. Root Cause Analysis — 7 Methodologies

Choose based on the scenario. Layer multiple methods when one alone doesn't explain the majority of the change.

### 2.1 Metric Decomposition (Top-Down)
**Use for:** High-level KPI drops. Fast, structured explanation for stakeholders.
**How:** Decompose metric into multiplicative/additive components (e.g., `Revenue = Traffic × Conversion × AOV`). Quantify WoW/MoM change for each. Rank by contribution.
**Viz:** Waterfall chart, contribution bar chart.
**Limit:** Hides second-order or interaction effects.

### 2.2 Dimensional Slice-and-Dice
**Use for:** Localizing where the change occurred. Segment-level issues.
**How:** Break metric by dimensions (geo, product, channel, customer type, device). Identify disproportionate impact. Drill recursively.
**Viz:** Ranked bar of delta by segment, heatmaps (segment × time).
**Limit:** Combinatorially large without pruning.

### 2.3 Driver Tree / Causal Chain
**Use for:** Complex systems with known dependencies; operational or funnel-based metrics.
**How:** Build dependency graph (e.g., Revenue ← Orders ← Sessions + Conversion Rate). Evaluate each node for anomalies. Trace degradation upstream/downstream.
**Limit:** Requires correct dependency assumptions.

### 2.4 Cohort-Based Analysis
**Use for:** Behavioral or retention-driven metrics. Suspected changes in user quality.
**How:** Group by cohort (signup month, first purchase, campaign exposure). Compare performance across time. Separate acquisition effects from engagement effects.
**Limit:** Slower signal for recent changes.

### 2.5 Change-Point and Anomaly Analysis
**Use for:** Sudden drops or spikes. Suspected incidents or launches.
**How:** Identify exact change-point timestamp. Align with known events (deploys, pricing changes, outages). Compare pre/post distributions.
**Viz:** Time-series with annotated events, pre vs post distributions.
**Limit:** Does not explain gradual trends.

### 2.6 Counterfactual / Baseline Comparison
**Use for:** Seasonal businesses. Isolating impact from expected trends.
**How:** Establish expected baseline (historical average, model, control group). Compare actuals to expected. Attribute deviation.
**Limit:** Baseline assumptions matter.

### 2.7 Funnel Analysis
**Use for:** Conversion, signup, or checkout drops.
**How:** Define stages. Compare stage-level conversion rates. Identify largest drop-offs. Segment affected users.
**Limit:** Requires clean event instrumentation.

---

## 3. Handling Uncertainty in RCA

### The 7 uncertainty signals — assume uncertainty remains if ANY hold

1. Identified drivers explain less than a majority of the change
2. Different methodologies identify different primary drivers
3. Impact is spread across many small contributors with no dominant driver
4. No clear change-point or event alignment
5. Small changes in time window/filters materially change findings
6. Identified drivers conflict with known domain logic
7. Data quality or pipeline concerns exist

### When uncertain, the agent must:
- Apply at least one additional, orthogonal RCA methodology
- Surface multiple plausible drivers
- Assign confidence levels (high/medium/low) to each
- Explicitly state what is known, suspected, and unresolved

### Layering progression (recommended order):
1. Metric decomposition (what changed)
2. Segment analysis (where)
3. Temporal analysis (when)
4. Funnel/cohort/dependency analysis (why)
5. Baseline/counterfactual (how unexpected)

If multiple methods point to the same driver → confidence increases. If they disagree → surface all plausible drivers and explain the discrepancy. Never force a single explanation when evidence is ambiguous.

---

## 4. Cohort & Retention Analysis

### NRR vs GRR
- **Gross Revenue Retention (GRR):** retains original revenue from cohort, includes downsells/contractions, EXCLUDES upsells
- **Net Revenue Retention (NRR):** total revenue including upsells, expansion, cross-selling

Use a fixed time box for fair comparison between old and new cohorts.

### Key distinctions
- **Contractual** (SaaS): firm knows exactly when customer defects
- **Non-contractual** (retail): churn is fuzzy, requires inactivity threshold (e.g., 30 days)

### Survival analysis (advanced)
Standard retention curves describe the past. Survival analysis estimates future churn probability:
- **Kaplan-Meier:** non-parametric survival curve, no distribution assumed
- **Cox Proportional Hazard:** identifies variables affecting churn speed

### Caveats
- **Sparse cohorts** disappear from results if no activity occurred. Use LEFT JOIN to date_dim to force zero-value rows.
- **Mix shifts:** declining overall retention may reflect acquiring more customers from a low-retention segment, not product degradation
- **Revenue recognition:** SaaS 12-month contracts may be 12 monthly records or 1 annual record depending on rev rec rules (ASC 606), affecting SQL timing logic

---

## 5. Funnel Analysis

### Sessionization — define before building any funnel
- **Time-based:** session = events followed by inactivity gap (typically 30 min)
- **Navigation-based:** explicit login/logout boundaries. Fails if termination records missing.
- **Hybrid:** new session if referring URL changes even within time window

### Implementation strategies (inform Pipeline Builder which to use)
- **Naive joins (avoid):** independent aggregate counts by date. Can produce >100% conversion rates.
- **Sequential left joins:** links events by user_id with increasing timestamps. O(n²) — spills with billions of rows.
- **Stacked window functions (recommended):** ROW_NUMBER + LAG/LEAD within user partitions. Avoids self-joins.
- **MATCH_RECOGNIZE (when available):** SQL:2016 pattern matching. Available in Snowflake, BigQuery, Trino. Best for complex event sequences.

### Edge cases
- **Backwards navigation:** users going checkout → homepage. Decide: first occurrence, last, or contiguous only.
- **Rolling conversion:** use rolling windows (e.g., converted within 7 days of previous step) for different user velocities
- **Tracking duplicates:** events firing twice inflate metrics. Always check unique IDs vs total counts.

### Performance notes for Pipeline Builder
- Multi-hop joins on high-cardinality users are expensive
- Cluster events table by (event_time, user_id) in Snowflake/BigQuery
- Define funnel logic once (semantic layer) to avoid metric inconsistency

---

## 6. Causal Analysis

### What's feasible in SQL
- **Difference-in-Differences (DiD):** label treated vs control, pre vs post. `DiD = (Y_T_post − Y_T_pre) − (Y_C_post − Y_C_pre)`. Equivalent to regression `Y ~ treated + post + treated*post`.
- **Event Study (parallel trends validation):** create relative-week-to-intervention. Plot avg outcomes. If treated/control don't track pre-intervention, DiD assumptions are violated.
- **Simple OLS:** `b = Cov(X,Y) / Var(X)` from aggregates. Use log transforms and NULLIF to avoid division by zero.
- **Panel fixed effects:** demean by entity (subtract entity mean), then run DiD or OLS on demeaned values.

### What's NOT feasible in basic SQL
ARIMA, Bayesian causal impact, propensity score matching. Flag these for Python execution in Pipeline Builder.

---

## 7. Worked Examples (condensed)

**Example 1 — Top-down KPI drop:** Revenue −8% WoW. Decompose → traffic −6%, conversion −2%, AOV flat. Traffic explains most. Next: slice-and-dice to localize.

**Example 2 — Localizing:** Same −8%. Segment by geo → US accounts for −5% of the −8%. US mobile disproportionately hit. Uncertainty: low. Next: change-point analysis.

**Example 3 — Sudden anomaly:** Conversion −40% in one day. Change-point aligns with checkout deploy. Immediate post-release. Uncertainty: low. Next: funnel analysis on checkout stage.

**Example 4 — Funnel:** Conversion down, traffic stable. Drop concentrated at checkout. New users disproportionately affected. Uncertainty: medium. Next: segment by device + cohort.

**Example 5 — Behavioral shift:** Retention trending down 3 months. Newer cohorts have lower retention, older stable. Uncertainty: medium. Next: investigate acquisition channel mix.

**Example 6 — Layered under uncertainty:** Revenue −6%, fragmented. Small declines across traffic, conversion, AOV. No single segment dominant. No clear change-point. Uncertainty: HIGH. State explicitly and recommend monitoring.

**Example 7 — Pre-analysis gate failure:** Revenue dropped but metric definition recently changed. RCA invalid. Resolve definition first.

---

## RCA Output Template

```
Summary: [Metric] changed [X%] [period comparison].

Key Drivers:
1. [Driver A] (−X%, [high/medium/low] confidence)
2. [Driver B] (−X%, [high/medium/low] confidence)

Insights:
- Nature of decline (localized vs broad, acquisition vs engagement, etc.)
- ~X% remains unexplained

Next Investigations:
- [Specific follow-up analyses]
```

## Failure Modes
- Blame a single cause without decomposition
- Ignore data quality issues
- Overfit explanations to recent events
- Confuse correlation with causation
