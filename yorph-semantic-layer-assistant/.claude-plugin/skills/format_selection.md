# Skill: Output Format Selection

This skill governs Step 4 (format selection) — helping the user pick the right output format for their stack. Can be asked during onboarding or deferred to just before output generation.

---

## When to trigger

- During Step 3 onboarding if it flows naturally
- At the start of Step 5 (recommendations) if not yet collected
- If the user asks "what formats do you support?"

---

## Format guide

Present this only if the user seems unsure. If they say "dbt" immediately, just confirm and move on.

```
Which format would you like?

**dbt** — generates schema.yaml with model descriptions + metrics.yaml
  for dbt Semantic Layer (MetricFlow). Best if you already use dbt.

**Snowflake** — generates a Snowflake semantic layer YAML compatible with
  Cortex Analyst. Best if you're on Snowflake and want native semantic views.

**JSON** — machine-readable, works with any BI tool or custom pipeline.

**YAML** — human-readable generic format, easy to adapt to any tool.

**OSI Spec** — Open Semantic Interface spec, compatible with Cube, MetricFlow,
  and other headless BI frameworks.

**All formats** — I'll generate every format above. Useful if you're deciding
  which tool to use or want to share with your team for comparison.

Whatever you choose, I always also generate a plain-English `_readme.md`
that explains every metric formula and design decision.
```

---

## Recommended format by stack

Suggest based on what the user mentioned:

| User's stack | Recommended format |
|---|---|
| dbt already in use | dbt |
| Snowflake + Cortex | Snowflake |
| Looker / Tableau | YAML or JSON (import as custom semantic layer) |
| Cube.dev | OSI Spec |
| PowerBI | JSON |
| Not sure yet | All formats |
| Custom / internal tool | JSON |

---

## The companion document

Always explain this proactively:

```
Regardless of which technical format you pick, I'll also generate a
_readme.md document alongside it. This explains:

- Every entity and what it represents
- Every metric — its formula, filters, and business rule
- Every join — which direction, why that cardinality, any caveats
- Open questions to revisit as your data evolves
- A glossary of all business terms used

It's designed so a new analyst (or a stakeholder) can understand the
semantic layer without reading any YAML.
```
