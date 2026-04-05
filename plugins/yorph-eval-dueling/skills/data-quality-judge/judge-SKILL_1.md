---
name: data-quality-judge
description: >
  Evaluation rubric for judging multiple data analyst responses on data quality
  tasks. Use when acting as a judge scoring N conditions (2-10) on the same
  dataset. Derives challenge categories, scores each condition independently
  on an absolute scale, and produces a structured leaderboard verdict.
  Apply whenever given multiple analyst responses and raw data context.
---

# Data Quality Judge Skill

You are scoring N data analysts who each received the same raw dataset and blind prompt — no hints about what to look for. Your job is to derive the relevant challenges from the data and responses, then score each condition independently using an absolute rubric (not relative ranking).

---

## Step 1 — Derive the Challenge Set

Do not expect a manifest. Read the data and all responses, then build challenges using this taxonomy:

| Category | Examples |
|---|---|
| **Temporal** | Partial periods, backdated records, inconsistent date formats, timezone mixing |
| **Metric Ambiguity** | Two columns measuring the same thing differently, aggregation grain mismatches |
| **Structural / Schema** | Inconsistent casing ("pro" vs "PRO"), mixed types, null codes (-1, "N/A") |
| **Null Patterns** | Nulls concentrated in a subgroup (structured), conditional nulls |
| **Relational / Join** | Key type mismatches, fanout joins, orphaned FKs, session ID collisions |
| **Business Logic** | Label leakage, status lifecycle traps (cancelled in revenue), impossible values |

Include a challenge if: **detectable from the data** AND **would materially affect analysis if missed**.
Aim for **5–10 challenges**. Don't pad. Don't collapse two distinct issues into one.

---

## Step 2 — Score Each Condition (Absolute Scale)

Score every condition independently for every challenge. Do not compare conditions to each other — apply the rubric to each response on its own merits.

**Detection (0–3)**
- 0 = Missed entirely
- 1 = Vague hint ("data may have inconsistencies")
- 2 = Clearly identified by column name or issue type
- 3 = Identified with specific column, value, count, or row-level evidence

**Depth (0–3)**
- 0 = No explanation
- 1 = Named the problem only
- 2 = Explained why it matters for analysis
- 3 = Root cause identified + impact quantified or demonstrated

**Handling (0–4)**
- 0 = No mention of how to handle it
- 1 = Acknowledged it should be investigated
- 2 = Described a plausible fix
- 3 = Described the correct specific fix with implementation detail
- 4 = Correct fix + showed verification (confirmed fix resolves the issue)

**Total = Detection + Depth + Handling (max 10)**

**Difficulty heuristic:**
- Easy = visible with `.describe()`, `.value_counts()`, `.info()`
- Medium = requires cross-tabulation or comparing aggregates across columns
- Hard = requires domain knowledge, temporal reasoning, or multi-step verification

---

## Step 3 — Overall Assessment

After scoring all challenges, produce an overall ranking (best to worst by total score across all challenges) and a brief explanation of what separated the top conditions from the rest.

---

## Step 4 — Output Format

Respond **ONLY** with valid JSON. No markdown fences, no preamble, no text outside the JSON object.

The `conditions` array inside each challenge must include **every condition** that was provided — do not omit any.
`conditionSummaries` must have an entry for **every condition label**.
`overallRanking` must list **every condition label**, best first.

```json
{
  "overallRanking": ["<label best>", "<label 2nd>", "..."],
  "overallReasoning": "2-3 sentences on what separated the top conditions from the rest",
  "conditionSummaries": {
    "<label>": "1-2 sentence characterization of this condition's approach and blind spots"
  },
  "challenges": [
    {
      "name": "Short descriptive name",
      "category": "Temporal | Metric Ambiguity | Structural | Null Patterns | Relational | Business Logic",
      "difficulty": "Easy | Medium | Hard",
      "description": "1 sentence: what the issue is and why it matters",
      "conditions": [
        {
          "label": "<condition label>",
          "score": <0-10>,
          "detection": <0-3>,
          "depth": <0-3>,
          "handling": <0-4>,
          "reasoning": "1 sentence: what this condition did or missed for this specific challenge"
        }
      ]
    }
  ]
}
```
