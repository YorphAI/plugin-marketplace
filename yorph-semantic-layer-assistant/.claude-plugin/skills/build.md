# Skill: Semantic Layer Build Phase

This skill governs Step 4 — the 9-agent parallel build. It covers what to show the user while agents work, how to surface questions progressively, and how to handle the agent lifecycle.

---

## Kicking off the build

Tell the user what's happening before spawning agents. Keep it brief:

```
Let's build your semantic layer.

I'm starting 9 specialist agents in parallel — 3 each for join validation,
metric definition, and grain design. They'll work through your [N] tables
simultaneously and I'll check in with you whenever they hit a decision
that needs your input.

This usually takes 1–3 minutes. I'll show you progress as they go.
```

---

## Progress updates

Post brief updates as agents complete major phases. Don't overwhelm — one update per role is enough:

```
🔗 Join Validator — found 14 candidate joins, validating cardinality...
📐 Measure Builder — identified 23 metric candidates across 5 domains...
📏 Granularity Definer — grain confirmed on 8 of 11 tables...
```

If an agent hits a question it needs to ask, pause the progress update and surface the question using the clarification templates in `prompts/clarification.md`.

---

## Surfacing assumption questions during the build

Questions arrive as agents work — don't batch them for the end. Surface them as soon as they're flagged:

1. Receive the question from the agent's structured output (`assumption_questions` array)
2. Prioritise: blocking → high-impact → data quality → preference
3. Use Template 1, 2, or 3 from `prompts/clarification.md`
4. Wait for the user's answer
5. Pass the answer back to the agent context before continuing

Example mid-build interruption:
```
[Quick question from the Join Validator — shouldn't take long]

I'm looking at how your `orders` and `order_items` tables relate. I can see
that 99.7% of order_ids in `orders` also appear in `order_items`, but about
0.3% don't.

This matters because: if we join orders → order_items with INNER JOIN, those
0.3% of orders disappear from revenue totals. If we use LEFT JOIN, they're
preserved (with NULL item amounts).

Which is correct for your business?
A) Some orders genuinely have no line items yet (drafts, etc.) — use LEFT JOIN
B) Every order should always have items — those 0.3% are probably bad data
C) Not sure — use LEFT JOIN for safety and flag it

My recommendation: A (LEFT JOIN), based on the 0.3% gap.
```

---

## When agents conflict within a role

If two join validators reach different conclusions on the same join:

```
[Two of my join validators disagree — I need your input]

🔵 JV-1 (Strict): This join is safe — validated 1:many with clean FK.
🟠 JV-2 (Explorer): This join has an unusual path — sessions can link to
   orders via either session_id OR user_id, and both paths give different counts.

The data shows:
- Via session_id: 94% of sessions match an order
- Via user_id: 71% of sessions match an order

Which join path should we use for conversion metrics?
```

---

## When agents depend on each other

The Measure Builder sometimes needs a join to be validated before it can confirm a metric. If that happens:

```
The Measure Builder is waiting for one join validation before it can confirm
the "Conversion Rate" metric. The Join Validator is checking `sessions → orders`
now — I'll resume as soon as it's done.
```

Don't surface this as an error — it's normal sequencing. Just let the user know you're aware and progressing.

---

## Build completion summary

When all 9 agents have stable outputs and all blocking questions are answered:

```
✅ All agents done.

Here's what was found across your [N] tables:

| | |
|--|--|
| Tables profiled | [N] |
| Joins validated | [N] safe, [N] flagged with caution |
| Metrics identified | [N] across [N] domains |
| Business rules applied | [N] (from your documentation) |
| Assumption questions answered | [N] |
| Open questions to revisit | [N] |

Ready to put together your three recommendations.
```

Then hand off to `skills/recommendations.md`.

---

## Assembling agent_outputs after build completes

After all 9 agents have finished, collect their structured JSON blocks and assemble them into the `agent_outputs` dict that `save_output` expects. Each agent emits a labeled block in its response — extract the JSON from each:

```
agent_outputs = {
  # From join_validator agents — take the union from all 3 JV agents' JOINS_VALIDATED: blocks
  "joins": [
    {
      "join": "orders → order_items",    # native format from JV agent output
      "join_key": "order_id",
      "cardinality": "1:many",
      "null_pct_left": 0.0,
      "null_pct_right": 0.2,
      "safe": true,
      "notes": "Clean 1:many. Average 3.2 items per order."
    }
    # ... more joins
  ],

  # From MB-1 (MEASURES_MB1: block)
  "measures_mb1": [
    {
      "measure_id": "total_revenue",
      "label": "Total Revenue",
      "aggregation": "SUM",
      "source_table": "orders",
      "source_column": "revenue",
      "filter": "status = 'completed'",
      "additivity": "fully_additive",
      "confidence": "high"
    }
  ],

  # From MB-2 (MEASURES_MB2: block) — includes mb1 measures + additional
  "measures_mb2": [...],

  # From MB-3 (MEASURES_MB3: block) — grouped by domain
  "measures_mb3": [...],

  # From GD-1 (GRAIN_GD1: block)
  "grain_gd1": [
    {
      "table": "orders",
      "grain": "one row per order",
      "grain_key": "order_id",
      "validated": true
    }
  ],

  # From GD-2 and GD-3
  "grain_gd2": [...],
  "grain_gd3": [...],

  # Collected across all agents and user answers
  "business_rules": [
    "Revenue is only recognised when status = 'completed'",
    "Refunded orders are excluded from GMV metrics"
  ],

  # Questions that remained unresolved
  "open_questions": [
    "Confirm whether draft orders (status='N/A') should be excluded from all metrics"
  ],

  # From document context glossary
  "glossary": {
    "GMV": "Gross Merchandise Value — total value of all orders before refunds",
    "NMV": "Net Merchandise Value — GMV minus refunds and cancellations"
  }
}
```

Hold this dict in context — it's passed to `save_output` verbatim when the user chooses a recommendation.

---

## If an agent errors

If a single sub-agent fails (e.g. a validation SQL times out):

- Don't fail the whole build
- Note which sub-agent failed and what it was trying to do
- Continue with the remaining 8 agents
- In the final recommendations, note what's missing and why

Example:
```
⚠ GD-3 (Architect) couldn't complete its hybrid grain analysis — the
validation query on your `events` table timed out (that table has 500M+ rows).

I've proceeded with GD-1 (Atomic) and GD-2 (Reporting) outputs. Recommendation 3
will use a simplified grain design — we can revisit the hybrid model after
optimising the query.
```
