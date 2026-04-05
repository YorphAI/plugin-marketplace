# Scenario Brief: finance_simple

**Domain:** finance | **Complexity:** simple

A minimal accounting schema: chart of accounts, journal entries, cost centers, and periods. Tests whether the agent identifies P&L structure, debit/credit accounting logic, and period-based measures.

---

## Tables

- **accounts**: Chart of accounts. One row per GL account.
- **cost_centers**: Cost center master. P&L accounts are cost-center coded.
- **periods**: Accounting periods (months). Used for period-close reporting.
- **journal_entries**: Double-entry bookkeeping lines. One row per debit/credit line.

---

## Data Quality Issues (deliberately injected)

These are known issues the agent MUST discover and surface:

### journal_entries.cost_center_id — `high_null`

cost_center_id is NULL for balance sheet entries (not P&L). This is correct — only P&L entries are cost-center coded.

**Prevalence:** 35% of rows

### journal_entries.amount — `encoded_null`

Reversing entries have negative amounts. The agent must understand debit/credit logic: revenue is credit (negative in a debit-normal system).

**Prevalence:** 15% of rows

---

## Expected Joins (ground truth)

- `journal_entries` → `accounts` on `account_id` [many:1]
- `journal_entries` → `cost_centers` on `cost_center_id` [many:1]
- `journal_entries` → `periods` on `period_id` [many:1]

---

## Expected Measures (ground truth)

- **Total Revenue**: SUM(journal_entries.amount) WHERE account_type='revenue', entry_type!='reversal'
- **Total Expenses**: SUM(journal_entries.amount) WHERE account_type='expense', entry_type!='reversal'
- **Gross Profit**: SUM(journal_entries.amount) WHERE account_type IN ('revenue','cogs')
- **EBITDA**: SUM(journal_entries.amount) WHERE account_type IN ('revenue','expense','cogs')
- **Journal Entry Count**: COUNT(journal_entries.entry_id)

---

## Expected Business Rules

- In a debit-normal system, revenue is credit (negative). Negate for P&L reporting.
- Reversing entries (entry_type='reversal') must be excluded from period totals.
- cost_center_id NULL = balance sheet entry. Never filter on cost_center for BS accounts.
- Period-end is the close date — use period.end_date for all period-over-period metrics.
