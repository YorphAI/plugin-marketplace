# Scenario Brief: ecommerce_medium

**Domain:** ecommerce | **Complexity:** medium

Full e-commerce stack: orders, returns, promotions, inventory, sessions, and page views. Includes a fan-out trap (sessions → page_views, both linking to customers/orders), encoded nulls on anonymous sessions, and negative inventory values.

---

## Tables

- **orders**: Order headers. One row per customer order.
- **order_items**: Line items within orders. One row per product per order.
- **customers**: Customer accounts.
- **products**: Product catalog.
- **returns**: Return requests. One row per return (may cover partial order).
- **promotions**: Promo codes and discount campaigns.
- **order_promotions**: Junction table linking orders to applied promotions.
- **inventory**: Daily inventory snapshot per product per warehouse.
- **warehouses**: Fulfilment warehouse locations.
- **sessions**: Web/app sessions. Anonymous sessions have NULL customer_id.
- **page_views**: Individual page view events within sessions.

---

## Data Quality Issues (deliberately injected)

These are known issues the agent MUST discover and surface:

### sessions.customer_id — `high_null`

30% of sessions are anonymous (customer_id NULL before login).

**Prevalence:** 30% of rows

### sessions.channel — `encoded_null`

'(none)' and 'direct' are often encoded nulls from analytics tools.

**Prevalence:** 15% of rows

### inventory.quantity_on_hand — `negative_values`

Negative inventory occurs when returns are processed before stock is updated.

**Prevalence:** 3% of rows

### page_views.session_id — `fan_out_trap`

Joining orders → sessions → page_views inflates order-level metrics because one session can have many page views. The Join Validator should flag this as a fan-out.

**Prevalence:** always

### returns.refund_amount — `duplicate_metric`

returns.refund_amount and orders.revenue are both measures of money — an analyst might accidentally double-count by summing both.

**Prevalence:** always

---

## Expected Joins (ground truth)

- `orders` → `customers` on `customer_id` [many:1]
- `order_items` → `orders` on `order_id` [many:1]
- `order_items` → `products` on `product_id` [many:1]
- `returns` → `orders` on `order_id` [many:1]
- `order_promotions` → `orders` on `order_id` [many:1]
- `order_promotions` → `promotions` on `promo_id` [many:1]
- `inventory` → `products` on `product_id` [many:1]
- `inventory` → `warehouses` on `warehouse_id` [many:1]
- `sessions` → `customers` on `customer_id` [many:1]
- `page_views` → `sessions` on `session_id` [many:1] ⚠ fan_out trap

---

## Expected Measures (ground truth)

- **Gross Revenue**: SUM(orders.revenue) WHERE status = 'completed'
- **Net Revenue**: SUM(orders.revenue) WHERE status = 'completed'
- **Refunds**: SUM(returns.refund_amount) WHERE status = 'approved'
- **Orders Placed**: COUNT(orders.order_id) WHERE status != 'N/A'
- **Return Rate**: RATIO(returns.*)
- **Units Sold**: SUM(order_items.quantity)
- **Sessions**: COUNT(sessions.session_id)
- **Conversion Rate**: RATIO(sessions.*)
- **Inventory on Hand**: SUM(inventory.quantity_on_hand) WHERE quantity_on_hand > 0

---

## Expected Business Rules

- Net Revenue = Gross Revenue - Refunds (only include approved returns).
- Conversion Rate = orders with status='completed' / total sessions.
- Negative inventory values exist — always filter quantity_on_hand > 0 for reporting.
- Orders with status='N/A' were never confirmed — exclude from all revenue metrics.
- Page views MUST NOT be joined directly to orders — use session as the bridge.
