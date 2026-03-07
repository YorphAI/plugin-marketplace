---
name: data-simulator
description: Use this skill whenever the user wants to generate, simulate, or fabricate realistic datasets for testing, demos, or stress-testing data analysis pipelines. Triggers include: "generate some test data", "simulate a dataset", "make fake data", "create sample data for X domain", "I want to test my pipeline", "give me a challenging dataset", "generate data with messy/tricky/realistic problems", or any request to produce synthetic tabular data. Always use this skill even if the request seems simple — it ensures the output is reusable, seeded, and analytically challenging in configurable ways. Also triggers when the user wants to test or benchmark the data-analysis-multi-approach skill.
---

# Data Simulator Skill

Generate realistic, seeded, analytically challenging datasets from a plain-English description. Output is always a Python script (reusable, reproducible) plus a challenge manifest documenting every trap planted in the data.

---

## Step 1: Parse the Request

Extract from the user's plain-English description:

1. **Domain** — what kind of business/data is this? Map to one of the built-in domains or construct a custom one.
2. **Scale** — how many rows/entities? Default: ~1,000–5,000 rows unless specified.
3. **Challenge level** — mild, moderate, severe, or mixed. Default: moderate.
4. **Specific challenges requested** — any the user explicitly mentioned.
5. **Seed** — use 42 unless the user specifies otherwise.

If the domain or key parameters are ambiguous, make a reasonable default choice and state it — don't ask, just proceed and note assumptions at the top of your response.

---

## Step 2: Select Domain Schema

### Built-in Domains

**E-commerce / Sales**
Key entities: orders, order lines, customers, products
Key fields: order_id, customer_id, product_id, product_category, quantity, unit_price, discount_pct, revenue, order_date, ship_date, status, country, region
Natural relationships: orders have multiple lines; customers have multiple orders; products belong to categories

**Finance / Transactions**
Key entities: transactions, accounts, merchants
Key fields: transaction_id, account_id, merchant_id, merchant_category, amount, currency, fx_rate, transaction_date, posted_date, type (debit/credit/refund), status, channel
Natural relationships: accounts have many transactions; merchants have categories; refunds link back to original transactions

**SaaS / Product Analytics**
Key entities: users, sessions, events, subscriptions
Key fields: user_id, session_id, event_name, event_timestamp, plan_type, mrr, signup_date, churn_date, feature_flags, device, country
Natural relationships: users have sessions; sessions have events; subscriptions have start/end dates and plan changes

**Custom Domain**
If domain doesn't match above, infer a plausible schema from the user's description. Generate 8–15 fields that reflect realistic business data for that domain.

---

## Step 3: Design the Challenges

For each challenge, decide:
- **Which fields** it affects
- **What percentage** of rows it impacts
- **How subtle** it is (obvious vs. hidden)

### Full Challenge Menu

#### Nulls & Missing Data
- `sparse_nulls` — random ~2–5% nulls across several fields
- `structured_nulls` — nulls that aren't random (e.g. STATE is null for all non-US rows — plausible but traps analysts who drop nulls blindly)
- `null_codes` — missing data encoded as sentinel values: -1, 999, "N/A", "NULL", "unknown", 0 where 0 is nonsensical
- `conditional_nulls` — field B is always null when field A has a certain value (hidden dependency)

#### Outliers & Anomalies
- `statistical_outliers` — a small number of values 4–6 sigma from mean (real but extreme)
- `impossible_values` — values that are logically wrong: negative quantities, future dates, revenue > 1M on a $10 product, age = 0
- `soft_anomalies` — values that are plausible individually but anomalous in context (e.g. a single transaction 10x the customer's normal spend)
- `sign_errors` — a subset of numeric fields with flipped signs (e.g. refunds recorded as positive)

#### Schema & Structural Issues
- `mixed_types` — a numeric column with occasional string values mixed in ("N/A", "pending", "")
- `inconsistent_casing` — categorical fields with inconsistent capitalization ("USA", "usa", "U.S.A.")
- `duplicate_rows` — exact or near-duplicate rows (same key, slightly different values)
- `duplicate_ids` — IDs that appear multiple times with different data (fan-out / join trap)
- `column_name_traps` — ambiguously named columns (e.g. both `revenue` and `sales` that differ; `date` vs `created_date` vs `order_date`)
- `encoding_issues` — special characters in string fields that break naive parsers

#### Temporal Traps
- `partial_period` — the most recent time period (month/quarter/year) is incomplete, making naive YoY comparisons misleading
- `timezone_mix` — timestamps from multiple timezones stored without tz info, making event ordering wrong
- `irregular_cadence` — data has gaps (weekends, holidays, outages) that look like drops
- `date_format_mix` — dates stored in multiple formats in the same column ("2024-01-15", "01/15/2024", "Jan 15 2024")
- `backdated_records` — some records have created_at dates earlier than the system's launch date
- `future_dates` — a handful of records timestamped in the future

#### Business Logic Traps
- `metric_ambiguity` — two fields that seem to measure the same thing but differ (e.g. `revenue` ≠ `quantity × unit_price` due to undocumented discounts)
- `status_lifecycle_traps` — orders/transactions in terminal states (cancelled, refunded) that still show up in naive revenue sums
- `currency_mix` — amounts in multiple currencies without a clear fx_rate or normalization column
- `cohort_bleed` — user signup dates that don't align with their first event (referral/import artifact)
- `label_leakage_bait` — a column that is suspiciously predictive of the target (e.g. a `churn_flag` column that's 1 day ahead of actual churn)

#### Relational Traps (single-table)
- `orphaned_records` — foreign keys that reference non-existent parent records
- `fanout_joins` — a join between two tables produces more rows than expected due to one-to-many on both sides
- `self_joins_needed` — data that requires a self-join to analyze correctly (e.g. refund linked to original transaction_id)

---

## Relational Multi-Table Mode

Trigger this mode when the user asks for multi-table data, join testing, pipeline testing, or anything relational. Generate 2–3 CSVs that are designed to be joined together — but with traps buried in the joins.

### When to use it
- User says "multi-table", "relational", "join", "pipeline", "foreign keys", "star schema", "fact and dimension tables"
- Challenge level is set to "severe" or "advanced"
- Domain naturally has multiple entities (all built-in domains qualify)

### Table structure by domain

**E-commerce / Sales** (3 tables)
- `customers.csv` — one row per customer (customer_id PK)
- `orders.csv` — one row per order (order_id PK, customer_id FK)
- `order_lines.csv` — one row per line item (line_id PK, order_id FK, product_id FK)

**Finance / Transactions** (3 tables)
- `accounts.csv` — one row per account (account_id PK)
- `transactions.csv` — one row per transaction (transaction_id PK, account_id FK, merchant_id FK)
- `merchants.csv` — one row per merchant (merchant_id PK)

**SaaS / Product Analytics** (3 tables)
- `users.csv` — one row per user (user_id PK)
- `subscriptions.csv` — one row per subscription period (sub_id PK, user_id FK) — users can have multiple
- `events.csv` — one row per event (event_id PK, user_id FK, session_id)

### Relational challenge menu

Plant a selection of these across the table set. Each should be documented in the manifest with which join it affects.

**Cardinality traps**
- `fanout_join` — table A has duplicate PKs (or near-duplicate), causing a join with table B to silently multiply rows. Classic symptom: SUM() after join is 2x the correct value.
- `many_to_many_hidden` — both sides of a join have duplicates, causing explosive row multiplication. Neither table looks wrong in isolation.
- `aggregation_before_join_required` — joining first then aggregating gives wrong answer; must aggregate one side first. No error thrown, just wrong numbers.

**Key integrity traps**
- `orphaned_fk` — ~3–5% of FK values in the child table have no matching PK in the parent (e.g. order_lines reference order_ids that don't exist in orders). Inner join silently drops them; left join reveals nulls.
- `missing_pk_records` — some PKs exist in the fact table but are absent from the dimension table (e.g. merchant_id in transactions not present in merchants.csv). Common in real pipelines when dimension tables lag.
- `recycled_ids` — an ID value is reused across time periods for different entities (e.g. merchant_id 1042 refers to two different merchants in different years). Joining on ID alone gives wrong attribution.

**Key format traps**
- `key_type_mismatch` — FK is stored as integer in one table, string in the other (`1042` vs `"1042"`). Pandas merge silently produces 0 matches.
- `key_casing_mismatch` — string keys with inconsistent casing across tables (`"user_A99"` vs `"User_a99"`).
- `key_whitespace` — leading/trailing whitespace in key fields of one table (`"  1042"` vs `"1042"`).
- `composite_key_partial` — join requires two columns (e.g. merchant_id + date) but one table only has one of them, tempting analysts to join on the wrong grain.

**Temporal join traps**
- `slowly_changing_dimension` — a dimension (e.g. customer plan_type, merchant category) changes over time, but the dimension table only has the current value. Joining gives the wrong historical label.
- `event_before_entity` — some events in the fact table predate the entity's creation date in the dimension table (import artifact). A strict join on date range drops them.
- `duplicate_effective_dates` — a slowly-changing dimension table has two rows with the same effective date for the same entity, making it ambiguous which version is correct.

**Semantic traps**
- `shared_column_name_different_meaning` — both tables have a column called `status` or `type` but they mean different things. After a join, it's easy to accidentally use the wrong one (or for `pd.merge` to suffix them confusingly).
- `currency_grain_mismatch` — one table stores amounts in USD, another in local currency, with no explicit currency column in one of them.
- `aggregation_grain_mismatch` — one table is at daily grain, another at monthly grain. Joining them inflates or deflates values depending on how the join is done.

### Script structure for multi-table mode

Extend the single-table structure with:

```python
# ── 1. Generate base tables ──────────────────────────────────────────
customers_df = generate_customers(n=500)
orders_df = generate_orders(customers_df, n=2000)
order_lines_df = generate_order_lines(orders_df, n=5000)

# ── 2. Inject single-table challenges ────────────────────────────────
customers_df = inject_inconsistent_casing(customers_df, col='country')
orders_df = inject_partial_period(orders_df, col='order_date')

# ── 3. Inject relational challenges ──────────────────────────────────
# These operate across tables — functions take and return multiple dfs
customers_df, orders_df = inject_orphaned_fk(customers_df, orders_df)
orders_df = inject_fanout_join(orders_df)
customers_df, orders_df = inject_key_type_mismatch(customers_df, orders_df, key='customer_id')

# ── 4. Output all tables ─────────────────────────────────────────────
customers_df.to_csv('customers.csv', index=False)
orders_df.to_csv('orders.csv', index=False)
order_lines_df.to_csv('order_lines.csv', index=False)
```

Relational injectors that span tables should accept and return all affected dataframes as a tuple. Make the trap localized and surgical — don't corrupt entire tables, just enough rows to be non-obvious but detectable with careful analysis.

### Manifest additions for multi-table mode

Add a **Join Map** section before the challenges list:

```markdown
## Join Map
| Left Table | Right Table | Join Key(s) | Expected Type | Trap? |
|---|---|---|---|---|
| orders | customers | customer_id | many-to-one | ✅ key_type_mismatch |
| order_lines | orders | order_id | many-to-one | ✅ fanout_join |
| order_lines | products | product_id | many-to-one | ⚠️ orphaned_fk |
```

This gives the analyst a roadmap and makes scoring unambiguous.

---

## Step 4: Write the Python Script

Structure the script as follows:

```python
"""
[Domain] Synthetic Dataset Generator
Seed: [seed] | Rows: ~[n] | Challenge level: [level]
Generated by data-simulator skill.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

SEED = 42
np.random.seed(SEED)
random.seed(SEED)

# ── 1. Base data generation ──────────────────────────────────────────
# Generate clean, realistic base data first

# ── 2. Challenge injectors ───────────────────────────────────────────
# One clearly-named function per challenge, e.g.:
def inject_structured_nulls(df): ...
def inject_metric_ambiguity(df): ...
def inject_partial_period(df): ...

# ── 3. Apply challenges ──────────────────────────────────────────────
# Call each injector in sequence
df = inject_structured_nulls(df)
df = inject_metric_ambiguity(df)
# etc.

# ── 4. Output ────────────────────────────────────────────────────────
df.to_csv('synthetic_[domain]_data.csv', index=False)
print(f"Generated {len(df)} rows → synthetic_[domain]_data.csv")
```

**Code quality rules:**
- Each challenge is a separate, named function — makes the manifest accurate and the script auditable
- Use realistic-sounding fake names, companies, products (use hardcoded lists, not UUIDs)
- Base data should pass a "looks real" smell test before challenges are injected
- Include a `--clean` flag / boolean constant at the top to generate challenge-free data for baseline comparison
- Script must be runnable with only `pandas` and `numpy`

---

## Step 5: Write the Challenge Manifest

After the script, always output a manifest in this format:

```markdown
# Challenge Manifest — [Domain] Dataset
*Generated [date] | Seed: [seed] | ~[n] rows*

## Challenges Planted

### [Challenge Name]
- **Type**: [category from menu above]
- **Field(s) affected**: [column names]
- **Scope**: [e.g. "~4% of rows", "all rows where country ≠ 'US'"]
- **How to catch it**: [what a good analyst would notice]
- **How to miss it**: [the naive mistake that walks right past it]

### [Next challenge...]
...

## Scoring Guide
An analyst who catches all N challenges scores 100%.
Partial credit per challenge is at the analyst's discretion.
```

Save the manifest as `challenge_manifest_[domain].md`.

---

## Step 6: Deliver

Present both files to the user. Briefly summarize:
- The domain schema used
- How many challenges were planted and at what level
- Any notable assumptions made

Suggest they run the script, then hand the CSV to the data-analysis-multi-approach skill (if available) to see which divergences it catches.
