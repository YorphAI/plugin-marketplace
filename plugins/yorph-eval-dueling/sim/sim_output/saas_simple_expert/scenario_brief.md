# Scenario Brief: saas_simple

**Domain:** saas | **Complexity:** simple

A minimal SaaS schema: accounts, subscriptions, billing, and usage events. Clean FK relationships. Tests whether the agent correctly identifies MRR, ARR, churn, and expansion as the core SaaS metrics.

---

## Tables

- **accounts**: Customer accounts (companies). One row per account.
- **subscriptions**: Subscription records. One account can have multiple (upsell/multi-product).
- **billing_periods**: Invoice periods per subscription. One row per billing cycle.
- **usage_events**: Product usage events streamed from the SDK. Very high volume.

---

## Data Quality Issues (deliberately injected)

These are known issues the agent MUST discover and surface:

### subscriptions.cancelled_at — `high_null`

cancelled_at is NULL for active subscriptions (expected). The agent must not flag this as a data quality issue.

**Prevalence:** 75% of rows

### usage_events.feature_name — `encoded_null`

feature_name = 'unknown' is an encoded null from the SDK's fallback.

**Prevalence:** 5% of rows

---

## Expected Joins (ground truth)

- `subscriptions` → `accounts` on `account_id` [many:1]
- `billing_periods` → `subscriptions` on `subscription_id` [many:1]
- `usage_events` → `accounts` on `account_id` [many:1]
- `usage_events` → `subscriptions` on `subscription_id` [many:1]

---

## Expected Measures (ground truth)

- **MRR**: SUM(subscriptions.mrr_amount) WHERE status = 'active'
- **ARR**: SUM(subscriptions.arr_amount) WHERE status = 'active'
- **Active Accounts**: COUNT_DISTINCT(subscriptions.account_id) WHERE status='active'
- **New MRR**: SUM(subscriptions.mrr_amount) WHERE type='new'
- **Churned MRR**: SUM(subscriptions.mrr_amount) WHERE status='cancelled'
- **Expansion MRR**: SUM(subscriptions.mrr_amount) WHERE type='expansion'
- **Churn Rate**: RATIO(subscriptions.*)
- **ARPA**: AVG(subscriptions.mrr_amount) WHERE status='active'
- **Invoices Issued**: COUNT(billing_periods.billing_id)

---

## Expected Business Rules

- MRR = sum of mrr_amount WHERE status = 'active'.
- ARR = MRR × 12 (or use arr_amount column directly).
- Churn Rate = cancelled MRR in period / starting MRR.
- Expansion MRR = MRR growth from existing accounts (upgrades only).
- usage_events.feature_name = 'unknown' should be excluded from feature adoption metrics.
