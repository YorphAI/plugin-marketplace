# yorph-taggy

A lightweight Jira replacement where **chat with Claude is the only interface**
and **Postgres is the only datastore**. Issues, sprints, epics, comments,
releases, docs — every concept Jira treats as a first-class object collapses
into one of three things: an **item**, a **parent link**, or a **tag**.
New concepts (severity, customer, RICE, OKR) are just new tag prefixes — zero
schema changes.

```
                ┌──────────────────────────────────┐
   you ──chat──►│  Claude (this plugin's skills)   │──SQL──► Postgres
                └──────────────────────────────────┘            ▲
                              │                                 │
                              └──── psql / pg8000 ──────────────┘
                                       (taggy_ro for reads,
                                        taggy_rw for writes)
```

## What's in here

- `schema.sql` — two tables (`items`, `tags`) and indexes. That's the entire
  schema.
- `setup_db.py` — bootstrap helper. Creates the database, the two roles
  (`taggy_rw`, `taggy_ro`), applies the schema, writes `~/.yorph/taggy/config.json`.
- `bin/taggy-env` — sourceable shell helper that exports `TAGGY_RW`,
  `TAGGY_RO`, and `TAGGY_ACTOR` from the config file.
- `CLAUDE.md` — rules the agent follows in every conversation.
- `skills/setup/` — guided one-time setup.
- `skills/tracker/` — main skill. Filing, finding, tagging, commenting.
- `skills/analytics/` — burndowns, velocity, cumulative flow, charts.
- `EXAMPLES.md` — fifteen worked examples, every one a real eval.
- `examples/run_evals.py` — executable harness for those fifteen evals.

## Install

This plugin lives under the Yorph Claude Code marketplace, like the other
`yorph-*` plugins. Once Claude Code can see it, say:

> "set up taggy"

and the `setup` skill will walk you through hosting (local Docker, GCP Cloud
SQL, Supabase, Neon, or an existing Postgres), create the database and roles,
and write a config file with both connection strings and your display name.

A teammate joining an existing deployment runs the same skill in **join**
mode — they only need the two connection strings and their display name.

## Use

After setup, just talk to Claude. Three teasers below — each one is a real
eval, walked through end-to-end in [EXAMPLES.md](EXAMPLES.md).

---

> "Got a complaint that login on staging.acme.com bounces back even with
> the right password — looks cookie-related."

```
1 similar item already in proj:auth:
  #2 — session cookie domain not respected on subdomains   (status:review, @alice)

File fresh and link to it, file as a child, or just comment on #2?
```

<sub>*Before filing, the agent searches for near-matches. On "file fresh and link," it tags the new bug `relates:2` so the cross-reference is durable. The dedup-search is one ILIKE joined with the project tag — no separate "duplicates" table.*</sub>

---

> "What did the board look like four days ago?"

```
status              | key | title
--------------------+-----+------------------------------------------------------------
status:backlog      | 4   | Add WebAuthn passkey support
status:backlog      | 5   | Auth audit log retention policy
status:backlog      | 8   | Login page missing CSRF protection on forgot-password form
status:backlog      | 11  | Tune recommender ranker weights for diversity
status:in-progress  | 2   | session cookie domain not respected on subdomains
status:in-progress  | 3   | CSRF token rotation flakes intermittently
status:in-progress  | 10  | Recommender stuck on cold start for new users
status:review       | 1   | login redirect drops the next param after SSO
```

<sub>*Point-in-time queries fall out of one predicate: `tagged_at <= T AND (removed_at IS NULL OR removed_at > T)`. Apply it to sprint membership, type, and status, and the "as of" board appears. Docs and comments are filtered out by the type tag.*</sub>

---

> "Tag the audit-log task with severity sev2."

```
"severity" is new — registering it as a convention so the team stays in sync.
Filed:  #16 — convention:severity (sev0 = full outage … sev3 = cosmetic)
Tagged: #5 — Auth audit log retention policy   +severity:sev2
```

<sub>*New concepts are new tag prefixes — never schema migrations. The agent records what the prefix means as a `convention:<prefix>` item in the same `items` table; teammates see it the moment they connect.*</sub>

---

→ Full tour: 15 examples in [EXAMPLES.md](EXAMPLES.md), covering filing,
finding, history queries, aggregations, restructuring, and zero-DDL
extensibility. **No SQL is ever printed to you during normal operation** —
the technical details in this README are for the curious, not the user.

## Evals

Every example in EXAMPLES.md is also an executable eval. The harness seeds
a deterministic dataset, runs the 15 examples against it, and asserts on
the result:

```bash
python3 examples/run_evals.py
```

Each eval runs in its own transaction (rolled back at the end), so the
seed stays pristine across runs and the harness is order-insensitive. Use
this to catch regressions when you change the schema, the skill SQL, or
the seed.

## Why two tables

| Concept Jira has | Where it lives here |
|---|---|
| Issue | `items` row |
| Sub-task / comment / doc page | `items` row with `parent` set |
| Status, assignee, priority, points, sprint, release, labels | `tags` rows |
| Activity log / audit trail | `tags` rows with `tagged_at` / `removed_at` |
| Custom fields (severity, customer, OKR, RICE) | new tag prefix — no DDL |

Removing a tag soft-deletes (sets `removed_at`); the row stays. Burndowns,
cycle time, cumulative flow, and "what changed last week" all fall out of
queries against this single table — no separate event log needed.

The `taggy_ro` role is the safety net: it has `SELECT` only, so the agent can
write arbitrary analytics SQL with no risk of damaging state.

## Dependencies

- Postgres 14+ (any flavor; default deployment recipe is GCP Cloud SQL).
- `psql` available locally — the agent uses it directly for ad-hoc reads.
- `pg8000` (pure-Python Postgres driver) — installed by the setup skill;
  used for safe parameterized writes.
- `matplotlib` — installed lazily by the analytics skill on first chart.
- Python 3.10+ (already required by Claude Code).

## Out of scope (for now)

- Web viewer / dashboard — chat is the UI.
- Jira CSV importer.
- MCP server exposing this to non-Claude-Code surfaces.
- Notifications (Slack/email on assignment).
- File attachments.
- Permissions beyond DB roles.
