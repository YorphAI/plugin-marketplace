# yorph-taggy — Plugin Instructions

## What this plugin is

A two-table Postgres tracker. Issues, sprints, epics, comments, releases, docs —
every concept Jira treats as a first-class object collapses into one of three
things: an **item** (`items` row), a **parent link** (`items.parent`), or a
**tag** (`tags` row). New concepts (severity, customer, RICE, OKR) are just new
tag prefixes — zero schema churn.

The agent does the work. There is no CLI of pre-built commands. The skills
document the schema and tag conventions; the agent then writes SQL on the fly
to file items, find them, tag and retag, build burndowns, draw cumulative-flow
charts, and so on.

Config lives at `~/.yorph/taggy/config.json` (env override: `YORPH_TAGGY_HOME`).
Two Postgres roles bound the blast radius:

- `taggy_rw` — used for mutations (`INSERT` / `UPDATE`).
- `taggy_ro` — used for reads. Cannot mutate. The safety net for
  arbitrary analytics SQL.

## Which skill to use

- "set up taggy", "install taggy", "create the database", "join an existing
  taggy", "what's my actor handle" → `yorph-taggy:setup`
- File items, tag/retag, find items, comment, list, search, summarize,
  cross-reference docs and tickets → `yorph-taggy:tracker`
- Burndowns, velocity, cumulative flow, story points by engineer, sprint
  reports, "show me a chart of …", anything that aggregates the tag history →
  `yorph-taggy:analytics`

## Core rules

1. **Never expose SQL to the user.** Explain in plain language what you did and
   what you found. Assume a non-technical reader.
2. **Always reference items as `#KEY — title`** (e.g. `#42 — fix login redirect`).
   Users say "the login bug"; you resolve it to a key.
3. **Assume the user works by description, not number.** They don't memorize
   keys. Always resolve their description to candidate items, confirm `#KEY —
   title` back to them, and only then act.
4. **Resolve ambiguity by asking.** If a reference matches more than one item,
   list candidates with their keys and titles, and ask which.
5. **Search before filing.** Before creating a new item, hunt for near-matches
   and surface them. Either link via `relates:<key>`, file as a child if it's
   a sub-issue, or proceed fresh — the user decides.
6. **Confirm before destructive actions.** Deleting items, removing many tags
   at once, mass retagging. Reads are free.
7. **Tag conventions are conventions, not rules.** If the user invents a new
   tag pattern, just use it — and register it (rule 8) so the team stays
   coherent.
8. **Register new conventions.** When a brand-new prefix appears (e.g.
   `severity:`, `customer:`), file a `convention:<prefix>` item documenting
   what it means and what values are allowed. On every tracker session,
   read these so teammates inherit each other's vocabulary.
9. **Read with `taggy_ro`. Write with `taggy_rw`.** Default to read-only.
10. **Preserve history.** Never `DELETE` from `tags`; set `removed_at`
    instead. The history *is* the analytics layer.

## Tag conventions (starting vocabulary)

| Concept | Pattern | Examples |
|---|---|---|
| Type | bare word | `#bug`, `#task`, `#story`, `#epic`, `#doc` |
| Status | `status:<value>` | `status:backlog`, `status:in-progress`, `status:review`, `status:done` |
| Assignee | `@<handle>` | `@alice`, `@bob` |
| Priority | bare letter+digit | `p0`, `p1`, `p2`, `p3` |
| Estimate | `points:<n>` | `points:1`, `points:5` |
| Sprint | `sprint:<id>` | `sprint:2026-q2-w1` |
| Release | `release:<id>` | `release:2026-w16` |
| Project | `proj:<slug>` | `proj:recommender` |
| Team | `team:<slug>` | `team:platform` |
| Free labels | `#<word>` | `#flaky`, `#customer-escalation` |

These are starting suggestions. On first use of a fresh database, sniff the
existing tag distribution (`SELECT tag, count(*) FROM tags GROUP BY tag`) and
adopt whatever the team already uses.
