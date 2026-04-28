# Yorph Tracker — v1 Engineering Spec

A lightweight Jira replacement where **chat with Claude is the only interface** and **Postgres is the only datastore**. Issues, sprints, epics, comments, releases, documentation — every concept Jira treats as a first-class object collapses into one of three things: an **item**, a **parent link**, or a **tag**. New concepts the team invents later (severity, customer, RICE score, OKR) are just new tag prefixes — zero schema changes.

Ships as a Claude Code plugin in `plugins/yorph-tracker/`, following the conventions of `yorph-automate`.

## How this system actually works

**All analytics, search, reporting, and cross-cutting roll-ups are produced by the agent's natural-language-to-SQL ability** turning a chat request into a query against the two-table store, combined with the agent's general coding ability for tasks SQL can't do alone (rendering charts with matplotlib, reading git history, summarizing prose, etc.).

The plugin **does not** ship a CLI of pre-built commands (no `tracker.py file --type bug --priority p0 ...`). It ships a schema, a connection string, two database roles (read-write and read-only), and a set of skill files that document the conventions. Everything else is the agent writing SQL or Python on the fly when the user asks for something.

The skill files exist as **guardrails on tag formation**, not as an API. Their job is to steer the agent toward a consistent tagging vocabulary — so that when one user files a bug as `#bug` and another user later asks "list all bugs assigned to alice this sprint," the query returns the right rows. The skill content is mostly: "use these tag prefixes; resolve ambiguity by asking; preserve history with soft-deletes; reference items by `#KEY — title`." Without this guidance the model would drift between `#bug`, `bug`, `type:bug`, and `category:bug` across users and sessions, and analytics would silently rot. With it, tagging stays coherent and the NL-to-SQL pipeline stays reliable.

## Data Model

Two tables in Postgres. That's the entire schema.

```sql
CREATE TABLE items (
  key         TEXT PRIMARY KEY,        -- short id, e.g. '42'
  title       TEXT NOT NULL,           -- one-line description, always shown alongside key
  body        TEXT,                    -- long form (markdown)
  parent      TEXT REFERENCES items(key) ON DELETE CASCADE,
  created_by  TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE tags (
  id          BIGSERIAL PRIMARY KEY,
  item        TEXT NOT NULL REFERENCES items(key) ON DELETE CASCADE,
  tag         TEXT NOT NULL,
  tagged_by   TEXT NOT NULL,
  tagged_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  removed_by  TEXT,
  removed_at  TIMESTAMPTZ
);
CREATE UNIQUE INDEX ON tags(item, tag) WHERE removed_at IS NULL;
CREATE INDEX ON tags(tag);
CREATE INDEX ON tags(item, tag, tagged_at);
```

**Why this is enough:**

- **Comments, sub-tasks, epic children, doc pages** — items with `parent` set. The thing they have in common (they hang off another item) is captured once.
- **Status changes, assignments, priority, estimates, sprint membership, release inclusion, labels** — tag rows. Removing a tag *soft-deletes* (sets `removed_at`); the row stays. The full history of every state change is preserved in one place, so burndowns, cycle time, cumulative flow, and "what changed last week" all fall out of queries against this single table — no separate activity/event log needed.
- **Free-form metadata** — tags with conventions like `points:5`, `due:2026-05-01`, `p0`, `proj:recommender`, `release:2026-w16`. Conventions, not enforced columns.

## Interaction Model

The plugin is one skill (`tracker`) plus a connection string. The skill documents the two tables, the tag conventions, and a handful of code patterns. **The agent writes SQL on the fly** for everything — filing items, finding items, building burndowns, charting velocity. The SQL examples in the skill are reference material, not an exposed API.

Two Postgres roles control blast radius:

- `tracker_rw` — used for chat-driven mutations.
- `tracker_ro` — used for analytics and any read-only operation.

The agent uses `tracker_ro` unless it is actually mutating state. The read-only role cannot execute `INSERT`/`UPDATE`/`DELETE`/`DDL` — this is the safety net that lets Claude write arbitrary analytics SQL without risk.

## Worked Examples

The two-table model plus chat-driven SQL is enough to handle each of these. Engineers reading this can sanity-check that there are no hidden object types needed.

### "Show me story points by engineer over the last 4 sprints"

Story points live as `points:N` tags. Sprint membership lives as `sprint:<id>` tags. Engineer assignment lives as `@<handle>` tags. Claude finds the four most recently active `sprint:*` tags (by max `tagged_at`), then for each sprint sums `points:N` across items that also carry each engineer's `@` tag. Output is a markdown table with sprints as columns and engineers as rows. Because tag history is preserved via soft-delete, reassignment after sprint close doesn't distort historical numbers — Claude can answer "as of sprint close" or "as of today" by picking the right `tagged_at` / `removed_at` window.

### "Give me all tickets and relevant documentation related to the recommender project"

Tickets and docs are not separate types — both are items, distinguished by tags (`#bug`, `#task`, `#doc`) and by body length. Claude unions three searches: items tagged `#recommender` or `proj:recommender`, items whose title or body matches "recommender" in Postgres full-text search, and items whose `parent` chain leads to a recommender-project root item. Results are grouped by tag profile (tickets vs. docs vs. discussions) and rendered as `#KEY — title` lists with body snippets.

### "Summarize what went into last week's release"

The `tags` table preserves every status transition with `tagged_at` / `removed_at` timestamps. Claude finds items whose `status:done` tag was added in the last 7 days (or whose `release:<latest>` tag was added last week — whichever convention the team uses), reads each item's title and body, groups them by `proj:*` or `area:*` tag, and writes a prose summary plus a bulleted list. No release-tracking object is needed; release tagging is just another convention.

### "Update ticket descriptions based on the code changes"

Because the plugin runs inside Claude Code, the agent has git access and the DB connection in the same session. Claude reads recent commits (range chosen by the user — last day, since main, etc.), parses each commit message for `#KEY` references, summarizes the actual code delta (files touched, behavior change), and either appends an `## Implementation` section to the matching item's `body` or — cleaner — creates a child item with `parent = <key>` tagged `#code-update` and a body capturing the changelog. The original description stays intact; history is preserved either way.

### "Give me a chart of velocity flowing through different ticket statuses for my team"

A cumulative flow diagram falls directly out of the tags table: for each date in the window, count items where each `status:*` tag was active (i.e., `tagged_at <= date AND (removed_at IS NULL OR removed_at > date)`). "My team" filters on team membership — stored either as `team:platform` tags on items, or via a meta-item `team:platform` whose tags are the engineer handles, whichever convention the team adopts. Claude writes a short matplotlib script, saves a PNG, and shows the chart with a one-paragraph narrative explaining the bottlenecks ("review queue is growing, done is flat — review capacity is the limiter").

Each example demonstrates the same property: **the agent's NL-to-SQL and general coding abilities are doing the real work; the schema's job is to be cheap and uniform enough that those abilities have room to operate.**

## Rules in CLAUDE.md

1. **Never expose SQL to the user.** Explain what you did and what you found in plain language. Assume the user is non-technical.
2. **Always reference items as `#KEY — title`** (e.g., `#42 — fix login redirect`). Users should never have to memorize numbers — they say "close the login bug" and you resolve the reference.
3. **Resolve ambiguous references by asking.** If "the login bug" matches more than one item, list candidates with their keys + titles and ask which one.
4. **Confirm before destructive actions** (deleting items, removing many tags at once). Read operations are free.
5. **Tag conventions are conventions, not rules.** If the user invents a new tag pattern, just use it. Don't refuse or normalize without asking.
6. **Use the `tracker_ro` role for anything that doesn't mutate.** Switch to `tracker_rw` only when actually changing state.
7. **Preserve history.** Never `DELETE` from `tags`; always update `removed_at` instead. The history is the analytics layer.

## Skill File — Tag Convention Guardrails

The skill steers the agent toward a consistent vocabulary. Recommended starting conventions, all documented in the skill body:

| Concept | Tag pattern | Examples |
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

These are starting suggestions. Teams can extend or replace them — the skill instructs the agent to discover and adopt the team's actual conventions on first use, then stay consistent within them.

## Setup

One-time, conversational, AI-driven. The skill asks where to host (GCP Cloud SQL, Supabase, Neon, existing Postgres, local Docker), then drives the right commands. It creates the database, the two roles (`tracker_rw`, `tracker_ro`), applies the schema, writes a config file with both connection strings and the user's display name, and reports back when done. Each subsequent teammate runs the same skill in "join existing" mode — they only need the connection strings and their own display name.

Config lives at `~/.yorph/tracker/config.json` (gitignored), with env override `YORPH_TRACKER_HOME`. Schema:

```json
{
  "db_url_rw": "postgres://tracker_rw:...@host/tracker",
  "db_url_ro": "postgres://tracker_ro:...@host/tracker",
  "actor": "alice"
}
```

## Dependencies

- Postgres (any flavor; default deployment recipe is GCP Cloud SQL).
- `psql` available locally (the agent uses it directly for ad-hoc queries).
- One pip package, `pg8000` (pure Python Postgres driver), used by the setup helper for schema migration. No system libs required.
- Python 3.10+ (already required by Claude Code).

## Acceptance Criteria

1. Schema fits on one screen. (It does.)
2. A user can file an item, tag it, retag it, and ask "what changed on #42 this week" — all in chat, with no jargon in the output.
3. Each of the five worked examples above produces a sensible answer end-to-end against a freshly seeded database.
4. Adding a new concept (e.g., severity, customer, RICE score) requires zero schema changes — it's a new tag prefix the team starts using.
5. Two teammates writing concurrently don't collide on item key allocation; tag history is never lost on retag.
6. The `tracker_ro` role cannot execute `INSERT`/`UPDATE`/`DELETE`/`DDL` (verified by test).
7. The agent never prints SQL to the user during normal operation; it explains in plain language what it did and what it found.

## Out of Scope (v2+)

- Web viewer / dashboard — chat is the UI.
- Jira CSV importer.
- MCP server exposing the tracker to non–Claude-Code surfaces.
- Notifications (Slack/email on assignment).
- File attachments (would need GCS or similar).
- Permissions beyond DB roles (per-project ACLs, etc.).

All of these are easy to add later because the data model imposes no constraints on them.