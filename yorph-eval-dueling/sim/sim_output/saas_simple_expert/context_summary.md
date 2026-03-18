# Context Summary — saas_simple

# Enriched Profiles — Batch 1 of 1 (4 tables)


## main.accounts
Rows: 2,000 | Profiled: 2026-03-10

**Columns:**
`account_id` (INTEGER) → ~ "Account Id"
  Stats: null=0.0% | ~distinct=2,308 | range=[1, 2000]
  Samples: 1, 2000
`name` (VARCHAR)
  Stats: null=0.0% | ~distinct=2,080 | avg_len=11
  Samples: Company 5, Company 13, Company 25
`domain` (VARCHAR)
  Stats: null=0.0% | ~distinct=2,062 | avg_len=13
  Samples: company13.io, company15.io, company17.io
`plan` (VARCHAR)
  Stats: null=0.0% | ~distinct=3 | avg_len=7
  Samples: enterprise, starter, growth
`industry` (VARCHAR)
  Stats: null=0.0% | ~distinct=6 | avg_len=7
  Samples: E-commerce, Media, HealthTech
`employee_count` (INTEGER) → ~ "Employee Count"
  Stats: null=0.0% | ~distinct=237 | range=[10, 2000]
  Samples: 10, 2000
`country` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=3
  Samples: DEU, USA, GBR
`created_at` (TIMESTAMP) → ~ "Created At"
  Stats: null=0.0% | ~distinct=2,072
  Samples: 2020-01-02 00:00:00, 2025-06-23 01:00:00
`health_score` (DECIMAL(4,1)) → ~ "Health Score"
  Stats: null=0.0% | ~distinct=837 | range=[20.0, 99.9]
  Samples: 20.0, 99.9

## main.billing_periods
Rows: 30,000 | Profiled: 2026-03-10

**Columns:**
`billing_id` (INTEGER) → ~ "Billing Id"
  Stats: null=0.0% | ~distinct=28,918 | range=[1, 30000]
  Samples: 1, 30000
`subscription_id` (INTEGER) → ~ "Subscription Id"
  Stats: null=0.0% | ~distinct=5,618 | range=[1, 5000]
  Samples: 1, 5000
`period_start` (DATE) → ~ "Period Start"
  Stats: null=0.0% | ~distinct=2,474
  Samples: 2020-01-01, 2225-05-06
`period_end` (DATE) → ~ "Period End"
  Stats: null=0.0% | ~distinct=2,474
  Samples: 2020-01-31, 2225-06-05
`amount_invoiced` (DECIMAL(10,2)) → ~ "Amount Invoiced"
  Stats: null=0.0% | ~distinct=23,369 | range=[50.00, 2049.90]
  Samples: 50.00, 2049.90
`amount_paid` (DECIMAL(10,2)) → ~ "Amount Paid"
  Stats: null=6.7% | ~distinct=23,190 | range=[50.00, 2049.90]
  Samples: 50.00, 2049.90
`status` (VARCHAR)
  Stats: null=0.0% | ~distinct=3 | avg_len=4
  Samples: paid, overdue, void
`paid_at` (TIMESTAMP) → ~ "Paid At"
  Stats: null=6.7% | ~distinct=24,095
  Samples: 2020-01-02 00:00:00, 2102-02-19 00:00:00

## main.subscriptions
Rows: 5,000 | Profiled: 2026-03-10

**Columns:**
`subscription_id` (INTEGER) → ~ "Subscription Id"
  Stats: null=0.0% | ~distinct=5,618 | range=[1, 5000]
  Samples: 1, 5000
`account_id` (INTEGER) → ~ "Account Id"
  Stats: null=0.0% | ~distinct=2,308 | range=[1, 2000]
  Samples: 1, 2000
`plan` (VARCHAR)
  Stats: null=0.0% | ~distinct=3 | avg_len=7
  Samples: growth, enterprise, starter
`status` (VARCHAR)
  Stats: null=0.0% | ~distinct=3 | avg_len=7
  Samples: paused, cancelled, active
`type` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=6
  Samples: reactivation, contraction, expansion
`mrr_amount` (DECIMAL(10,2)) → ~ "Mrr Amount"
  Stats: null=0.0% | ~distinct=139 | range=[55.00, 6410.00]
  Samples: 55.00, 6410.00
`arr_amount` (DECIMAL(10,2)) → ~ "Arr Amount"
  Stats: null=0.0% | ~distinct=174 | range=[660.00, 76920.00]
  Samples: 660.00, 76920.00
`billing_cycle` (VARCHAR) → ~ "Billing Cycle"
  Stats: null=0.0% | ~distinct=3 | avg_len=7
  Samples: quarterly, annual, monthly
`started_at` (DATE) → ~ "Started At"
  Stats: null=0.0% | ~distinct=1,654
  Samples: 2020-01-01, 2023-12-30
`cancelled_at` (DATE) → ~ "Cancelled At"
  Stats: null=75.0% | ~distinct=359
  Samples: 2020-03-31, 2024-03-26
`trial_ends_at` (DATE) → ~ "Trial Ends At"
  Stats: null=95.0% | ~distinct=76
  Samples: 2020-01-15, 2023-12-25

## main.usage_events
Rows: 500,000 | Profiled: 2026-03-10

**Columns:**
`event_id` (INTEGER) → ~ "Event Id"
  Stats: null=0.0% | ~distinct=516,619 | range=[1, 500000]
  Samples: 1, 500000
`account_id` (INTEGER) → ~ "Account Id"
  Stats: null=0.0% | ~distinct=2,308 | range=[1, 2000]
  Samples: 1, 2000
`subscription_id` (INTEGER) → ~ "Subscription Id"
  Stats: null=0.0% | ~distinct=5,618 | range=[1, 5000]
  Samples: 1, 5000
`event_type` (VARCHAR) → ~ "Event Type"
  Stats: null=0.0% | ~distinct=4 | avg_len=8
  Samples: api_call, export, feature_used
`feature_name` (VARCHAR) → ~ "Feature Name"
  Stats: null=0.0% | ~distinct=7 | avg_len=8
  Samples: reports, settings, integrations
`occurred_at` (TIMESTAMP) → ~ "Occurred At"
  Stats: null=0.0% | ~distinct=538,437
  Samples: 2022-01-01 00:01:00, 2022-12-14 05:20:00
`duration_ms` (INTEGER) → ~ "Duration Ms"
  Stats: null=0.0% | ~distinct=5,212 | range=[100, 5099]
  Samples: 100, 5099
`metadata` (VARCHAR)
  Stats: null=0.0% | ~distinct=1 | avg_len=20
  Samples: {"source": "sdk_v2"}


> ℹ No documents loaded. Column semantics are inferred from names and profiles only. Upload a data dictionary or provide a documentation URL to improve accuracy.