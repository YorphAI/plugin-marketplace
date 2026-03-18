# Context Summary — finance_medium

# Enriched Profiles — Batch 1 of 1 (10 tables)


## main.accounts
Rows: 14 | Profiled: 2026-03-10

**Columns:**
`account_id` (VARCHAR) → ~ "Account Id"
  Stats: null=0.0% | ~distinct=14 | avg_len=4
  Samples: 6100, 6400, 2000
`name` (VARCHAR)
  Stats: null=0.0% | ~distinct=15 | avg_len=11
  Samples: Operating Expenses, Salaries, Service Revenue
`account_type` (VARCHAR) → ~ "Account Type"
  Stats: null=0.0% | ~distinct=6 | avg_len=6
  Samples: asset, liability, revenue
`account_class` (VARCHAR) → ~ "Account Class"
  Stats: null=0.0% | ~distinct=2 | avg_len=15
  Samples: balance_sheet, income_statement
`parent_id` (VARCHAR) → ~ "Parent Id"
  Stats: null=50.0% | ~distinct=3 | avg_len=4
  Samples: 6000, 4000, 5000
`is_active` (BOOLEAN) → ~ "Is Active"
  Stats: null=0.0% | ~distinct=1

## main.ap_invoices
Rows: 10,000 | Profiled: 2026-03-10

**Columns:**
`invoice_id` (INTEGER) → ~ "Invoice Id"
  Stats: null=0.0% | ~distinct=8,565 | range=[1, 10000]
  Samples: 1, 10000
`vendor_id` (INTEGER) → ~ "Vendor Id"
  Stats: null=0.0% | ~distinct=223 | range=[1, 200]
  Samples: 1, 200
`period_id` (INTEGER) → ~ "Period Id"
  Stats: null=0.0% | ~distinct=56 | range=[1, 60]
  Samples: 1, 60
`entity_id` (VARCHAR) → ~ "Entity Id"
  Stats: null=0.0% | ~distinct=5 | avg_len=7
  Samples: ENT-005, ENT-003, ENT-004
`invoice_date` (DATE) → ~ "Invoice Date"
  Stats: null=0.0% | ~distinct=1,654
  Samples: 2020-01-01, 2023-12-30
`due_date` (DATE) → ~ "Due Date"
  Stats: null=0.0% | ~distinct=1,654
  Samples: 2020-01-31, 2024-01-29
`amount_total` (DECIMAL(12,2)) → ~ "Amount Total"
  Stats: null=0.0% | ~distinct=9,462 | range=[502.00, 20499.00]
  Samples: 502.00, 20499.00
`amount_due` (DECIMAL(12,2)) → ~ "Amount Due"
  Stats: null=0.0% | ~distinct=8,250 | range=[0.00, 20499.00]
`currency` (VARCHAR)
  Stats: null=0.0% | ~distinct=3 | avg_len=3
  Samples: GBP, USD, EUR
`status` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=4
  Samples: paid, open, overdue

## main.ar_invoices
Rows: 15,000 | Profiled: 2026-03-10

**Columns:**
`invoice_id` (INTEGER) → ~ "Invoice Id"
  Stats: null=0.0% | ~distinct=13,155 | range=[1, 15000]
  Samples: 1, 15000
`customer_id` (INTEGER) → ~ "Customer Id"
  Stats: null=0.0% | ~distinct=520 | range=[1, 500]
  Samples: 1, 500
`period_id` (INTEGER) → ~ "Period Id"
  Stats: null=0.0% | ~distinct=56 | range=[1, 60]
  Samples: 1, 60
`entity_id` (VARCHAR) → ~ "Entity Id"
  Stats: null=0.0% | ~distinct=5 | avg_len=7
  Samples: ENT-005, ENT-003, ENT-004
`invoice_date` (DATE) → ~ "Invoice Date"
  Stats: null=0.0% | ~distinct=1,654
  Samples: 2020-01-01, 2023-12-30
`due_date` (DATE) → ~ "Due Date"
  Stats: null=0.0% | ~distinct=1,601
  Samples: 2020-02-15, 2024-02-13
`amount_total` (DECIMAL(12,2)) → ~ "Amount Total"
  Stats: null=0.0% | ~distinct=14,792 | range=[1003.00, 50998.00]
  Samples: 1003.00, 50998.00
`amount_due` (DECIMAL(12,2)) → ~ "Amount Due"
  Stats: null=0.0% | ~distinct=13,565 | range=[0.00, 50998.00]
`currency` (VARCHAR)
  Stats: null=0.0% | ~distinct=3 | avg_len=3
  Samples: EUR, GBP, USD
`status` (VARCHAR)
  Stats: null=0.0% | ~distinct=3 | avg_len=4
  Samples: open, overdue, paid

## main.budget_vs_actuals
Rows: 2,400 | Profiled: 2026-03-10

**Columns:**
`account_id` (VARCHAR) → ~ "Account Id"
  Stats: null=0.0% | ~distinct=5 | avg_len=4
  Samples: 6100, 4100, 6300
`cost_center_id` (VARCHAR) → ~ "Cost Center Id"
  Stats: null=0.0% | ~distinct=9 | avg_len=6
  Samples: CC-008, CC-004, CC-007
`period_id` (INTEGER) → ~ "Period Id"
  Stats: null=0.0% | ~distinct=56 | range=[1, 60]
  Samples: 1, 60
`budget_amount` (DECIMAL(12,2)) → ~ "Budget Amount"
  Stats: null=0.0% | ~distinct=2,588 | range=[5000.00, 54942.00]
  Samples: 5000.00, 54942.00
`actual_amount` (DECIMAL(12,2)) → ~ "Actual Amount"
  Stats: null=0.0% | ~distinct=2,592 | range=[4500.00, 56492.00]
  Samples: 4500.00, 56492.00
`variance_amount` (DECIMAL(12,2)) → ~ "Variance Amount"
  Stats: null=0.0% | ~distinct=2,162 | range=[-20894.00, 45390.00]
  Samples: -20894.00, 45390.00
`variance_pct` (DECIMAL(8,4)) → ~ "Variance Pct"
  Stats: null=0.0% | ~distinct=2,177 | range=[-81.8403, 906.8931]
  Samples: -81.8403, 906.8931

## main.cost_centers
Rows: 8 | Profiled: 2026-03-10

**Columns:**
`cost_center_id` (VARCHAR) → ~ "Cost Center Id"
  Stats: null=0.0% | ~distinct=9 | avg_len=6
  Samples: CC-008, CC-004, CC-005
`name` (VARCHAR)
  Stats: null=0.0% | ~distinct=9 | avg_len=7
  Samples: IT, Finance, HR
`department` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=5
  Samples: Product, Revenue, R&D

## main.customers
Rows: 500 | Profiled: 2026-03-10

**Columns:**
`customer_id` (INTEGER) → ~ "Customer Id"
  Stats: null=0.0% | ~distinct=520 | range=[1, 500]
  Samples: 1, 500
`name` (VARCHAR)
  Stats: null=0.0% | ~distinct=517 | avg_len=12
  Samples: Customer 69, Customer 91, Customer 106
`country` (VARCHAR)
  Stats: null=0.0% | ~distinct=3 | avg_len=3
  Samples: GBR, DEU, USA
`credit_limit` (DECIMAL(12,2)) → ~ "Credit Limit"
  Stats: null=0.0% | ~distinct=562 | range=[10010.00, 109300.00]
  Samples: 10010.00, 109300.00

## main.entities
Rows: 5 | Profiled: 2026-03-10

**Columns:**
`entity_id` (VARCHAR) → ~ "Entity Id"
  Stats: null=0.0% | ~distinct=5 | avg_len=7
  Samples: ENT-005, ENT-003, ENT-004
`name` (VARCHAR)
  Stats: null=0.0% | ~distinct=5 | avg_len=16
  Samples: UK Operations Ltd, Australia Pty Ltd, US Operations LLC
`country` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=3
  Samples: USA, DEU, GBR
`currency` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=3
  Samples: USD, GBP, EUR
`is_parent` (BOOLEAN) → ~ "Is Parent"
  Stats: null=0.0% | ~distinct=2
`parent_id` (VARCHAR) → ~ "Parent Id"
  Stats: null=20.0% | ~distinct=1 | avg_len=7
  Samples: ENT-001

## main.journal_entries
Rows: 200,000 | Profiled: 2026-03-10

**Columns:**
`entry_id` (INTEGER) → ~ "Entry Id"
  Stats: null=0.0% | ~distinct=96,025 | range=[1, 100001]
  Samples: 1, 100001
`line_number` (INTEGER) → ~ "Line Number"
  Stats: null=0.0% | ~distinct=2 | range=[1, 2]
  Samples: 1, 2
`entity_id` (VARCHAR) → ~ "Entity Id"
  Stats: null=0.0% | ~distinct=5 | avg_len=7
  Samples: ENT-005, ENT-001, ENT-004
`period_id` (INTEGER) → ~ "Period Id"
  Stats: null=0.0% | ~distinct=56 | range=[1, 60]
  Samples: 1, 60
`account_id` (VARCHAR) → ~ "Account Id"
  Stats: null=0.0% | ~distinct=7 | avg_len=4
  Samples: 4100, 6100, 2000
`cost_center_id` (VARCHAR) → ~ "Cost Center Id"
  Stats: null=28.6% | ~distinct=9 | avg_len=6
  Samples: CC-008, CC-004, CC-006
`description` (VARCHAR)
  Stats: null=0.0% | ~distinct=89,936 | avg_len=13
  Samples: Entry 61443.0, Entry 61446.0, Entry 61447.0
`amount` (DECIMAL(14,2))
  Stats: null=0.0% | ~distinct=83,825 | range=[-10049.90, 10049.80]
  Samples: -10049.90, 10049.80
`currency` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=3
  Samples: AUD, EUR, GBP
`exchange_rate` (DECIMAL(10,6)) → ~ "Exchange Rate"
  Stats: null=0.0% | ~distinct=4 | range=[0.650000, 1.270000]
  Samples: 0.650000, 1.270000
`amount_usd` (DECIMAL(14,2)) → ~ "Amount Usd"
  Stats: null=40.0% | ~distinct=64,320 | range=[32.76, 12763.25]
  Samples: 32.76, 12763.25
`entry_type` (VARCHAR) → ~ "Entry Type"
  Stats: null=0.0% | ~distinct=4 | avg_len=8
  Samples: accrual, elimination, reversal
`posted_at` (TIMESTAMP) → ~ "Posted At"
  Stats: null=0.0% | ~distinct=220,479
  Samples: 2020-01-01 00:30:00, 2031-05-29 17:00:00

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

## main.vendors
Rows: 200 | Profiled: 2026-03-10

**Columns:**
`vendor_id` (INTEGER) → ~ "Vendor Id"
  Stats: null=0.0% | ~distinct=223 | range=[1, 200]
  Samples: 1, 200
`name` (VARCHAR)
  Stats: null=0.0% | ~distinct=279 | avg_len=9
  Samples: Vendor 10, Vendor 15, Vendor 28
`country` (VARCHAR)
  Stats: null=0.0% | ~distinct=3 | avg_len=3
  Samples: DEU, GBR, USA
`category` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=12
  Samples: Professional Services, Software, Office
`payment_terms` (INTEGER) → ~ "Payment Terms"
  Stats: null=0.0% | ~distinct=3 | range=[30, 60]
  Samples: 30, 60


> ℹ No documents loaded. Column semantics are inferred from names and profiles only. Upload a data dictionary or provide a documentation URL to improve accuracy.