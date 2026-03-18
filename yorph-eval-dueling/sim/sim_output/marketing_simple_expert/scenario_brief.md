# Scenario Brief: marketing_simple

**Domain:** marketing | **Complexity:** simple

A clean marketing schema: campaigns, clicks, and conversions. Tests whether the agent identifies ROAS, CPA, CTR, and conversion rate as the core marketing measures.

---

## Tables

- **campaigns**: Ad campaigns. One row per campaign.
- **ad_spend**: Daily spend, impressions, and reach by campaign.
- **clicks**: Individual ad clicks. campaign_id NULL for organic traffic.
- **conversions**: Conversion events (purchase, signup, lead). One row per event.

---

## Data Quality Issues (deliberately injected)

These are known issues the agent MUST discover and surface:

### clicks.campaign_id — `high_null`

20% of clicks have NULL campaign_id — organic/direct traffic.

**Prevalence:** 20% of rows

### conversions.revenue — `high_null`

revenue is NULL for lead-gen conversions (non-transactional goals).

**Prevalence:** 30% of rows

---

## Expected Joins (ground truth)

- `clicks` → `campaigns` on `campaign_id` [many:1]
- `conversions` → `clicks` on `click_id` [1:1]
- `ad_spend` → `campaigns` on `campaign_id` [many:1]

---

## Expected Measures (ground truth)

- **Total Ad Spend**: SUM(ad_spend.spend_amount)
- **Clicks**: COUNT(clicks.click_id)
- **Conversions**: COUNT(conversions.conversion_id)
- **Attributed Revenue**: SUM(conversions.revenue) WHERE revenue IS NOT NULL
- **ROAS**: RATIO(conversions.*)
- **CPA**: RATIO(ad_spend.*)
- **CTR**: RATIO(clicks.*)
- **Impressions**: SUM(ad_spend.impressions)

---

## Expected Business Rules

- ROAS = revenue / spend. Only include conversions with non-NULL revenue.
- CPA = spend / conversions. Use campaign-level grouping.
- CTR = clicks / impressions.
- 20% of clicks have no campaign_id — these are organic. Exclude from paid metrics.
