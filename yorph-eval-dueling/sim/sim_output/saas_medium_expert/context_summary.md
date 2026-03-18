# Context Summary — saas_medium

# Enriched Profiles — Batch 1 of 1 (8 tables)


## main.accounts
Rows: 3,000 | Profiled: 2026-03-10

**Columns:**
`account_id` (INTEGER) → ~ "Account Id"
  Stats: null=0.0% | ~distinct=3,075 | range=[1, 3000]
  Samples: 1, 3000
`name` (VARCHAR)
  Stats: null=0.0% | ~distinct=3,144 | avg_len=12
  Samples: Company 34, Company 55, Company 63
`plan` (VARCHAR)
  Stats: null=0.0% | ~distinct=3 | avg_len=7
  Samples: growth, starter, enterprise
`industry` (VARCHAR)
  Stats: null=0.0% | ~distinct=5 | avg_len=6
  Samples: SaaS, HealthTech, E-comm
`country` (VARCHAR)
  Stats: null=0.0% | ~distinct=3 | avg_len=3
  Samples: DEU, GBR, USA
`created_at` (TIMESTAMP) → ~ "Created At"
  Stats: null=0.0% | ~distinct=2,172
  Samples: 2019-01-01 12:00:00, 2023-02-09 00:00:00
`health_score` (DECIMAL(4,1)) → ~ "Health Score"
  Stats: null=0.0% | ~distinct=950 | range=[15.0, 99.9]
  Samples: 15.0, 99.9

## main.billing_periods
Rows: 50,000 | Profiled: 2026-03-10

**Columns:**
`billing_id` (INTEGER) → ~ "Billing Id"
  Stats: null=0.0% | ~distinct=45,031 | range=[1, 50000]
  Samples: 1, 50000
`subscription_id` (INTEGER) → ~ "Subscription Id"
  Stats: null=0.0% | ~distinct=6,545 | range=[1, 7000]
  Samples: 1, 7000
`period_start` (DATE) → ~ "Period Start"
  Stats: null=0.0% | ~distinct=4,101
  Samples: 2019-01-01, 2361-03-09
`period_end` (DATE) → ~ "Period End"
  Stats: null=0.0% | ~distinct=4,101
  Samples: 2019-01-31, 2361-04-08
`amount_invoiced` (DECIMAL(10,2)) → ~ "Amount Invoiced"
  Stats: null=0.0% | ~distinct=13,959 | range=[50.00, 3049.70]
  Samples: 50.00, 3049.70
`amount_paid` (DECIMAL(10,2)) → ~ "Amount Paid"
  Stats: null=8.3% | ~distinct=13,959 | range=[50.00, 3049.70]
  Samples: 50.00, 3049.70
`status` (VARCHAR)
  Stats: null=0.0% | ~distinct=3 | avg_len=4
  Samples: void, paid, overdue
`paid_at` (TIMESTAMP) → ~ "Paid At"
  Stats: null=8.3% | ~distinct=43,784
  Samples: 2019-01-02 00:00:00, 2155-11-24 00:00:00

## main.cohorts
Rows: 72,000 | Profiled: 2026-03-10

**Columns:**
`account_id` (INTEGER) → ~ "Account Id"
  Stats: null=0.0% | ~distinct=3,075 | range=[1, 3000]
  Samples: 1, 3000
`cohort_month` (DATE) → ~ "Cohort Month"
  Stats: null=0.0% | ~distinct=1
  Samples: 2020-01-01, 2020-01-01
`months_since` (INTEGER) → ~ "Months Since"
  Stats: null=0.0% | ~distinct=24 | range=[0, 23]
`mrr` (DECIMAL(10,2))
  Stats: null=0.0% | ~distinct=7,896 | range=[50.00, 549.90]
  Samples: 50.00, 549.90
`retention_pct` (DECIMAL(5,2)) → ~ "Retention Pct"
  Stats: null=0.0% | ~distinct=64 | range=[40.00, 99.00]
  Samples: 40.00, 99.00

## main.feature_flags
Rows: 15,000 | Profiled: 2026-03-10

**Columns:**
`account_id` (INTEGER) → ~ "Account Id"
  Stats: null=0.0% | ~distinct=3,075 | range=[1, 3000]
  Samples: 1, 3000
`feature_name` (VARCHAR) → ~ "Feature Name"
  Stats: null=0.0% | ~distinct=5 | avg_len=11
  Samples: custom_reports, bulk_export, sso
`is_enabled` (BOOLEAN) → ~ "Is Enabled"
  Stats: null=0.0% | ~distinct=2
`enabled_at` (TIMESTAMP) → ~ "Enabled At"
  Stats: null=20.0% | ~distinct=11,193
  Samples: 2020-01-02 00:00:00, 2061-01-24 00:00:00

## main.mrr_history
Rows: 150,000 | Profiled: 2026-03-10

**Columns:**
`account_id` (INTEGER) → ~ "Account Id"
  Stats: null=0.0% | ~distinct=3,075 | range=[1, 3000]
  Samples: 1, 3000
`snapshot_month` (DATE) → ~ "Snapshot Month"
  Stats: null=0.0% | ~distinct=48
  Samples: 2020-01-01, 2024-02-01
`mrr` (DECIMAL(10,2))
  Stats: null=0.0% | ~distinct=22,334 | range=[100.00, 2099.90]
  Samples: 100.00, 2099.90
`new_mrr` (DECIMAL(10,2)) → ~ "New Mrr"
  Stats: null=0.0% | ~distinct=203 | range=[0.00, 298.50]
`expansion_mrr` (DECIMAL(10,2)) → ~ "Expansion Mrr"
  Stats: null=0.0% | ~distinct=102 | range=[0.00, 198.00]
`contraction_mrr` (DECIMAL(10,2)) → ~ "Contraction Mrr"
  Stats: null=0.0% | ~distinct=56 | range=[0.00, 49.00]
`churned_mrr` (DECIMAL(10,2)) → ~ "Churned Mrr"
  Stats: null=0.0% | ~distinct=27 | range=[0.00, 87.00]
`ending_mrr` (DECIMAL(10,2)) → ~ "Ending Mrr"
  Stats: null=0.0% | ~distinct=6,427 | range=[100.00, 2388.40]
  Samples: 100.00, 2388.40

## main.subscriptions
Rows: 7,000 | Profiled: 2026-03-10

**Columns:**
`subscription_id` (INTEGER) → ~ "Subscription Id"
  Stats: null=0.0% | ~distinct=6,545 | range=[1, 7000]
  Samples: 1, 7000
`account_id` (INTEGER) → ~ "Account Id"
  Stats: null=0.0% | ~distinct=3,075 | range=[1, 3000]
  Samples: 1, 3000
`plan` (VARCHAR)
  Stats: null=0.0% | ~distinct=3 | avg_len=7
  Samples: growth, enterprise, starter
`status` (VARCHAR)
  Stats: null=0.0% | ~distinct=2 | avg_len=7
  Samples: active, cancelled
`type` (VARCHAR)
  Stats: null=0.0% | ~distinct=3 | avg_len=5
  Samples: new, contraction, expansion
`mrr_amount` (DECIMAL(10,2)) → ~ "Mrr Amount"
  Stats: null=0.0% | ~distinct=179 | range=[55.00, 9365.00]
  Samples: 55.00, 9365.00
`arr_amount` (DECIMAL(10,2)) → ~ "Arr Amount"
  Stats: null=0.0% | ~distinct=185 | range=[660.00, 112380.00]
  Samples: 660.00, 112380.00
`billing_cycle` (VARCHAR) → ~ "Billing Cycle"
  Stats: null=0.0% | ~distinct=2 | avg_len=7
  Samples: annual, monthly
`started_at` (DATE) → ~ "Started At"
  Stats: null=0.0% | ~distinct=2,062
  Samples: 2019-01-01, 2023-12-30
`cancelled_at` (DATE) → ~ "Cancelled At"
  Stats: null=75.0% | ~distinct=2,037
  Samples: 2019-04-02, 2024-03-29

## main.support_tickets
Rows: 20,000 | Profiled: 2026-03-10

**Columns:**
`ticket_id` (INTEGER) → ~ "Ticket Id"
  Stats: null=0.0% | ~distinct=18,226 | range=[1, 20000]
  Samples: 1, 20000
`account_id` (INTEGER) → ~ "Account Id"
  Stats: null=0.0% | ~distinct=3,075 | range=[1, 3000]
  Samples: 1, 3000
`subject` (VARCHAR)
  Stats: null=0.0% | ~distinct=21,825 | avg_len=10
  Samples: Issue 24, Issue 50, Issue 54
`category` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=9
  Samples: feature_request, technical, billing
`priority` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=4
  Samples: low, medium, high
`status` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=7
  Samples: resolved, open, closed
`created_at` (TIMESTAMP) → ~ "Created At"
  Stats: null=0.0% | ~distinct=17,200
  Samples: 2021-01-01 01:00:00, 2023-04-14 09:00:00
`resolved_at` (TIMESTAMP) → ~ "Resolved At"
  Stats: null=28.6% | ~distinct=7,670
  Samples: 2021-01-01 04:00:00, 2023-04-16 13:00:00
`csat_score` (INTEGER) → ~ "Csat Score"
  Stats: null=20.0% | ~distinct=4 | range=[2, 5]
  Samples: 2, 5

## main.usage_events
Rows: 1,000,000 | Profiled: 2026-03-10

**Columns:**
`event_id` (INTEGER) → ~ "Event Id"
  Stats: null=0.0% | ~distinct=953,281 | range=[1, 1000000]
  Samples: 1, 1000000
`account_id` (INTEGER) → ~ "Account Id"
  Stats: null=0.0% | ~distinct=3,075 | range=[1, 3000]
  Samples: 1, 3000
`subscription_id` (INTEGER) → ~ "Subscription Id"
  Stats: null=0.0% | ~distinct=6,545 | range=[1, 7000]
  Samples: 1, 7000
`event_type` (VARCHAR) → ~ "Event Type"
  Stats: null=0.0% | ~distinct=4 | avg_len=8
  Samples: feature_used, api_call, export
`feature_name` (VARCHAR) → ~ "Feature Name"
  Stats: null=0.0% | ~distinct=6 | avg_len=8
  Samples: integrations, unknown, api
`occurred_at` (TIMESTAMP) → ~ "Occurred At"
  Stats: null=0.0% | ~distinct=979,812
  Samples: 2022-01-01 00:00:30, 2022-12-14 05:20:00
`duration_ms` (INTEGER) → ~ "Duration Ms"
  Stats: null=0.0% | ~distinct=5,212 | range=[100, 5099]
  Samples: 100, 5099


> ℹ No documents loaded. Column semantics are inferred from names and profiles only. Upload a data dictionary or provide a documentation URL to improve accuracy.