# Eval: Budget vs. Actual — Sales & COGS by Customer

## What This Tests

Given a full fiscal year of budgeted and actual sales and COGS data at the customer × product × month grain, reconcile budget to actual and explain the variance. The key challenge is that **the budget and actuals don't cover the same customers** — some customers were budgeted but never materialized, others appeared mid-year with no budget, and a few have partial budget coverage.

## Data Files

| File | Rows | Description |
|------|------|-------------|
| `data/budget.csv` | ~840 | Monthly budgeted units, price, revenue, COGS, and gross profit by customer × product |
| `data/actuals.csv` | ~900 | Monthly actual units, price, revenue, COGS, and gross profit by customer × product |
| `data/customers.csv` | 38 | Customer master with segment, products, and budget gap annotations |

## Budget Gap Types

The intentional mismatches between budget and actuals are documented in `customers.csv`:

| Gap Type | Count | Description |
|----------|-------|-------------|
| `budgeted_no_actuals` | 3 | Customer was in the annual plan but the deal fell through. Budget revenue never materialized — shows as unfavorable variance. |
| `unbudgeted_new_win` | 5 | Customer was won mid-year and has no budget at all. All their revenue is "unbudgeted" — favorable variance that the AI should call out separately. |
| `added_mid_year` | 2 | Customer exists in actuals all year but was only added to the budget partway through (e.g., month 4+). Earlier months have actuals but no budget. |
| `dropped_mid_year` | 1 | Customer was in the budget through a certain month, then dropped. Later months have actuals but no budget. |
| `sporadic_gaps` | 1 | Budget exists for most months but is missing for 3-4 specific months (forecast wasn't updated consistently). |
| `none` | 26 | Full budget and actuals for all 12 months. |

## Variance Drivers

### Revenue Variance
- **Volume variance**: Actual demand differed from plan (±15-25% noise per customer-product-month)
- **Price variance**: Enterprise customers negotiated 3-8% discounts vs. list price; Mid-Market 0-4%. SKU-D gets a slight premium in Nov-Dec peak.
- **Customer variance**: $721K of budgeted revenue from 3 customers that never materialized, partially offset by $1.4M from 5 unbudgeted new wins

### COGS Variance
- **H2 input cost inflation**: COGS runs ~5% above plan from July onward across all products
- **SKU-D supply disruption**: 15% COGS spike in Q3 (Jul-Sep) due to supplier issues
- **Random supplier variance**: ±3% month-to-month noise

### Products (6 SKUs)

| Product | Avg Price | COGS % | Seasonality | Notes |
|---------|----------|--------|-------------|-------|
| SKU-A | $1,200 | 55% | Flat | Core product, steady |
| SKU-B | $800 | 60% | H2-heavy | Back-half loaded |
| SKU-C | $3,500 | 45% | Flat | Premium, highest margin |
| SKU-D | $450 | 65% | Q4 spike | Consumable, Q3 supply issue |
| SKU-E | $2,000 | 50% | Front-loaded | Project-based, H1 heavy |
| SKU-F | $600 | 70% | Flat | Low margin commodity |

## Expected Challenges for AI

1. **Joining budget to actuals**: The datasets have different customer × product × month coverage. A naive left join in either direction loses data.
2. **Classifying variance**: Revenue variance must be decomposed into price, volume, and customer-level (budgeted-but-lost, unbudgeted-new-win) components.
3. **Handling missing budget rows**: For months/customers with actuals but no budget, the AI must decide whether to treat this as "100% favorable variance" or separate it as unbudgeted revenue. The latter is correct.
4. **COGS story**: The H2 inflation and SKU-D supply disruption are the real stories — the AI should identify these patterns rather than just reporting aggregate COGS variance.
5. **Gross margin bridge**: Budget GP margin was 47.0%, actual was 45.7%. The AI should explain this 130bp compression — it's driven by the mix of COGS inflation, price concessions, and customer mix shift (new wins tend to be smaller/lower-margin).

## Key Metrics (seed=42)

| Metric | Budget | Actual | Variance |
|--------|--------|--------|----------|
| Revenue | $23.2M | $22.9M | -1.3% |
| COGS | $12.3M | $12.4M | +1.1% |
| Gross Profit | $10.9M | $10.5M | -4.1% |
| GP Margin | 47.0% | 45.7% | -130bps |
