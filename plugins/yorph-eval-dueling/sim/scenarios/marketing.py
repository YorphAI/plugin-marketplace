"""
Marketing attribution simulation scenarios.

  SIMPLE  — campaigns, ad_spend, clicks, conversions. Basic ROAS/CPA measures.
  MEDIUM  — adds UTM-tracked sessions, touchpoints, and a multi-touch attribution
            challenge: the touchpoints table has one row per channel per conversion,
            so direct joins to conversions fan out ROAS calculations.
"""

from .base import (
    Scenario, DataQualityIssue, GroundTruth,
    ExpectedJoin, ExpectedMeasure,
)


# ── SIMPLE ─────────────────────────────────────────────────────────────────────

MARKETING_SIMPLE = Scenario(
    name="marketing_simple",
    domain="marketing",
    complexity="simple",
    description=(
        "A clean marketing schema: campaigns, clicks, and conversions. "
        "Tests whether the agent identifies ROAS, CPA, CTR, and conversion rate "
        "as the core marketing measures."
    ),
    schemas=["main"],
    data_quality_issues=[
        DataQualityIssue(
            table="clicks", column="campaign_id",
            issue_type="high_null",
            description="20% of clicks have NULL campaign_id — organic/direct traffic.",
            prevalence="20% of rows",
        ),
        DataQualityIssue(
            table="conversions", column="revenue",
            issue_type="high_null",
            description="revenue is NULL for lead-gen conversions (non-transactional goals).",
            prevalence="30% of rows",
        ),
    ],
    ground_truth=GroundTruth(
        expected_joins=[
            ExpectedJoin("clicks",      "campaigns",  "campaign_id",  "many:1"),
            ExpectedJoin("conversions", "clicks",     "click_id",     "1:1"),
            ExpectedJoin("ad_spend",    "campaigns",  "campaign_id",  "many:1"),
        ],
        expected_measures=[
            ExpectedMeasure("total_spend",    "Total Ad Spend",  "SUM",   "ad_spend",   "spend_amount",  [],                    "Paid Media"),
            ExpectedMeasure("total_clicks",   "Clicks",          "COUNT", "clicks",     "click_id",      [],                    "Paid Media"),
            ExpectedMeasure("conversions",    "Conversions",     "COUNT", "conversions","conversion_id", [],                    "Paid Media"),
            ExpectedMeasure("revenue",        "Attributed Revenue","SUM", "conversions","revenue",       ["revenue IS NOT NULL"],"Paid Media"),
            ExpectedMeasure("roas",           "ROAS",            "RATIO", "conversions",None,            [],                    "Paid Media"),
            ExpectedMeasure("cpa",            "CPA",             "RATIO", "ad_spend",   None,            [],                    "Paid Media"),
            ExpectedMeasure("ctr",            "CTR",             "RATIO", "clicks",     None,            [],                    "Paid Media"),
            ExpectedMeasure("impressions",    "Impressions",     "SUM",   "ad_spend",   "impressions",   [],                    "Paid Media"),
        ],
        business_rules=[
            "ROAS = revenue / spend. Only include conversions with non-NULL revenue.",
            "CPA = spend / conversions. Use campaign-level grouping.",
            "CTR = clicks / impressions.",
            "20% of clicks have no campaign_id — these are organic. Exclude from paid metrics.",
        ],
        open_questions=[
            "Should ROAS use last-click or first-click attribution?",
            "How should lead-gen conversions (revenue=NULL) factor into CPA calculations?",
        ],
        grain_per_table={
            "campaigns":   ["campaign_id"],
            "ad_spend":    ["spend_id"],
            "clicks":      ["click_id"],
            "conversions": ["conversion_id"],
        },
    ),
    table_descriptions={
        "campaigns":   "Ad campaigns. One row per campaign.",
        "ad_spend":    "Daily spend, impressions, and reach by campaign.",
        "clicks":      "Individual ad clicks. campaign_id NULL for organic traffic.",
        "conversions": "Conversion events (purchase, signup, lead). One row per event.",
    },
    seed_sql=[
        """
        CREATE TABLE campaigns (
            campaign_id   INTEGER PRIMARY KEY,
            name          VARCHAR,
            channel       VARCHAR,    -- paid_search | social | display | email
            objective     VARCHAR,    -- awareness | consideration | conversion
            start_date    DATE,
            end_date      DATE,
            budget        DECIMAL(10,2),
            is_active     BOOLEAN
        )
        """,
        """
        INSERT INTO campaigns
        SELECT
            i,
            'Campaign ' || i,
            CASE WHEN i%4=0 THEN 'paid_search' WHEN i%4=1 THEN 'social'
                 WHEN i%4=2 THEN 'display' ELSE 'email' END,
            CASE WHEN i%3=0 THEN 'awareness' WHEN i%3=1 THEN 'consideration'
                 ELSE 'conversion' END,
            DATE '2022-01-01' + INTERVAL ((i%52)*7) DAY,
            DATE '2022-01-01' + INTERVAL ((i%52)*7+90) DAY,
            ROUND(500.0+(i*73.0)%10000, 2),
            i%5 != 0
        FROM generate_series(1, 200) t(i)
        """,
        """
        CREATE TABLE ad_spend (
            spend_id      INTEGER PRIMARY KEY,
            campaign_id   INTEGER,
            spend_date    DATE,
            spend_amount  DECIMAL(10,2),
            impressions   INTEGER,
            reach         INTEGER
        )
        """,
        """
        INSERT INTO ad_spend
        SELECT
            i,
            (i%200)+1,
            DATE '2022-01-01' + INTERVAL (i%730) DAY,
            ROUND(10.0+(i*7.3)%500, 2),
            CAST((i%5000)+100 AS INTEGER),
            CAST((i%3000)+50 AS INTEGER)
        FROM generate_series(1, 50000) t(i)
        """,
        """
        CREATE TABLE clicks (
            click_id     INTEGER PRIMARY KEY,
            campaign_id  INTEGER,    -- NULL for organic
            clicked_at   TIMESTAMP,
            device_type  VARCHAR,
            country      VARCHAR,
            keyword      VARCHAR
        )
        """,
        """
        INSERT INTO clicks
        SELECT
            i,
            CASE WHEN i%5=0 THEN NULL ELSE (i%200)+1 END,
            TIMESTAMPTZ '2022-01-01 08:00:00' + INTERVAL (i*60) SECOND,
            CASE WHEN i%3=0 THEN 'desktop' WHEN i%3=1 THEN 'mobile' ELSE 'tablet' END,
            CASE WHEN i%4=0 THEN 'USA' WHEN i%4=1 THEN 'GBR'
                 WHEN i%4=2 THEN 'DEU' ELSE 'AUS' END,
            CASE WHEN i%3=0 THEN 'brand' WHEN i%3=1 THEN 'generic' ELSE NULL END
        FROM generate_series(1, 500000) t(i)
        """,
        """
        CREATE TABLE conversions (
            conversion_id  INTEGER PRIMARY KEY,
            click_id       INTEGER,
            campaign_id    INTEGER,
            conversion_type VARCHAR,   -- purchase | signup | lead | trial
            revenue        DECIMAL(10,2),   -- NULL for non-transactional
            converted_at   TIMESTAMP,
            country        VARCHAR
        )
        """,
        """
        INSERT INTO conversions
        SELECT
            i,
            (i%500000)+1 AS click_id,
            (i%200)+1 AS campaign_id,
            CASE WHEN i%4=0 THEN 'purchase' WHEN i%4=1 THEN 'signup'
                 WHEN i%4=2 THEN 'lead' ELSE 'trial' END,
            CASE WHEN i%4>=2 THEN NULL   -- lead/trial have no revenue
                 ELSE ROUND(20.0+(i*17.3)%500, 2) END,
            TIMESTAMPTZ '2022-01-01 08:00:00' + INTERVAL (i*300) SECOND,
            CASE WHEN i%4=0 THEN 'USA' WHEN i%4=1 THEN 'GBR'
                 WHEN i%4=2 THEN 'DEU' ELSE 'AUS' END
        FROM generate_series(1, 30000) t(i)
        """,
    ],
)


# ── MEDIUM ─────────────────────────────────────────────────────────────────────

MARKETING_MEDIUM = Scenario(
    name="marketing_medium",
    domain="marketing",
    complexity="medium",
    description=(
        "Full attribution stack: campaigns, spend, UTM sessions, touchpoints, and conversions. "
        "Key challenge: touchpoints is a multi-touch attribution table with one row per "
        "channel per conversion — joining it directly to conversions fans out revenue. "
        "The agent must detect this and recommend aggregating touchpoints first."
    ),
    schemas=["main"],
    data_quality_issues=[
        DataQualityIssue(
            table="touchpoints", column="conversion_id",
            issue_type="fan_out_trap",
            description=(
                "touchpoints has 1-many rows per conversion (one per channel in the attribution path). "
                "Joining conversions → touchpoints then summing revenue fans out the revenue figure. "
                "Must aggregate touchpoints before joining."
            ),
            prevalence="always",
        ),
        DataQualityIssue(
            table="sessions", column="utm_medium",
            issue_type="encoded_null",
            description="utm_medium = '(none)' is GA's encoded null for direct traffic.",
            prevalence="20% of rows",
        ),
        DataQualityIssue(
            table="ad_spend", column="spend_amount",
            issue_type="duplicate_metric",
            description=(
                "ad_spend.spend_amount and campaign_budgets.allocated_budget both represent money. "
                "spend is actuals; budget is planned. The agent should distinguish these."
            ),
            prevalence="always",
        ),
    ],
    ground_truth=GroundTruth(
        expected_joins=[
            ExpectedJoin("sessions",        "campaigns",   "campaign_id",  "many:1"),
            ExpectedJoin("conversions",     "sessions",    "session_id",   "many:1"),
            ExpectedJoin("touchpoints",     "conversions", "conversion_id","many:1",
                         is_trap=True, trap_type="fan_out"),
            ExpectedJoin("ad_spend",        "campaigns",   "campaign_id",  "many:1"),
            ExpectedJoin("campaign_budgets","campaigns",   "campaign_id",  "many:1"),
        ],
        expected_measures=[
            ExpectedMeasure("total_spend",    "Total Spend",    "SUM",   "ad_spend",   "spend_amount", [],                   "Paid Media"),
            ExpectedMeasure("roas",           "ROAS",           "RATIO", "conversions",None,           [],                   "Paid Media"),
            ExpectedMeasure("cpa",            "CPA",            "RATIO", "ad_spend",   None,           [],                   "Paid Media"),
            ExpectedMeasure("sessions",       "Sessions",       "COUNT", "sessions",   "session_id",   [],                   "Acquisition"),
            ExpectedMeasure("conversion_rate","Conversion Rate","RATIO", "sessions",   None,           [],                   "Acquisition"),
            ExpectedMeasure("budget_pacing",  "Budget Pacing",  "RATIO", "campaign_budgets",None,      [],                   "Planning"),
        ],
        business_rules=[
            "NEVER join conversions → touchpoints without pre-aggregating — it fans out revenue.",
            "Use last-touch attribution by default (touchpoints.position = 'last').",
            "utm_medium = '(none)' should be labelled 'direct' in channel reporting.",
            "ad_spend.spend_amount is actuals; campaign_budgets.allocated_budget is planned.",
        ],
        open_questions=[
            "Which attribution model should be used: last-touch, first-touch, or linear?",
            "How should cross-device journeys (same user, different session_id) be handled?",
        ],
        grain_per_table={
            "campaigns":        ["campaign_id"],
            "campaign_budgets": ["campaign_id", "budget_month"],
            "ad_spend":         ["spend_id"],
            "sessions":         ["session_id"],
            "conversions":      ["conversion_id"],
            "touchpoints":      ["touchpoint_id"],
        },
    ),
    table_descriptions={
        "campaigns":        "Ad campaigns.",
        "campaign_budgets": "Monthly budget allocations per campaign.",
        "ad_spend":         "Daily actual spend per campaign.",
        "sessions":         "Web sessions with UTM parameters.",
        "conversions":      "Conversion events.",
        "touchpoints":      "Multi-touch attribution — one row per channel per conversion. "
                            "Fan-out risk: aggregate before joining to conversions.",
    },
    seed_sql=[
        """
        CREATE TABLE campaigns (
            campaign_id  INTEGER PRIMARY KEY,
            name         VARCHAR,
            channel      VARCHAR,
            objective    VARCHAR,
            start_date   DATE,
            end_date     DATE,
            is_active    BOOLEAN
        )
        """,
        """
        INSERT INTO campaigns
        SELECT
            i, 'Campaign ' || i,
            CASE WHEN i%4=0 THEN 'paid_search' WHEN i%4=1 THEN 'social'
                 WHEN i%4=2 THEN 'display' ELSE 'email' END,
            CASE WHEN i%3=0 THEN 'awareness' WHEN i%3=1 THEN 'consideration'
                 ELSE 'conversion' END,
            DATE '2021-01-01' + INTERVAL ((i%104)*7) DAY,
            DATE '2021-01-01' + INTERVAL ((i%104)*7+90) DAY,
            i%4 != 0
        FROM generate_series(1, 500) t(i)
        """,
        """
        CREATE TABLE campaign_budgets (
            campaign_id       INTEGER,
            budget_month      DATE,
            allocated_budget  DECIMAL(10,2),
            PRIMARY KEY (campaign_id, budget_month)
        )
        """,
        # 500 campaigns × 36 months = 18000 unique combos.
        # Key: campaign = i%500+1, month = floor(i/500)
        """
        INSERT INTO campaign_budgets
        SELECT
            (i%500)+1 AS campaign_id,
            (DATE '2021-01-01' + (CAST(FLOOR(i/500) AS INTEGER) * INTERVAL 1 MONTH))::DATE AS budget_month,
            ROUND(1000.0+(i*73.0)%20000, 2)
        FROM generate_series(0, 17999) t(i)
        """,
        """
        CREATE TABLE ad_spend (
            spend_id     INTEGER PRIMARY KEY,
            campaign_id  INTEGER,
            spend_date   DATE,
            spend_amount DECIMAL(10,2),
            impressions  INTEGER,
            clicks       INTEGER
        )
        """,
        """
        INSERT INTO ad_spend
        SELECT
            i, (i%500)+1,
            DATE '2021-01-01' + INTERVAL (i%1095) DAY,
            ROUND(5.0+(i*7.3)%1000, 2),
            CAST((i%10000)+500 AS INTEGER),
            CAST((i%500)+10 AS INTEGER)
        FROM generate_series(1, 100000) t(i)
        """,
        """
        CREATE TABLE sessions (
            session_id   INTEGER PRIMARY KEY,
            campaign_id  INTEGER,
            utm_source   VARCHAR,
            utm_medium   VARCHAR,   -- '(none)' = encoded null
            utm_campaign VARCHAR,
            started_at   TIMESTAMP,
            device_type  VARCHAR,
            converted    BOOLEAN
        )
        """,
        """
        INSERT INTO sessions
        SELECT
            i,
            CASE WHEN i%5=0 THEN NULL ELSE (i%500)+1 END,
            CASE WHEN i%4=0 THEN 'google' WHEN i%4=1 THEN 'meta'
                 WHEN i%4=2 THEN 'email' ELSE 'direct' END,
            CASE WHEN i%5=0 THEN '(none)'
                 WHEN i%4=0 THEN 'cpc' WHEN i%4=1 THEN 'social'
                 WHEN i%4=2 THEN 'email' ELSE 'organic' END,
            CASE WHEN i%5=0 THEN NULL ELSE 'campaign_' || ((i%500)+1) END,
            TIMESTAMPTZ '2021-01-01 08:00:00' + INTERVAL (i*120) SECOND,
            CASE WHEN i%3=0 THEN 'desktop' WHEN i%3=1 THEN 'mobile' ELSE 'tablet' END,
            i%20 = 0  -- 5% conversion rate
        FROM generate_series(1, 2000000) t(i)
        """,
        """
        CREATE TABLE conversions (
            conversion_id  INTEGER PRIMARY KEY,
            session_id     INTEGER,
            campaign_id    INTEGER,
            revenue        DECIMAL(10,2),
            conversion_type VARCHAR,
            converted_at   TIMESTAMP
        )
        """,
        """
        INSERT INTO conversions
        SELECT
            i,
            (i*20)%2000000+1 AS session_id,  -- every 20th session converted
            (i%500)+1,
            CASE WHEN i%3=0 THEN NULL ELSE ROUND(15.0+(i*23.7)%600, 2) END,
            CASE WHEN i%3=0 THEN 'lead' ELSE 'purchase' END,
            TIMESTAMPTZ '2021-01-01 08:00:00' + INTERVAL (i*2400) SECOND
        FROM generate_series(1, 100000) t(i)
        """,
        # ── touchpoints (fan-out trap) ─────────────────────────────────────────
        """
        CREATE TABLE touchpoints (
            touchpoint_id   INTEGER PRIMARY KEY,
            conversion_id   INTEGER,
            channel         VARCHAR,
            position        VARCHAR,    -- first | middle | last
            credit_pct      DECIMAL(5,2),   -- % of conversion credit (linear attribution)
            touched_at      TIMESTAMP
        )
        """,
        """
        INSERT INTO touchpoints
        SELECT
            i,
            CAST(FLOOR(i/3) AS INTEGER)+1 AS conversion_id,  -- avg 3 touchpoints per conversion
            CASE WHEN i%4=0 THEN 'paid_search' WHEN i%4=1 THEN 'social'
                 WHEN i%4=2 THEN 'email' ELSE 'display' END,
            CASE WHEN i%3=0 THEN 'first' WHEN i%3=1 THEN 'middle' ELSE 'last' END,
            ROUND(100.0/3.0, 2) AS credit_pct,   -- linear model
            TIMESTAMPTZ '2021-01-01 08:00:00' + INTERVAL (i*800) SECOND
        FROM generate_series(1, 300000) t(i)
        """,
    ],
)
