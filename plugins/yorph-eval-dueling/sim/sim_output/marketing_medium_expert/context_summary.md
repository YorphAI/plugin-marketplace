# Context Summary — marketing_medium

# Enriched Profiles — Batch 1 of 1 (6 tables)


## main.ad_spend
Rows: 100,000 | Profiled: 2026-03-10

**Columns:**
`spend_id` (INTEGER) → ~ "Spend Id"
  Stats: null=0.0% | ~distinct=96,025 | range=[1, 100000]
  Samples: 1, 100000
`campaign_id` (INTEGER) → ~ "Campaign Id"
  Stats: null=0.0% | ~distinct=520 | range=[1, 500]
  Samples: 1, 500
`spend_date` (DATE) → ~ "Spend Date"
  Stats: null=0.0% | ~distinct=1,378
  Samples: 2021-01-01, 2023-12-31
`spend_amount` (DECIMAL(10,2)) → ~ "Spend Amount"
  Stats: null=0.0% | ~distinct=13,008 | range=[5.00, 1004.90]
  Samples: 5.00, 1004.90
`impressions` (INTEGER)
  Stats: null=0.0% | ~distinct=7,957 | range=[500, 10499]
  Samples: 500, 10499
`clicks` (INTEGER)
  Stats: null=0.0% | ~distinct=520 | range=[10, 509]
  Samples: 10, 509

## main.campaign_budgets
Rows: 18,000 | Profiled: 2026-03-10

**Columns:**
`campaign_id` (INTEGER) → ~ "Campaign Id"
  Stats: null=0.0% | ~distinct=520 | range=[1, 500]
  Samples: 1, 500
`budget_month` (DATE) → ~ "Budget Month"
  Stats: null=0.0% | ~distinct=33
  Samples: 2021-01-01, 2023-12-01
`allocated_budget` (DECIMAL(10,2)) → ~ "Allocated Budget"
  Stats: null=0.0% | ~distinct=23,788 | range=[1000.00, 20999.00]
  Samples: 1000.00, 20999.00

## main.campaigns
Rows: 500 | Profiled: 2026-03-10

**Columns:**
`campaign_id` (INTEGER) → ~ "Campaign Id"
  Stats: null=0.0% | ~distinct=520 | range=[1, 500]
  Samples: 1, 500
`name` (VARCHAR)
  Stats: null=0.0% | ~distinct=462 | avg_len=12
  Samples: Campaign 1, Campaign 3, Campaign 6
`channel` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=7
  Samples: email, paid_search, display
`objective` (VARCHAR)
  Stats: null=0.0% | ~distinct=2 | avg_len=11
  Samples: conversion, awareness, consideration
`start_date` (DATE) → ~ "Start Date"
  Stats: null=0.0% | ~distinct=99
  Samples: 2021-01-01, 2022-12-23
`end_date` (DATE) → ~ "End Date"
  Stats: null=0.0% | ~distinct=101
  Samples: 2021-04-01, 2023-03-23
`is_active` (BOOLEAN) → ~ "Is Active"
  Stats: null=0.0% | ~distinct=2

## main.conversions
Rows: 100,000 | Profiled: 2026-03-10

**Columns:**
`conversion_id` (INTEGER) → ~ "Conversion Id"
  Stats: null=0.0% | ~distinct=96,025 | range=[1, 100000]
  Samples: 1, 100000
`session_id` (INTEGER) → ~ "Session Id"
  Stats: null=0.0% | ~distinct=96,618 | range=[1, 1999981]
  Samples: 1, 1999981
`campaign_id` (INTEGER) → ~ "Campaign Id"
  Stats: null=0.0% | ~distinct=520 | range=[1, 500]
  Samples: 1, 500
`revenue` (DECIMAL(10,2))
  Stats: null=33.3% | ~distinct=2,081 | range=[15.00, 614.70]
  Samples: 15.00, 614.70
`conversion_type` (VARCHAR) → ~ "Conversion Type"
  Stats: null=0.0% | ~distinct=2 | avg_len=7
  Samples: purchase, lead
`converted_at` (TIMESTAMP) → ~ "Converted At"
  Stats: null=0.0% | ~distinct=110,823
  Samples: 2021-01-01 08:40:00, 2028-08-10 03:40:00

## main.sessions
Rows: 2,000,000 | Profiled: 2026-03-10

**Columns:**
`session_id` (INTEGER) → ~ "Session Id"
  Stats: null=0.0% | ~distinct=1,831,607 | range=[1, 2000000]
  Samples: 1, 2000000
`campaign_id` (INTEGER) → ~ "Campaign Id"
  Stats: null=20.0% | ~distinct=357 | range=[2, 500]
  Samples: 2, 500
`utm_source` (VARCHAR) → ~ "Utm Source"
  Stats: null=0.0% | ~distinct=4 | avg_len=5
  Samples: email, direct, meta
`utm_medium` (VARCHAR) → ~ "Utm Medium"
  Stats: null=0.0% | ~distinct=5 | avg_len=5
  Samples: email, cpc, organic
`utm_campaign` (VARCHAR) → ~ "Utm Campaign"
  Stats: null=20.0% | ~distinct=371 | avg_len=12
  Samples: campaign_425, campaign_429, campaign_455
`started_at` (TIMESTAMP) → ~ "Started At"
  Stats: null=0.0% | ~distinct=2,184,835
  Samples: 2021-01-01 08:02:00, 2028-08-10 03:40:00
`device_type` (VARCHAR) → ~ "Device Type"
  Stats: null=0.0% | ~distinct=3 | avg_len=6
  Samples: tablet, mobile, desktop
`converted` (BOOLEAN)
  Stats: null=0.0% | ~distinct=2

## main.touchpoints
Rows: 300,000 | Profiled: 2026-03-10

**Columns:**
`touchpoint_id` (INTEGER) → ~ "Touchpoint Id"
  Stats: null=0.0% | ~distinct=273,786 | range=[1, 300000]
  Samples: 1, 300000
`conversion_id` (INTEGER) → ~ "Conversion Id"
  Stats: null=0.0% | ~distinct=96,025 | range=[1, 100001]
  Samples: 1, 100001
`channel` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=7
  Samples: social, email, paid_search
`position` (VARCHAR)
  Stats: null=0.0% | ~distinct=3 | avg_len=5
  Samples: last, first, middle
`credit_pct` (DECIMAL(5,2)) → ~ "Credit Pct"
  Stats: null=0.0% | ~distinct=1 | range=[33.33, 33.33]
  Samples: 33.33, 33.33
`touched_at` (TIMESTAMP) → ~ "Touched At"
  Stats: null=0.0% | ~distinct=331,851
  Samples: 2021-01-01 08:13:20, 2028-08-10 03:40:00


> ℹ No documents loaded. Column semantics are inferred from names and profiles only. Upload a data dictionary or provide a documentation URL to improve accuracy.