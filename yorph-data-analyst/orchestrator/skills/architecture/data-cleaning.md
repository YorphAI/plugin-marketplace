# Data Cleaning Methodology

Decision framework for planning cleaning steps. The Orchestrator uses this to architect which cleaning steps belong in the pipeline. The Pipeline Builder implements them.

---

## Core Principles (non-negotiable)

1. **Context-driven** — clean for the user's stated goal, not because data "looks messy"
2. **Preserve raw data** — never overwrite inputs; all transforms must be reversible or traceable
3. **Flag over delete** — when in doubt, add a quality flag column rather than dropping rows
4. **Deterministic** — every step must be rule-based, repeatable on future data, no ad hoc fixes
5. **Explainable** — if you can't explain why a value is invalid or why a correction was applied, don't apply it

---

## Profiling (always the first pipeline step)

Plan three profiling passes. The glimpse from the `connect` skill provides the raw material:

- **Structural:** field names, inferred dtypes, schema consistency, nested/semi-structured fields, row/column counts
- **Statistical:** null rates, unique counts, numeric distributions, categorical frequencies
- **Semantic:** detect placeholders ("N/A", "-999", "TBD"), unit inconsistencies, fields that look related (date pairs, ID-to-total relationships)

Output: an anomaly map — what looks wrong and what type of issue it is.

---

## Quality Issue Classification

Classify every issue before choosing a strategy:

| Category | Examples |
|---|---|
| Missingness | True nulls, placeholder values, structurally missing fields |
| Invalid values | Out-of-range, malformed formats, impossible combinations |
| Inconsistencies | Multiple formats for same concept, case/spelling differences, unit mismatches |
| Duplicates | Exact, near-duplicate, entity-level (same customer, different rows) |
| Noise & outliers | Typos, measurement errors, legitimate extremes |

---

## Null Handling Decision Framework

This is the most consequential cleaning decision. Get it wrong and you either invent data that didn't exist or discard signal.

### Leave NULL when absence IS the data point

| Example | Why NULL is correct |
|---|---|
| `order_shipped_date = NULL` | Order hasn't shipped. A date invents an event. |
| `refund_amount = NULL` | No refund issued. `0` ≠ "not applicable" in all contexts. |
| `last_login_at = NULL` | User never logged in. Any timestamp implies a login. |
| `cancellation_reason = NULL` | Never canceled. Any value implies cancellation. |
| `product_rating = NULL` | No rating given. Mean/default converts "no interaction" into sentiment. |
| `patient_smoking_status = NULL` | Unknown/not disclosed. Guessing introduces bias. |

### Treat as error when a value is required by definition

- `transaction_amount = NULL` → every transaction must have an amount. Flag, recover, or drop.
- `primary_key = NULL` → identifiers must always be present. Drop or quarantine.

### Impute only when ALL of these hold

1. Required by downstream system or model AND
2. Missingness is random and low (<~1-5%) AND
3. Missingness does NOT correlate with specific users, time periods, or categories AND
4. Field is not sensitive or regulated

**Imputation methods by context:**
- Deterministic recovery first (e.g., `order_total` = sum of line items)
- Median/mean for low-random numeric missingness
- Mode for categoricals with dominant value (99%+ one value)
- Interpolation for time-series short gaps in smooth signals
- Flag every imputed value

### Never impute when

- Missingness may carry semantic meaning
- Missingness is correlated (specific segments, time periods)
- Field is sensitive, regulated, or financial

### Drop only when

- Missing critical identifiers (no recovery possible)
- Record is unusable for any purpose

**All imputation decisions must be documented as assumptions in the trust report.**

---

## Semi-Structured Data (JSON, logs)

These decisions must be made before cleaning begins:

1. **Representation strategy** — choose one:
   - Preserve nesting (API payloads, operational use)
   - Flatten (analytics, BI, tabular storage)
   - Both (recommended when feasible)

2. **Key normalization** — when normalizing key names (case, separators), detect collisions. Never silently overwrite colliding fields. Resolve via namespacing or canonical-key selection.

3. **Schema drift** — infer schema from sample, track optional vs required fields, detect new/removed/renamed keys and type changes across records or over time.

4. **Lineage** — when flattening, maintain JSONPath lineage for each derived field so you can trace back to raw structure.

---

## Deduplication

Never deduplicate without first defining what "duplicate" means for this data:
- **Row-level:** exact duplicate rows
- **Entity-level:** same real-world entity, different rows (e.g., same customer with slight name variations)
- **Event-level:** same event recorded multiple times (tracking fires twice)

Determine which record is canonical. Preserve lineage when merging.

---

## Outlier Handling

Outliers are not errors by default. The pipeline plan must specify:
- Detection method (statistical: IQR/z-score, or rule-based: domain thresholds)
- Plausibility check (is this value possible given domain context?)
- Action: flag first, remove only with strong justification

---

## Validation After Cleaning (always the last cleaning step)

Plan a validation gate that checks:
- Row counts before vs after (unexplained drops = problem)
- Aggregate consistency (totals, means shouldn't change unexpectedly)
- Reduction in invalid values (cleaning should improve quality metrics)
- No unintended data loss

If results change materially, the trust report must explain why.

---

## Failure Modes

The agent must NOT:
- Over-clean and remove signal
- Impute without justification
- Assume domain rules without evidence
- Hide uncertainty
