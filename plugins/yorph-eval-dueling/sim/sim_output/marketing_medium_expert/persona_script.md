# Persona Script: Data Architect (expert)

> **Scenario:** marketing_medium  
> **Domain:** marketing  
> **Complexity:** medium

---

## Who this persona is

A senior data architect at the company. Knows the schema well — has been working with this data for 2+ years. Has a data dictionary documenting business names, metric formulas, and known quirks. Uses precise technical language. Will catch incorrect grain assumptions and push back on metrics that don't match documented formulas.

## Behavioural flags
- Uploads data dictionary: Yes
- Challenges join recommendations: Yes
- Tries to skip clarifying questions: No
- Preferred recommendation: Balanced

---

## Conversation Script

Paste each turn into Claude **in order**. Wait for the full response before sending the next.

### Turn 1 — Connect to simulation warehouse
**Phase:** `connect`

```
Let's get started. Please connect to the simulation warehouse and profile all schemas.
```

> **Watch for:** Agent should call connect_warehouse(warehouse_type='simulation') then run_profiler() automatically.

### Turn 2 — Answer clarifying questions with full context
**Phase:** `clarify`

```
This is a marketing data warehouse. The primary business process is Full attribution stack: campaigns, spend, UTM sessions, touchpoints, and conversions. Key challenge: touchpoints is a multi-touch attribution table with one row per channel per conversion — joining it directly to conversions fans out revenue. The agent must detect this and recommend aggregating touchpoints first..

Fact tables: campaigns. Dimension tables: customers, products.

Key business rules:
- Revenue excludes orders with status = 'N/A' or 'refunded'
- order_items.unit_price is the price at order time — may differ from products.price due to promotions
- 'N/A' in the status column is an encoded null meaning the order was attempted but never confirmed

I'll upload our data dictionary now.
```

> **Watch for:** Agent should pick up business_rules and the encoded null pattern. Watch for whether it properly notes that status='N/A' is encoded null, not a valid status value.

### Turn 3 — Challenge a specific join assumption
**Phase:** `build`

```
Before you finalise the join recommendations: I want to make sure you've validated the join between order_items and products on product_id. Can you run a query to check the FK match rate? We've had issues with discontinued products not being in the catalog.
```

> **Watch for:** Agent (Join Validator) should call execute_validation_sql with a query checking distinct product_ids in order_items vs products. If match rate < 100%, it should flag discontinued products as an open question.

### Turn 4 — Select recommendation and flag an issue
**Phase:** `review`

```
I want Recommendation 3 (Balanced). But I have a concern: the Comprehensive set includes 'avg_order_value' as a SUM-based derived metric. AVG is non-additive — it can't be correctly rolled up across dimensions. Can you confirm whether the Balanced recommendation marks avg_order_value as non_additive?
```

> **Watch for:** Agent should confirm avg_order_value has additivity='non_additive'. This tests whether the Measure Builder correctly flagged additivity.

### Turn 5 — Request dbt format with specific filename
**Phase:** `save`

```
Please save the Balanced recommendation in dbt format. Use filename 'production_semantic_layer'. Also confirm the companion readme includes the business rules we discussed about status='N/A' and revenue exclusion.
```

> **Watch for:** Agent should call save_output with format='dbt', recommendation_number=3, filename='production_semantic_layer'. Readme should include the N/A business rule.

---

## Data Dictionary to Upload

Save the following as `data_dictionary.csv` and upload it when the agent asks for documents:

```csv
table_name,column_name,business_name,description,pii,valid_values,metric_formula
orders,order_id,Order ID,Unique order identifier,false,,
orders,revenue,Gross Revenue,"Pre-tax order value in USD. Excludes shipping and taxes. NULL for cancelled/N/A orders.",false,,SUM(revenue) WHERE status NOT IN ('N/A','refunded')
orders,status,Order Status,"Fulfilment status. 'N/A' = order was attempted but not confirmed.",false,"completed,pending,refunded,N/A",
orders,customer_id,Customer ID,FK to customers.customer_id,false,,
customers,customer_id,Customer ID,Unique customer identifier,false,,
customers,email,Email Address,Customer email,true,,
order_items,order_id,Order ID,FK to orders.order_id,false,,
order_items,quantity,Quantity,Units ordered,false,,SUM(quantity)
order_items,unit_price,Unit Price,"Price at time of order. May differ from products.price if promo applied.",false,,
```
