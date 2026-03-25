# Eval: B2B Quarterly Financial Attribution

## What This Tests

Given two quarters of B2B SaaS revenue and cost data, explain **what drove the change** from Q3 to Q4 2024. Produce a waterfall chart breaking down the contribution of each factor with the analysis behind it.

## Attribution Factors

- **Price effect**: Revenue change from list price changes — but only for customers who *renewed* at the new price (contract-based pricing with annual renewals)
- **Volume — new logos**: Revenue from customers acquired during the period
- **Volume — expansion**: Seat growth within existing accounts
- **Volume — contraction**: Seat reduction (including elasticity-driven contraction at renewal)
- **Churn drag**: Revenue lost from churned customers, segmented by reason
- **Channel mix shift**: Revenue impact from changing channel composition (different ASPs and discount levels)
- **Product mix shift**: Revenue impact from changing product composition
- **Channel cost inflation**: Cost increase from gradual tech inflation + cloud cost spike
- **Rep productivity**: Impact of new hire ramp time on acquisition velocity

## Why It's Hard

1. **Price changes roll through renewals, not all at once**: A list price increase only affects customers whose contracts renew in Q4. The AI must identify which customers transitioned and separate the renewal-timing effect from the price effect.
2. **Price and volume are coupled via elasticity**: Price increases cause some customers to churn or reduce seats at renewal. Naive decomposition double-counts — attributing the churn to "volume" while also counting the price increase.
3. **Channel discounts blur the price signal**: Two customers on the same product at the same list price have different realized prices depending on channel. A channel mix shift looks like a price change if you only look at average revenue per seat.
4. **New vs. existing revenue requires join logic**: The AI must join revenue data with customer acquisition dates to separate new-logo revenue from existing-customer revenue.
5. **Churn reasons matter for the narrative**: "Budget cuts" spiking in Q4 tells a different story than "competitive loss" — the AI should surface this.
6. **Strategic channel is lumpy**: A single large Strategic deal can swing the quarter — the AI must decide whether to call this out as a one-off or treat it as normal channel variance.
7. **Cost attribution is channel-specific**: The cloud cost spike disproportionately hits Self-Serve and Inside Sales. A single "cost inflation" number obscures which channels are getting squeezed.

## Data Files

| File | Rows | Description |
|------|------|-------------|
| `data/weekly_revenue.csv` | ~15,700 | Weekly revenue by customer — seats, unit price, list price, discount, revenue |
| `data/customers.csv` | ~700 | Customer master — product, channel, segment, acquisition date, renewal month, rep, status |
| `data/churn_events.csv` | ~24 | Churn records with reason category and lost revenue |
| `data/channel_costs.csv` | 390 | Weekly tech/infrastructure costs by channel and cost category |
| `data/sales_reps.csv` | 24 | Rep roster — channel, hire date, quota, tenure |
| `data/price_changes.csv` | 3 | List price change log with effective dates and reasons |

## Simulation Design

### Products (8 products, anonymized)

| Product | Monthly List Price | Elasticity | Notes |
|---------|-------------------|------------|-------|
| Product 1 | $120 → $128 | -0.5 (inelastic) | Core platform, +6.7% cost pass-through in Q4 |
| Product 2 | $85 | -0.8 (moderate) | Collaboration tool, no price change |
| Product 3 | $200 → $210 | -0.4 (inelastic) | Analytics suite, +5% value capture after feature release |
| Product 4 | $45 | -1.2 (elastic) | Entry-level tool, no price change |
| Product 5 | $150 | -0.6 (inelastic) | Security module, no price change |
| Product 6 | $95 → $85 | -1.4 (elastic) | Data connector, -10.5% competitive response |
| Product 7 | $180 | -0.3 (very inelastic) | Enterprise API, no price change |
| Product 8 | $60 | -1.0 (moderate) | Reporting tool, no price change |

### Channels (5 channels)

| Channel | Avg Discount | Deal Size | Acquisition Pattern |
|---------|-------------|-----------|-------------------|
| Direct Sales | 15% | ~40 seats | Lumpy — some weeks 0, some weeks 2-3 deals |
| Partner | 15% | ~25 seats | Steady, mid-market focused |
| Inside Sales | 8% | ~15 seats | Steady, SMB-heavy |
| Self-Serve | 0% (list price) | ~5 seats | High volume, small deals, highest churn |
| Strategic | 20% | ~150 seats | Very lumpy — rare but massive deals |

### Price Change Mechanics

List price changes are announced at a point in time but **only take effect when each customer's annual contract renews**. This means:
- A Q4 list price increase only affects customers with renewal months in Oct/Nov/Dec
- Customers renewing in Jan-Sep still pay the old price throughout Q4
- New customers acquired after the price change pay the new price immediately

At renewal with a price increase:
- **Elasticity-driven churn**: P(churn) = |elasticity| × price_change% × 0.5
- **Seat contraction**: Surviving customers may reduce seats proportional to elasticity × price_change% × 0.3
- More elastic products (Product 6) see stronger volume responses to price changes

At renewal with a price decrease (Product 6):
- Slight seat expansion among existing customers
- Higher new-logo acquisition rate post-change

### Churn Model

- Base annualized churn: ~7.5%
- Q4 multiplier: 1.3× (year-end budget rationalization)
- SMB churns 1.5× more, Enterprise 0.6×
- Q4 churn reason shift: "budget cuts" rises from 15% to 35% of churn reasons
- Price-driven churn at renewal is labeled "competitive loss", "budget cuts", or "product fit"

### Channel Costs

- Gradual inflation: ~0.3%/week (~15% annualized)
- **Cloud cost spike from week 20**: Self-Serve +22%, Inside Sales +18%, Strategic +10%, Direct Sales +8%, Partner +6% on hosting costs
- Cost categories: hosting, tooling, support_platform, partner_portal, dedicated_infra (varies by channel)

### Sales Rep Productivity

- ~25% of reps are new hires (started during the 26-week window)
- New reps ramp linearly over 12 weeks from 40-70% base productivity to full
- Tenured reps operate at 80-120% baseline
- Rep productivity directly scales new customer acquisition rate per channel

### Volume Noise

- Autocorrelated AR(1) process with mean reversion (ρ=0.7, σ=0.03)
- Clamped to ±15% — a good week tends to follow a good week
- Not i.i.d. random — weekly revenue for a given customer has realistic short-term persistence

## Key Metrics (seed=2024)

| Metric | Q3 | Q4 | Change |
|--------|-----|-----|--------|
| Revenue | $4.82M | $5.97M | +23.8% |
| Active Customers | 609 | 688 | +13.0% |
| Channel Costs | $2.23M | $2.42M | +8.3% |
| Gross Margin | $2.59M | $3.55M | +37.2% |
| New Customers (in-window) | — | 202 total | — |
| Q4 Churn | — | 12 customers | — |

### Channel Breakdown

| Channel | Q3 Revenue | Q4 Revenue | Q/Q Change |
|---------|-----------|-----------|------------|
| Direct Sales | $1.84M | $2.09M | +13.5% |
| Partner | $0.87M | $1.01M | +16.0% |
| Inside Sales | $0.40M | $0.44M | +11.8% |
| Self-Serve | $0.10M | $0.12M | +19.8% |
| Strategic | $1.61M | $2.30M | +43.1% |

Strategic's outsized growth (+43%) is driven by a few large deal closings — the AI should flag this concentration risk.

## Expected Output

The AI should produce:
1. A **revenue waterfall**: Q3 Revenue → Price → New Logos → Expansion → Contraction → Churn → Mix → Q4 Revenue
2. A **cost waterfall**: Q3 Costs → Inflation → Cloud Spike → Channel Mix → Q4 Costs
3. A **margin bridge** combining revenue and cost waterfalls
4. **Churn analysis** broken down by reason, with the Q4 budget-cuts spike called out
5. **Channel-level deep dive** noting Strategic lumpiness and Self-Serve cost pressure
6. Commentary on the **price-elasticity interaction** — that Product 6's price cut drove volume, while Product 3's increase caused some contraction
7. Acknowledgment that only a fraction of customers have renewed at new prices, so the full price effect hasn't materialized yet
