# Scenario Brief: marketing_medium

**Domain:** marketing | **Complexity:** medium

Full attribution stack: campaigns, spend, UTM sessions, touchpoints, and conversions. Key challenge: touchpoints is a multi-touch attribution table with one row per channel per conversion — joining it directly to conversions fans out revenue. The agent must detect this and recommend aggregating touchpoints first.

---

## Tables

- **campaigns**: Ad campaigns.
- **campaign_budgets**: Monthly budget allocations per campaign.
- **ad_spend**: Daily actual spend per campaign.
- **sessions**: Web sessions with UTM parameters.
- **conversions**: Conversion events.
- **touchpoints**: Multi-touch attribution — one row per channel per conversion. Fan-out risk: aggregate before joining to conversions.

---

## Data Quality Issues (deliberately injected)

These are known issues the agent MUST discover and surface:

### touchpoints.conversion_id — `fan_out_trap`

touchpoints has 1-many rows per conversion (one per channel in the attribution path). Joining conversions → touchpoints then summing revenue fans out the revenue figure. Must aggregate touchpoints before joining.

**Prevalence:** always

### sessions.utm_medium — `encoded_null`

utm_medium = '(none)' is GA's encoded null for direct traffic.

**Prevalence:** 20% of rows

### ad_spend.spend_amount — `duplicate_metric`

ad_spend.spend_amount and campaign_budgets.allocated_budget both represent money. spend is actuals; budget is planned. The agent should distinguish these.

**Prevalence:** always

---

## Expected Joins (ground truth)

- `sessions` → `campaigns` on `campaign_id` [many:1]
- `conversions` → `sessions` on `session_id` [many:1]
- `touchpoints` → `conversions` on `conversion_id` [many:1] ⚠ fan_out trap
- `ad_spend` → `campaigns` on `campaign_id` [many:1]
- `campaign_budgets` → `campaigns` on `campaign_id` [many:1]

---

## Expected Measures (ground truth)

- **Total Spend**: SUM(ad_spend.spend_amount)
- **ROAS**: RATIO(conversions.*)
- **CPA**: RATIO(ad_spend.*)
- **Sessions**: COUNT(sessions.session_id)
- **Conversion Rate**: RATIO(sessions.*)
- **Budget Pacing**: RATIO(campaign_budgets.*)

---

## Expected Business Rules

- NEVER join conversions → touchpoints without pre-aggregating — it fans out revenue.
- Use last-touch attribution by default (touchpoints.position = 'last').
- utm_medium = '(none)' should be labelled 'direct' in channel reporting.
- ad_spend.spend_amount is actuals; campaign_budgets.allocated_budget is planned.
