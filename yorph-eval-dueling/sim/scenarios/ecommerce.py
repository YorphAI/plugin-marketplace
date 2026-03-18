"""
E-commerce simulation scenarios.

Three complexity levels:

  SIMPLE  — 4 tables, clean schema, obvious relationships. Baseline sanity check.
  MEDIUM  — 12 tables, returns, promotions, sessions, inventory. Includes fan-out
            trap and encoded nulls.
  COMPLEX — 20 tables across two schemas (PUBLIC + ANALYTICS). Legacy column naming,
            a pre-aggregated summary table mixed with atomic fact tables, and multiple
            ambiguous join paths. Designed to stress the Join Validator and Grain Detector.
"""

from .base import (
    Scenario, DataQualityIssue, GroundTruth,
    ExpectedJoin, ExpectedMeasure,
)


# ── SIMPLE ─────────────────────────────────────────────────────────────────────

ECOMMERCE_SIMPLE = Scenario(
    name="ecommerce_simple",
    domain="ecommerce",
    complexity="simple",
    description=(
        "A minimal e-commerce schema: orders, line items, customers, products. "
        "Clean FK relationships, obvious measures. Good for baseline smoke tests."
    ),
    schemas=["main"],
    data_quality_issues=[
        DataQualityIssue(
            table="orders", column="status",
            issue_type="encoded_null",
            description="10% of status values are 'N/A' — orders that were never confirmed.",
            prevalence="10% of rows",
        ),
        DataQualityIssue(
            table="orders", column="revenue",
            issue_type="high_null",
            description="Revenue is NULL for cancelled orders (status='N/A').",
            prevalence="10% of rows",
        ),
    ],
    ground_truth=GroundTruth(
        expected_joins=[
            ExpectedJoin("orders", "customers",   "customer_id", "many:1"),
            ExpectedJoin("order_items", "orders", "order_id",    "many:1"),
            ExpectedJoin("order_items", "products","product_id", "many:1"),
        ],
        expected_measures=[
            ExpectedMeasure("total_revenue",   "Total Revenue",      "SUM",            "orders",     "revenue",   ["status != 'N/A'"],    "Revenue"),
            ExpectedMeasure("order_count",     "Order Count",        "COUNT",          "orders",     "order_id",  ["status != 'N/A'"],    "Revenue"),
            ExpectedMeasure("avg_order_value", "Avg Order Value",    "AVG",            "orders",     "revenue",   ["status != 'N/A'"],    "Revenue"),
            ExpectedMeasure("units_sold",      "Units Sold",         "SUM",            "order_items","quantity",  [],                     "Product"),
            ExpectedMeasure("customer_count",  "Unique Customers",   "COUNT_DISTINCT", "orders",     "customer_id",[],                   "Customer"),
        ],
        business_rules=[
            "Revenue is NULL for orders where status = 'N/A' — treat as cancelled/voided.",
            "order_items.unit_price may differ from products.price (promotions applied at order time).",
        ],
        open_questions=[
            "Should orders with status='N/A' be excluded from all revenue metrics or only from recognised revenue?",
        ],
        grain_per_table={
            "orders":      ["order_id"],
            "order_items": ["order_id", "line_item_id"],
            "customers":   ["customer_id"],
            "products":    ["product_id"],
        },
    ),
    table_descriptions={
        "orders":      "Purchase orders placed by customers. One row per order header.",
        "order_items": "Individual line items within each order. One row per product per order.",
        "customers":   "Registered customers. One row per customer account.",
        "products":    "Product catalog. One row per SKU.",
    },
    seed_sql=[
        # ── customers ──────────────────────────────────────────────────────────
        """
        CREATE TABLE customers (
            customer_id  INTEGER PRIMARY KEY,
            name         VARCHAR,
            email        VARCHAR,
            region       VARCHAR,      -- AMER | EMEA | APAC
            segment      VARCHAR,      -- enterprise | mid_market | smb
            created_at   DATE
        )
        """,
        """
        INSERT INTO customers
        SELECT
            i AS customer_id,
            'Customer ' || i AS name,
            'user' || i || '@example.com' AS email,
            CASE WHEN i % 3 = 0 THEN 'EMEA'
                 WHEN i % 3 = 1 THEN 'AMER'
                 ELSE 'APAC' END AS region,
            CASE WHEN i % 10 < 2 THEN 'enterprise'
                 WHEN i % 10 < 6 THEN 'mid_market'
                 ELSE 'smb' END AS segment,
            DATE '2021-01-01' + INTERVAL (i % 730) DAY AS created_at
        FROM generate_series(1, 500) t(i)
        """,
        # ── products ───────────────────────────────────────────────────────────
        """
        CREATE TABLE products (
            product_id   INTEGER PRIMARY KEY,
            name         VARCHAR,
            category     VARCHAR,
            subcategory  VARCHAR,
            price        DECIMAL(10,2),
            unit_cost    DECIMAL(10,2),
            is_active    BOOLEAN
        )
        """,
        """
        INSERT INTO products
        SELECT
            i AS product_id,
            'Product ' || i AS name,
            CASE WHEN i % 4 = 0 THEN 'Electronics'
                 WHEN i % 4 = 1 THEN 'Apparel'
                 WHEN i % 4 = 2 THEN 'Home'
                 ELSE 'Books' END AS category,
            CASE WHEN i % 8 = 0 THEN 'Smartphones'
                 WHEN i % 8 = 1 THEN 'T-Shirts'
                 WHEN i % 8 = 2 THEN 'Furniture'
                 WHEN i % 8 = 3 THEN 'Fiction'
                 WHEN i % 8 = 4 THEN 'Laptops'
                 WHEN i % 8 = 5 THEN 'Outerwear'
                 WHEN i % 8 = 6 THEN 'Kitchen'
                 ELSE 'Non-Fiction' END AS subcategory,
            ROUND(9.99 + (i * 7.5) % 500, 2) AS price,
            ROUND(4.00 + (i * 3.2) % 200, 2) AS unit_cost,
            i % 10 != 0 AS is_active   -- 10% discontinued
        FROM generate_series(1, 120) t(i)
        """,
        # ── orders ─────────────────────────────────────────────────────────────
        """
        CREATE TABLE orders (
            order_id       INTEGER PRIMARY KEY,
            customer_id    INTEGER,
            order_date     DATE,
            status         VARCHAR,    -- completed | pending | refunded | N/A
            revenue        DECIMAL(12,2),
            discount       DECIMAL(12,2),
            shipping_cost  DECIMAL(8,2),
            created_at     TIMESTAMP
        )
        """,
        """
        INSERT INTO orders
        SELECT
            i AS order_id,
            (i % 500) + 1 AS customer_id,
            DATE '2023-01-01' + INTERVAL (i % 365) DAY AS order_date,
            -- 10% encoded null, 10% refunded, 25% pending, rest completed
            CASE WHEN i % 10 = 0 THEN 'N/A'
                 WHEN i % 7  = 0 THEN 'refunded'
                 WHEN i % 4  = 0 THEN 'pending'
                 ELSE 'completed' END AS status,
            -- Revenue NULL for N/A orders
            CASE WHEN i % 10 = 0 THEN NULL
                 ELSE ROUND(15.0 + (i * 13.7) % 800, 2) END AS revenue,
            ROUND((i % 30) * 1.5, 2) AS discount,
            ROUND(4.99 + (i % 20) * 0.5, 2) AS shipping_cost,
            TIMESTAMPTZ '2023-01-01 00:00:00' + INTERVAL (i * 1800) SECOND AS created_at
        FROM generate_series(1, 5000) t(i)
        """,
        # ── order_items ────────────────────────────────────────────────────────
        """
        CREATE TABLE order_items (
            order_id      INTEGER,
            line_item_id  INTEGER,
            product_id    INTEGER,
            quantity      INTEGER,
            unit_price    DECIMAL(10,2),
            discount_pct  DECIMAL(5,2),
            PRIMARY KEY (order_id, line_item_id)
        )
        """,
        """
        INSERT INTO order_items
        SELECT
            (i % 5000) + 1 AS order_id,
            CAST(FLOOR(i / 5000) AS INTEGER) + 1 AS line_item_id,
            (i % 120) + 1 AS product_id,
            (i % 5) + 1 AS quantity,
            ROUND(9.99 + (i % 200), 2) AS unit_price,
            ROUND((i % 30) * 0.5, 2) AS discount_pct
        FROM generate_series(0, 14999) t(i)
        """,
    ],
)


# ── MEDIUM ─────────────────────────────────────────────────────────────────────

ECOMMERCE_MEDIUM = Scenario(
    name="ecommerce_medium",
    domain="ecommerce",
    complexity="medium",
    description=(
        "Full e-commerce stack: orders, returns, promotions, inventory, sessions, and page views. "
        "Includes a fan-out trap (sessions → page_views, both linking to customers/orders), "
        "encoded nulls on anonymous sessions, and negative inventory values."
    ),
    schemas=["main"],
    data_quality_issues=[
        DataQualityIssue(
            table="sessions", column="customer_id",
            issue_type="high_null",
            description="30% of sessions are anonymous (customer_id NULL before login).",
            prevalence="30% of rows",
        ),
        DataQualityIssue(
            table="sessions", column="channel",
            issue_type="encoded_null",
            description="'(none)' and 'direct' are often encoded nulls from analytics tools.",
            prevalence="15% of rows",
        ),
        DataQualityIssue(
            table="inventory", column="quantity_on_hand",
            issue_type="negative_values",
            description="Negative inventory occurs when returns are processed before stock is updated.",
            prevalence="3% of rows",
        ),
        DataQualityIssue(
            table="page_views", column="session_id",
            issue_type="fan_out_trap",
            description=(
                "Joining orders → sessions → page_views inflates order-level metrics "
                "because one session can have many page views. "
                "The Join Validator should flag this as a fan-out."
            ),
            prevalence="always",
        ),
        DataQualityIssue(
            table="returns", column="refund_amount",
            issue_type="duplicate_metric",
            description=(
                "returns.refund_amount and orders.revenue are both measures of money — "
                "an analyst might accidentally double-count by summing both."
            ),
            prevalence="always",
        ),
    ],
    ground_truth=GroundTruth(
        expected_joins=[
            ExpectedJoin("orders",      "customers",     "customer_id",  "many:1"),
            ExpectedJoin("order_items", "orders",        "order_id",     "many:1"),
            ExpectedJoin("order_items", "products",      "product_id",   "many:1"),
            ExpectedJoin("returns",     "orders",        "order_id",     "many:1"),
            ExpectedJoin("order_promotions", "orders",   "order_id",     "many:1"),
            ExpectedJoin("order_promotions", "promotions","promo_id",    "many:1"),
            ExpectedJoin("inventory",   "products",      "product_id",   "many:1"),
            ExpectedJoin("inventory",   "warehouses",    "warehouse_id", "many:1"),
            ExpectedJoin("sessions",    "customers",     "customer_id",  "many:1"),
            ExpectedJoin("page_views",  "sessions",      "session_id",   "many:1",
                         is_trap=True, trap_type="fan_out"),
        ],
        expected_measures=[
            ExpectedMeasure("gross_revenue",    "Gross Revenue",     "SUM",   "orders",     "revenue",       ["status = 'completed'"],       "Revenue"),
            ExpectedMeasure("net_revenue",      "Net Revenue",       "SUM",   "orders",     "revenue",       ["status = 'completed'"],       "Revenue"),
            ExpectedMeasure("refund_amount",    "Refunds",           "SUM",   "returns",    "refund_amount", ["status = 'approved'"],        "Revenue"),
            ExpectedMeasure("order_count",      "Orders Placed",     "COUNT", "orders",     "order_id",      ["status != 'N/A'"],            "Orders"),
            ExpectedMeasure("return_rate",      "Return Rate",       "RATIO", "returns",    None,            [],                             "Orders"),
            ExpectedMeasure("units_sold",       "Units Sold",        "SUM",   "order_items","quantity",      [],                             "Product"),
            ExpectedMeasure("sessions_count",   "Sessions",          "COUNT", "sessions",   "session_id",    [],                             "Acquisition"),
            ExpectedMeasure("conversion_rate",  "Conversion Rate",   "RATIO", "sessions",   None,            [],                             "Acquisition"),
            ExpectedMeasure("inventory_level",  "Inventory on Hand", "SUM",   "inventory",  "quantity_on_hand",["quantity_on_hand > 0"],    "Inventory"),
        ],
        business_rules=[
            "Net Revenue = Gross Revenue - Refunds (only include approved returns).",
            "Conversion Rate = orders with status='completed' / total sessions.",
            "Negative inventory values exist — always filter quantity_on_hand > 0 for reporting.",
            "Orders with status='N/A' were never confirmed — exclude from all revenue metrics.",
            "Page views MUST NOT be joined directly to orders — use session as the bridge.",
        ],
        open_questions=[
            "Should 'pending' orders be included in order_count or only 'completed'?",
            "Is conversion_rate sessions-to-orders or sessions-to-revenue?",
            "How should multi-touch promo attribution work — first touch, last touch, or linear?",
        ],
        grain_per_table={
            "orders":           ["order_id"],
            "order_items":      ["order_id", "line_item_id"],
            "customers":        ["customer_id"],
            "products":         ["product_id"],
            "returns":          ["return_id"],
            "promotions":       ["promo_id"],
            "order_promotions": ["order_id", "promo_id"],
            "inventory":        ["product_id", "warehouse_id", "snapshot_date"],
            "warehouses":       ["warehouse_id"],
            "sessions":         ["session_id"],
            "page_views":       ["view_id"],
        },
    ),
    table_descriptions={
        "orders":           "Order headers. One row per customer order.",
        "order_items":      "Line items within orders. One row per product per order.",
        "customers":        "Customer accounts.",
        "products":         "Product catalog.",
        "returns":          "Return requests. One row per return (may cover partial order).",
        "promotions":       "Promo codes and discount campaigns.",
        "order_promotions": "Junction table linking orders to applied promotions.",
        "inventory":        "Daily inventory snapshot per product per warehouse.",
        "warehouses":       "Fulfilment warehouse locations.",
        "sessions":         "Web/app sessions. Anonymous sessions have NULL customer_id.",
        "page_views":       "Individual page view events within sessions.",
    },
    seed_sql=[
        # ── customers ──────────────────────────────────────────────────────────
        """
        CREATE TABLE customers (
            customer_id  INTEGER PRIMARY KEY,
            name         VARCHAR,
            email        VARCHAR,
            region       VARCHAR,
            segment      VARCHAR,
            ltv          DECIMAL(12,2),
            created_at   DATE
        )
        """,
        """
        INSERT INTO customers
        SELECT
            i, 'Customer ' || i, 'user' || i || '@example.com',
            CASE WHEN i%3=0 THEN 'EMEA' WHEN i%3=1 THEN 'AMER' ELSE 'APAC' END,
            CASE WHEN i%10<2 THEN 'enterprise' WHEN i%10<6 THEN 'mid_market' ELSE 'smb' END,
            ROUND(100.0 + (i * 47.3) % 5000, 2),
            DATE '2020-01-01' + INTERVAL (i % 1095) DAY
        FROM generate_series(1, 1000) t(i)
        """,
        # ── products ───────────────────────────────────────────────────────────
        """
        CREATE TABLE products (
            product_id   INTEGER PRIMARY KEY,
            name         VARCHAR,
            category     VARCHAR,
            subcategory  VARCHAR,
            sku          VARCHAR,
            price        DECIMAL(10,2),
            unit_cost    DECIMAL(10,2),
            weight_kg    DECIMAL(6,3),
            is_active    BOOLEAN
        )
        """,
        """
        INSERT INTO products
        SELECT
            i, 'Product ' || i,
            CASE WHEN i%4=0 THEN 'Electronics' WHEN i%4=1 THEN 'Apparel'
                 WHEN i%4=2 THEN 'Home' ELSE 'Books' END,
            CASE WHEN i%6=0 THEN 'Smartphones' WHEN i%6=1 THEN 'T-Shirts'
                 WHEN i%6=2 THEN 'Furniture' WHEN i%6=3 THEN 'Fiction'
                 WHEN i%6=4 THEN 'Laptops' ELSE 'Cookware' END,
            'SKU-' || LPAD(CAST(i AS VARCHAR), 5, '0'),
            ROUND(9.99 + (i*7.5)%500, 2),
            ROUND(4.0 + (i*3.2)%200, 2),
            ROUND(0.1 + (i%50)*0.1, 3),
            i%10 != 0
        FROM generate_series(1, 200) t(i)
        """,
        # ── orders ─────────────────────────────────────────────────────────────
        """
        CREATE TABLE orders (
            order_id       INTEGER PRIMARY KEY,
            customer_id    INTEGER,
            order_date     DATE,
            status         VARCHAR,
            revenue        DECIMAL(12,2),
            discount       DECIMAL(12,2),
            shipping_cost  DECIMAL(8,2),
            payment_method VARCHAR,
            created_at     TIMESTAMP
        )
        """,
        """
        INSERT INTO orders
        SELECT
            i, (i%1000)+1,
            DATE '2022-01-01' + INTERVAL (i%730) DAY,
            CASE WHEN i%10=0 THEN 'N/A' WHEN i%12=0 THEN 'refunded'
                 WHEN i%5=0  THEN 'pending' ELSE 'completed' END,
            CASE WHEN i%10=0 THEN NULL ELSE ROUND(15.0+(i*13.7)%800,2) END,
            ROUND((i%50)*1.5, 2),
            ROUND(4.99+(i%20)*0.5, 2),
            CASE WHEN i%4=0 THEN 'credit_card' WHEN i%4=1 THEN 'paypal'
                 WHEN i%4=2 THEN 'bank_transfer' ELSE 'buy_now_pay_later' END,
            TIMESTAMPTZ '2022-01-01 00:00:00' + INTERVAL (i*900) SECOND
        FROM generate_series(1, 10000) t(i)
        """,
        # ── order_items ────────────────────────────────────────────────────────
        """
        CREATE TABLE order_items (
            order_id      INTEGER,
            line_item_id  INTEGER,
            product_id    INTEGER,
            quantity      INTEGER,
            unit_price    DECIMAL(10,2),
            discount_pct  DECIMAL(5,2),
            PRIMARY KEY (order_id, line_item_id)
        )
        """,
        """
        INSERT INTO order_items
        SELECT
            (i%10000)+1,
            CAST(FLOOR(i/10000) AS INTEGER)+1,
            (i%200)+1,
            (i%5)+1,
            ROUND(9.99+(i%200), 2),
            ROUND((i%30)*0.5, 2)
        FROM generate_series(0, 29999) t(i)
        """,
        # ── returns ────────────────────────────────────────────────────────────
        """
        CREATE TABLE returns (
            return_id     INTEGER PRIMARY KEY,
            order_id      INTEGER,
            return_date   DATE,
            reason        VARCHAR,
            refund_amount DECIMAL(12,2),
            status        VARCHAR     -- pending | approved | rejected
        )
        """,
        """
        INSERT INTO returns
        SELECT
            i,
            -- reference completed orders by cycling through their IDs
            ((i - 1) % 8000) * 10 + 1 AS order_id,
            DATE '2022-03-01' + INTERVAL (i%700) DAY,
            CASE WHEN i%5=0 THEN 'defective'
                 WHEN i%5=1 THEN 'wrong_item'
                 WHEN i%5=2 THEN 'changed_mind'
                 WHEN i%5=3 THEN 'not_as_described'
                 ELSE 'damaged_in_shipping' END,
            ROUND(10.0+(i*17.3)%400, 2),
            CASE WHEN i%8=0 THEN 'rejected' WHEN i%8<3 THEN 'pending'
                 ELSE 'approved' END
        FROM generate_series(1, 800) t(i)
        """,
        # ── promotions ─────────────────────────────────────────────────────────
        """
        CREATE TABLE promotions (
            promo_id       INTEGER PRIMARY KEY,
            code           VARCHAR,
            discount_type  VARCHAR,   -- percentage | fixed_amount | free_shipping
            discount_value DECIMAL(8,2),
            min_order_amt  DECIMAL(8,2),
            start_date     DATE,
            end_date       DATE,
            is_active      BOOLEAN
        )
        """,
        """
        INSERT INTO promotions VALUES
            (1,  'SUMMER20',  'percentage',   20.0, 50.0,  DATE '2023-06-01', DATE '2023-08-31', false),
            (2,  'SAVE10',    'fixed_amount', 10.0, 30.0,  DATE '2023-01-01', DATE '2023-12-31', false),
            (3,  'FREESHIP',  'free_shipping', 0.0, 75.0,  DATE '2023-03-01', DATE '2023-03-31', false),
            (4,  'FLASH25',   'percentage',   25.0, 100.0, DATE '2023-11-24', DATE '2023-11-27', false),
            (5,  'WELCOME15', 'percentage',   15.0, 0.0,   DATE '2023-01-01', DATE '2023-12-31', false),
            (6,  'VIP30',     'percentage',   30.0, 200.0, DATE '2023-01-01', DATE '2023-12-31', true),
            (7,  'SAVE5',     'fixed_amount',  5.0, 20.0,  DATE '2024-01-01', DATE '2024-06-30', true),
            (8,  'SPRING15',  'percentage',   15.0, 40.0,  DATE '2024-03-01', DATE '2024-05-31', true)
        """,
        # ── order_promotions ───────────────────────────────────────────────────
        """
        CREATE TABLE order_promotions (
            order_id  INTEGER,
            promo_id  INTEGER,
            PRIMARY KEY (order_id, promo_id)
        )
        """,
        """
        INSERT INTO order_promotions
        SELECT DISTINCT
            (i%10000)+1 AS order_id,
            (i%8)+1     AS promo_id
        FROM generate_series(0, 2499) t(i)
        """,
        # ── warehouses ─────────────────────────────────────────────────────────
        """
        CREATE TABLE warehouses (
            warehouse_id  INTEGER PRIMARY KEY,
            name          VARCHAR,
            region        VARCHAR,
            country       VARCHAR,
            timezone      VARCHAR
        )
        """,
        """
        INSERT INTO warehouses VALUES
            (1, 'US East', 'AMER', 'USA', 'America/New_York'),
            (2, 'US West', 'AMER', 'USA', 'America/Los_Angeles'),
            (3, 'UK',      'EMEA', 'GBR', 'Europe/London'),
            (4, 'Germany', 'EMEA', 'DEU', 'Europe/Berlin'),
            (5, 'Singapore','APAC','SGP', 'Asia/Singapore'),
            (6, 'Australia','APAC','AUS', 'Australia/Sydney')
        """,
        # ── inventory ──────────────────────────────────────────────────────────
        """
        CREATE TABLE inventory (
            product_id       INTEGER,
            warehouse_id     INTEGER,
            snapshot_date    DATE,
            quantity_on_hand INTEGER,    -- can be negative (returns before restock)
            reorder_point    INTEGER,
            reorder_qty      INTEGER,
            PRIMARY KEY (product_id, warehouse_id, snapshot_date)
        )
        """,
        # 200 products × 6 warehouses × 6 weekly snapshots = 7200 rows.
        # Stride: product fastest, then wh, then date.
        # product = (i%1200)%200+1, wh = floor((i%1200)/200)+1, date_idx = floor(i/1200)
        """
        INSERT INTO inventory
        SELECT
            (i%1200)%200+1 AS product_id,
            CAST(FLOOR((i%1200)/200) AS INTEGER)+1 AS warehouse_id,
            DATE '2024-01-01' + INTERVAL (CAST(FLOOR(i/1200) AS INTEGER)*7) DAY AS snapshot_date,
            CASE WHEN i%33=0 THEN -(i%20)-1 ELSE (i%500)+10 END AS quantity_on_hand,
            (i%50)+5 AS reorder_point,
            (i%100)+50 AS reorder_qty
        FROM generate_series(0, 7199) t(i)
        """,
        # ── sessions ───────────────────────────────────────────────────────────
        """
        CREATE TABLE sessions (
            session_id    INTEGER PRIMARY KEY,
            customer_id   INTEGER,    -- NULL for anonymous sessions (30%)
            started_at    TIMESTAMP,
            ended_at      TIMESTAMP,
            channel       VARCHAR,    -- organic | paid_search | email | (none) | direct
            source        VARCHAR,
            medium        VARCHAR,
            campaign      VARCHAR,
            device_type   VARCHAR,
            converted     BOOLEAN     -- did this session lead to an order?
        )
        """,
        """
        INSERT INTO sessions
        SELECT
            i,
            -- 30% anonymous
            CASE WHEN i%10 < 3 THEN NULL ELSE (i%1000)+1 END AS customer_id,
            TIMESTAMPTZ '2022-01-01 08:00:00' + INTERVAL (i*1200) SECOND,
            TIMESTAMPTZ '2022-01-01 08:00:00' + INTERVAL (i*1200 + 300 + (i%600)) SECOND,
            -- (none) and direct are encoded nulls from GA
            CASE WHEN i%20=0 THEN '(none)'
                 WHEN i%15=0 THEN 'direct'
                 WHEN i%7=0  THEN 'email'
                 WHEN i%5=0  THEN 'paid_search'
                 WHEN i%3=0  THEN 'organic'
                 ELSE 'social' END,
            CASE WHEN i%5=0 THEN 'google' WHEN i%5=1 THEN 'meta'
                 WHEN i%5=2 THEN 'klaviyo' ELSE 'direct' END,
            CASE WHEN i%3=0 THEN 'cpc' WHEN i%3=1 THEN 'email' ELSE 'organic' END,
            CASE WHEN i%5=0 THEN 'summer_sale' WHEN i%5=1 THEN 'brand_awareness'
                 ELSE NULL END,
            CASE WHEN i%3=0 THEN 'desktop' WHEN i%3=1 THEN 'mobile' ELSE 'tablet' END,
            i%7 = 0   -- ~14% conversion rate
        FROM generate_series(1, 50000) t(i)
        """,
        # ── page_views ─────────────────────────────────────────────────────────
        # NOTE: this is the fan-out trap — many views per session
        """
        CREATE TABLE page_views (
            view_id     INTEGER PRIMARY KEY,
            session_id  INTEGER,
            page_url    VARCHAR,
            viewed_at   TIMESTAMP,
            time_on_page_sec INTEGER
        )
        """,
        """
        INSERT INTO page_views
        SELECT
            i AS view_id,
            (i % 50000) + 1 AS session_id,
            CASE WHEN i%6=0 THEN '/home'
                 WHEN i%6=1 THEN '/products'
                 WHEN i%6=2 THEN '/cart'
                 WHEN i%6=3 THEN '/checkout'
                 WHEN i%6=4 THEN '/account'
                 ELSE '/blog' END,
            TIMESTAMPTZ '2022-01-01 08:00:00' + INTERVAL (i*120) SECOND,
            (i%300) + 5
        FROM generate_series(1, 180000) t(i)
        """,
    ],
)


# ── COMPLEX ─────────────────────────────────────────────────────────────────────

ECOMMERCE_COMPLEX = Scenario(
    name="ecommerce_complex",
    domain="ecommerce",
    complexity="complex",
    description=(
        "A legacy e-commerce schema with two schemas (PUBLIC + ANALYTICS), "
        "old-style column naming (f_ord_id, d_cust_nbr), a pre-aggregated "
        "daily summary table coexisting with atomic fact tables, a genuine "
        "many-to-many between customers and storefronts, and multiple ambiguous "
        "join paths. Stress-tests the Join Validator and Grain Detector."
    ),
    schemas=["main", "analytics"],
    data_quality_issues=[
        DataQualityIssue(
            table="f_orders", column="f_ord_status_cd",
            issue_type="schema_drift",
            description=(
                "Legacy 'f_' prefix columns use status codes (1=completed, 2=pending, 3=cancelled) "
                "while the newer orders table uses string labels. "
                "The agent must recognise these are the same concept."
            ),
            prevalence="always",
        ),
        DataQualityIssue(
            table="analytics.daily_order_summary", column="total_revenue",
            issue_type="mixed_grain",
            description=(
                "daily_order_summary is pre-aggregated (one row per day × category). "
                "It must NOT be joined directly to atomic order facts — the grains are incompatible."
            ),
            prevalence="always",
        ),
        DataQualityIssue(
            table="customer_storefronts", column="customer_id",
            issue_type="ambiguous_key",
            description=(
                "customer_storefronts is a genuine M:M bridge. "
                "Joining orders → customer_storefronts without aggregating will fan-out order metrics."
            ),
            prevalence="always",
        ),
        DataQualityIssue(
            table="f_orders", column="f_cust_nbr",
            issue_type="encoded_null",
            description="Guest orders have f_cust_nbr = -1 (not a real customer). Filter required.",
            prevalence="8% of rows",
        ),
    ],
    ground_truth=GroundTruth(
        expected_joins=[
            ExpectedJoin("f_orders",      "d_customers",    "f_cust_nbr",     "many:1"),
            ExpectedJoin("f_order_lines", "f_orders",       "f_ord_id",       "many:1"),
            ExpectedJoin("f_order_lines", "d_products",     "f_prod_id",      "many:1"),
            ExpectedJoin("f_orders",      "d_storefronts",  "f_storefront_id","many:1"),
            ExpectedJoin("customer_storefronts","d_customers","customer_id",  "many:many",
                         is_trap=True, trap_type="fan_out"),
        ],
        expected_measures=[
            ExpectedMeasure("gross_revenue", "Gross Revenue", "SUM", "f_orders", "f_ord_revenue",
                            ["f_ord_status_cd = 1"], "Revenue"),
            ExpectedMeasure("order_count", "Order Count", "COUNT", "f_orders", "f_ord_id",
                            ["f_ord_status_cd = 1", "f_cust_nbr != -1"], "Revenue"),
        ],
        business_rules=[
            "f_ord_status_cd = 1 means 'completed'. Use this — not string labels — for revenue filters.",
            "f_cust_nbr = -1 are guest orders — exclude from customer-segmented metrics.",
            "analytics.daily_order_summary is pre-aggregated — never join to atomic order facts.",
        ],
        open_questions=[
            "Should guest orders (f_cust_nbr = -1) be included in total order count?",
            "Is the analytics schema pre-aggregated nightly or in real-time?",
            "Does f_ord_revenue include or exclude taxes?",
        ],
        grain_per_table={
            "f_orders":                   ["f_ord_id"],
            "f_order_lines":              ["f_ord_id", "f_line_nbr"],
            "d_customers":                ["d_cust_nbr"],
            "d_products":                 ["d_prod_id"],
            "d_storefronts":              ["d_storefront_id"],
            "customer_storefronts":       ["customer_id", "storefront_id"],
            "analytics.daily_order_summary": ["report_date", "category"],
        },
    ),
    table_descriptions={
        "f_orders":                      "Fact: order headers. Legacy 'f_' prefix schema.",
        "f_order_lines":                 "Fact: order line items.",
        "d_customers":                   "Dimension: customer master.",
        "d_products":                    "Dimension: product catalog.",
        "d_storefronts":                 "Dimension: retail storefronts (online channels).",
        "customer_storefronts":          "Bridge: M:M customers ↔ storefronts (multi-storefront accounts).",
        "analytics.daily_order_summary": "Pre-aggregated daily summary by category. NOT for row-level joins.",
    },
    seed_sql=[
        # Create analytics schema
        "CREATE SCHEMA IF NOT EXISTS analytics",

        # ── d_customers ────────────────────────────────────────────────────────
        """
        CREATE TABLE d_customers (
            d_cust_nbr    INTEGER PRIMARY KEY,   -- legacy: 'd_' prefix for dimensions
            d_cust_name   VARCHAR,
            d_cust_email  VARCHAR,
            d_region_cd   VARCHAR,
            d_seg_cd      VARCHAR,
            d_create_dt   DATE
        )
        """,
        """
        INSERT INTO d_customers
        SELECT i, 'Cust ' || i, 'c' || i || '@co.com',
            CASE WHEN i%3=0 THEN 'EU' WHEN i%3=1 THEN 'US' ELSE 'AP' END,
            CASE WHEN i%3=0 THEN 'ENT' WHEN i%3=1 THEN 'MM' ELSE 'SMB' END,
            DATE '2019-01-01' + INTERVAL (i%1460) DAY
        FROM generate_series(1, 2000) t(i)
        """,
        # ── d_products ─────────────────────────────────────────────────────────
        """
        CREATE TABLE d_products (
            d_prod_id    INTEGER PRIMARY KEY,
            d_prod_nm    VARCHAR,
            d_cat_nm     VARCHAR,
            d_subcat_nm  VARCHAR,
            d_unit_cost  DECIMAL(10,2),
            d_sell_price DECIMAL(10,2),
            d_active_flg CHAR(1)        -- 'Y' | 'N'
        )
        """,
        """
        INSERT INTO d_products
        SELECT i, 'Prod ' || i,
            CASE WHEN i%4=0 THEN 'Electronics' WHEN i%4=1 THEN 'Apparel'
                 WHEN i%4=2 THEN 'Home' ELSE 'Books' END,
            'Subcat ' || (i%12),
            ROUND(5.0+(i*2.7)%150, 2),
            ROUND(10.0+(i*7.5)%500, 2),
            CASE WHEN i%10=0 THEN 'N' ELSE 'Y' END
        FROM generate_series(1, 300) t(i)
        """,
        # ── d_storefronts ──────────────────────────────────────────────────────
        """
        CREATE TABLE d_storefronts (
            d_storefront_id  INTEGER PRIMARY KEY,
            d_store_nm       VARCHAR,
            d_channel_cd     VARCHAR,
            d_country_cd     VARCHAR
        )
        """,
        """
        INSERT INTO d_storefronts VALUES
            (1, 'US Website',   'WEB',    'USA'),
            (2, 'UK Website',   'WEB',    'GBR'),
            (3, 'DE Website',   'WEB',    'DEU'),
            (4, 'US App',       'MOBILE', 'USA'),
            (5, 'UK App',       'MOBILE', 'GBR'),
            (6, 'Wholesale',    'B2B',    'USA'),
            (7, 'Amazon US',    'MKTPL',  'USA'),
            (8, 'Amazon EU',    'MKTPL',  'DEU')
        """,
        # ── f_orders ───────────────────────────────────────────────────────────
        """
        CREATE TABLE f_orders (
            f_ord_id         INTEGER PRIMARY KEY,
            f_cust_nbr       INTEGER,    -- -1 for guest orders (8%)
            f_storefront_id  INTEGER,
            f_ord_dt         DATE,
            f_ord_status_cd  INTEGER,    -- 1=completed, 2=pending, 3=cancelled
            f_ord_revenue    DECIMAL(12,2),
            f_ord_disc_amt   DECIMAL(12,2),
            f_ord_ship_amt   DECIMAL(8,2),
            f_create_ts      TIMESTAMP
        )
        """,
        """
        INSERT INTO f_orders
        SELECT
            i,
            CASE WHEN i%12=0 THEN -1 ELSE (i%2000)+1 END AS f_cust_nbr,
            (i%8)+1 AS f_storefront_id,
            DATE '2020-01-01' + INTERVAL (i%1460) DAY,
            CASE WHEN i%8=0 THEN 3 WHEN i%5=0 THEN 2 ELSE 1 END AS f_ord_status_cd,
            CASE WHEN i%8=0 THEN NULL ELSE ROUND(10.0+(i*13.7)%900, 2) END,
            ROUND((i%60)*2.0, 2),
            ROUND(3.99+(i%25)*0.5, 2),
            TIMESTAMPTZ '2020-01-01 00:00:00' + INTERVAL (i*600) SECOND
        FROM generate_series(1, 20000) t(i)
        """,
        # ── f_order_lines ──────────────────────────────────────────────────────
        """
        CREATE TABLE f_order_lines (
            f_ord_id    INTEGER,
            f_line_nbr  INTEGER,
            f_prod_id   INTEGER,
            f_qty       INTEGER,
            f_unit_px   DECIMAL(10,2),
            f_disc_pct  DECIMAL(5,2),
            PRIMARY KEY (f_ord_id, f_line_nbr)
        )
        """,
        """
        INSERT INTO f_order_lines
        SELECT
            (i%20000)+1,
            CAST(FLOOR(i/20000) AS INTEGER)+1,
            (i%300)+1,
            (i%8)+1,
            ROUND(9.99+(i%300), 2),
            ROUND((i%40)*0.5, 2)
        FROM generate_series(0, 59999) t(i)
        """,
        # ── customer_storefronts (M:M bridge) ──────────────────────────────────
        """
        CREATE TABLE customer_storefronts (
            customer_id    INTEGER,
            storefront_id  INTEGER,
            first_order_dt DATE,
            PRIMARY KEY (customer_id, storefront_id)
        )
        """,
        """
        INSERT INTO customer_storefronts
        SELECT DISTINCT
            (i%2000)+1 AS customer_id,
            (i%8)+1    AS storefront_id,
            DATE '2020-01-01' + INTERVAL (i%1000) DAY
        FROM generate_series(0, 3999) t(i)
        """,
        # ── analytics.daily_order_summary (pre-aggregated — grain conflict) ────
        """
        CREATE TABLE analytics.daily_order_summary (
            report_date       DATE,
            category          VARCHAR,
            storefront_id     INTEGER,
            total_orders      INTEGER,
            total_revenue     DECIMAL(14,2),
            avg_order_value   DECIMAL(10,2),
            units_sold        INTEGER,
            PRIMARY KEY (report_date, category, storefront_id)
        )
        """,
        # 1460 dates × 4 categories × 8 storefronts = 46,720 unique combos.
        # Key: date = floor(i/32), category = floor(i/8)%4, storefront = i%8+1
        """
        INSERT INTO analytics.daily_order_summary
        SELECT
            DATE '2020-01-01' + INTERVAL (CAST(FLOOR(i/32) AS INTEGER)) DAY AS report_date,
            CASE WHEN CAST(FLOOR(i/8) AS INTEGER)%4=0 THEN 'Electronics'
                 WHEN CAST(FLOOR(i/8) AS INTEGER)%4=1 THEN 'Apparel'
                 WHEN CAST(FLOOR(i/8) AS INTEGER)%4=2 THEN 'Home'
                 ELSE 'Books' END AS category,
            (i%8)+1 AS storefront_id,
            CAST((i%50)+1 AS INTEGER) AS total_orders,
            ROUND(500.0+(i*73.1)%10000, 2) AS total_revenue,
            ROUND(50.0+(i*7.3)%200, 2) AS avg_order_value,
            CAST((i%200)+10 AS INTEGER) AS units_sold
        FROM generate_series(0, 46719) t(i)
        """,
    ],
)
