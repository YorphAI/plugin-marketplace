---
name: skew-analysis
description: Use this skill when a column has skew_detected=True in its profile and you need to decide the correct aggregation type, determine if outliers are data quality issues, choose whether to recommend a filtered measure, or document the distribution shape in the glossary.
---

# Skill: Skew Analysis

When a column is flagged with `skew_detected = True` in profiles, run these targeted queries on the fly using `execute_validation_sql` to get accurate distribution stats. Choose the cheapest query that answers your question.

---

## 1. Tail sampling (cheapest — scans ~5% of rows)

Use when you need accurate tail statistics (P99, tail average, tail count). Only reads rows above the P95 value from profiling.

```sql
SELECT
  COUNT(*)                   AS tail_count,
  AVG({column})              AS tail_avg,
  MIN({column})              AS tail_min,
  MAX({column})              AS tail_max,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {column}) AS tail_median
FROM {schema}.{table}
WHERE {column} > {p95_value_from_profile}
```

**When to use:** You want to understand what the top 5% looks like — are they legitimate high-value transactions, or data quality issues?

---

## 2. Moment-based skewness (cheap — simple aggregation, no sort)

Use when you need the actual skewness coefficient to quantify how skewed the distribution is.

```sql
SELECT
  COUNT({column})                                         AS n,
  AVG(CAST({column} AS FLOAT))                            AS mean,
  STDDEV(CAST({column} AS FLOAT))                         AS stddev,
  (SUM(POWER(CAST({column} AS FLOAT) - sub.mean, 3)) / COUNT({column}))
    / POWER(STDDEV(CAST({column} AS FLOAT)), 3)           AS skewness_coefficient
FROM {schema}.{table} TABLESAMPLE BERNOULLI(25),
     (SELECT AVG(CAST({column} AS FLOAT)) AS mean FROM {schema}.{table} TABLESAMPLE BERNOULLI(10)) sub
WHERE {column} IS NOT NULL
```

- **Skewness ≈ 0**: symmetric distribution
- **Skewness > 1**: right-skewed (common for revenue, amounts — long tail of high values)
- **Skewness < -1**: left-skewed (uncommon in business data)
- **|Skewness| > 2**: highly skewed — percentile-based measures may be misleading

**Simplified version** (works on most warehouses):
```sql
SELECT
  COUNT({column}) AS n,
  AVG(CAST({column} AS FLOAT)) AS mean,
  STDDEV(CAST({column} AS FLOAT)) AS stddev,
  -- Approximate skewness: 3 * (mean - median) / stddev
  3.0 * (AVG(CAST({column} AS FLOAT)) - PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {column}))
      / NULLIF(STDDEV(CAST({column} AS FLOAT)), 0) AS approx_skewness
FROM {schema}.{table} TABLESAMPLE BERNOULLI(25)
WHERE {column} IS NOT NULL
```

---

## 3. Histogram (cheap — GROUP BY, no sort)

Use when you need to understand the full distribution shape — where values concentrate, whether there are gaps or clusters.

```sql
SELECT
  WIDTH_BUCKET({column}, {min_value}, {max_value}, 20) AS bucket,
  COUNT(*)                                              AS row_count,
  MIN({column})                                         AS bucket_min,
  MAX({column})                                         AS bucket_max
FROM {schema}.{table}
WHERE {column} IS NOT NULL
  AND {column} BETWEEN {min_value} AND {max_value}
GROUP BY WIDTH_BUCKET({column}, {min_value}, {max_value}, 20)
ORDER BY bucket
```

Use `{min_value}` and `{max_value}` from the profiled `min_numeric` and `max_numeric`. If the distribution is extremely wide (max/min > 1000), consider using log-scale buckets or narrowing to P05–P95 range:

```sql
-- Narrowed histogram (P05 to P95 range, excludes outliers)
WHERE {column} BETWEEN {p05_value} AND {p95_value}
```

---

## 4. Top-N value frequencies (for low-cardinality skew)

Use when a numeric column has a few dominant values (e.g., 80% of orders are $0.00 or $9.99).

```sql
SELECT
  {column}        AS value,
  COUNT(*)        AS frequency,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 2) AS pct_of_total
FROM {schema}.{table}
WHERE {column} IS NOT NULL
GROUP BY {column}
ORDER BY frequency DESC
LIMIT 10
```

---

## Decision guide

| Question | Use query | Cost |
|----------|-----------|------|
| "What does the top 5% look like?" | Tail sampling (#1) | Very low |
| "How skewed is this exactly?" | Moment-based (#2) | Low |
| "What's the full distribution shape?" | Histogram (#3) | Low |
| "Are there dominant values?" | Top-N frequencies (#4) | Low |

**All queries avoid full table scans.** Tail sampling reads ~5% of rows, moment-based uses BERNOULLI(25%), histogram uses GROUP BY (no sort), top-N uses GROUP BY + LIMIT.

---

## When to trigger

Run skew analysis when you encounter a measure candidate column with `skew_detected = True` **and** you need to:
- Decide the correct aggregation (SUM vs MEDIAN vs trimmed mean)
- Determine if outliers are data quality issues or legitimate values
- Choose whether to recommend a filtered measure (e.g., "revenue excluding outliers > $X")
- Document the distribution shape in the glossary
