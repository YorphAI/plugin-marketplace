# Context Summary — ecommerce_simple

# Enriched Profiles — Batch 1 of 1 (4 tables)


## main.customers
Rows: 500 | Profiled: 2026-03-10

**Columns:**
`customer_id` (INTEGER) → ~ "Customer Id"
  Stats: null=0.0% | ~distinct=520 | range=[1, 500]
  Samples: 1, 500
`name` (VARCHAR)
  Stats: null=0.0% | ~distinct=517 | avg_len=12
  Samples: Customer 13, Customer 36, Customer 95
`email` (VARCHAR)
  Stats: null=0.0% | ~distinct=473 | avg_len=19
  Samples: user27@example.com, user37@example.com, user38@example.com
`region` (VARCHAR)
  Stats: null=0.0% | ~distinct=3 | avg_len=4
  Samples: APAC, AMER, EMEA
`segment` (VARCHAR)
  Stats: null=0.0% | ~distinct=3 | avg_len=7
  Samples: mid_market, smb, enterprise
`created_at` (DATE) → ~ "Created At"
  Stats: null=0.0% | ~distinct=554
  Samples: 2021-01-02, 2022-05-16

## main.order_items
Rows: 15,000 | Profiled: 2026-03-10

**Columns:**
`order_id` (INTEGER) → ~ "Order Id"
  Stats: null=0.0% | ~distinct=5,618 | range=[1, 5000]
  Samples: 1, 5000
`line_item_id` (INTEGER) → ~ "Line Item Id"
  Stats: null=0.0% | ~distinct=3 | range=[1, 3]
  Samples: 1, 3
`product_id` (INTEGER) → ~ "Product Id"
  Stats: null=0.0% | ~distinct=119 | range=[1, 120]
  Samples: 1, 120
`quantity` (INTEGER)
  Stats: null=0.0% | ~distinct=5 | range=[1, 5]
  Samples: 1, 5
`unit_price` (DECIMAL(10,2)) → ~ "Unit Price"
  Stats: null=0.0% | ~distinct=205 | range=[9.99, 208.99]
  Samples: 9.99, 208.99
`discount_pct` (DECIMAL(5,2)) → ~ "Discount Pct"
  Stats: null=0.0% | ~distinct=27 | range=[0.00, 14.50]

## main.orders
Rows: 5,000 | Profiled: 2026-03-10

**Columns:**
`order_id` (INTEGER) → ~ "Order Id"
  Stats: null=0.0% | ~distinct=5,618 | range=[1, 5000]
  Samples: 1, 5000
`customer_id` (INTEGER) → ~ "Customer Id"
  Stats: null=0.0% | ~distinct=520 | range=[1, 500]
  Samples: 1, 500
`order_date` (DATE) → ~ "Order Date"
  Stats: null=0.0% | ~distinct=414
  Samples: 2023-01-01, 2023-12-31
`status` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=8
  Samples: pending, completed, refunded
`revenue` (DECIMAL(12,2))
  Stats: null=10.0% | ~distinct=5,648 | range=[15.20, 814.90]
  Samples: 15.20, 814.90
`discount` (DECIMAL(12,2))
  Stats: null=0.0% | ~distinct=28 | range=[0.00, 43.50]
`shipping_cost` (DECIMAL(8,2)) → ~ "Shipping Cost"
  Stats: null=0.0% | ~distinct=20 | range=[4.99, 14.49]
  Samples: 4.99, 14.49
`created_at` (TIMESTAMP) → ~ "Created At"
  Stats: null=0.0% | ~distinct=4,802
  Samples: 2023-01-01 00:30:00, 2023-04-15 05:00:00

## main.products
Rows: 120 | Profiled: 2026-03-10

**Columns:**
`product_id` (INTEGER) → ~ "Product Id"
  Stats: null=0.0% | ~distinct=119 | range=[1, 120]
  Samples: 1, 120
`name` (VARCHAR)
  Stats: null=0.0% | ~distinct=115 | avg_len=10
  Samples: Product 35, Product 38, Product 47
`category` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=7
  Samples: Home, Electronics, Books
`subcategory` (VARCHAR)
  Stats: null=0.0% | ~distinct=9 | avg_len=9
  Samples: Outerwear, Smartphones, T-Shirts
`price` (DECIMAL(10,2))
  Stats: null=0.0% | ~distinct=110 | range=[12.49, 504.99]
  Samples: 12.49, 504.99
`unit_cost` (DECIMAL(10,2)) → ~ "Unit Cost"
  Stats: null=0.0% | ~distinct=107 | range=[5.60, 202.40]
  Samples: 5.60, 202.40
`is_active` (BOOLEAN) → ~ "Is Active"
  Stats: null=0.0% | ~distinct=2


> ℹ No documents loaded. Column semantics are inferred from names and profiles only. Upload a data dictionary or provide a documentation URL to improve accuracy.