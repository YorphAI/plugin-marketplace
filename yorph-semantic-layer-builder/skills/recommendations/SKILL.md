---
name: recommendations
description: Use this skill after all agents complete to present the three semantic layer designs, collect the user's grade selections, and save the final output. Triggered when the build phase completes or the user asks to see recommendations / choose a design.
---

# Skill: Recommendations & Output

This skill governs the final phase — presenting the three semantic layer designs, helping the user choose or combine, then generating and saving the final output.

---

## When all agents are done

Confirm to the user before presenting recommendations:

```
All done — here's what I found across your warehouse:

📊 Tables analysed: [N]
🔗 Joins validated: [N] (with [N] flagged for caution)
📐 Metrics identified: [N] (across [N] business domains)
📄 Document context applied: [N] sources

I've put together three semantic layer designs based on different philosophies.
Each one is complete — you can use any of them as-is, or tell me what you'd
like to change. Let me walk you through them.
```

---

## Presenting the three recommendations

Show each one clearly, with a short pitch and the key trade-offs. Do NOT dump the full YAML/JSON yet — that comes after they choose. Show structure and logic first.

### Template

```
---

## Recommendation 1 — Conservative

**Best for:** Teams that need every number to be 100% trusted before publishing.

**What it includes:**
- [N] entities: [list entity names with business labels]
- [N] core metrics: [list top 5-7 metrics]
- [N] validated joins (strict cardinality checks passed)
- Grain: Atomic — one row per [grain description for each fact]

**What it leaves out:**
- [N] metrics that depend on joins flagged as potentially unsafe
- Ratio metrics (e.g. conversion rate) — added only after join validation completes
- Pre-aggregated summary tables — query at atomic level only

**Trade-off:** Safest, smallest surface area. Analysts have maximum flexibility
to aggregate any way they want. Slower queries on large tables.

---

## Recommendation 2 — Comprehensive

**Best for:** Analytics teams that want everything available and will iterate.

**What it includes:**
- All [N] entities from Recommendation 1
- [N] metrics total — including [N] ratio metrics, [N] derived metrics
- [N] joins (all validated + [N] flagged with caution notes)
- Grain: Reporting — daily × [dimension] optimised for common BI queries

**What's different from Recommendation 1:**
- [list key additions: ratio metrics, extra joins, pre-aggregated tables etc.]

**Trade-off:** Richer out of the box, but [N] metrics have moderate complexity
and require reviewing the join safety notes before using in dashboards.

---

## Recommendation 3 — Balanced ← *My recommendation*

**Best for:** Most teams — practical, shaped by what you told me about your business.

**What it includes:**
- [N] entities in a two-layer model: [N] atomic fact tables + [N] summary tables
- [N] metrics, grouped by domain: [list domains]
- All safe joins from Rec 1 + [N] additional joins from Rec 2 that I validated
- Grain: Hybrid — atomic for drill-down, daily summaries for dashboards
- Business names from your documentation throughout

**What makes it different:**
- Uses your documented metric definitions ([N] from your data dictionary)
- Applies your business rules as filters on revenue and customer metrics
- Includes a date spine (calendar table) for gap-free time series

**Trade-off:** Slightly more complex to maintain than Rec 1, but much richer
than Rec 1 without the risk surface of Rec 2.

---

Which one would you like to use? Or would you like me to mix elements —
for example, the grain from Rec 1 with the metric set from Rec 3?
```

---

## Handling follow-up requests

### "Can I mix elements?"
Yes — common combinations:
- "Rec 1 joins + Rec 2 metrics" → generate with Conservative joins, Comprehensive measures
- "Rec 3 but without the summary tables" → generate Balanced minus the pre-agg layer
- "Rec 1 but add conversion rate" → add that one metric from Rec 2, validate its join

Rebuild the specific combination and confirm before saving.

### "Can you explain [metric/join/decision] in more detail?"
Refer to the agent output for that specific item. Show:
- Which sub-agent produced it
- What validation was run (show the SQL result)
- What the alternatives were
- Why this choice was made

### "I want to change [something]"
Handle it conversationally:
- Metric filter change → update the filter, confirm, regenerate
- Grain change → re-run the affected GD agent output
- Remove a metric → remove from list, confirm
- Add a new metric that wasn't found → ask for the column and formula, validate, add

Always confirm the change before regenerating: *"I'll update [X]. Anything else before I regenerate?"*

---

## Output format selection (if not already chosen)

If the user hasn't picked a format yet, ask here:

```
What format would you like the output in?

1. **dbt** — schema.yaml + metrics.yaml (MetricFlow compatible)
2. **Snowflake** — Snowflake semantic layer YAML (Cortex Analyst compatible)
3. **JSON** — machine-readable, works with any BI tool
4. **YAML** — generic, human-readable
5. **OSI Spec** — Open Semantic Interface (works with Cube, MetricFlow, Headless BI)
6. **All of the above** — generate every format

Note: I'll always include a plain-English document alongside your chosen format
that explains every decision, metric formula, and join relationship.
```

---

## Generating and saving the output

Once the user confirms their choice, call `save_output` with the structured agent outputs:

```
save_output(
  agent_outputs={
    "joins":           [...],   # from join_validator agents
    "measures_mb1":    [...],   # from MB-1 (Minimalist)
    "measures_mb2":    [...],   # from MB-2 (Analyst)
    "measures_mb3":    [...],   # from MB-3 (Strategist)
    "grain_gd1":       [...],   # from GD-1 (Purist)
    "grain_gd2":       [...],   # from GD-2 (Pragmatist)
    "grain_gd3":       [...],   # from GD-3 (Architect)
    "business_rules":  [...],   # applied rules (plain strings)
    "open_questions":  [...],   # unresolved questions
    "glossary":        {...}    # term → definition map
  },
  recommendation_number=3,     # 1=Conservative, 2=Comprehensive, 3=Balanced
  project_name="Acme Corp",
  description="E-commerce semantic layer",
  format="dbt",                # or snowflake / json / yaml / osi_spec / all
  filename="acme_semantic_layer"
)
```

The renderer will:
1. Build the `SemanticLayer` IR from the agent outputs using the chosen recommendation
2. Render the chosen technical format (dbt YAML, Snowflake YAML, etc.)
3. Always render a companion `_readme.md` document
4. Write both to `~/.yorph/output/`

### After saving, tell the user exactly what was created:

```
Your semantic layer has been saved:

📁 ~/.yorph/output/
  ├── acme_semantic_layer.yml          ← dbt schema + metrics (import into your dbt project)
  └── acme_semantic_layer_readme.md   ← plain-English explanation of every decision

**What's in the dbt file:**
- [N] model definitions with column descriptions
- [N] metric definitions (MetricFlow compatible)
- All validated join relationships

**Next steps:**
1. Copy `acme_semantic_layer.yml` into your dbt project's `models/` directory
2. Run `dbt parse` to validate syntax
3. Review the _readme.md — it lists [N] open questions to revisit as your
   data evolves

Want me to walk through any part of the output?
```

---

## The companion document — always generated

Even if the user only asked for dbt YAML, always generate `_readme.md`. It contains:

- **What was built** — entity count, metric count, join count, business rules applied
- **Every entity** — description, grain, source system, validated joins
- **Every metric** — business name, formula, filters, additivity, complexity, domain
- **Business rules** — plain-language rules applied as metric filters
- **Open questions** — unresolved ambiguities to revisit
- **Glossary** — terms from documentation

Tell the user about it: *"I've also saved a plain-English document — `_readme.md` — that explains every metric formula and join decision in plain language. Useful for onboarding new analysts or reviewing with stakeholders."*

---

## If the user wants to iterate after seeing the output

Keep the session open. They can:
- Ask to add/remove/change metrics
- Re-run with a different recommendation number
- Ask to generate an additional format
- Ask to regenerate with a new document they just uploaded

All previous agent outputs are available in context — you don't need to re-profile or re-run agents for minor changes.
