---
name: sample
description: Use this skill at the start of pipeline development to pull a statistically representative sample into memory. Triggered automatically by the Pipeline Builder after receiving the Orchestrator's context handoff.
---

# Skill: Sample

Pull a representative sample of the source data into memory for pipeline development and testing. The sample must be small enough to iterate quickly but large enough to preserve the distribution of key dimensions.

**Cardinal rule: never scan a full table in a database.** Always estimate row count first, then compute a sample percent to retrieve approximately the target number of rows.

---

## Sample size targets

| Source size | Strategy |
|---|---|
| ≤ 10,000 rows | Use full dataset — no sampling needed |
| 10,001 – 1,000,000 rows | Sample to ~10,000 rows |
| > 1,000,000 rows | Sample to ~50,000 rows |

These are targets, not hard limits. Stratified sampling may pull slightly more rows to meet the per-stratum minimum.

**Memory ceiling**: keep the in-memory sample under ~500 MB. For very wide tables (100+ columns), estimate row size first (see "Row size estimation" below) and reduce the row target if needed.

---

## Sampling decision: random vs. stratified

### Use random sampling when:
- The analysis does not depend on specific categorical dimensions
- The data is relatively uniform (no rare but important segments)
- Speed matters more than segment coverage (e.g., initial exploration)

### Use stratified sampling when:
- The architecture plan groups or filters by specific dimensions (region, channel, product category, cohort)
- The data has high-cardinality or imbalanced categorical columns where random sampling would under-represent rare groups
- The analysis involves segment comparison, cohort analysis, or funnel breakdown

**Default to stratified** whenever the architecture plan specifies grouping dimensions. Random sampling is the fallback for purely exploratory work.

---

## How to choose strata columns

Pick 1–3 columns from the architecture plan's grouping dimensions. Prefer:
1. The primary dimension the user cares about (e.g., `region`, `channel`, `cohort_month`)
2. Any dimension that is highly imbalanced (a few values dominate)
3. Any dimension used in a WHERE filter (to ensure filtered-out values still appear in the sample for validation)

Do not stratify on high-cardinality columns (>50 unique values). If the primary dimension is high-cardinality (e.g., `customer_id`), stratify on a coarser grouping instead (e.g., `customer_segment`).

---

## Database sampling — avoid full table scans

### Step 1: Get the row count

Use metadata tables or cheap queries to get the total row count without scanning the table:

**BigQuery:**
```sql
SELECT row_count
FROM `project.dataset.INFORMATION_SCHEMA.TABLE_STORAGE`
WHERE table_name = 'my_table'
```

**Snowflake:**
```sql
SELECT row_count
FROM information_schema.tables
WHERE table_name = 'MY_TABLE' AND table_schema = 'MY_SCHEMA'
```

**PostgreSQL:**
```sql
SELECT reltuples::bigint AS row_count
FROM pg_class WHERE relname = 'my_table'
```

If metadata is unavailable, use `SELECT COUNT(*) FROM table` as a last resort — it's a full scan but reads no column data.

### Step 2: Compute sample percent

Most databases only support `TABLESAMPLE SYSTEM (N PERCENT)`, not a row count target. Convert your target row count to a percent:

```
sample_pct = (target_rows / total_rows) × 100
```

Round up slightly (add 10–20%) because `TABLESAMPLE SYSTEM` is approximate — it samples at the block level, not the row level, so actual counts will vary.

```sql
-- BigQuery: target ~10,000 rows from a 500,000-row table
-- sample_pct = (10000 / 500000) * 100 * 1.15 = 2.3%
SELECT * FROM `project.dataset.my_table`
TABLESAMPLE SYSTEM (2.3 PERCENT)
```

```sql
-- Snowflake: same logic
SELECT * FROM my_schema.my_table
TABLESAMPLE SYSTEM (2.3)
```

If the computed percent is ≥ 100%, skip sampling and query the full table.

### Step 3: Apply a LIMIT as a safety net

`TABLESAMPLE` is approximate. Always add a `LIMIT` to hard-cap the result and prevent unexpectedly large returns:

```sql
SELECT * FROM `project.dataset.my_table`
TABLESAMPLE SYSTEM (2.3 PERCENT)
LIMIT 12000  -- target + buffer
```

### Step 4: Add random ordering (for stratified only)

For stratified sampling, wrap the system sample in a window function to pick `min_n` rows per stratum:

```sql
WITH sampled AS (
    SELECT * FROM `project.dataset.my_table`
    TABLESAMPLE SYSTEM (5 PERCENT)  -- oversample to ensure coverage
),
numbered AS (
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY region, channel  -- strata columns
            ORDER BY RAND()
        ) AS _rn,
        COUNT(*) OVER (
            PARTITION BY region, channel
        ) AS _group_size
    FROM sampled
),
filtered AS (
    SELECT *
    FROM numbered
    WHERE _group_size <= 100       -- keep all rows if stratum is small
       OR _rn <= 100               -- otherwise keep min_n per stratum
)
SELECT * EXCEPT (_rn, _group_size)
FROM filtered
LIMIT 50000  -- hard cap
```

**Key parameters:**
- `min_n` (rows per stratum): default 100. Increase to 200–500 for cohort or funnel analysis where per-group row count matters.
- `row_limit` (hard cap): the target sample size from the table above.
- Oversample the `TABLESAMPLE` percent by 2–3× when stratifying to ensure rare strata have enough rows before the window function filters.

---

## Row size estimation

For very wide tables or tables with nested/JSON columns, estimate the average row size before deciding how many rows to pull:

```sql
-- BigQuery
WITH s AS (
    SELECT * FROM `project.dataset.my_table`
    TABLESAMPLE SYSTEM (1 PERCENT)
)
SELECT
    AVG(BYTE_LENGTH(TO_JSON_STRING(s))) AS avg_bytes_per_row,
    COUNT(*) AS sample_rows
FROM s
```

```sql
-- Snowflake (approximate)
SELECT
    AVG(LENGTH(TO_JSON(OBJECT_CONSTRUCT(*)))) AS avg_bytes_per_row,
    COUNT(*) AS sample_rows
FROM my_table
TABLESAMPLE SYSTEM (1)
```

Then compute: `max_rows = 500,000,000 / avg_bytes_per_row` (500 MB ceiling). Use the smaller of this and the target from the size table.

---

## File-based sources

For CSV, Parquet, or other file sources loaded into memory:

- **Small files (≤ 50 MB)**: load the full file
- **Large files (> 50 MB)**: use chunked reading. Read the first chunk to get the schema, then sample:
  - CSV: read with `skiprows` + random offset, or load full then `.sample(n=target)`
  - Parquet: use row group sampling (`read_parquet` with `filters` or row group indices)

For stratified sampling on files, load the full file into memory first (if it fits), then apply the pandas stratified sample:

```python
def stratified_sample(df, strat_cols, min_n=100, row_limit=50000):
    """Stratified sample: min_n rows per group, capped at row_limit total."""
    groups = df.groupby(strat_cols, observed=True)
    sampled = groups.apply(
        lambda g: g.sample(n=min(len(g), min_n), random_state=42)
    ).reset_index(drop=True)
    if len(sampled) > row_limit:
        sampled = sampled.sample(n=row_limit, random_state=42)
    return sampled
```

---

## After sampling

1. Optionally re-run the shared `glimpse` skill (`shared/glimpse/SKILL.md`) on the sample if it may differ materially from the Orchestrator's initial glimpse (e.g., stratified sampling changed distributions).
2. Record the sampling metadata to pass back in the result summary:
   - Source row count
   - Sample row count
   - Sampling method (random / stratified)
   - Strata columns used (if stratified)
   - `min_n` and `row_limit` applied
   - Any strata that had fewer than `min_n` rows (flagged for the Orchestrator)
