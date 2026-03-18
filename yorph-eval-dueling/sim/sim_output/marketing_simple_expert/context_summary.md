# Context Summary — marketing_simple

# Enriched Profiles — Batch 1 of 1 (4 tables)


## main.ad_spend
Rows: 50,000 | Profiled: 2026-03-10

**Columns:**
`spend_id` (INTEGER) → ~ "Spend Id"
  Stats: null=0.0% | ~distinct=45,031 | range=[1, 50000]
  Samples: 1, 50000
`campaign_id` (INTEGER) → ~ "Campaign Id"
  Stats: null=0.0% | ~distinct=223 | range=[1, 200]
  Samples: 1, 200
`spend_date` (DATE) → ~ "Spend Date"
  Stats: null=0.0% | ~distinct=843
  Samples: 2022-01-01, 2023-12-31
`spend_amount` (DECIMAL(10,2)) → ~ "Spend Amount"
  Stats: null=0.0% | ~distinct=7,695 | range=[10.00, 509.90]
  Samples: 10.00, 509.90
`impressions` (INTEGER)
  Stats: null=0.0% | ~distinct=5,212 | range=[100, 5099]
  Samples: 100, 5099
`reach` (INTEGER)
  Stats: null=0.0% | ~distinct=3,075 | range=[50, 3049]
  Samples: 50, 3049

## main.campaigns
Rows: 200 | Profiled: 2026-03-10

**Columns:**
`campaign_id` (INTEGER) → ~ "Campaign Id"
  Stats: null=0.0% | ~distinct=223 | range=[1, 200]
  Samples: 1, 200
`name` (VARCHAR)
  Stats: null=0.0% | ~distinct=247 | avg_len=11
  Samples: Campaign 5, Campaign 7, Campaign 15
`channel` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=7
  Samples: display, email, paid_search
`objective` (VARCHAR)
  Stats: null=0.0% | ~distinct=2 | avg_len=11
  Samples: conversion, consideration, awareness
`start_date` (DATE) → ~ "Start Date"
  Stats: null=0.0% | ~distinct=47
  Samples: 2022-01-01, 2022-12-24
`end_date` (DATE) → ~ "End Date"
  Stats: null=0.0% | ~distinct=50
  Samples: 2022-04-01, 2023-03-24
`budget` (DECIMAL(10,2))
  Stats: null=0.0% | ~distinct=209 | range=[501.00, 10428.00]
  Samples: 501.00, 10428.00
`is_active` (BOOLEAN) → ~ "Is Active"
  Stats: null=0.0% | ~distinct=2

## main.clicks
Rows: 500,000 | Profiled: 2026-03-10

**Columns:**
`click_id` (INTEGER) → ~ "Click Id"
  Stats: null=0.0% | ~distinct=516,619 | range=[1, 500000]
  Samples: 1, 500000
`campaign_id` (INTEGER) → ~ "Campaign Id"
  Stats: null=20.0% | ~distinct=171 | range=[2, 200]
  Samples: 2, 200
`clicked_at` (TIMESTAMP) → ~ "Clicked At"
  Stats: null=0.0% | ~distinct=538,437
  Samples: 2022-01-01 08:01:00, 2022-12-14 13:20:00
`device_type` (VARCHAR) → ~ "Device Type"
  Stats: null=0.0% | ~distinct=3 | avg_len=6
  Samples: tablet, mobile, desktop
`country` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=3
  Samples: DEU, AUS, GBR
`keyword` (VARCHAR)
  Stats: null=33.3% | ~distinct=2 | avg_len=6
  Samples: brand, generic

## main.conversions
Rows: 30,000 | Profiled: 2026-03-10

**Columns:**
`conversion_id` (INTEGER) → ~ "Conversion Id"
  Stats: null=0.0% | ~distinct=28,918 | range=[1, 30000]
  Samples: 1, 30000
`click_id` (INTEGER) → ~ "Click Id"
  Stats: null=0.0% | ~distinct=28,918 | range=[2, 30001]
  Samples: 2, 30001
`campaign_id` (INTEGER) → ~ "Campaign Id"
  Stats: null=0.0% | ~distinct=223 | range=[1, 200]
  Samples: 1, 200
`conversion_type` (VARCHAR) → ~ "Conversion Type"
  Stats: null=0.0% | ~distinct=4 | avg_len=6
  Samples: trial, lead, signup
`revenue` (DECIMAL(10,2))
  Stats: null=50.0% | ~distinct=3,488 | range=[20.00, 519.70]
  Samples: 20.00, 519.70
`converted_at` (TIMESTAMP) → ~ "Converted At"
  Stats: null=0.0% | ~distinct=25,037
  Samples: 2022-01-01 08:05:00, 2022-04-15 13:00:00
`country` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=3
  Samples: DEU, USA, AUS


> ℹ No documents loaded. Column semantics are inferred from names and profiles only. Upload a data dictionary or provide a documentation URL to improve accuracy.