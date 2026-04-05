"""
Finance / accounting simulation scenarios.

  SIMPLE  — GL accounts, journal entries, cost centers. Basic P&L measures.
  MEDIUM  — adds AP, AR, budget vs actuals, multi-currency, and the
            "elimination entries" problem (intercompany transactions that
            must be excluded from consolidated reporting).
"""

from .base import (
    Scenario, DataQualityIssue, GroundTruth,
    ExpectedJoin, ExpectedMeasure,
)


# ── SIMPLE ─────────────────────────────────────────────────────────────────────

FINANCE_SIMPLE = Scenario(
    name="finance_simple",
    domain="finance",
    complexity="simple",
    description=(
        "A minimal accounting schema: chart of accounts, journal entries, cost centers, "
        "and periods. Tests whether the agent identifies P&L structure, debit/credit "
        "accounting logic, and period-based measures."
    ),
    schemas=["main"],
    data_quality_issues=[
        DataQualityIssue(
            table="journal_entries", column="cost_center_id",
            issue_type="high_null",
            description=(
                "cost_center_id is NULL for balance sheet entries (not P&L). "
                "This is correct — only P&L entries are cost-center coded."
            ),
            prevalence="35% of rows",
        ),
        DataQualityIssue(
            table="journal_entries", column="amount",
            issue_type="encoded_null",
            description=(
                "Reversing entries have negative amounts. "
                "The agent must understand debit/credit logic: "
                "revenue is credit (negative in a debit-normal system)."
            ),
            prevalence="15% of rows",
        ),
    ],
    ground_truth=GroundTruth(
        expected_joins=[
            ExpectedJoin("journal_entries", "accounts",     "account_id",     "many:1"),
            ExpectedJoin("journal_entries", "cost_centers", "cost_center_id", "many:1"),
            ExpectedJoin("journal_entries", "periods",      "period_id",      "many:1"),
        ],
        expected_measures=[
            ExpectedMeasure("total_revenue",   "Total Revenue",     "SUM", "journal_entries","amount",
                            ["account_type='revenue'", "entry_type!='reversal'"],   "P&L"),
            ExpectedMeasure("total_expenses",  "Total Expenses",    "SUM", "journal_entries","amount",
                            ["account_type='expense'", "entry_type!='reversal'"],   "P&L"),
            ExpectedMeasure("gross_profit",    "Gross Profit",      "SUM", "journal_entries","amount",
                            ["account_type IN ('revenue','cogs')"],                  "P&L"),
            ExpectedMeasure("ebitda",          "EBITDA",            "SUM", "journal_entries","amount",
                            ["account_type IN ('revenue','expense','cogs')"],        "P&L"),
            ExpectedMeasure("entry_count",     "Journal Entry Count","COUNT","journal_entries","entry_id",[],  "Operations"),
        ],
        business_rules=[
            "In a debit-normal system, revenue is credit (negative). Negate for P&L reporting.",
            "Reversing entries (entry_type='reversal') must be excluded from period totals.",
            "cost_center_id NULL = balance sheet entry. Never filter on cost_center for BS accounts.",
            "Period-end is the close date — use period.end_date for all period-over-period metrics.",
        ],
        open_questions=[
            "Is this a debit-normal or credit-normal accounting system?",
            "Should EBITDA include depreciation entries, or are they separate account types?",
            "Are intercompany transactions present and should they be eliminated?",
        ],
        grain_per_table={
            "accounts":        ["account_id"],
            "cost_centers":    ["cost_center_id"],
            "periods":         ["period_id"],
            "journal_entries": ["entry_id", "line_number"],
        },
    ),
    table_descriptions={
        "accounts":        "Chart of accounts. One row per GL account.",
        "cost_centers":    "Cost center master. P&L accounts are cost-center coded.",
        "periods":         "Accounting periods (months). Used for period-close reporting.",
        "journal_entries": "Double-entry bookkeeping lines. One row per debit/credit line.",
    },
    seed_sql=[
        """
        CREATE TABLE accounts (
            account_id    VARCHAR PRIMARY KEY,   -- e.g. '4000', '5100'
            name          VARCHAR,
            account_type  VARCHAR,    -- revenue | expense | cogs | asset | liability | equity
            account_class VARCHAR,    -- income_statement | balance_sheet
            parent_id     VARCHAR,    -- hierarchical chart of accounts
            is_active     BOOLEAN
        )
        """,
        """
        INSERT INTO accounts VALUES
            -- Revenue
            ('4000', 'Revenue',               'revenue',   'income_statement', NULL, true),
            ('4100', 'Product Revenue',        'revenue',   'income_statement', '4000', true),
            ('4200', 'Service Revenue',        'revenue',   'income_statement', '4000', true),
            ('4300', 'Subscription Revenue',   'revenue',   'income_statement', '4000', true),
            -- COGS
            ('5000', 'Cost of Goods Sold',     'cogs',      'income_statement', NULL, true),
            ('5100', 'Direct Materials',       'cogs',      'income_statement', '5000', true),
            ('5200', 'Direct Labour',          'cogs',      'income_statement', '5000', true),
            -- Expenses
            ('6000', 'Operating Expenses',     'expense',   'income_statement', NULL, true),
            ('6100', 'Salaries',               'expense',   'income_statement', '6000', true),
            ('6200', 'Rent',                   'expense',   'income_statement', '6000', true),
            ('6300', 'Marketing',              'expense',   'income_statement', '6000', true),
            ('6400', 'Depreciation',           'expense',   'income_statement', '6000', true),
            ('6500', 'R&D',                    'expense',   'income_statement', '6000', true),
            -- Assets
            ('1000', 'Cash',                   'asset',     'balance_sheet',    NULL, true),
            ('1100', 'Accounts Receivable',    'asset',     'balance_sheet',    NULL, true),
            ('1200', 'Inventory',              'asset',     'balance_sheet',    NULL, true),
            ('1500', 'Fixed Assets',           'asset',     'balance_sheet',    NULL, true),
            -- Liabilities
            ('2000', 'Accounts Payable',       'liability', 'balance_sheet',    NULL, true),
            ('2100', 'Accrued Expenses',       'liability', 'balance_sheet',    NULL, true),
            ('2200', 'Deferred Revenue',       'liability', 'balance_sheet',    NULL, true),
            -- Equity
            ('3000', 'Retained Earnings',      'equity',    'balance_sheet',    NULL, true),
            ('3100', 'Common Stock',           'equity',    'balance_sheet',    NULL, true)
        """,
        """
        CREATE TABLE cost_centers (
            cost_center_id  VARCHAR PRIMARY KEY,
            name            VARCHAR,
            department      VARCHAR,
            manager         VARCHAR,
            budget_owner    VARCHAR
        )
        """,
        """
        INSERT INTO cost_centers VALUES
            ('CC-001', 'Engineering',          'R&D',        'Alice Smith',  'CTO'),
            ('CC-002', 'Product',              'Product',    'Bob Jones',    'CPO'),
            ('CC-003', 'Sales',                'Revenue',    'Carol Davis',  'CRO'),
            ('CC-004', 'Marketing',            'Revenue',    'Dan Wilson',   'CMO'),
            ('CC-005', 'Customer Success',     'Revenue',    'Eve Brown',    'CRO'),
            ('CC-006', 'Finance',              'G&A',        'Frank Lee',    'CFO'),
            ('CC-007', 'HR',                   'G&A',        'Grace Kim',    'CPO'),
            ('CC-008', 'IT Infrastructure',    'R&D',        'Henry Park',   'CTO')
        """,
        """
        CREATE TABLE periods (
            period_id    INTEGER PRIMARY KEY,
            period_name  VARCHAR,      -- e.g. 'Jan 2023'
            start_date   DATE,
            end_date     DATE,
            fiscal_year  INTEGER,
            fiscal_qtr   INTEGER,
            is_closed    BOOLEAN
        )
        """,
        """
        INSERT INTO periods
        SELECT
            i,
            strftime(DATE '2020-01-01' + INTERVAL ((i-1)*30) DAY, '%b %Y'),
            DATE '2020-01-01' + INTERVAL ((i-1)*30) DAY,
            DATE '2020-01-01' + INTERVAL (i*30-1) DAY,
            2020 + CAST(FLOOR((i-1)/12) AS INTEGER),
            CAST(FLOOR((i-1)/3) % 4 + 1 AS INTEGER),
            i < 49   -- first 4 years closed
        FROM generate_series(1, 60) t(i)
        """,
        """
        CREATE TABLE journal_entries (
            entry_id       INTEGER,
            line_number    INTEGER,
            period_id      INTEGER,
            account_id     VARCHAR,
            cost_center_id VARCHAR,    -- NULL for balance sheet accounts
            description    VARCHAR,
            amount         DECIMAL(14,2),   -- positive=debit, negative=credit
            entry_type     VARCHAR,   -- standard | accrual | reversal | elimination
            posted_at      TIMESTAMP,
            created_by     VARCHAR,
            PRIMARY KEY (entry_id, line_number)
        )
        """,
        """
        INSERT INTO journal_entries
        SELECT
            CAST(FLOOR(i/2) + 1 AS INTEGER) AS entry_id,
            (i%2)+1 AS line_number,
            (i%60)+1 AS period_id,
            CASE WHEN i%8=0 THEN '4100' WHEN i%8=1 THEN '4200' WHEN i%8=2 THEN '4300'
                 WHEN i%8=3 THEN '5100' WHEN i%8=4 THEN '6100' WHEN i%8=5 THEN '6300'
                 WHEN i%8=6 THEN '1100' ELSE '2000' END AS account_id,
            -- balance sheet accounts get NULL cost_center
            CASE WHEN i%8 >= 6 THEN NULL
                 ELSE 'CC-00' || CAST((i%8)+1 AS VARCHAR) END AS cost_center_id,
            'Entry ' || CAST(FLOOR(i/2)+1 AS VARCHAR) || '-L' || CAST((i%2)+1 AS VARCHAR),
            CASE WHEN i%13=0 THEN -ROUND(1000+(i*37.3)%5000, 2)  -- reversals
                 WHEN i%2=0  THEN  ROUND(100+(i*17.3)%3000, 2)   -- debits
                 ELSE            -ROUND(100+(i*17.3)%3000, 2) END,  -- credits
            CASE WHEN i%13=0 THEN 'reversal' WHEN i%7=0 THEN 'accrual' ELSE 'standard' END,
            TIMESTAMPTZ '2020-01-01 00:00:00' + INTERVAL (i*3600) SECOND,
            CASE WHEN i%5=0 THEN 'system' ELSE 'user' || CAST(i%20 AS VARCHAR) END
        FROM generate_series(1, 100000) t(i)
        """,
    ],
)


# ── MEDIUM ─────────────────────────────────────────────────────────────────────

FINANCE_MEDIUM = Scenario(
    name="finance_medium",
    domain="finance",
    complexity="medium",
    description=(
        "Multi-entity finance schema: GL, AP, AR, budget vs actuals, multi-currency, "
        "and intercompany transactions. "
        "Key challenge: elimination entries (entry_type='elimination') must be excluded "
        "from consolidated P&L — the agent must identify this business rule. "
        "Multi-currency amounts require the exchange_rate column for USD conversion."
    ),
    schemas=["main"],
    data_quality_issues=[
        DataQualityIssue(
            table="journal_entries", column="entity_id",
            issue_type="ambiguous_key",
            description=(
                "Consolidated reports must exclude intercompany elimination entries "
                "(entry_type='elimination'). Missing this filter overstates revenue and expenses. "
                "A critical business rule the agent must surface."
            ),
            prevalence="8% of rows",
        ),
        DataQualityIssue(
            table="journal_entries", column="amount_usd",
            issue_type="high_null",
            description=(
                "amount_usd is NULL for entries in USD (no conversion needed). "
                "Use COALESCE(amount_usd, amount) for USD-normalised reporting."
            ),
            prevalence="60% of rows",
        ),
        DataQualityIssue(
            table="budget_vs_actuals", column="variance_pct",
            issue_type="duplicate_metric",
            description=(
                "budget_vs_actuals.variance_pct can be derived from actual_amount and budget_amount. "
                "Having it pre-computed creates a risk of inconsistency if the formula changes."
            ),
            prevalence="always",
        ),
    ],
    ground_truth=GroundTruth(
        expected_joins=[
            ExpectedJoin("journal_entries",  "accounts",      "account_id",     "many:1"),
            ExpectedJoin("journal_entries",  "cost_centers",  "cost_center_id", "many:1"),
            ExpectedJoin("journal_entries",  "periods",       "period_id",      "many:1"),
            ExpectedJoin("journal_entries",  "entities",      "entity_id",      "many:1"),
            ExpectedJoin("ap_invoices",      "vendors",       "vendor_id",      "many:1"),
            ExpectedJoin("ap_invoices",      "periods",       "period_id",      "many:1"),
            ExpectedJoin("ar_invoices",      "customers",     "customer_id",    "many:1"),
            ExpectedJoin("ar_invoices",      "periods",       "period_id",      "many:1"),
            ExpectedJoin("budget_vs_actuals","accounts",      "account_id",     "many:1"),
            ExpectedJoin("budget_vs_actuals","cost_centers",  "cost_center_id", "many:1"),
        ],
        expected_measures=[
            ExpectedMeasure("consolidated_revenue",  "Consolidated Revenue","SUM", "journal_entries","amount",
                            ["account_type='revenue'","entry_type!='elimination'","entry_type!='reversal'"], "P&L"),
            ExpectedMeasure("ap_outstanding",        "AP Outstanding",     "SUM", "ap_invoices", "amount_due",
                            ["status='open'"], "AP"),
            ExpectedMeasure("ar_outstanding",        "AR Outstanding",     "SUM", "ar_invoices", "amount_due",
                            ["status='open'"], "AR"),
            ExpectedMeasure("budget_variance",       "Budget Variance $",  "SUM", "budget_vs_actuals","variance_amount",[], "Budget"),
            ExpectedMeasure("budget_variance_pct",   "Budget Variance %",  "AVG", "budget_vs_actuals","variance_pct",   [], "Budget"),
        ],
        business_rules=[
            "ALWAYS exclude entry_type='elimination' from consolidated P&L to avoid double-counting.",
            "ALWAYS exclude entry_type='reversal' from period totals.",
            "Multi-currency: use COALESCE(amount_usd, amount) to normalise all amounts to USD.",
            "AP outstanding = sum of ap_invoices.amount_due WHERE status='open'.",
            "AR DSO = AR outstanding / (annual revenue / 365).",
        ],
        open_questions=[
            "Which entities are in scope for consolidation?",
            "Should budget comparisons use the original budget or the latest reforecast?",
            "Is revenue recognised on invoice date or cash receipt date?",
        ],
        grain_per_table={
            "entities":          ["entity_id"],
            "accounts":          ["account_id"],
            "cost_centers":      ["cost_center_id"],
            "periods":           ["period_id"],
            "journal_entries":   ["entry_id", "line_number"],
            "vendors":           ["vendor_id"],
            "ap_invoices":       ["invoice_id"],
            "customers":         ["customer_id"],
            "ar_invoices":       ["invoice_id"],
            "budget_vs_actuals": ["account_id", "cost_center_id", "period_id"],
        },
    ),
    table_descriptions={
        "entities":          "Legal entities (subsidiaries, holding companies).",
        "accounts":          "Chart of accounts.",
        "cost_centers":      "Cost center master.",
        "periods":           "Accounting periods.",
        "journal_entries":   "All GL entries including intercompany eliminations.",
        "vendors":           "AP vendor master.",
        "ap_invoices":       "Accounts payable invoices.",
        "customers":         "AR customer master.",
        "ar_invoices":       "Accounts receivable invoices.",
        "budget_vs_actuals": "Period-level budget vs actual comparison by account and cost center.",
    },
    seed_sql=[
        """
        CREATE TABLE entities (
            entity_id    VARCHAR PRIMARY KEY,
            name         VARCHAR,
            country      VARCHAR,
            currency     VARCHAR,
            is_parent    BOOLEAN,
            parent_id    VARCHAR
        )
        """,
        """
        INSERT INTO entities VALUES
            ('ENT-001', 'Global Holdings Inc',  'USA', 'USD', true,  NULL),
            ('ENT-002', 'US Operations LLC',    'USA', 'USD', false, 'ENT-001'),
            ('ENT-003', 'UK Operations Ltd',    'GBR', 'GBP', false, 'ENT-001'),
            ('ENT-004', 'Germany GmbH',         'DEU', 'EUR', false, 'ENT-001'),
            ('ENT-005', 'Australia Pty Ltd',    'AUS', 'AUD', false, 'ENT-001')
        """,
        """
        CREATE TABLE accounts (
            account_id    VARCHAR PRIMARY KEY,
            name          VARCHAR,
            account_type  VARCHAR,
            account_class VARCHAR,
            parent_id     VARCHAR,
            is_active     BOOLEAN
        )
        """,
        """
        INSERT INTO accounts VALUES
            ('4000','Revenue','revenue','income_statement',NULL,true),
            ('4100','Product Revenue','revenue','income_statement','4000',true),
            ('4200','Service Revenue','revenue','income_statement','4000',true),
            ('5000','COGS','cogs','income_statement',NULL,true),
            ('5100','Direct Costs','cogs','income_statement','5000',true),
            ('6000','Operating Expenses','expense','income_statement',NULL,true),
            ('6100','Salaries','expense','income_statement','6000',true),
            ('6200','Rent','expense','income_statement','6000',true),
            ('6300','Marketing','expense','income_statement','6000',true),
            ('6400','Depreciation','expense','income_statement','6000',true),
            ('1000','Cash','asset','balance_sheet',NULL,true),
            ('1100','Accounts Receivable','asset','balance_sheet',NULL,true),
            ('2000','Accounts Payable','liability','balance_sheet',NULL,true),
            ('3000','Retained Earnings','equity','balance_sheet',NULL,true)
        """,
        """
        CREATE TABLE cost_centers (
            cost_center_id VARCHAR PRIMARY KEY,
            name           VARCHAR,
            department     VARCHAR
        )
        """,
        """
        INSERT INTO cost_centers VALUES
            ('CC-001','Engineering','R&D'),('CC-002','Product','Product'),
            ('CC-003','Sales','Revenue'),('CC-004','Marketing','Revenue'),
            ('CC-005','Customer Success','Revenue'),('CC-006','Finance','G&A'),
            ('CC-007','HR','G&A'),('CC-008','IT','R&D')
        """,
        """
        CREATE TABLE periods (
            period_id   INTEGER PRIMARY KEY,
            period_name VARCHAR,
            start_date  DATE,
            end_date    DATE,
            fiscal_year INTEGER,
            fiscal_qtr  INTEGER,
            is_closed   BOOLEAN
        )
        """,
        """
        INSERT INTO periods
        SELECT i,
            strftime(DATE '2020-01-01' + INTERVAL ((i-1)*30) DAY, '%b %Y'),
            DATE '2020-01-01' + INTERVAL ((i-1)*30) DAY,
            DATE '2020-01-01' + INTERVAL (i*30-1) DAY,
            2020 + CAST(FLOOR((i-1)/12) AS INTEGER),
            CAST(FLOOR((i-1)/3) % 4 + 1 AS INTEGER),
            i < 49
        FROM generate_series(1, 60) t(i)
        """,
        """
        CREATE TABLE journal_entries (
            entry_id        INTEGER,
            line_number     INTEGER,
            entity_id       VARCHAR,
            period_id       INTEGER,
            account_id      VARCHAR,
            cost_center_id  VARCHAR,
            description     VARCHAR,
            amount          DECIMAL(14,2),    -- in entity's local currency
            currency        VARCHAR,
            exchange_rate   DECIMAL(10,6),
            amount_usd      DECIMAL(14,2),    -- NULL if already USD
            entry_type      VARCHAR,          -- standard|accrual|reversal|elimination
            posted_at       TIMESTAMP,
            PRIMARY KEY (entry_id, line_number)
        )
        """,
        """
        INSERT INTO journal_entries
        SELECT
            CAST(FLOOR(i/2)+1 AS INTEGER),
            (i%2)+1,
            'ENT-00' || CAST((i%5)+1 AS VARCHAR),
            (i%60)+1,
            CASE WHEN i%7=0 THEN '4100' WHEN i%7=1 THEN '4200' WHEN i%7=2 THEN '5100'
                 WHEN i%7=3 THEN '6100' WHEN i%7=4 THEN '6300' WHEN i%7=5 THEN '1100'
                 ELSE '2000' END,
            CASE WHEN i%7 >= 5 THEN NULL ELSE 'CC-00' || CAST((i%8)+1 AS VARCHAR) END,
            'Entry ' || CAST(FLOOR(i/2)+1 AS VARCHAR),
            CASE WHEN i%2=0 THEN ROUND(50+(i*17.3)%10000, 2)
                 ELSE            -ROUND(50+(i*17.3)%10000, 2) END,
            CASE WHEN i%5=0 THEN 'USD' WHEN i%5=1 THEN 'GBP'
                 WHEN i%5=2 THEN 'EUR' WHEN i%5=3 THEN 'AUD' ELSE 'USD' END,
            CASE WHEN i%5=0 THEN 1.0 WHEN i%5=1 THEN 1.27
                 WHEN i%5=2 THEN 1.09 WHEN i%5=3 THEN 0.65 ELSE 1.0 END,
            -- amount_usd NULL for USD entries
            CASE WHEN i%5 IN (0,4) THEN NULL
                 ELSE ROUND(ABS(ROUND(50+(i*17.3)%10000, 2)) *
                      CASE WHEN i%5=1 THEN 1.27 WHEN i%5=2 THEN 1.09 ELSE 0.65 END, 2) END,
            -- 8% are intercompany eliminations
            CASE WHEN i%13=0 THEN 'elimination' WHEN i%11=0 THEN 'reversal'
                 WHEN i%7=0  THEN 'accrual' ELSE 'standard' END,
            TIMESTAMPTZ '2020-01-01 00:00:00' + INTERVAL (i*1800) SECOND
        FROM generate_series(1, 200000) t(i)
        """,
        """
        CREATE TABLE vendors (
            vendor_id   INTEGER PRIMARY KEY,
            name        VARCHAR,
            country     VARCHAR,
            category    VARCHAR,
            payment_terms INTEGER    -- days
        )
        """,
        """
        INSERT INTO vendors
        SELECT i, 'Vendor ' || i,
            CASE WHEN i%3=0 THEN 'USA' WHEN i%3=1 THEN 'GBR' ELSE 'DEU' END,
            CASE WHEN i%4=0 THEN 'Software' WHEN i%4=1 THEN 'Professional Services'
                 WHEN i%4=2 THEN 'Infrastructure' ELSE 'Office' END,
            CASE WHEN i%3=0 THEN 30 WHEN i%3=1 THEN 45 ELSE 60 END
        FROM generate_series(1, 200) t(i)
        """,
        """
        CREATE TABLE ap_invoices (
            invoice_id   INTEGER PRIMARY KEY,
            vendor_id    INTEGER,
            period_id    INTEGER,
            entity_id    VARCHAR,
            invoice_date DATE,
            due_date     DATE,
            amount_total DECIMAL(12,2),
            amount_due   DECIMAL(12,2),
            currency     VARCHAR,
            status       VARCHAR    -- open | paid | overdue | void
        )
        """,
        """
        INSERT INTO ap_invoices
        SELECT
            i, (i%200)+1, (i%60)+1,
            'ENT-00' || CAST((i%5)+1 AS VARCHAR),
            DATE '2020-01-01' + INTERVAL (i%1460) DAY,
            DATE '2020-01-01' + INTERVAL (i%1460+30) DAY,
            ROUND(500+(i*73.0)%20000, 2),
            CASE WHEN i%6=0 THEN 0.0 ELSE ROUND(500+(i*73.0)%20000, 2) END,
            CASE WHEN i%3=0 THEN 'USD' WHEN i%3=1 THEN 'GBP' ELSE 'EUR' END,
            CASE WHEN i%6=0 THEN 'paid' WHEN i%8=0 THEN 'overdue'
                 WHEN i%20=0 THEN 'void' ELSE 'open' END
        FROM generate_series(1, 10000) t(i)
        """,
        """
        CREATE TABLE customers (
            customer_id  INTEGER PRIMARY KEY,
            name         VARCHAR,
            country      VARCHAR,
            credit_limit DECIMAL(12,2)
        )
        """,
        """
        INSERT INTO customers
        SELECT i, 'Customer ' || i,
            CASE WHEN i%3=0 THEN 'USA' WHEN i%3=1 THEN 'GBR' ELSE 'DEU' END,
            ROUND(10000+(i*730.0)%100000, 2)
        FROM generate_series(1, 500) t(i)
        """,
        """
        CREATE TABLE ar_invoices (
            invoice_id   INTEGER PRIMARY KEY,
            customer_id  INTEGER,
            period_id    INTEGER,
            entity_id    VARCHAR,
            invoice_date DATE,
            due_date     DATE,
            amount_total DECIMAL(12,2),
            amount_due   DECIMAL(12,2),
            currency     VARCHAR,
            status       VARCHAR
        )
        """,
        """
        INSERT INTO ar_invoices
        SELECT
            i, (i%500)+1, (i%60)+1,
            'ENT-00' || CAST((i%5)+1 AS VARCHAR),
            DATE '2020-01-01' + INTERVAL (i%1460) DAY,
            DATE '2020-01-01' + INTERVAL (i%1460+45) DAY,
            ROUND(1000+(i*137.0)%50000, 2),
            CASE WHEN i%8=0 THEN 0.0 ELSE ROUND(1000+(i*137.0)%50000, 2) END,
            CASE WHEN i%3=0 THEN 'USD' WHEN i%3=1 THEN 'GBP' ELSE 'EUR' END,
            CASE WHEN i%8=0 THEN 'paid' WHEN i%10=0 THEN 'overdue'
                 ELSE 'open' END
        FROM generate_series(1, 15000) t(i)
        """,
        """
        CREATE TABLE budget_vs_actuals (
            account_id       VARCHAR,
            cost_center_id   VARCHAR,
            period_id        INTEGER,
            budget_amount    DECIMAL(12,2),
            actual_amount    DECIMAL(12,2),
            variance_amount  DECIMAL(12,2),
            variance_pct     DECIMAL(8,4),
            PRIMARY KEY (account_id, cost_center_id, period_id)
        )
        """,
        # 5 accounts × 8 cost_centers × 60 periods = 2400 unique combos.
        # Stride: period cycles fastest (60), then cc (8), then account (5).
        """
        INSERT INTO budget_vs_actuals
        SELECT
            CASE WHEN CAST(FLOOR(i/480) AS INTEGER)=0 THEN '4100'
                 WHEN CAST(FLOOR(i/480) AS INTEGER)=1 THEN '4200'
                 WHEN CAST(FLOOR(i/480) AS INTEGER)=2 THEN '6100'
                 WHEN CAST(FLOOR(i/480) AS INTEGER)=3 THEN '6300'
                 ELSE '5100' END AS account_id,
            'CC-00' || CAST(CAST(FLOOR(i/60) AS INTEGER)%8+1 AS VARCHAR) AS cost_center_id,
            (i%60)+1 AS period_id,
            ROUND(5000+(i*73.0)%50000, 2) AS budget_amount,
            ROUND(4500+(i*67.0)%52000, 2) AS actual_amount,
            ROUND(4500+(i*67.0)%52000, 2) - ROUND(5000+(i*73.0)%50000, 2) AS variance_amount,
            ROUND(
                (ROUND(4500+(i*67.0)%52000, 2) - ROUND(5000+(i*73.0)%50000, 2))
                / ROUND(5000+(i*73.0)%50000, 2) * 100.0, 4) AS variance_pct
        FROM generate_series(0, 2399) t(i)
        """,
    ],
)
