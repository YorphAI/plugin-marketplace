---
name: tracker
description: The main yorph-taggy skill. Use whenever the user wants to file, find, tag, retag, comment on, or summarize items — bugs, tasks, stories, epics, docs, comments, or anything else that lives in the tracker. Triggers include "file a bug/task/story", "create a ticket", "tag #42 as …", "what's the status of …", "list everything tagged …", "show me what alice is working on", "comment on #42", "add a child task to …", "close #42", "what changed on #42 this week". Do NOT use for charts/burndowns/velocity (use yorph-taggy:analytics) or first-time install (use yorph-taggy:setup).
---

# Tracker — yorph-taggy

The data model is two tables: `items` and `tags`. Read [schema.sql] (sibling
of this skill, two levels up). Tag conventions are documented in CLAUDE.md.

This skill teaches the agent how to file, find, tag, retag, comment, and
summarize against that schema using `psql` (reads) and `pg8000` (writes).

## Preamble: every bash call

Each Bash tool invocation is a fresh shell, so source the env helper at the
top of every command block. The plugin lives next to this skill at
`<plugin>/bin/taggy-env`. If you don't already have `$PLUGIN_DIR` set in the
session, derive it once:

```bash
PLUGIN_DIR="$(ls -d "$HOME"/Documents/Yorph/yorph-marketplace/plugins/yorph-taggy 2>/dev/null \
              || ls -d /Applications/Claude/plugins/yorph-taggy 2>/dev/null)"
. "$PLUGIN_DIR/bin/taggy-env"
```

After sourcing: `$TAGGY_RO`, `$TAGGY_RW`, `$TAGGY_ACTOR` are exported.

If `taggy-env` returns 1 because the config is missing, stop and route the
user to `yorph-taggy:setup`.

## Core rules (recap)

1. **Never print SQL to the user.** Explain plainly what you did and what you
   found. Pretend they don't know any database exists.
2. **Always render items as `#KEY — title`.** Never expose a key without its
   title.
3. **Assume the user references items by description, not number.** They say
   "the login bug" or "Alice's recommender investigation," not "#42." Always
   resolve the description to candidate items first, confirm `#KEY — title`
   back to them, and only then act.
4. **Resolve ambiguity by asking.** When a description matches more than one
   item, list candidates with their keys and active tag profile, and ask.
5. **Confirm destructive ops.** Deletions, mass retags. Reads are free.
6. **Tags are conventions.** Adopt existing patterns first; if the user
   invents one, follow it *and* register it (see "Convention registry"
   below).
7. **Read with `taggy_ro`, write with `taggy_rw`.** Default to read-only.
8. **History is sacred.** Soft-delete tags via `removed_at`. Never `DELETE`.
9. **Search before filing.** Before creating a new item, look for similar
   ones; surface near-matches and let the user confirm the right action
   (file fresh, file as a child, or just tag the existing one).

## Tag vocabulary — built-in vs. team-specific

Two layers feed the agent's tag vocabulary.

**Layer 1 — Jira-sense built into CLAUDE.md.** The agent already knows that
type tags like `#bug`/`#task`/`#story`/`#epic` exist, that status values
follow `status:<value>`, that estimates use `points:<n>`, that assignees use
`@<handle>`, that sprints use `sprint:<id>`, and so on. This is the floor.

**Layer 2 — the convention registry inside the database.** When a team
invents a new prefix (a customer field, a severity scale, a RICE score,
anything the floor doesn't cover), you record it as a `convention:<prefix>`
item — same items table, no new mechanism. Anyone joining the deployment
later inherits the vocabulary the moment they connect.

Sniff both layers at the start of a tracker session. First the active tag
distribution:

```bash
psql "$TAGGY_RO" -At -c "SELECT tag, count(*) FROM tags WHERE removed_at IS NULL GROUP BY tag ORDER BY 2 DESC LIMIT 50"
```

Then the registered conventions:

```bash
psql "$TAGGY_RO" -c "SELECT key, title, body FROM items WHERE title LIKE 'convention:%' ORDER BY title"
```

When the user introduces a tag pattern that isn't in either layer, file a
`convention:<prefix>` item documenting what it means, what values are
allowed, and why it exists. The act of registering is what keeps the
vocabulary coherent across people and sessions.

### Filing a convention

```bash
PREFIX='severity'
SUMMARY='Severity of an incident: severity:sev0 (full outage) → severity:sev3 (cosmetic).'
BODY='Values: sev0=full outage, sev1=major degradation, sev2=minor degradation, sev3=cosmetic.
Apply to incident-style items. Set at file-time; revise as new info arrives.'

python3 - "$PREFIX" "$SUMMARY" "$BODY" <<'PY'
import sys, json, os, pathlib, urllib.parse, pg8000.dbapi
prefix, summary, body = sys.argv[1], sys.argv[2], sys.argv[3]
home = pathlib.Path(os.environ.get("YORPH_TAGGY_HOME") or
                    (pathlib.Path.home() / ".yorph" / "taggy"))
cfg = json.loads((home / "config.json").read_text())
p = urllib.parse.urlparse(cfg["db_url_rw"])
conn = pg8000.dbapi.connect(user=p.username, password=p.password,
                            host=p.hostname, port=p.port or 5432,
                            database=(p.path or "/").lstrip("/"))
conn.autocommit = False
cur = conn.cursor()
cur.execute(
    "INSERT INTO items (title, body, created_by) VALUES (%s, %s, %s) RETURNING key",
    (f"convention:{prefix} — {summary}", body, cfg["actor"]),
)
key = cur.fetchone()[0]
cur.execute(
    "INSERT INTO tags (item, tag, tagged_by) VALUES (%s, %s, %s)",
    (key, "#convention", cfg["actor"]),
)
conn.commit(); conn.close()
print(key)
PY
```

The `#convention` tag makes these easy to list. The title prefix
`convention:` makes them easy to find lexically too.

---

## Patterns

### Read: simple list / search

`psql` with `-At` (tuples-only, unaligned) for parseable output, or with
default formatting if you're showing the result to yourself before
narrating.

```bash
psql "$TAGGY_RO" <<'SQL'
SELECT i.key, i.title
FROM items i
JOIN tags t ON t.item = i.key AND t.removed_at IS NULL
WHERE t.tag = 'status:in-progress'
ORDER BY i.updated_at DESC
LIMIT 50;
SQL
```

For free-text search across title + body:

```bash
psql "$TAGGY_RO" -v needle="recommender" <<'SQL'
SELECT key, title
FROM items
WHERE title ILIKE '%' || :'needle' || '%'
   OR body  ILIKE '%' || :'needle' || '%'
ORDER BY updated_at DESC
LIMIT 50;
SQL
```

`:'needle'` is psql's safe variable interpolation — it quotes and escapes the
value as a SQL string literal. Use this whenever the agent passes a value
that may contain quotes.

### Read: items with their full active tag set

```bash
psql "$TAGGY_RO" <<'SQL'
SELECT i.key, i.title,
       string_agg(t.tag, ' ' ORDER BY t.tag) AS tags
FROM items i
LEFT JOIN tags t ON t.item = i.key AND t.removed_at IS NULL
WHERE i.key = ANY(string_to_array('42,57,113', ','))
GROUP BY i.key, i.title;
SQL
```

### Read: search-for-similar (run this before filing)

Before creating a new item, hunt for near-matches. The user often doesn't
know — or doesn't remember — that a similar item already exists. Three
passes, in order:

1. **Direct text overlap** on title or body (ILIKE on the most distinctive
   noun in the user's description).
2. **Same project + same type** if the user named a project: pull recent
   items in that project that share the type tag they're about to use.
3. **Recent traffic** if neither of those returns much: items
   `tagged_at`-touched in the last 14 days.

```bash
psql "$TAGGY_RO" -v needle='cookie' -v proj='proj:auth' <<'SQL'
SELECT i.key, i.title,
       coalesce(string_agg(t.tag, ' ' ORDER BY t.tag), '') AS tags
FROM items i
LEFT JOIN tags t ON t.item = i.key AND t.removed_at IS NULL
WHERE (i.title ILIKE '%' || :'needle' || '%'
    OR i.body  ILIKE '%' || :'needle' || '%')
   OR i.key IN (SELECT item FROM tags WHERE tag = :'proj' AND removed_at IS NULL)
GROUP BY i.key, i.title, i.updated_at
ORDER BY i.updated_at DESC
LIMIT 10;
SQL
```

If anything plausibly related comes back:

- Show the matches as `#KEY — title (active tags)`.
- Ask: file fresh, file as a child of one of these (`parent` link), or just
  tag the existing item with what's new (e.g. add a comment item under it,
  or escalate priority)?

If the user files fresh anyway, **link forward** by adding a `relates:<key>`
tag pointing at the closest match. That preserves the cross-reference even
when the items are conceptually distinct.

### Write: file a new item

Writes go through `pg8000` so arbitrary user content (multi-line bodies,
quotes, dollar signs, newlines) round-trips safely as a parameter — no
shell-escaping landmines. Values are passed as **positional args** to
`python3 -`, not as env vars (a bash assignment without `export` would not
reach the subprocess).

```bash
TITLE='login redirect drops the next param after SSO'
BODY='When users hit /login?next=/foo, the redirect after SSO returns them to /, not /foo. Likely the cookie write strips the query string.'
TAGS='#bug p1 status:backlog @alice proj:auth'

python3 - "$TITLE" "$BODY" "$TAGS" <<'PY'
import sys, json, os, pathlib, urllib.parse, pg8000.dbapi
title, body, tags_str = sys.argv[1], sys.argv[2] or None, sys.argv[3]
home = pathlib.Path(os.environ.get("YORPH_TAGGY_HOME") or
                    (pathlib.Path.home() / ".yorph" / "taggy"))
cfg = json.loads((home / "config.json").read_text())
p = urllib.parse.urlparse(cfg["db_url_rw"])
conn = pg8000.dbapi.connect(user=p.username, password=p.password,
                            host=p.hostname, port=p.port or 5432,
                            database=(p.path or "/").lstrip("/"))
conn.autocommit = False
cur = conn.cursor()
actor = cfg["actor"]
cur.execute(
    "INSERT INTO items (title, body, created_by) VALUES (%s, %s, %s) RETURNING key",
    (title, body, actor),
)
key = cur.fetchone()[0]
for t in tags_str.split():
    cur.execute(
        "INSERT INTO tags (item, tag, tagged_by) VALUES (%s, %s, %s)",
        (key, t, actor),
    )
conn.commit(); conn.close()
print(key)
PY
```

The script prints the new key. Narrate to the user as `#<KEY> — <title>`.

### Write: child item (comment, sub-task, doc page)

Same as filing, but set `parent`. Tag the parent's type as appropriate
(`#comment`, `#subtask`, `#code-update`, `#doc`).

```bash
PARENT=42
TITLE='alice: looked into the cookie write — confirmed the issue, fix in #57'
BODY=''
TAGS='#comment'

python3 - "$PARENT" "$TITLE" "$BODY" "$TAGS" <<'PY'
import sys, json, os, pathlib, urllib.parse, pg8000.dbapi
parent, title, body, tags_str = sys.argv[1], sys.argv[2], sys.argv[3] or None, sys.argv[4]
home = pathlib.Path(os.environ.get("YORPH_TAGGY_HOME") or
                    (pathlib.Path.home() / ".yorph" / "taggy"))
cfg = json.loads((home / "config.json").read_text())
p = urllib.parse.urlparse(cfg["db_url_rw"])
conn = pg8000.dbapi.connect(user=p.username, password=p.password,
                            host=p.hostname, port=p.port or 5432,
                            database=(p.path or "/").lstrip("/"))
conn.autocommit = False
cur = conn.cursor()
actor = cfg["actor"]
cur.execute(
    "INSERT INTO items (title, body, parent, created_by) "
    "VALUES (%s, %s, %s, %s) RETURNING key",
    (title, body, parent, actor),
)
key = cur.fetchone()[0]
for t in tags_str.split():
    cur.execute(
        "INSERT INTO tags (item, tag, tagged_by) VALUES (%s, %s, %s)",
        (key, t, actor),
    )
conn.commit(); conn.close()
print(key)
PY
```

### Write: tag an existing item

Idempotent — if the active tag already exists, do nothing. Otherwise insert.

```bash
KEY=42
TAG='status:in-progress'

python3 - "$KEY" "$TAG" <<'PY'
import sys, json, os, pathlib, urllib.parse, pg8000.dbapi
key, tag = sys.argv[1], sys.argv[2]
home = pathlib.Path(os.environ.get("YORPH_TAGGY_HOME") or
                    (pathlib.Path.home() / ".yorph" / "taggy"))
cfg = json.loads((home / "config.json").read_text())
p = urllib.parse.urlparse(cfg["db_url_rw"])
conn = pg8000.dbapi.connect(user=p.username, password=p.password,
                            host=p.hostname, port=p.port or 5432,
                            database=(p.path or "/").lstrip("/"))
conn.autocommit = False
cur = conn.cursor()
cur.execute(
    "INSERT INTO tags (item, tag, tagged_by) VALUES (%s, %s, %s) "
    "ON CONFLICT DO NOTHING",  # partial unique index dedups while active
    (key, tag, cfg["actor"]),
)
conn.commit(); conn.close()
PY
```

> The partial unique index `(item, tag) WHERE removed_at IS NULL` makes
> `ON CONFLICT DO NOTHING` skip when the tag is already actively present.

### Write: retag (replace one status / sprint / assignee with another)

The convention: the same prefix may have only one active value at a time. To
move `#42` from `status:backlog` to `status:in-progress`, soft-delete the old
status tag(s) and insert the new one — in a single transaction.

```bash
KEY=42
PREFIX='status:'
NEW_TAG='status:in-progress'

python3 - "$KEY" "$PREFIX" "$NEW_TAG" <<'PY'
import sys, json, os, pathlib, urllib.parse, pg8000.dbapi
key, prefix, new_tag = sys.argv[1], sys.argv[2], sys.argv[3]
home = pathlib.Path(os.environ.get("YORPH_TAGGY_HOME") or
                    (pathlib.Path.home() / ".yorph" / "taggy"))
cfg = json.loads((home / "config.json").read_text())
p = urllib.parse.urlparse(cfg["db_url_rw"])
conn = pg8000.dbapi.connect(user=p.username, password=p.password,
                            host=p.hostname, port=p.port or 5432,
                            database=(p.path or "/").lstrip("/"))
conn.autocommit = False
cur = conn.cursor()
actor = cfg["actor"]
cur.execute(
    "UPDATE tags SET removed_at = now(), removed_by = %s "
    "WHERE item = %s AND tag LIKE %s AND removed_at IS NULL "
    "  AND tag <> %s",
    (actor, key, prefix + "%", new_tag),
)
cur.execute(
    "INSERT INTO tags (item, tag, tagged_by) VALUES (%s, %s, %s) "
    "ON CONFLICT DO NOTHING",
    (key, new_tag, actor),
)
conn.commit(); conn.close()
PY
```

Pick `PREFIX` based on the concept being replaced:

| Concept | PREFIX | Notes |
|---|---|---|
| Status | `status:` | one active status at a time |
| Sprint | `sprint:` | usually one active sprint |
| Release | `release:` | one active release |
| Project | `proj:` | one project — but cross-project is allowed; ask |
| Estimate | `points:` | one active estimate |
| Priority | `p` | bare `p0`/`p1`/… → use a different idiom (below) |

For priority (bare `p0..p3`, no colon), filter on `tag ~ '^p[0-9]+$'`:

```bash
# soft-delete prior priority tags before inserting new one
cur.execute(
    "UPDATE tags SET removed_at = now(), removed_by = %s "
    "WHERE item = %s AND tag ~ '^p[0-9]+$' AND removed_at IS NULL "
    "  AND tag <> %s",
    (cfg["actor"], key, new_tag),
)
```

For assignee (`@<handle>`), filter on `tag LIKE '@%'`. Ask first if you're
about to *replace* the assignee vs. *add* a co-assignee — both are common.

### Write: untag (soft-delete one tag)

```bash
KEY=42
TAG='@alice'

python3 - "$KEY" "$TAG" <<'PY'
import sys, json, os, pathlib, urllib.parse, pg8000.dbapi
key, tag = sys.argv[1], sys.argv[2]
home = pathlib.Path(os.environ.get("YORPH_TAGGY_HOME") or
                    (pathlib.Path.home() / ".yorph" / "taggy"))
cfg = json.loads((home / "config.json").read_text())
p = urllib.parse.urlparse(cfg["db_url_rw"])
conn = pg8000.dbapi.connect(user=p.username, password=p.password,
                            host=p.hostname, port=p.port or 5432,
                            database=(p.path or "/").lstrip("/"))
conn.autocommit = False
cur = conn.cursor()
cur.execute(
    "UPDATE tags SET removed_at = now(), removed_by = %s "
    "WHERE item = %s AND tag = %s AND removed_at IS NULL",
    (cfg["actor"], key, tag),
)
conn.commit(); conn.close()
PY
```

### Write: edit title or body

Pass an empty string for any field you don't want to change.

```bash
KEY=42
TITLE='login redirect drops the next param after SSO'
BODY='Updated repro: only happens when the cookie domain is set to .example.com.'

python3 - "$KEY" "$TITLE" "$BODY" <<'PY'
import sys, json, os, pathlib, urllib.parse, pg8000.dbapi
key, title, body = sys.argv[1], sys.argv[2], sys.argv[3]
home = pathlib.Path(os.environ.get("YORPH_TAGGY_HOME") or
                    (pathlib.Path.home() / ".yorph" / "taggy"))
cfg = json.loads((home / "config.json").read_text())
p = urllib.parse.urlparse(cfg["db_url_rw"])
conn = pg8000.dbapi.connect(user=p.username, password=p.password,
                            host=p.hostname, port=p.port or 5432,
                            database=(p.path or "/").lstrip("/"))
conn.autocommit = False
cur = conn.cursor()
fields, values = [], []
if title:
    fields.append("title = %s"); values.append(title)
if body:
    fields.append("body = %s"); values.append(body)
if not fields:
    sys.exit("nothing to update")
values.append(key)
cur.execute(f"UPDATE items SET {', '.join(fields)} WHERE key = %s", values)
conn.commit(); conn.close()
PY
```

`updated_at` is bumped automatically by the trigger.

---

## Resolving "the login bug"

When the user references an item by description rather than key:

1. Try a tight ILIKE on `title` first (most common case).
2. If 0 hits, broaden to title + body and to active tags.
3. If 0 still, ask for more detail.
4. If 2+ hits, list candidates as `#KEY — title (active tags)` and ask.
5. Do not silently pick.

```bash
psql "$TAGGY_RO" -v needle='login' <<'SQL'
SELECT i.key, i.title,
       coalesce(string_agg(t.tag, ' ' ORDER BY t.tag), '') AS tags
FROM items i
LEFT JOIN tags t ON t.item = i.key AND t.removed_at IS NULL
WHERE i.title ILIKE '%' || :'needle' || '%'
   OR i.body  ILIKE '%' || :'needle' || '%'
GROUP BY i.key, i.title
ORDER BY i.updated_at DESC
LIMIT 10;
SQL
```

---

## "What changed on #42 this week"

```bash
psql "$TAGGY_RO" -v key='42' -v window='7 days' <<'SQL'
SELECT 'added'   AS event, tag, tagged_by   AS who, tagged_at   AS at FROM tags
WHERE item = :'key' AND tagged_at  > now() - interval :'window'
UNION ALL
SELECT 'removed' AS event, tag, removed_by  AS who, removed_at  AS at FROM tags
WHERE item = :'key' AND removed_at IS NOT NULL
                   AND removed_at > now() - interval :'window'
ORDER BY at;
SQL
```

Narrate as a bullet list grouped by day, e.g. "Mon: alice moved it to
in-progress and bumped priority to p1."

---

## "Tickets and docs related to project X"

Three unions, dedup on `key`:

```bash
psql "$TAGGY_RO" -v needle='recommender' <<'SQL'
WITH by_tag AS (
  SELECT i.key
  FROM items i
  JOIN tags t ON t.item = i.key AND t.removed_at IS NULL
  WHERE t.tag IN ('#' || :'needle', 'proj:' || :'needle')
), by_text AS (
  SELECT key FROM items
  WHERE title ILIKE '%' || :'needle' || '%'
     OR body  ILIKE '%' || :'needle' || '%'
), by_parent AS (
  WITH RECURSIVE chain(key, parent) AS (
    SELECT key, parent FROM items WHERE key IN (SELECT key FROM by_tag UNION SELECT key FROM by_text)
    UNION ALL
    SELECT i.key, i.parent FROM items i JOIN chain c ON i.parent = c.key
  )
  SELECT key FROM chain
), all_keys AS (
  SELECT key FROM by_tag UNION SELECT key FROM by_text UNION SELECT key FROM by_parent
)
SELECT i.key, i.title,
       coalesce(string_agg(t.tag, ' ' ORDER BY t.tag), '') AS tags,
       length(coalesce(i.body, '')) AS body_len
FROM items i
LEFT JOIN tags t ON t.item = i.key AND t.removed_at IS NULL
WHERE i.key IN (SELECT key FROM all_keys)
GROUP BY i.key, i.title, i.body
ORDER BY i.updated_at DESC;
SQL
```

When narrating, group results by their tag profile: "**Tickets** (carry
`#bug` / `#task`)", "**Docs** (carry `#doc` or have long bodies)",
"**Discussion** (everything else)". Render each as `#KEY — title` with a
two-line body snippet.

---

## "Update ticket descriptions based on the code changes"

You're inside Claude Code, so `git` is in the same session. Workflow:

1. Read the commit range the user wants. Default to "since the most recent
   commit on the main branch":
   ```bash
   git log --since='1 day' --pretty='%h %s' main..HEAD || git log --since='1 day' --pretty='%h %s'
   ```
2. For each commit, scrape `#<digits>` references from the message and from
   `git show <hash>` (file paths can hint too).
3. For each referenced item: append a child item with `parent = <key>` and
   tag `#code-update`. Body = a one-paragraph summary of what changed (files
   touched, behavior delta) plus the commit hash. *Don't* mutate the parent
   body unless the user explicitly asks.
4. Show the user the diff (per-item: which child you added) before
   committing the writes. They may want to edit summaries.

This preserves the original description and keeps history traceable.

---

## Rendering rules

- Always include `#KEY` in front of titles, with an em-dash separator.
- For lists: `- #KEY — title  (#bug, p1, status:in-progress, @alice)`
- For tables: keep columns short — Key, Title, Status, Assignee, Points.
- For prose summaries: lead with the count and the headline ("4 items
  changed last week, all in `proj:auth` …"). One paragraph max. Then the
  list.
- Truncate bodies to ~160 chars in lists, full body when the user asks for
  one item.
- Never paste raw SQL or Python at the user. If they ask "how did you do
  that", explain in plain language; only show code if they explicitly want
  it.

## Confirmation rules

Confirm before:
- Deleting an item (`DELETE FROM items WHERE key = …`).
- Removing more than ~5 tags in one operation.
- Mass retags spanning more than ~10 items.
- Editing a body that's longer than ~500 chars (in case you'd be clobbering
  someone's careful prose).

Skip confirmation for:
- Reads.
- Single tag adds/removes.
- Editing a title or short body.
- Filing a new item.
