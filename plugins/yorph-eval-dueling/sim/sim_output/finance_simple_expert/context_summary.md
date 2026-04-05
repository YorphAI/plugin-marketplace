# Context Summary — finance_simple

# Enriched Profiles — Batch 1 of 1 (4 tables)


## main.accounts
Rows: 22 | Profiled: 2026-03-10

**Columns:**
`account_id` (VARCHAR) → ~ "Account Id"
  Stats: null=0.0% | ~distinct=21 | avg_len=4
  Samples: 5200, 3100, 1200
`name` (VARCHAR)
  Stats: null=0.0% | ~distinct=23 | avg_len=13
  Samples: Operating Expenses, Deferred Revenue, Depreciation
`account_type` (VARCHAR) → ~ "Account Type"
  Stats: null=0.0% | ~distinct=6 | avg_len=6
  Samples: asset, liability, cogs
`account_class` (VARCHAR) → ~ "Account Class"
  Stats: null=0.0% | ~distinct=2 | avg_len=15
  Samples: balance_sheet, income_statement
`parent_id` (VARCHAR) → ~ "Parent Id"
  Stats: null=54.5% | ~distinct=3 | avg_len=4
  Samples: 6000, 4000, 5000
`is_active` (BOOLEAN) → ~ "Is Active"
  Stats: null=0.0% | ~distinct=1

## main.cost_centers
Rows: 8 | Profiled: 2026-03-10

**Columns:**
`cost_center_id` (VARCHAR) → ~ "Cost Center Id"
  Stats: null=0.0% | ~distinct=9 | avg_len=6
  Samples: CC-008, CC-005, CC-004
`name` (VARCHAR)
  Stats: null=0.0% | ~distinct=9 | avg_len=9
  Samples: IT Infrastructure, Sales, Product
`department` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=5
  Samples: Product, G&A, Revenue
`manager` (VARCHAR)
  Stats: null=0.0% | ~distinct=7 | avg_len=10
  Samples: Alice Smith, Henry Park, Dan Wilson
`budget_owner` (VARCHAR) → ~ "Budget Owner"
  Stats: null=0.0% | ~distinct=5 | avg_len=3
  Samples: CRO, CPO, CTO

## main.journal_entries
Rows: 100,000 | Profiled: 2026-03-10

**Columns:**
`entry_id` (INTEGER) → ~ "Entry Id"
  Stats: null=0.0% | ~distinct=45,031 | range=[1, 50001]
  Samples: 1, 50001
`line_number` (INTEGER) → ~ "Line Number"
  Stats: null=0.0% | ~distinct=2 | range=[1, 2]
  Samples: 1, 2
`period_id` (INTEGER) → ~ "Period Id"
  Stats: null=0.0% | ~distinct=56 | range=[1, 60]
  Samples: 1, 60
`account_id` (VARCHAR) → ~ "Account Id"
  Stats: null=0.0% | ~distinct=9 | avg_len=4
  Samples: 6100, 2000, 1100
`cost_center_id` (VARCHAR) → ~ "Cost Center Id"
  Stats: null=25.0% | ~distinct=6 | avg_len=6
  Samples: CC-003, CC-005, CC-002
`description` (VARCHAR)
  Stats: null=0.0% | ~distinct=107,486 | avg_len=16
  Samples: Entry 10.0-L1, Entry 21.0-L2, Entry 33.0-L2
`amount` (DECIMAL(14,2))
  Stats: null=0.0% | ~distinct=37,760 | range=[-5999.90, 3099.80]
  Samples: -5999.90, 3099.80
`entry_type` (VARCHAR) → ~ "Entry Type"
  Stats: null=0.0% | ~distinct=3 | avg_len=8
  Samples: accrual, standard, reversal
`posted_at` (TIMESTAMP) → ~ "Posted At"
  Stats: null=0.0% | ~distinct=101,980
  Samples: 2020-01-01 01:00:00, 2031-05-29 17:00:00
`created_by` (VARCHAR) → ~ "Created By"
  Stats: null=0.0% | ~distinct=17 | avg_len=6
  Samples: user2, user16, user19

## main.periods
Rows: 60 | Profiled: 2026-03-10

**Columns:**
`period_id` (INTEGER) → ~ "Period Id"
  Stats: null=0.0% | ~distinct=56 | range=[1, 60]
  Samples: 1, 60
`period_name` (VARCHAR) → ~ "Period Name"
  Stats: null=0.0% | ~distinct=49 | avg_len=8
  Samples: Jan 2021, Nov 2021, Sep 2023
`start_date` (DATE) → ~ "Start Date"
  Stats: null=0.0% | ~distinct=56
  Samples: 2020-01-01, 2024-11-05
`end_date` (DATE) → ~ "End Date"
  Stats: null=0.0% | ~distinct=65
  Samples: 2020-01-30, 2024-12-04
`fiscal_year` (INTEGER) → ~ "Fiscal Year"
  Stats: null=0.0% | ~distinct=5 | range=[2020, 2024]
  Samples: 2020, 2024
`fiscal_qtr` (INTEGER) → ~ "Fiscal Qtr"
  Stats: null=0.0% | ~distinct=4 | range=[1, 4]
  Samples: 1, 4
`is_closed` (BOOLEAN) → ~ "Is Closed"
  Stats: null=0.0% | ~distinct=2


> ℹ No documents loaded. Column semantics are inferred from names and profiles only. Upload a data dictionary or provide a documentation URL to improve accuracy.