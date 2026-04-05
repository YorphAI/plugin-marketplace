# Scenario Brief: finance_medium

**Domain:** finance | **Complexity:** medium

Multi-entity finance schema: GL, AP, AR, budget vs actuals, multi-currency, and intercompany transactions. Key challenge: elimination entries (entry_type='elimination') must be excluded from consolidated P&L — the agent must identify this business rule. Multi-currency amounts require the exchange_rate column for USD conversion.

---

## Tables

- **entities**: Legal entities (subsidiaries, holding companies).
- **accounts**: Chart of accounts.
- **cost_centers**: Cost center master.
- **periods**: Accounting periods.
- **journal_entries**: All GL entries including intercompany eliminations.
- **vendors**: AP vendor master.
- **ap_invoices**: Accounts payable invoices.
- **customers**: AR customer master.
- **ar_invoices**: Accounts receivable invoices.
- **budget_vs_actuals**: Period-level budget vs actual comparison by account and cost center.

---

## Data Quality Issues (deliberately injected)

These are known issues the agent MUST discover and surface:

### journal_entries.entity_id — `ambiguous_key`

Consolidated reports must exclude intercompany elimination entries (entry_type='elimination'). Missing this filter overstates revenue and expenses. A critical business rule the agent must surface.

**Prevalence:** 8% of rows

### journal_entries.amount_usd — `high_null`

amount_usd is NULL for entries in USD (no conversion needed). Use COALESCE(amount_usd, amount) for USD-normalised reporting.

**Prevalence:** 60% of rows

### budget_vs_actuals.variance_pct — `duplicate_metric`

budget_vs_actuals.variance_pct can be derived from actual_amount and budget_amount. Having it pre-computed creates a risk of inconsistency if the formula changes.

**Prevalence:** always

---

## Expected Joins (ground truth)

- `journal_entries` → `accounts` on `account_id` [many:1]
- `journal_entries` → `cost_centers` on `cost_center_id` [many:1]
- `journal_entries` → `periods` on `period_id` [many:1]
- `journal_entries` → `entities` on `entity_id` [many:1]
- `ap_invoices` → `vendors` on `vendor_id` [many:1]
- `ap_invoices` → `periods` on `period_id` [many:1]
- `ar_invoices` → `customers` on `customer_id` [many:1]
- `ar_invoices` → `periods` on `period_id` [many:1]
- `budget_vs_actuals` → `accounts` on `account_id` [many:1]
- `budget_vs_actuals` → `cost_centers` on `cost_center_id` [many:1]

---

## Expected Measures (ground truth)

- **Consolidated Revenue**: SUM(journal_entries.amount) WHERE account_type='revenue', entry_type!='elimination', entry_type!='reversal'
- **AP Outstanding**: SUM(ap_invoices.amount_due) WHERE status='open'
- **AR Outstanding**: SUM(ar_invoices.amount_due) WHERE status='open'
- **Budget Variance $**: SUM(budget_vs_actuals.variance_amount)
- **Budget Variance %**: AVG(budget_vs_actuals.variance_pct)

---

## Expected Business Rules

- ALWAYS exclude entry_type='elimination' from consolidated P&L to avoid double-counting.
- ALWAYS exclude entry_type='reversal' from period totals.
- Multi-currency: use COALESCE(amount_usd, amount) to normalise all amounts to USD.
- AP outstanding = sum of ap_invoices.amount_due WHERE status='open'.
- AR DSO = AR outstanding / (annual revenue / 365).
