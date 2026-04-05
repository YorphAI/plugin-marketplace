# Scenario Brief: ecommerce_simple

**Domain:** ecommerce | **Complexity:** simple

A minimal e-commerce schema: orders, line items, customers, products. Clean FK relationships, obvious measures. Good for baseline smoke tests.

---

## Tables

- **orders**: Purchase orders placed by customers. One row per order header.
- **order_items**: Individual line items within each order. One row per product per order.
- **customers**: Registered customers. One row per customer account.
- **products**: Product catalog. One row per SKU.

---

## Data Quality Issues (deliberately injected)

These are known issues the agent MUST discover and surface:

### orders.status — `encoded_null`

10% of status values are 'N/A' — orders that were never confirmed.

**Prevalence:** 10% of rows

### orders.revenue — `high_null`

Revenue is NULL for cancelled orders (status='N/A').

**Prevalence:** 10% of rows

---

## Expected Joins (ground truth)

- `orders` → `customers` on `customer_id` [many:1]
- `order_items` → `orders` on `order_id` [many:1]
- `order_items` → `products` on `product_id` [many:1]

---

## Expected Measures (ground truth)

- **Total Revenue**: SUM(orders.revenue) WHERE status != 'N/A'
- **Order Count**: COUNT(orders.order_id) WHERE status != 'N/A'
- **Avg Order Value**: AVG(orders.revenue) WHERE status != 'N/A'
- **Units Sold**: SUM(order_items.quantity)
- **Unique Customers**: COUNT_DISTINCT(orders.customer_id)

---

## Expected Business Rules

- Revenue is NULL for orders where status = 'N/A' — treat as cancelled/voided.
- order_items.unit_price may differ from products.price (promotions applied at order time).
