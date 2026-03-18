# Eval: Price/Volume/Mix Variance Analysis

## What This Tests

The ability to decompose revenue variance between actuals and budget into **price**, **volume**, and **mix** effects — without double-counting — across thousands of SKUs, multiple channels, currencies, and time periods.

This is one of the hardest problems in FP&A because:
- Actuals are at transaction grain; budgets are at category/channel/region grain
- Product IDs don't cleanly join across systems
- Discount formats are inconsistent
- Duplicate transactions must be detected without losing legitimate entries
- FX conversion is required for multi-currency transactions
- Budget phasing doesn't always sum to 100%

## Data Files

| File | Format | ~Rows | Description |
|------|--------|-------|-------------|
| `data/transactions.csv` | CSV | 30K | Individual sales transactions for FY2024 |
| `data/products.xlsx` | XLSX | 500+2K | Product catalog (Sheet 1) and price history (Sheet 2) |
| `data/channels.csv` | CSV | 50 | Channel hierarchy and commission rates |
| `data/budget_plan.xlsx` | XLSX | 200+40 | Annual budget targets (Sheet 1) and quarterly phasing (Sheet 2) |
| `data/fx_rates.csv` | CSV | 2K | Daily FX rates for 2024 |

## Dirty Data Design

These are the intentional data quality issues embedded in the files. A robust AI must detect and handle all of them.

### transactions.csv
- **Fuzzy product IDs**: ~5% of `product_id` values have trailing whitespace or case mismatches vs. the product catalog
- **Discount format inconsistency**: Some `discount_pct` values are decimals (0.15) while others are whole numbers (15)
- **Return flag encoding chaos**: `return_flag` uses "Y"/"N", "yes"/"no", 1/0, TRUE/FALSE, and some nulls
- **Duplicate transactions**: ~200 duplicate `txn_id` rows with slightly different amounts (simulates system double-posts)
- **Mixed date formats**: Some dates are MM/DD/YYYY, others YYYY-MM-DD
- **Negative quantities**: A handful of negative `qty` values that are NOT returns — they are data entry errors
- **Currency naming**: Currency column has "USD", "usd", "US Dollar" inconsistently

### products.xlsx — Catalog sheet
- **Orphan transactions**: Some products appear in transactions but not in catalog (discontinued/removed)
- **Inconsistent categories**: Category names have inconsistent capitalization ("Electronics" vs "electronics" vs "ELECTRONICS")

### products.xlsx — Price History sheet
- **Overlapping date ranges**: Some products have overlapping effective dates (ambiguous which price applies)
- **Bad cost data**: Some cost values are 0 or negative

### channels.csv
- **Orphan channel references**: Some `channel_id` values in transactions don't exist in this file

### budget_plan.xlsx — Annual sheet
- **Grain mismatch**: Budget is at category x channel_type x region grain (coarser than transactions)
- **Category name mismatch**: Budget category names don't exactly match product catalog categories

### budget_plan.xlsx — Quarterly sheet
- **Phasing doesn't sum to 100%**: Some categories have quarterly phasing percentages that don't add up to 100%

### fx_rates.csv
- Clean data — no intentional issues

## Expected Challenges for AI

1. Reconcile product IDs across systems with fuzzy matching
2. Normalize the discount format without double-discounting
3. Deduplicate transactions without losing legitimate similar entries
4. Choose the correct price from overlapping price history windows
5. Map fine-grained actuals to coarse-grained budgets for variance calculation
6. Decompose price/volume/mix effects without double-counting
7. Handle FX conversion with clean but gapped daily rates
8. Deal with budget phasing that doesn't sum to 100%
