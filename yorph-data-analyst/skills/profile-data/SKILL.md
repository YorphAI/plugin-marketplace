---
name: profile-data
description: Produce a token-efficient statistical portrait of a dataset — schema, dtypes, null rates, distinct counts, numeric ranges, and sample values. Load this skill any time you need to understand the shape of data — during initial connection, after sampling, when the user adds new data mid-session, or whenever you need to verify what columns and values actually exist before making claims about the data. Used by both the Orchestrator and Pipeline Builder. If you're about to reference column names, data types, or value distributions, make sure you've glimpsed first.
---

# Skill: Glimpse

Two-step process: **Peek** then **Profile**. Output is always a plain string (CSV-formatted tables, not JSON) for token efficiency.

---

## Step 1: Peek

Look at actual values so the agent understands the semantics of each column. This replaces brute-force null-pattern detection — the LLM can see what "null" looks like in this dataset just by reading the values.

### Classify columns first

For each column, determine its role:
- **Categorical:** string/object columns, or numeric columns with very low cardinality (< ~20 unique values)
- **Numeric:** int/float columns with reasonable cardinality
- **Datetime:** columns that parse as dates/timestamps
- **ID/Key:** high-cardinality strings that look like identifiers (UUIDs, sequential IDs)
- **Free text:** long strings with high uniqueness (descriptions, notes, comments)

### Then peek at values based on role

**Categorical (nunique < 50):** Show all unique values with counts.

```python
# Template — adapt per column
for col in categorical_cols:
    if df[col].nunique(dropna=False) < 50:
        counts = df[col].value_counts(dropna=False).reset_index()
        counts.columns = ['value', 'count']
        print(f"\n=== {col} (all {df[col].nunique(dropna=False)} unique) ===")
        print(counts.to_csv(index=False))
```

**Categorical (nunique >= 50):** Show top 25 and bottom 25 by frequency. This reveals both the dominant values and the long tail (where data quality issues usually hide).

```python
for col in high_cardinality_categorical_cols:
    counts = df[col].value_counts(dropna=False)
    top = counts.head(25).reset_index()
    bottom = counts.tail(25).reset_index()
    top.columns = bottom.columns = ['value', 'count']
    print(f"\n=== {col} ({counts.shape[0]} unique) — top 25 ===")
    print(top.to_csv(index=False))
    print(f"--- {col} — bottom 25 ---")
    print(bottom.to_csv(index=False))
```

**Numeric:** Skip the peek (profiling handles these). But if a numeric column has suspiciously low cardinality, peek at it as categorical — it may be an encoded flag or category.

**Datetime:** Show min, max, and a 5-row sample of raw values to reveal the format.

**ID/Key:** Skip. Just note the column exists, its dtype, and its cardinality.

**Free text:** Show 5 sample values (first 100 chars each) so the agent understands the content.

### What to look for during peek

The agent should note (mentally or explicitly) during the peek:
- Null-like placeholders visible in the values (N/A, -, NULL, empty strings, etc.)
- Inconsistent representations of the same concept (US/USA/United States, Y/Yes/YES)
- Suspicious values in numeric-looking columns (currency symbols, percentages as strings)
- Columns that look related (start_date/end_date, amount/currency, first_name/last_name)

---

## Step 2: Profile

After peeking, compute a statistical summary. Output as a CSV-formatted table with one row per column.

### Core stats (always compute)

```python
import pandas as pd
import numpy as np

def profile(df: pd.DataFrame) -> str:
    rows = []
    total = len(df)
    for col in df.columns:
        s = df[col]
        n_null = s.isna().sum()
        n_unique = s.nunique(dropna=True)

        row = {
            'column': col,
            'dtype': str(s.dtype),
            'rows': total,
            'pct_null': round(n_null / max(total, 1), 4),
            'n_unique': n_unique,
            'pct_unique': round(n_unique / max(total - n_null, 1), 4),
        }

        # Numeric stats
        num = pd.to_numeric(s, errors='coerce')
        if num.notna().sum() > 0:
            row.update({
                'min': num.min(),
                'max': num.max(),
                'mean': round(num.mean(), 4),
                'p05': num.quantile(0.05),
                'p25': num.quantile(0.25),
                'p50': num.quantile(0.50),
                'p75': num.quantile(0.75),
                'p95': num.quantile(0.95),
            })

        rows.append(row)

    return pd.DataFrame(rows).to_csv(index=False)
```

### Flags (append as extra columns or as a separate warnings list)

Compute these after the core stats. Each is a boolean or short string:

| Flag | Condition | Why it matters |
|---|---|---|
| `high_null` | pct_null > 0.30 | May need imputation strategy or drop decision |
| `all_null` | pct_null == 1.0 | Column is empty — likely drop |
| `single_value` | n_unique == 1 | No variance — useless for analysis |
| `low_cardinality_numeric` | numeric dtype but n_unique < 20 | Probably a category or flag, not a measure |
| `high_cardinality_string` | string dtype and pct_unique > 0.90 | Probably an ID or free text, not a dimension |
| `potential_date` | string column where >80% of non-null values parse as a date | Should be cast to datetime |
| `negative_values` | numeric min < 0 in a column where negatives are unusual (amounts, counts) | May indicate refunds, corrections, or errors |
| `wide_range` | p95/p05 ratio > 1000 (for positive numerics) | Outliers or mixed units |

### Output format

The final glimpse output should be a single string the agent can read in context:

```
=== GLIMPSE: [dataset_name] ===
[total_rows] rows, [total_cols] columns

--- PROFILE ---
column,dtype,rows,pct_null,n_unique,pct_unique,min,max,mean,p05,p25,p50,p75,p95,flags
order_id,int64,10000,0.0,10000,1.0,1,10000,5000.5,500,2500,5000,7500,9500,high_cardinality_string
amount,float64,10000,0.02,847,0.085,−50.0,9999.99,245.32,12.5,85.0,195.0,310.0,650.0,negative_values
status,object,10000,0.0,5,0.0005,,,,,,,,,,low_cardinality
...

--- PEEK: status (5 unique) ---
value,count
completed,6500
pending,2100
cancelled,800
refunded,500
NULL,100

--- PEEK: category (128 unique — top 25) ---
value,count
Electronics,1200
Clothing,980
...

--- PEEK: category (bottom 25) ---
value,count
Artisanal Cheese,2
Vintage Maps,1
...
```

---

## When to use each step

| Context | Step 1 (Peek) | Step 2 (Profile) |
|---|---|---|
| Orchestrator during `connect-data-source` | Yes — understand the data | Yes — full profile |
| Pipeline Builder during `sample-data` | Optional — if sample differs materially from glimpse | Yes — re-profile the sample |
| Pipeline Builder after `produce-pipeline` | No | Yes — profile transformed output for validation |

---

## Principles

- The peek is for the agent's understanding. It replaces exhaustive pattern-matching with LLM judgment.
- The profile is for structured decision-making. It gives the architecture and validation skills hard numbers to work with.
- Always output as CSV, never JSON. CSV is 2-3x more token-efficient for tabular data.
- The glimpse output is the primary input to the design-transformation-architecture skill. A good glimpse = a good pipeline plan.
