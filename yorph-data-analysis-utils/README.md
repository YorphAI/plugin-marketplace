# Yorph Data Analysis Agent Plugin

Data engineering and analysis specialization skills for Claude. Covers synthetic data generation, multi-approach analysis with a persistent semantic layer, and semantic feature extraction for messy text fields.

## Skills

### `data-simulator`

Generate realistic, seeded, analytically challenging synthetic datasets from a plain-English description.

**What it produces:**
- A reproducible Python script (pandas + numpy, no other dependencies)
- A challenge manifest documenting every trap planted in the data

**Challenge types it can plant:** nulls and null codes, statistical outliers, impossible values, schema/structural issues, temporal traps (partial periods, timezone mix, date format inconsistency), business logic traps, relational traps across multiple tables

**Trigger phrases:**
- "generate test data for X"
- "simulate a dataset"
- "I want to test my pipeline"
- "give me a challenging dataset"
- "generate data with messy/realistic problems"

### `data-analysis-multi-approach`

Run multiple analytical approaches in parallel before committing to a single answer. Surfaces divergences — places where reasonable choices produce materially different results — and maintains a persistent `semantic_layer.md` with confirmed decisions.

**Dimensions it explores:** metric definitions (gross vs net, null handling, time windows), aggregation methods (mean vs median, sum vs count), filter choices (outlier thresholds, segment scope), join strategies (key selection, join type, duplicate handling)

**Trigger phrases:**
- "analyze this CSV / dataset"
- "calculate revenue / retention / churn"
- "what are the trends in this data"
- "build a pipeline for Y"
- "define my semantic layer"

### `semantic-join`

Extract structured features from messy text fields — canonical names, categories, parsed values — then use those features for matching, joining, deduplication, and enrichment. Avoids per-row LLM calls by doing cheap extraction once per record, then using deterministic comparisons downstream.

**What it handles:** spelling correction, canonical normalization, category inference, parsed field extraction, cross-dataset matching, deduplication

**Trigger phrases:**
- "match records across these two datasets"
- "find duplicates in this list"
- "add a category column"
- "normalize / fix spelling in this column"
- "what's the average price of chocolate" (where rows say "dark chocolate", "milk choc", etc.)

## Workflow

### Simulate → Analyze

```
1. data-simulator    → generates a challenging CSV + challenge manifest
2. data-analysis-multi-approach → analyzes the CSV, surfaces divergences
3. (optional) yorph-evals → judges how well different analyst skills handled it
```

### Enrich → Analyze

```
1. semantic-join     → extracts structured columns from messy text
2. data-analysis-multi-approach → analyzes the now-clean, enriched data
```
