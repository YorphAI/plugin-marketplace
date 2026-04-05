# Context Summary — ecommerce_complex

# Enriched Profiles — Batch 1 of 1 (7 tables)


## main.customer_storefronts
Rows: 2,000 | Profiled: 2026-03-10

**Columns:**
`customer_id` (INTEGER) → ~ "Customer Id"
  Stats: null=0.0% | ~distinct=2,308 | range=[1, 2000]
  Samples: 1, 2000
`storefront_id` (INTEGER) → ~ "Storefront Id"
  Stats: null=0.0% | ~distinct=9 | range=[1, 8]
  Samples: 1, 8
`first_order_dt` (DATE) → ~ "First Order Dt"
  Stats: null=0.0% | ~distinct=1,026
  Samples: 2020-01-01, 2022-09-26

## main.d_customers
Rows: 2,000 | Profiled: 2026-03-10

**Columns:**
`d_cust_nbr` (INTEGER) → ~ "D Cust Nbr"
  Stats: null=0.0% | ~distinct=2,308 | range=[1, 2000]
  Samples: 1, 2000
`d_cust_name` (VARCHAR) → ~ "D Cust Name"
  Stats: null=0.0% | ~distinct=1,979 | avg_len=8
  Samples: Cust 10, Cust 19, Cust 34
`d_cust_email` (VARCHAR) → ~ "D Cust Email"
  Stats: null=0.0% | ~distinct=1,896 | avg_len=11
  Samples: c10@co.com, c12@co.com, c17@co.com
`d_region_cd` (VARCHAR) → ~ "D Region Cd"
  Stats: null=0.0% | ~distinct=3 | avg_len=2
  Samples: US, EU, AP
`d_seg_cd` (VARCHAR) → ~ "D Seg Cd"
  Stats: null=0.0% | ~distinct=3 | avg_len=3
  Samples: MM, SMB, ENT
`d_create_dt` (DATE) → ~ "D Create Dt"
  Stats: null=0.0% | ~distinct=1,469
  Samples: 2019-01-01, 2022-12-30

## main.d_products
Rows: 300 | Profiled: 2026-03-10

**Columns:**
`d_prod_id` (INTEGER) → ~ "D Prod Id"
  Stats: null=0.0% | ~distinct=339 | range=[1, 300]
  Samples: 1, 300
`d_prod_nm` (VARCHAR) → ~ "D Prod Nm"
  Stats: null=0.0% | ~distinct=321 | avg_len=8
  Samples: Prod 3, Prod 4, Prod 7
`d_cat_nm` (VARCHAR) → ~ "D Cat Nm"
  Stats: null=0.0% | ~distinct=4 | avg_len=7
  Samples: Home, Electronics, Books
`d_subcat_nm` (VARCHAR) → ~ "D Subcat Nm"
  Stats: null=0.0% | ~distinct=13 | avg_len=8
  Samples: Subcat 3, Subcat 5, Subcat 8
`d_unit_cost` (DECIMAL(10,2)) → ~ "D Unit Cost"
  Stats: null=0.0% | ~distinct=307 | range=[5.60, 154.70]
  Samples: 5.60, 154.70
`d_sell_price` (DECIMAL(10,2)) → ~ "D Sell Price"
  Stats: null=0.0% | ~distinct=183 | range=[10.00, 507.50]
  Samples: 10.00, 507.50
`d_active_flg` (VARCHAR) → ~ "D Active Flg"
  Stats: null=0.0% | ~distinct=2 | avg_len=1
  Samples: N, Y

## main.d_storefronts
Rows: 8 | Profiled: 2026-03-10

**Columns:**
`d_storefront_id` (INTEGER) → ~ "D Storefront Id"
  Stats: null=0.0% | ~distinct=9 | range=[1, 8]
  Samples: 1, 8
`d_store_nm` (VARCHAR) → ~ "D Store Nm"
  Stats: null=0.0% | ~distinct=9 | avg_len=9
  Samples: UK App, Wholesale, US Website
`d_channel_cd` (VARCHAR) → ~ "D Channel Cd"
  Stats: null=0.0% | ~distinct=4 | avg_len=4
  Samples: WEB, MOBILE, B2B
`d_country_cd` (VARCHAR) → ~ "D Country Cd"
  Stats: null=0.0% | ~distinct=3 | avg_len=3
  Samples: DEU, USA, GBR

## main.f_order_lines
Rows: 60,000 | Profiled: 2026-03-10

**Columns:**
`f_ord_id` (INTEGER) → ~ "F Ord Id"
  Stats: null=0.0% | ~distinct=18,226 | range=[1, 20000]
  Samples: 1, 20000
`f_line_nbr` (INTEGER) → ~ "F Line Nbr"
  Stats: null=0.0% | ~distinct=3 | range=[1, 3]
  Samples: 1, 3
`f_prod_id` (INTEGER) → ~ "F Prod Id"
  Stats: null=0.0% | ~distinct=339 | range=[1, 300]
  Samples: 1, 300
`f_qty` (INTEGER) → ~ "F Quantity"
  Stats: null=0.0% | ~distinct=9 | range=[1, 8]
  Samples: 1, 8
`f_unit_px` (DECIMAL(10,2)) → ~ "F Unit Px"
  Stats: null=0.0% | ~distinct=333 | range=[9.99, 308.99]
  Samples: 9.99, 308.99
`f_disc_pct` (DECIMAL(5,2)) → ~ "F Disc Pct"
  Stats: null=0.0% | ~distinct=37 | range=[0.00, 19.50]

## main.f_orders
Rows: 20,000 | Profiled: 2026-03-10

**Columns:**
`f_ord_id` (INTEGER) → ~ "F Ord Id"
  Stats: null=0.0% | ~distinct=18,226 | range=[1, 20000]
  Samples: 1, 20000
`f_cust_nbr` (INTEGER) → ~ "F Cust Nbr"
  Stats: null=0.0% | ~distinct=2,308 | range=[-1, 2000]
  Samples: -1, 2000
`f_storefront_id` (INTEGER) → ~ "F Storefront Id"
  Stats: null=0.0% | ~distinct=9 | range=[1, 8]
  Samples: 1, 8
`f_ord_dt` (DATE) → ~ "F Ord Dt"
  Stats: null=0.0% | ~distinct=1,654
  Samples: 2020-01-01, 2023-12-30
`f_ord_status_cd` (INTEGER) → ~ "F Ord Status Cd"
  Stats: null=0.0% | ~distinct=3 | range=[1, 3]
  Samples: 1, 3
`f_ord_revenue` (DECIMAL(12,2)) → ~ "F Ord Revenue"
  Stats: null=12.5% | ~distinct=10,240 | range=[10.10, 909.90]
  Samples: 10.10, 909.90
`f_ord_disc_amt` (DECIMAL(12,2)) → ~ "F Ord Disc Amount"
  Stats: null=0.0% | ~distinct=61 | range=[0.00, 118.00]
`f_ord_ship_amt` (DECIMAL(8,2)) → ~ "F Ord Ship Amount"
  Stats: null=0.0% | ~distinct=24 | range=[3.99, 15.99]
  Samples: 3.99, 15.99
`f_create_ts` (TIMESTAMP) → ~ "F Create Timestamp"
  Stats: null=0.0% | ~distinct=21,895
  Samples: 2020-01-01 00:10:00, 2020-05-18 22:20:00

## analytics.daily_order_summary
Rows: 46,720 | Profiled: 2026-03-10

**Columns:**
`report_date` (DATE) → ~ "Report Date"
  Stats: null=0.0% | ~distinct=1,654
  Samples: 2020-01-01, 2023-12-30
`category` (VARCHAR)
  Stats: null=0.0% | ~distinct=4 | avg_len=7
  Samples: Electronics, Home, Apparel
`storefront_id` (INTEGER) → ~ "Storefront Id"
  Stats: null=0.0% | ~distinct=9 | range=[1, 8]
  Samples: 1, 8
`total_orders` (INTEGER) → ~ "Total Orders"
  Stats: null=0.0% | ~distinct=45 | range=[1, 50]
  Samples: 1, 50
`total_revenue` (DECIMAL(14,2)) → ~ "Total Revenue"
  Stats: null=0.0% | ~distinct=49,158 | range=[500.00, 10499.70]
  Samples: 500.00, 10499.70
`avg_order_value` (DECIMAL(10,2)) → ~ "Avg Order Value"
  Stats: null=0.0% | ~distinct=2,601 | range=[50.00, 249.90]
  Samples: 50.00, 249.90
`units_sold` (INTEGER) → ~ "Units Sold"
  Stats: null=0.0% | ~distinct=221 | range=[10, 209]
  Samples: 10, 209


> ℹ No documents loaded. Column semantics are inferred from names and profiles only. Upload a data dictionary or provide a documentation URL to improve accuracy.