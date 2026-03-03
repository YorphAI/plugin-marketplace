---
name: onboarding
description: Use this skill during the onboarding phase to gather industry context and business information before running agent analysis. Triggers include: "tell me about your data", "what industry are you in", "who uses the data", "what metrics matter", "what does this data represent", "upload a data dictionary", "add business context".
---

# Skill: Onboarding — Industry & Data Context

This skill governs Step 3 — the conversational questions that give the agents the business context they need to build a good semantic layer. Ask one topic at a time. Keep it conversational, not a form.

---

## Why this matters

Without context, agents infer meaning from column names and statistics alone. With context, they know:
- Which tables are facts vs dimensions
- What "revenue" means in this business (gross? net? recognised?)
- What time periods matter (fiscal year? calendar year? rolling 30 days?)
- Who the end users are and what they care about

---

## Question sequence

### Q1 — Industry and what the data represents

```
To make sure the semantic layer speaks your business language — what industry
are you in, and what does this data represent?

For example: "We're a B2B SaaS company — this is our Salesforce CRM data
combined with our product usage events from Segment."
```

Wait for the answer. Then follow up naturally if needed:
- *"What's the core business process this data tracks — sales pipeline? subscription billing? fulfilment?"*
- *"Is this transactional data (one row per event) or already aggregated (daily summaries)?"*

### Q2 — Who uses the data and what they care about

```
Who are the main consumers of this semantic layer — data analysts, business
stakeholders, a BI tool like Looker/Tableau/PowerBI?

And what are the top 3-5 questions they're trying to answer? For example:
"What's our MRR by segment?", "Which campaigns drove the most conversions?"
```

This shapes which metrics the agents prioritise and what domain groupings make sense.

### Q3 — Documents (only if not already uploaded)

```
Do you have any of these?

📄 A data dictionary — column descriptions and business names
📊 A SaaS app doc — e.g. Stripe schema guide, Salesforce field reference
📐 An existing semantic layer — dbt YAML, LookML, or similar
🔗 A documentation URL — Confluence, Notion, GitHub wiki

These aren't required, but they significantly improve the output.
Just upload or paste a link, or say "no" to proceed with inference.
```

### Q4 — Output format (if not yet decided)

```
What format do you want the semantic layer in?

1. dbt — schema.yaml + metrics (MetricFlow)
2. Snowflake — semantic layer YAML (Cortex Analyst)
3. JSON
4. YAML (generic)
5. OSI Spec (Cube, MetricFlow, Headless BI)
6. All formats

Whatever you choose, I'll also always generate a plain-English document
explaining every decision.
```

---

## Using the answers to guide agents

After onboarding, add a context block to the agent prompt (system.md Step 4):

```
BUSINESS CONTEXT:
- Industry: [answer]
- Data represents: [answer]
- Key consumers: [answer]
- Top questions to answer: [list]
- Priority metrics (user-mentioned): [list]
- Output format: [choice]
```

Agents read this context and:
- Prioritise the user-mentioned metrics in their output
- Use the correct time grain (fiscal year vs calendar year)
- Apply domain labels that match the user's language
- Surface the top-questions-relevant measures first in recommendations

---

## Keeping it short

If the user gives a rich answer to Q1, you often have enough to proceed. Don't ask all four questions if earlier answers already cover it. For example, if they say *"We're using Stripe — building a billing semantic layer for our finance team"*, you know:
- Industry: SaaS/fintech
- Data: billing/subscription
- Consumer: finance
- Priority metrics: MRR, ARR, churn, refunds

In that case, skip Q2 and go straight to documents.
