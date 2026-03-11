# Escalation Protocol

This document defines when and how agents escalate issues to the user. Referenced by all agents.

---

## When to escalate

**Stop and escalate** whenever you encounter any of these situations:

1. **Ambiguity you can't resolve** — two equally valid interpretations of the data, and choosing wrong would produce incorrect results
2. **Contradictions** — documentation says one thing, data shows another (a `⚠ CONFLICT` tag)
3. **Quality blockers** — a column critical to your output has >20% nulls, constant values, or stale data
4. **Missing dependencies** — your output depends on a table, column, or relationship that doesn't exist in the warehouse
5. **User context needed** — the right answer depends on business knowledge you don't have (e.g. "is this column net or gross revenue?")

## How to escalate

When escalating, always provide:

1. **What you found** — the specific data point or conflict
2. **Why it matters** — what goes wrong if you guess incorrectly
3. **Options** — the 2-3 possible resolutions
4. **Your recommendation** — which option you'd pick based on the evidence, and why

## Format

Use the `assumption_questions` array in your `AgentOutput`:

```json
{
  "question": "Your question here — specific and actionable",
  "why_it_matters": "What goes wrong if we guess incorrectly",
  "options": ["Option A — with brief explanation", "Option B — with brief explanation"],
  "my_assumption": "What I'd pick and why, based on the evidence"
}
```

## Do NOT escalate

- Things you can validate with `execute_validation_sql` or `get_sample_slice` — check first, escalate only if the check is inconclusive
- Stylistic preferences (naming conventions, grouping) — use the documented name if available, otherwise use a sensible default
