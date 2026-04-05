"""
SaaS / subscription simulation scenarios.

  SIMPLE  — accounts, subscriptions, billing_periods, usage_events.
            Clean schema, obvious MRR/ARR/churn measures.
  MEDIUM  — adds features, feature_flags, cohorts, mrr_history, support_tickets,
            and the infamous "which table owns MRR" ambiguity (both subscriptions
            and mrr_history claim to define monthly revenue).
"""

from .base import (
    Scenario, DataQualityIssue, GroundTruth,
    ExpectedJoin, ExpectedMeasure,
)


# ── SIMPLE ─────────────────────────────────────────────────────────────────────

SAAS_SIMPLE = Scenario(
    name="saas_simple",
    domain="saas",
    complexity="simple",
    description=(
        "A minimal SaaS schema: accounts, subscriptions, billing, and usage events. "
        "Clean FK relationships. Tests whether the agent correctly identifies MRR, "
        "ARR, churn, and expansion as the core SaaS metrics."
    ),
    schemas=["main"],
    data_quality_issues=[
        DataQualityIssue(
            table="subscriptions", column="cancelled_at",
            issue_type="high_null",
            description="cancelled_at is NULL for active subscriptions (expected). "
                        "The agent must not flag this as a data quality issue.",
            prevalence="75% of rows",
        ),
        DataQualityIssue(
            table="usage_events", column="feature_name",
            issue_type="encoded_null",
            description="feature_name = 'unknown' is an encoded null from the SDK's fallback.",
            prevalence="5% of rows",
        ),
    ],
    ground_truth=GroundTruth(
        expected_joins=[
            ExpectedJoin("subscriptions",  "accounts",         "account_id",  "many:1"),
            ExpectedJoin("billing_periods","subscriptions",    "subscription_id","many:1"),
            ExpectedJoin("usage_events",   "accounts",         "account_id",  "many:1"),
            ExpectedJoin("usage_events",   "subscriptions",    "subscription_id","many:1"),
        ],
        expected_measures=[
            ExpectedMeasure("mrr",              "MRR",                   "SUM",   "subscriptions", "mrr_amount",    ["status = 'active'"],  "Revenue"),
            ExpectedMeasure("arr",              "ARR",                   "SUM",   "subscriptions", "arr_amount",    ["status = 'active'"],  "Revenue"),
            ExpectedMeasure("active_accounts",  "Active Accounts",       "COUNT_DISTINCT","subscriptions","account_id",["status='active'"],"Accounts"),
            ExpectedMeasure("new_mrr",          "New MRR",               "SUM",   "subscriptions", "mrr_amount",   ["type='new'"],          "Revenue"),
            ExpectedMeasure("churned_mrr",      "Churned MRR",           "SUM",   "subscriptions", "mrr_amount",   ["status='cancelled'"],  "Revenue"),
            ExpectedMeasure("expansion_mrr",    "Expansion MRR",         "SUM",   "subscriptions", "mrr_amount",   ["type='expansion'"],    "Revenue"),
            ExpectedMeasure("churn_rate",       "Churn Rate",            "RATIO", "subscriptions", None,           [],                      "Revenue"),
            ExpectedMeasure("avg_revenue_per_account","ARPA",            "AVG",   "subscriptions", "mrr_amount",   ["status='active'"],     "Revenue"),
            ExpectedMeasure("billing_events",   "Invoices Issued",       "COUNT", "billing_periods","billing_id",  [],                      "Billing"),
        ],
        business_rules=[
            "MRR = sum of mrr_amount WHERE status = 'active'.",
            "ARR = MRR × 12 (or use arr_amount column directly).",
            "Churn Rate = cancelled MRR in period / starting MRR.",
            "Expansion MRR = MRR growth from existing accounts (upgrades only).",
            "usage_events.feature_name = 'unknown' should be excluded from feature adoption metrics.",
        ],
        open_questions=[
            "Is ARR calculated as MRR × 12 or as the contract value regardless of billing frequency?",
            "Should trials (status='trial') be counted in active_accounts?",
            "How is contraction MRR (downgrade) different from churn?",
        ],
        grain_per_table={
            "accounts":       ["account_id"],
            "subscriptions":  ["subscription_id"],
            "billing_periods":["billing_id"],
            "usage_events":   ["event_id"],
        },
    ),
    table_descriptions={
        "accounts":        "Customer accounts (companies). One row per account.",
        "subscriptions":   "Subscription records. One account can have multiple (upsell/multi-product).",
        "billing_periods": "Invoice periods per subscription. One row per billing cycle.",
        "usage_events":    "Product usage events streamed from the SDK. Very high volume.",
    },
    seed_sql=[
        # ── accounts ───────────────────────────────────────────────────────────
        """
        CREATE TABLE accounts (
            account_id      INTEGER PRIMARY KEY,
            name            VARCHAR,
            domain          VARCHAR,
            plan            VARCHAR,    -- starter | growth | enterprise
            industry        VARCHAR,
            employee_count  INTEGER,
            country         VARCHAR,
            created_at      TIMESTAMP,
            health_score    DECIMAL(4,1)  -- 0–100
        )
        """,
        """
        INSERT INTO accounts
        SELECT
            i,
            'Company ' || i,
            'company' || i || '.io',
            CASE WHEN i%10<2 THEN 'enterprise' WHEN i%10<6 THEN 'growth' ELSE 'starter' END,
            CASE WHEN i%6=0 THEN 'SaaS' WHEN i%6=1 THEN 'FinTech'
                 WHEN i%6=2 THEN 'HealthTech' WHEN i%6=3 THEN 'E-commerce'
                 WHEN i%6=4 THEN 'Media' ELSE 'Other' END,
            CAST(10 * (i%200) + 10 AS INTEGER),
            CASE WHEN i%4=0 THEN 'USA' WHEN i%4=1 THEN 'GBR'
                 WHEN i%4=2 THEN 'DEU' ELSE 'AUS' END,
            TIMESTAMPTZ '2020-01-01 00:00:00' + INTERVAL (i*86400) SECOND,
            ROUND(20.0 + (i*7.3)%80, 1)
        FROM generate_series(1, 2000) t(i)
        """,
        # ── subscriptions ──────────────────────────────────────────────────────
        """
        CREATE TABLE subscriptions (
            subscription_id  INTEGER PRIMARY KEY,
            account_id       INTEGER,
            plan             VARCHAR,
            status           VARCHAR,     -- active | cancelled | trial | paused
            type             VARCHAR,     -- new | expansion | contraction | reactivation
            mrr_amount       DECIMAL(10,2),
            arr_amount       DECIMAL(10,2),
            billing_cycle    VARCHAR,     -- monthly | annual | quarterly
            started_at       DATE,
            cancelled_at     DATE,        -- NULL for active
            trial_ends_at    DATE         -- NULL if not on trial
        )
        """,
        """
        INSERT INTO subscriptions
        SELECT
            i,
            (i%2000)+1 AS account_id,
            CASE WHEN i%10<2 THEN 'enterprise' WHEN i%10<6 THEN 'growth' ELSE 'starter' END,
            CASE WHEN i%4=0 THEN 'cancelled' WHEN i%20=0 THEN 'trial'
                 WHEN i%30=0 THEN 'paused'   ELSE 'active' END,
            CASE WHEN i%5=0 THEN 'expansion' WHEN i%7=0 THEN 'contraction'
                 WHEN i%12=0 THEN 'reactivation' ELSE 'new' END,
            ROUND(
                CASE WHEN i%10<2 THEN 1500.0+(i%500)*10
                     WHEN i%10<6 THEN 200.0+(i%100)*5
                     ELSE 49.0+(i%50)*1 END, 2),
            ROUND(
                CASE WHEN i%10<2 THEN 18000.0+(i%500)*120
                     WHEN i%10<6 THEN 2400.0+(i%100)*60
                     ELSE 588.0+(i%50)*12 END, 2),
            CASE WHEN i%3=0 THEN 'annual' WHEN i%3=1 THEN 'quarterly' ELSE 'monthly' END,
            DATE '2020-01-01' + INTERVAL (i%1460) DAY,
            CASE WHEN i%4=0 THEN DATE '2020-01-01' + INTERVAL ((i%1460)+90) DAY ELSE NULL END,
            CASE WHEN i%20=0 THEN DATE '2020-01-01' + INTERVAL ((i%1460)+14) DAY ELSE NULL END
        FROM generate_series(1, 5000) t(i)
        """,
        # ── billing_periods ────────────────────────────────────────────────────
        """
        CREATE TABLE billing_periods (
            billing_id       INTEGER PRIMARY KEY,
            subscription_id  INTEGER,
            period_start     DATE,
            period_end       DATE,
            amount_invoiced  DECIMAL(10,2),
            amount_paid      DECIMAL(10,2),
            status           VARCHAR,    -- paid | overdue | void | refunded
            paid_at          TIMESTAMP
        )
        """,
        """
        INSERT INTO billing_periods
        SELECT
            i,
            (i%5000)+1,
            DATE '2020-01-01' + INTERVAL (FLOOR(i/12)*30) DAY,
            DATE '2020-01-01' + INTERVAL (FLOOR(i/12)*30+30) DAY,
            ROUND(50.0+(i*13.7)%2000, 2),
            CASE WHEN i%15=0 THEN NULL ELSE ROUND(50.0+(i*13.7)%2000, 2) END,
            CASE WHEN i%15=0 THEN 'overdue'
                 WHEN i%50=0 THEN 'void'
                 WHEN i%30=0 THEN 'refunded'
                 ELSE 'paid' END,
            CASE WHEN i%15=0 THEN NULL
                 ELSE TIMESTAMPTZ '2020-01-01 00:00:00' + INTERVAL (i*86400) SECOND END
        FROM generate_series(1, 30000) t(i)
        """,
        # ── usage_events ───────────────────────────────────────────────────────
        """
        CREATE TABLE usage_events (
            event_id         INTEGER PRIMARY KEY,
            account_id       INTEGER,
            subscription_id  INTEGER,
            event_type       VARCHAR,    -- feature_used | login | export | api_call
            feature_name     VARCHAR,    -- 'unknown' = encoded null (5%)
            occurred_at      TIMESTAMP,
            duration_ms      INTEGER,
            metadata         VARCHAR     -- JSON string (simplified)
        )
        """,
        """
        INSERT INTO usage_events
        SELECT
            i,
            (i%2000)+1,
            (i%5000)+1,
            CASE WHEN i%4=0 THEN 'feature_used' WHEN i%4=1 THEN 'login'
                 WHEN i%4=2 THEN 'export' ELSE 'api_call' END,
            CASE WHEN i%20=0 THEN 'unknown'  -- encoded null
                 WHEN i%6=0 THEN 'dashboard'
                 WHEN i%6=1 THEN 'reports'
                 WHEN i%6=2 THEN 'integrations'
                 WHEN i%6=3 THEN 'api'
                 WHEN i%6=4 THEN 'automations'
                 ELSE 'settings' END,
            TIMESTAMPTZ '2022-01-01 00:00:00' + INTERVAL (i*60) SECOND,
            (i%5000)+100,
            '{"source": "sdk_v2"}'
        FROM generate_series(1, 500000) t(i)
        """,
    ],
)


# ── MEDIUM ─────────────────────────────────────────────────────────────────────

SAAS_MEDIUM = Scenario(
    name="saas_medium",
    domain="saas",
    complexity="medium",
    description=(
        "Full SaaS stack: accounts, subscriptions, billing, usage, features, MRR history, "
        "and support tickets. "
        "Key challenge: BOTH subscriptions.mrr_amount AND mrr_history.mrr define MRR — "
        "the agent must identify which is the authoritative source."
    ),
    schemas=["main"],
    data_quality_issues=[
        DataQualityIssue(
            table="mrr_history", column="mrr",
            issue_type="duplicate_metric",
            description=(
                "mrr_history.mrr and subscriptions.mrr_amount both represent MRR. "
                "mrr_history is a point-in-time snapshot table; subscriptions is the live record. "
                "The agent should surface this ambiguity and ask which is authoritative for trending."
            ),
            prevalence="always",
        ),
        DataQualityIssue(
            table="feature_flags", column="enabled_at",
            issue_type="high_null",
            description="feature_flags.enabled_at is NULL for flags that were enabled at account creation.",
            prevalence="20% of rows",
        ),
        DataQualityIssue(
            table="support_tickets", column="resolved_at",
            issue_type="high_null",
            description="resolved_at is NULL for open tickets. Normal — not a data quality issue.",
            prevalence="15% of rows",
        ),
        DataQualityIssue(
            table="cohorts", column="cohort_month",
            issue_type="mixed_grain",
            description=(
                "cohorts is a month-grain table (one row per account per cohort month). "
                "It must not be joined directly to daily usage events."
            ),
            prevalence="always",
        ),
    ],
    ground_truth=GroundTruth(
        expected_joins=[
            ExpectedJoin("subscriptions",  "accounts",       "account_id",      "many:1"),
            ExpectedJoin("billing_periods","subscriptions",  "subscription_id", "many:1"),
            ExpectedJoin("usage_events",   "accounts",       "account_id",      "many:1"),
            ExpectedJoin("feature_flags",  "accounts",       "account_id",      "many:1"),
            ExpectedJoin("mrr_history",    "accounts",       "account_id",      "many:1"),
            ExpectedJoin("cohorts",        "accounts",       "account_id",      "many:1",
                         is_trap=True, trap_type="fan_out"),
            ExpectedJoin("support_tickets","accounts",       "account_id",      "many:1"),
        ],
        expected_measures=[
            ExpectedMeasure("mrr",              "MRR",              "SUM",   "subscriptions", "mrr_amount", ["status='active'"], "Revenue"),
            ExpectedMeasure("arr",              "ARR",              "SUM",   "subscriptions", "arr_amount", ["status='active'"], "Revenue"),
            ExpectedMeasure("churn_rate",       "Churn Rate",       "RATIO", "subscriptions", None,         [],                  "Revenue"),
            ExpectedMeasure("ndr",              "Net Dollar Retention","RATIO","subscriptions",None,         [],                  "Revenue"),
            ExpectedMeasure("feature_adoption", "Feature Adoption %","RATIO","feature_flags",  None,         [],                 "Product"),
            ExpectedMeasure("dau",              "Daily Active Accounts","COUNT_DISTINCT","usage_events","account_id",[],         "Engagement"),
            ExpectedMeasure("ticket_volume",    "Support Tickets",  "COUNT", "support_tickets","ticket_id", [],                  "Support"),
            ExpectedMeasure("median_ttresolve", "Median Time to Resolve","AVG","support_tickets",None,      [],                  "Support"),
        ],
        business_rules=[
            "Use subscriptions.mrr_amount for live MRR snapshots; mrr_history for period-over-period trending.",
            "Net Dollar Retention (NDR) = (starting MRR + expansion - contraction - churn) / starting MRR.",
            "cohorts must only be joined to month-grain aggregations, not to daily usage_events.",
            "feature_flags.enabled_at NULL means the feature was enabled at account creation.",
        ],
        open_questions=[
            "Which table is the source of truth for MRR: subscriptions or mrr_history?",
            "How should DAU be defined — accounts with at least one login, or any usage event?",
            "Should churned accounts (with open tickets) be included in support_ticket metrics?",
        ],
        grain_per_table={
            "accounts":       ["account_id"],
            "subscriptions":  ["subscription_id"],
            "billing_periods":["billing_id"],
            "usage_events":   ["event_id"],
            "feature_flags":  ["account_id", "feature_name"],
            "mrr_history":    ["account_id", "snapshot_month"],
            "cohorts":        ["account_id", "cohort_month"],
            "support_tickets":["ticket_id"],
        },
    ),
    table_descriptions={
        "accounts":        "Customer accounts.",
        "subscriptions":   "Subscription records with live MRR.",
        "billing_periods": "Invoice billing periods.",
        "usage_events":    "Product usage events.",
        "feature_flags":   "Which features are enabled per account.",
        "mrr_history":     "Monthly MRR snapshot for trending. NOT the live record.",
        "cohorts":         "Monthly cohort assignments. Month-grain — do not join to daily facts.",
        "support_tickets": "Customer support tickets.",
    },
    seed_sql=[
        # ── accounts (same as simple) ──────────────────────────────────────────
        """
        CREATE TABLE accounts (
            account_id    INTEGER PRIMARY KEY,
            name          VARCHAR,
            plan          VARCHAR,
            industry      VARCHAR,
            country       VARCHAR,
            created_at    TIMESTAMP,
            health_score  DECIMAL(4,1)
        )
        """,
        """
        INSERT INTO accounts
        SELECT
            i, 'Company ' || i,
            CASE WHEN i%10<2 THEN 'enterprise' WHEN i%10<6 THEN 'growth' ELSE 'starter' END,
            CASE WHEN i%5=0 THEN 'SaaS' WHEN i%5=1 THEN 'FinTech'
                 WHEN i%5=2 THEN 'HealthTech' WHEN i%5=3 THEN 'E-comm' ELSE 'Other' END,
            CASE WHEN i%3=0 THEN 'USA' WHEN i%3=1 THEN 'GBR' ELSE 'DEU' END,
            TIMESTAMPTZ '2019-01-01 00:00:00' + INTERVAL (i*43200) SECOND,
            ROUND(15.0+(i*7.3)%85, 1)
        FROM generate_series(1, 3000) t(i)
        """,
        # ── subscriptions ──────────────────────────────────────────────────────
        """
        CREATE TABLE subscriptions (
            subscription_id  INTEGER PRIMARY KEY,
            account_id       INTEGER,
            plan             VARCHAR,
            status           VARCHAR,
            type             VARCHAR,
            mrr_amount       DECIMAL(10,2),
            arr_amount       DECIMAL(10,2),
            billing_cycle    VARCHAR,
            started_at       DATE,
            cancelled_at     DATE
        )
        """,
        """
        INSERT INTO subscriptions
        SELECT
            i, (i%3000)+1,
            CASE WHEN i%10<2 THEN 'enterprise' WHEN i%10<6 THEN 'growth' ELSE 'starter' END,
            CASE WHEN i%4=0 THEN 'cancelled' WHEN i%20=0 THEN 'trial' ELSE 'active' END,
            CASE WHEN i%5=0 THEN 'expansion' WHEN i%7=0 THEN 'contraction'
                 ELSE 'new' END,
            ROUND(CASE WHEN i%10<2 THEN 2000+(i%500)*15 WHEN i%10<6 THEN 250+(i%100)*5
                       ELSE 49+(i%50) END, 2),
            ROUND(CASE WHEN i%10<2 THEN 24000+(i%500)*180 WHEN i%10<6 THEN 3000+(i%100)*60
                       ELSE 588+(i%50)*12 END, 2),
            CASE WHEN i%3=0 THEN 'annual' ELSE 'monthly' END,
            DATE '2019-01-01' + INTERVAL (i%1825) DAY,
            CASE WHEN i%4=0 THEN DATE '2019-01-01' + INTERVAL ((i%1825)+90) DAY ELSE NULL END
        FROM generate_series(1, 7000) t(i)
        """,
        # ── billing_periods ────────────────────────────────────────────────────
        """
        CREATE TABLE billing_periods (
            billing_id       INTEGER PRIMARY KEY,
            subscription_id  INTEGER,
            period_start     DATE,
            period_end       DATE,
            amount_invoiced  DECIMAL(10,2),
            amount_paid      DECIMAL(10,2),
            status           VARCHAR,
            paid_at          TIMESTAMP
        )
        """,
        """
        INSERT INTO billing_periods
        SELECT
            i, (i%7000)+1,
            DATE '2019-01-01' + INTERVAL (FLOOR(i/12)*30) DAY,
            DATE '2019-01-01' + INTERVAL (FLOOR(i/12)*30+30) DAY,
            ROUND(50.0+(i*11.7)%3000, 2),
            CASE WHEN i%12=0 THEN NULL ELSE ROUND(50.0+(i*11.7)%3000, 2) END,
            CASE WHEN i%12=0 THEN 'overdue' WHEN i%40=0 THEN 'void'
                 ELSE 'paid' END,
            CASE WHEN i%12=0 THEN NULL
                 ELSE TIMESTAMPTZ '2019-01-01 00:00:00' + INTERVAL (i*86400) SECOND END
        FROM generate_series(1, 50000) t(i)
        """,
        # ── usage_events ───────────────────────────────────────────────────────
        """
        CREATE TABLE usage_events (
            event_id        INTEGER PRIMARY KEY,
            account_id      INTEGER,
            subscription_id INTEGER,
            event_type      VARCHAR,
            feature_name    VARCHAR,
            occurred_at     TIMESTAMP,
            duration_ms     INTEGER
        )
        """,
        """
        INSERT INTO usage_events
        SELECT
            i, (i%3000)+1, (i%7000)+1,
            CASE WHEN i%4=0 THEN 'feature_used' WHEN i%4=1 THEN 'login'
                 WHEN i%4=2 THEN 'export' ELSE 'api_call' END,
            CASE WHEN i%20=0 THEN 'unknown'
                 WHEN i%5=0 THEN 'dashboard' WHEN i%5=1 THEN 'reports'
                 WHEN i%5=2 THEN 'integrations' WHEN i%5=3 THEN 'api'
                 ELSE 'automations' END,
            TIMESTAMPTZ '2022-01-01 00:00:00' + INTERVAL (i*30) SECOND,
            (i%5000)+100
        FROM generate_series(1, 1000000) t(i)
        """,
        # ── feature_flags ──────────────────────────────────────────────────────
        """
        CREATE TABLE feature_flags (
            account_id    INTEGER,
            feature_name  VARCHAR,
            is_enabled    BOOLEAN,
            enabled_at    TIMESTAMP,    -- NULL = enabled at account creation
            PRIMARY KEY (account_id, feature_name)
        )
        """,
        # 3000 accounts × 5 features = 15000 unique combos.
        # Key: account = floor(i/5)+1, feature = i%5
        """
        INSERT INTO feature_flags
        SELECT
            CAST(FLOOR(i/5) AS INTEGER)+1 AS account_id,
            CASE WHEN i%5=0 THEN 'advanced_analytics'
                 WHEN i%5=1 THEN 'api_access'
                 WHEN i%5=2 THEN 'custom_reports'
                 WHEN i%5=3 THEN 'sso'
                 ELSE 'bulk_export' END AS feature_name,
            i%7 != 0 AS is_enabled,
            CASE WHEN i%5=0 THEN NULL
                 ELSE TIMESTAMPTZ '2020-01-01 00:00:00' + INTERVAL (i*86400) SECOND END
        FROM generate_series(0, 14999) t(i)
        """,
        # ── mrr_history (point-in-time MRR snapshot — the duplicate-metric trap) ─
        """
        CREATE TABLE mrr_history (
            account_id      INTEGER,
            snapshot_month  DATE,
            mrr             DECIMAL(10,2),
            new_mrr         DECIMAL(10,2),
            expansion_mrr   DECIMAL(10,2),
            contraction_mrr DECIMAL(10,2),
            churned_mrr     DECIMAL(10,2),
            ending_mrr      DECIMAL(10,2),
            PRIMARY KEY (account_id, snapshot_month)
        )
        """,
        # 3000 accounts × 50 months = 150000 rows.
        # account = i%3000+1, month_idx = floor(i/3000) → 0..49
        """
        INSERT INTO mrr_history
        SELECT
            (i%3000)+1 AS account_id,
            (DATE '2020-01-01' + (CAST(FLOOR(i/3000) AS INTEGER) * INTERVAL 1 MONTH))::DATE AS snapshot_month,
            ROUND(100+(i*17.3)%2000, 2) AS mrr,
            ROUND((i%200)*1.5, 2) AS new_mrr,
            ROUND((i%100)*2.0, 2) AS expansion_mrr,
            ROUND((i%50)*1.0, 2) AS contraction_mrr,
            ROUND((i%30)*3.0, 2) AS churned_mrr,
            ROUND(100+(i*17.3)%2000+(i%200)*1.5, 2) AS ending_mrr
        FROM generate_series(0, 149999) t(i)
        """,
        # ── cohorts (month-grain — mixed-grain trap) ───────────────────────────
        """
        CREATE TABLE cohorts (
            account_id    INTEGER,
            cohort_month  DATE,
            months_since  INTEGER,
            mrr           DECIMAL(10,2),
            retention_pct DECIMAL(5,2),
            PRIMARY KEY (account_id, cohort_month, months_since)
        )
        """,
        # 3000 accounts × 24 months_since = 72000 rows (one cohort month per account).
        # account = i%3000+1, months_since = floor(i/3000)
        """
        INSERT INTO cohorts
        SELECT
            (i%3000)+1 AS account_id,
            DATE '2020-01-01' AS cohort_month,
            CAST(FLOOR(i/3000) AS INTEGER) AS months_since,
            ROUND(50+(i*7.3)%500, 2),
            ROUND(40.0+(i%60)*1.0, 2)
        FROM generate_series(0, 71999) t(i)
        """,
        # ── support_tickets ────────────────────────────────────────────────────
        """
        CREATE TABLE support_tickets (
            ticket_id    INTEGER PRIMARY KEY,
            account_id   INTEGER,
            subject      VARCHAR,
            category     VARCHAR,    -- billing | technical | feature_request | other
            priority     VARCHAR,    -- low | medium | high | critical
            status       VARCHAR,    -- open | in_progress | resolved | closed
            created_at   TIMESTAMP,
            resolved_at  TIMESTAMP,  -- NULL for open tickets
            csat_score   INTEGER     -- 1–5, NULL if not rated
        )
        """,
        """
        INSERT INTO support_tickets
        SELECT
            i,
            (i%3000)+1,
            'Issue ' || i,
            CASE WHEN i%4=0 THEN 'billing' WHEN i%4=1 THEN 'technical'
                 WHEN i%4=2 THEN 'feature_request' ELSE 'other' END,
            CASE WHEN i%10=0 THEN 'critical' WHEN i%5=0 THEN 'high'
                 WHEN i%3=0 THEN 'medium' ELSE 'low' END,
            CASE WHEN i%7=0 THEN 'open' WHEN i%7=1 THEN 'in_progress'
                 WHEN i%7=2 THEN 'resolved' ELSE 'closed' END,
            TIMESTAMPTZ '2021-01-01 00:00:00' + INTERVAL (i*3600) SECOND,
            CASE WHEN i%7<2 THEN NULL  -- open/in_progress tickets
                 ELSE TIMESTAMPTZ '2021-01-01 00:00:00' + INTERVAL (i*3600+(i%72)*3600) SECOND END,
            CASE WHEN i%5=0 THEN NULL ELSE CAST((i%5)+1 AS INTEGER) END
        FROM generate_series(1, 20000) t(i)
        """,
    ],
)
