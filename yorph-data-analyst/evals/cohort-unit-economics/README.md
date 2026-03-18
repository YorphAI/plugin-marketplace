# Eval: Cohort-Based Unit Economics

## What This Tests

The ability to track **CAC payback**, **LTV**, and **gross margin** by acquisition cohort over time — when customers change plans, receive credits, churn and reactivate, and consume shared resources.

## Why It's Hard

- **Identity resolution**: The definition of "a customer" is ambiguous — one company may have multiple accounts, merged accounts, or accounts that split
- **Churn and reactivation**: Customers who cancel and return break simple cohort bucketing — do they rejoin their original cohort or start a new one?
- **Plan changes**: Mid-cycle upgrades, downgrades, and add-ons make per-cohort revenue attribution non-trivial
- **Credits and refunds**: Timing of credits vs. when the service was consumed creates revenue recognition mismatches
- **Shared cost allocation**: Infrastructure, support, and overhead costs must be allocated to cohorts, but the allocation basis (users? revenue? usage?) changes the answer dramatically
- **System disagreements**: Billing, usage, support, and CRM systems rarely agree on customer counts, revenue, or activity dates
- **Survivorship bias**: Naive LTV calculations overweight long-lived customers and underweight recent cohorts with incomplete data

## Planned Data Files (Not Yet Generated)

| File | Description |
|------|-------------|
| `customers.csv` | Customer master with signup dates, plan history, account merges |
| `billing_events.csv` | Invoices, payments, credits, refunds with timestamps |
| `usage_metrics.csv` | Daily/monthly product usage by customer |
| `support_tickets.csv` | Support interactions with cost and resolution data |
| `marketing_spend.csv` | Campaign-level spend with attribution to signups |
| `infrastructure_costs.csv` | Monthly shared infrastructure costs to allocate |
