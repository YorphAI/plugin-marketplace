# Context Summary — ecommerce_medium

# Enriched Profiles — Batch 1 of 1 (11 tables)


## main.customers
Rows: 1,000 | Profiled: 2026-03-10

**Columns:**
`customer_id` (INTEGER) → ~ "Customer Id"
  Stats: null=0.0% | ~distinct=1,232 | range=[1, 1000]
  Samples: 1, 1000
`name` (VARCHAR)
  Stats: null=0.0% | ~distinct=1,075 | avg_len=12
  Samples: Customer 69, Customer 91, Customer 106
`email` (VARCHAR)
  Stats: null=0.0% | ~distinct=894 | avg_len=19
  Samples: user40@example.com, user58@example.com, user66@example.com
`region` (VARCHAR)
  Stats: null=0.0% | ~distinct=3 | avg_len=4
  Samples: APAC, AMER, EMEA
`segment` (VARCHAR)
  Stats: null=0.0% | ~distinct=3 | avg_len=7
  Samples: enterprise, mid_market, smb
`ltv` (DECIMAL(12,2))
  Stats: null=0.0% | ~distinct=1,104 | range=[102.00, 5094.10]
  Samples: 102.00, 5094.10
`created_at` (DATE) → ~ "Created At"
  Stats: null=0.0% | ~distinct=1,026
  Samples: 2020-01-02, 2022-09-27

## main.inventory
Rows: 7,200 | Profiled: 2026-03-10

**Columns:**
`product_id` (INTEGER) → ~ "Product Id"
  Stats: null=0.0% | ~distinct=223 | range=[1, 200]
  Samples: 1, 200
`warehouse_id` (INTEGER) → ~ "Warehouse Id"
  Stats: null=0.0% | ~distinct=6 | range=[1, 6]
  Samples: 1, 6
`snapshot_date` (DATE) → ~ "Snapshot Date"
  Stats: null=0.0% | ~distinct=6
  Samples: 2024-01-01, 2024-02-05
`quantity_on_hand` (INTEGER) → ~ "Quantity On Hand"
  Stats: null=0.0% | ~distinct=532 | range=[-20, 509]
  Samples: -20, 509
`reorder_point` (INTEGER) → ~ "Reorder Point"
  Stats: null=0.0% | ~distinct=47 | range=[5, 54]
  Samples: 5, 54
`reorder_qty` (INTEGER) → ~ "Reorder Quantity"
  Stats: null=0.0% | ~distinct=98 | range=[50, 149]
  Samples: 50, 149

## main.order_items
Rows: 30,000 | Profiled: 2026-03-10

**Columns:**
`order_id` (INTEGER) → ~ "Order Id"
  Stats: null=0.0% | ~distinct=8,565 | range=[1, 10000]
  Samples: 1, 10000
`line_item_id` (INTEGER) → ~ "Line Item Id"
  Stats: null=0.0% | ~distinct=3 | range=[1, 3]
  Samples: 1, 3
`product_id` (INTEGER) → ~ "Product Id"
  Stats: null=0.0% | ~distinct=223 | range=[1, 200]
  Samples: 1, 200
`quantity` (INTEGER)
  Stats: null=0.0% | ~distinct=5 | range=[1, 5]
  Samples: 1, 5
`unit_price` (DECIMAL(10,2)) → ~ "Unit Price"
  Stats: null=0.0% | ~distinct=205 | range=[9.99, 208.99]
  Samples: 9.99, 208.99
`discount_pct` (DECIMAL(5,2)) → ~ "Discount Pct"
  Stats: null=0.0% | ~distinct=27 | range=[0.00, 14.50]

## main.order_promotions
Rows: 2,500 | Profiled: 2026-03-10

**Columns:**
`order_id` (INTEGER) → ~ "Order Id"
  Stats: null=0.0% | ~distinct=2,558 | range=[1, 2500]
  Samples: 1, 2500
`promo_id` (INTEGER) → ~ "Promo Id"
  Stats: null=0.0% | ~distinct=9 | range=[1, 8]
  Samples: 1, 8

## main.orders
Rows: 10,000 | Profiled: 2026-03-10

**Columns:**
`order_id` (INTEGER) → ~ "Order Id"
  Stats: null=0.0% | ~distinct=8,565 | range=[1, 10000]
  Samples: 1, 10000
`customer_id` (INTEGER) → ~ "Customer Id"
  Stats: null=0.0% | ~distinct=1,232 | range=[1, 1000]
  Samples: 1, 1000
`order_date` (DATE) → ~ "Order Date"
  Stats: null=0.0% | ~distinct=843
  Samples: 2022-01-01, 2023-12-31
`status` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=8
  Samples: refunded, pending, completed
`revenue` (DECIMAL(12,2))
  Stats: null=10.0% | ~distinct=10,310 | range=[15.10, 814.90]
  Samples: 15.10, 814.90
`discount` (DECIMAL(12,2))
  Stats: null=0.0% | ~distinct=49 | range=[0.00, 73.50]
`shipping_cost` (DECIMAL(8,2)) → ~ "Shipping Cost"
  Stats: null=0.0% | ~distinct=20 | range=[4.99, 14.49]
  Samples: 4.99, 14.49
`payment_method` (VARCHAR) → ~ "Payment Method"
  Stats: null=0.0% | ~distinct=4 | avg_len=12
  Samples: buy_now_pay_later, credit_card, paypal
`created_at` (TIMESTAMP) → ~ "Created At"
  Stats: null=0.0% | ~distinct=11,444
  Samples: 2022-01-01 00:15:00, 2022-04-15 05:00:00

## main.page_views
Rows: 180,000 | Profiled: 2026-03-10

**Columns:**
`view_id` (INTEGER) → ~ "View Id"
  Stats: null=0.0% | ~distinct=171,929 | range=[1, 180000]
  Samples: 1, 180000
`session_id` (INTEGER) → ~ "Session Id"
  Stats: null=0.0% | ~distinct=45,031 | range=[1, 50000]
  Samples: 1, 50000
`page_url` (VARCHAR) → ~ "Page Url"
  Stats: null=0.0% | ~distinct=6 | avg_len=7
  Samples: /cart, /home, /products
`viewed_at` (TIMESTAMP) → ~ "Viewed At"
  Stats: null=0.0% | ~distinct=195,542
  Samples: 2022-01-01 08:02:00, 2022-09-08 09:00:00
`time_on_page_sec` (INTEGER) → ~ "Time On Page Sec"
  Stats: null=0.0% | ~distinct=340 | range=[5, 304]
  Samples: 5, 304

## main.products
Rows: 200 | Profiled: 2026-03-10

**Columns:**
`product_id` (INTEGER) → ~ "Product Id"
  Stats: null=0.0% | ~distinct=223 | range=[1, 200]
  Samples: 1, 200
`name` (VARCHAR)
  Stats: null=0.0% | ~distinct=178 | avg_len=10
  Samples: Product 1, Product 11, Product 16
`category` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=7
  Samples: Apparel, Home, Electronics
`subcategory` (VARCHAR)
  Stats: null=0.0% | ~distinct=6 | avg_len=8
  Samples: T-Shirts, Fiction, Laptops
`sku` (VARCHAR)
  Stats: null=0.0% | ~distinct=198 | avg_len=9
  Samples: SKU-00001, SKU-00020, SKU-00025
`price` (DECIMAL(10,2))
  Stats: null=0.0% | ~distinct=223 | range=[9.99, 507.49]
  Samples: 9.99, 507.49
`unit_cost` (DECIMAL(10,2)) → ~ "Unit Cost"
  Stats: null=0.0% | ~distinct=109 | range=[4.00, 202.40]
  Samples: 4.00, 202.40
`weight_kg` (DECIMAL(6,3)) → ~ "Weight Kg"
  Stats: null=0.0% | ~distinct=57 | range=[0.100, 5.000]
  Samples: 0.100, 5.000
`is_active` (BOOLEAN) → ~ "Is Active"
  Stats: null=0.0% | ~distinct=2

## main.promotions
Rows: 8 | Profiled: 2026-03-10

**Columns:**
`promo_id` (INTEGER) → ~ "Promo Id"
  Stats: null=0.0% | ~distinct=9 | range=[1, 8]
  Samples: 1, 8
`code` (VARCHAR)
  Stats: null=0.0% | ~distinct=7 | avg_len=7
  Samples: SAVE10, SUMMER20, SPRING15
`discount_type` (VARCHAR) → ~ "Discount Type"
  Stats: null=0.0% | ~distinct=3 | avg_len=11
  Samples: fixed_amount, free_shipping, percentage
`discount_value` (DECIMAL(8,2)) → ~ "Discount Value"
  Stats: null=0.0% | ~distinct=7 | range=[0.00, 30.00]
`min_order_amt` (DECIMAL(8,2)) → ~ "Min Order Amount"
  Stats: null=0.0% | ~distinct=9 | range=[0.00, 200.00]
`start_date` (DATE) → ~ "Start Date"
  Stats: null=0.0% | ~distinct=6
  Samples: 2023-01-01, 2024-03-01
`end_date` (DATE) → ~ "End Date"
  Stats: null=0.0% | ~distinct=5
  Samples: 2023-03-31, 2024-06-30
`is_active` (BOOLEAN) → ~ "Is Active"
  Stats: null=0.0% | ~distinct=2

## main.returns
Rows: 800 | Profiled: 2026-03-10

**Columns:**
`return_id` (INTEGER) → ~ "Return Id"
  Stats: null=0.0% | ~distinct=959 | range=[1, 800]
  Samples: 1, 800
`order_id` (INTEGER) → ~ "Order Id"
  Stats: null=0.0% | ~distinct=808 | range=[1, 7991]
  Samples: 1, 7991
`return_date` (DATE) → ~ "Return Date"
  Stats: null=0.0% | ~distinct=870
  Samples: 2022-03-01, 2024-01-29
`reason` (VARCHAR)
  Stats: null=0.0% | ~distinct=5 | avg_len=13
  Samples: changed_mind, not_as_described, wrong_item
`refund_amount` (DECIMAL(12,2)) → ~ "Refund Amount"
  Stats: null=0.0% | ~distinct=917 | range=[10.50, 409.90]
  Samples: 10.50, 409.90
`status` (VARCHAR)
  Stats: null=0.0% | ~distinct=3 | avg_len=8
  Samples: approved, rejected, pending

## main.sessions
Rows: 50,000 | Profiled: 2026-03-10

**Columns:**
`session_id` (INTEGER) → ~ "Session Id"
  Stats: null=0.0% | ~distinct=45,031 | range=[1, 50000]
  Samples: 1, 50000
`customer_id` (INTEGER) → ~ "Customer Id"
  Stats: null=30.0% | ~distinct=877 | range=[4, 1000]
  Samples: 4, 1000
`started_at` (TIMESTAMP) → ~ "Started At"
  Stats: null=0.0% | ~distinct=58,298
  Samples: 2022-01-01 08:20:00, 2023-11-26 18:40:00
`ended_at` (TIMESTAMP) → ~ "Ended At"
  Stats: null=0.0% | ~distinct=47,390
  Samples: 2022-01-01 08:25:01, 2023-11-26 18:48:20
`channel` (VARCHAR)
  Stats: null=0.0% | ~distinct=6 | avg_len=7
  Samples: direct, paid_search, email
`source` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=6
  Samples: google, meta, klaviyo
`medium` (VARCHAR)
  Stats: null=0.0% | ~distinct=3 | avg_len=5
  Samples: email, organic, cpc
`campaign` (VARCHAR)
  Stats: null=60.0% | ~distinct=2 | avg_len=13
  Samples: summer_sale, brand_awareness
`device_type` (VARCHAR) → ~ "Device Type"
  Stats: null=0.0% | ~distinct=3 | avg_len=6
  Samples: tablet, mobile, desktop
`converted` (BOOLEAN)
  Stats: null=0.0% | ~distinct=2

## main.warehouses
Rows: 6 | Profiled: 2026-03-10

**Columns:**
`warehouse_id` (INTEGER) → ~ "Warehouse Id"
  Stats: null=0.0% | ~distinct=6 | range=[1, 6]
  Samples: 1, 6
`name` (VARCHAR)
  Stats: null=0.0% | ~distinct=5 | avg_len=7
  Samples: Germany, US East, US West
`region` (VARCHAR)
  Stats: null=0.0% | ~distinct=3 | avg_len=4
  Samples: APAC, AMER, EMEA
`country` (VARCHAR)
  Stats: null=0.0% | ~distinct=5 | avg_len=3
  Samples: DEU, USA, AUS
`timezone` (VARCHAR)
  Stats: null=0.0% | ~distinct=5 | avg_len=15
  Samples: Asia/Singapore, America/Los_Angeles, America/New_York


> ℹ No documents loaded. Column semantics are inferred from names and profiles only. Upload a data dictionary or provide a documentation URL to improve accuracy.