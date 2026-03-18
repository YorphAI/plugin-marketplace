# Scenario Brief: ecommerce_complex

**Domain:** ecommerce | **Complexity:** complex

A legacy e-commerce schema with two schemas (PUBLIC + ANALYTICS), old-style column naming (f_ord_id, d_cust_nbr), a pre-aggregated daily summary table coexisting with atomic fact tables, a genuine many-to-many between customers and storefronts, and multiple ambiguous join paths. Stress-tests the Join Validator and Grain Detector.

---

## Tables

- **f_orders**: Fact: order headers. Legacy 'f_' prefix schema.
- **f_order_lines**: Fact: order line items.
- **d_customers**: Dimension: customer master.
- **d_products**: Dimension: product catalog.
- **d_storefronts**: Dimension: retail storefronts (online channels).
- **customer_storefronts**: Bridge: M:M customers ↔ storefronts (multi-storefront accounts).
- **analytics.daily_order_summary**: Pre-aggregated daily summary by category. NOT for row-level joins.

---

## Data Quality Issues (deliberately injected)

These are known issues the agent MUST discover and surface:

### f_orders.f_ord_status_cd — `schema_drift`

Legacy 'f_' prefix columns use status codes (1=completed, 2=pending, 3=cancelled) while the newer orders table uses string labels. The agent must recognise these are the same concept.

**Prevalence:** always

### analytics.daily_order_summary.total_revenue — `mixed_grain`

daily_order_summary is pre-aggregated (one row per day × category). It must NOT be joined directly to atomic order facts — the grains are incompatible.

**Prevalence:** always

### customer_storefronts.customer_id — `ambiguous_key`

customer_storefronts is a genuine M:M bridge. Joining orders → customer_storefronts without aggregating will fan-out order metrics.

**Prevalence:** always

### f_orders.f_cust_nbr — `encoded_null`

Guest orders have f_cust_nbr = -1 (not a real customer). Filter required.

**Prevalence:** 8% of rows

---

## Expected Joins (ground truth)

- `f_orders` → `d_customers` on `f_cust_nbr` [many:1]
- `f_order_lines` → `f_orders` on `f_ord_id` [many:1]
- `f_order_lines` → `d_products` on `f_prod_id` [many:1]
- `f_orders` → `d_storefronts` on `f_storefront_id` [many:1]
- `customer_storefronts` → `d_customers` on `customer_id` [many:many] ⚠ fan_out trap

---

## Expected Measures (ground truth)

- **Gross Revenue**: SUM(f_orders.f_ord_revenue) WHERE f_ord_status_cd = 1
- **Order Count**: COUNT(f_orders.f_ord_id) WHERE f_ord_status_cd = 1, f_cust_nbr != -1

---

## Expected Business Rules

- f_ord_status_cd = 1 means 'completed'. Use this — not string labels — for revenue filters.
- f_cust_nbr = -1 are guest orders — exclude from customer-segmented metrics.
- analytics.daily_order_summary is pre-aggregated — never join to atomic order facts.
