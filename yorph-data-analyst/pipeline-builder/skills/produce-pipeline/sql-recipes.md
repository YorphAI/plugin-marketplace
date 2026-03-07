# SQL Recipes

Reference implementations for analytical methodologies. Use as templates when building Python/pandas pipelines and when translating to SQL for in-database execution via `scale-execution`.

---

## PVM Variance Bridge

```sql
WITH actuals_staged AS (
    SELECT product_id, customer_id,
           SUM(qty) AS act_qty,
           SUM(rev) / NULLIF(SUM(qty), 0) AS act_price
    FROM fact_actuals WHERE period = '2024-Q1'
    GROUP BY 1, 2
),
budget_staged AS (
    SELECT product_id, customer_id,
           SUM(qty) AS bud_qty,
           SUM(rev) / NULLIF(SUM(qty), 0) AS bud_price
    FROM fact_budget WHERE period = '2024-Q1'
    GROUP BY 1, 2
),
comparison_base AS (
    SELECT
        COALESCE(a.product_id, b.product_id) AS product_id,
        a.act_qty, a.act_price,
        b.bud_qty, b.bud_price,
        SUM(a.act_qty) OVER() AS total_act_qty,
        SUM(b.bud_qty) OVER() AS total_bud_qty
    FROM actuals_staged a
    FULL JOIN budget_staged b
        ON a.product_id = b.product_id AND a.customer_id = b.customer_id
)
SELECT
    product_id,
    (act_price - bud_price) * act_qty AS price_effect,
    (act_qty - bud_qty) * bud_price AS volume_mix_total,
    CASE WHEN bud_qty IS NULL THEN (act_qty * act_price) ELSE 0 END AS new_business_effect
FROM comparison_base;
```

---

## Cohort Retention Curve

```sql
WITH cohort_start AS (
    SELECT customer_id, MIN(event_date) AS first_date
    FROM transactions
    GROUP BY 1
)
SELECT
    period,
    cohort_size,
    retained_users,
    retained_users * 1.0 / cohort_size AS pct_retained
FROM (
    SELECT
        DATE_PART('year', AGE(t.event_date, c.first_date)) AS period,
        COUNT(DISTINCT c.customer_id) AS retained_users,
        FIRST_VALUE(COUNT(DISTINCT c.customer_id)) OVER (ORDER BY period) AS cohort_size
    FROM cohort_start c
    JOIN transactions t ON c.customer_id = t.customer_id
    GROUP BY 1
) aa;
```

### Cumulative Revenue for NRR

```sql
SELECT
    cohort_month,
    period,
    SUM(monthly_amount) OVER (PARTITION BY cohort_month ORDER BY period) AS cumulative_revenue
FROM revenue_table;
```

---

## Difference-in-Differences

```sql
WITH tagged AS (
    SELECT
        product_id, week, outcome,
        CASE WHEN is_treated = 1 THEN 'T' ELSE 'C' END AS grp,
        CASE WHEN week >= DATE '2025-10-01' THEN 'post' ELSE 'pre' END AS period
    FROM fact_table
),
means AS (
    SELECT grp, period, AVG(outcome) AS y_bar
    FROM tagged
    GROUP BY 1, 2
),
pivot AS (
    SELECT
        MAX(CASE WHEN grp='T' AND period='post' THEN y_bar END) AS t_post,
        MAX(CASE WHEN grp='T' AND period='pre'  THEN y_bar END) AS t_pre,
        MAX(CASE WHEN grp='C' AND period='post' THEN y_bar END) AS c_post,
        MAX(CASE WHEN grp='C' AND period='pre'  THEN y_bar END) AS c_pre
    FROM means
)
SELECT
    t_post - t_pre AS treated_change,
    c_post - c_pre AS control_change,
    (t_post - t_pre) - (c_post - c_pre) AS did_effect
FROM pivot;
```

---

## Event Study (Parallel Trends Check)

```sql
WITH e AS (
    SELECT
        product_id, is_treated,
        DATE_DIFF(week, DATE '2025-10-01', WEEK) AS rel_wk,
        outcome
    FROM fact_table
    WHERE week BETWEEN DATE '2025-07-01' AND DATE '2026-01-01'
)
SELECT
    rel_wk,
    AVG(CASE WHEN is_treated=1 THEN outcome END) AS treated_avg,
    AVG(CASE WHEN is_treated=0 THEN outcome END) AS control_avg
FROM e
GROUP BY 1
ORDER BY 1;
```

---

## Simple OLS Regression

```sql
WITH stats AS (
    SELECT AVG(x) AS xbar, AVG(y) AS ybar
    FROM data
),
sums AS (
    SELECT
        SUM((d.x - s.xbar) * (d.y - s.ybar)) AS sxy,
        SUM((d.x - s.xbar) * (d.x - s.xbar)) AS sxx
    FROM data d
    CROSS JOIN stats s
)
SELECT
    sxy / NULLIF(sxx, 0) AS slope_b
FROM sums;
```

---

## Panel Fixed Effects (Demeaning)

```sql
WITH pm AS (
    SELECT product_id, AVG(outcome) AS ybar
    FROM fact_table
    GROUP BY 1
),
demeaned AS (
    SELECT f.*, (f.outcome - pm.ybar) AS y_within
    FROM fact_table f
    JOIN pm USING (product_id)
)
SELECT * FROM demeaned;
```

---

## Time-Series Features: Lag + Moving Average

```sql
SELECT
    product_id, week, outcome,
    LAG(outcome, 1) OVER (PARTITION BY product_id ORDER BY week) AS y_lag1,
    AVG(outcome) OVER (
        PARTITION BY product_id
        ORDER BY week
        ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
    ) AS ma3_prev
FROM fact_table;
```
