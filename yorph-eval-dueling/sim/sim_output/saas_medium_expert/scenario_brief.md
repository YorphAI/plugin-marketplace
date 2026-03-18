# Scenario Brief: saas_medium

**Domain:** saas | **Complexity:** medium

Full SaaS stack: accounts, subscriptions, billing, usage, features, MRR history, and support tickets. Key challenge: BOTH subscriptions.mrr_amount AND mrr_history.mrr define MRR — the agent must identify which is the authoritative source.

---

## Tables

- **accounts**: Customer accounts.
- **subscriptions**: Subscription records with live MRR.
- **billing_periods**: Invoice billing periods.
- **usage_events**: Product usage events.
- **feature_flags**: Which features are enabled per account.
- **mrr_history**: Monthly MRR snapshot for trending. NOT the live record.
- **cohorts**: Monthly cohort assignments. Month-grain — do not join to daily facts.
- **support_tickets**: Customer support tickets.

---

## Data Quality Issues (deliberately injected)

These are known issues the agent MUST discover and surface:

### mrr_history.mrr — `duplicate_metric`

mrr_history.mrr and subscriptions.mrr_amount both represent MRR. mrr_history is a point-in-time snapshot table; subscriptions is the live record. The agent should surface this ambiguity and ask which is authoritative for trending.

**Prevalence:** always

### feature_flags.enabled_at — `high_null`

feature_flags.enabled_at is NULL for flags that were enabled at account creation.

**Prevalence:** 20% of rows

### support_tickets.resolved_at — `high_null`

resolved_at is NULL for open tickets. Normal — not a data quality issue.

**Prevalence:** 15% of rows

### cohorts.cohort_month — `mixed_grain`

cohorts is a month-grain table (one row per account per cohort month). It must not be joined directly to daily usage events.

**Prevalence:** always

---

## Expected Joins (ground truth)

- `subscriptions` → `accounts` on `account_id` [many:1]
- `billing_periods` → `subscriptions` on `subscription_id` [many:1]
- `usage_events` → `accounts` on `account_id` [many:1]
- `feature_flags` → `accounts` on `account_id` [many:1]
- `mrr_history` → `accounts` on `account_id` [many:1]
- `cohorts` → `accounts` on `account_id` [many:1] ⚠ fan_out trap
- `support_tickets` → `accounts` on `account_id` [many:1]

---

## Expected Measures (ground truth)

- **MRR**: SUM(subscriptions.mrr_amount) WHERE status='active'
- **ARR**: SUM(subscriptions.arr_amount) WHERE status='active'
- **Churn Rate**: RATIO(subscriptions.*)
- **Net Dollar Retention**: RATIO(subscriptions.*)
- **Feature Adoption %**: RATIO(feature_flags.*)
- **Daily Active Accounts**: COUNT_DISTINCT(usage_events.account_id)
- **Support Tickets**: COUNT(support_tickets.ticket_id)
- **Median Time to Resolve**: AVG(support_tickets.*)

---

## Expected Business Rules

- Use subscriptions.mrr_amount for live MRR snapshots; mrr_history for period-over-period trending.
- Net Dollar Retention (NDR) = (starting MRR + expansion - contraction - churn) / starting MRR.
- cohorts must only be joined to month-grain aggregations, not to daily usage_events.
- feature_flags.enabled_at NULL means the feature was enabled at account creation.
