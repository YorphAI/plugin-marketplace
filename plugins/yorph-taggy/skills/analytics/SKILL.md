---
name: analytics
description: Aggregate, time-window, and chart queries against the yorph-taggy tag history. Use when the user asks for a burndown, velocity, cumulative flow, "story points by engineer over the last N sprints", "what shipped in release X", "throughput", "cycle time", "time in status", or any chart/graph that summarizes the tag history. Loads matplotlib patterns and tag-window SQL idioms. Do NOT use for filing/finding/tagging individual items (use yorph-taggy:tracker) or first-time install (use yorph-taggy:setup).
---

# Analytics — yorph-taggy

The `tags` table preserves every state transition with `tagged_at` and
`removed_at`. Burndowns, cumulative-flow diagrams, velocity, cycle time, and
"as of last Friday" queries all fall out of windowed scans against that one
table. Reads only — always use `$TAGGY_RO`.

## Preamble

```bash
PLUGIN_DIR="$(ls -d "$HOME"/Documents/Yorph/yorph-marketplace/plugins/yorph-taggy 2>/dev/null \
              || ls -d /Applications/Claude/plugins/yorph-taggy 2>/dev/null)"
. "$PLUGIN_DIR/bin/taggy-env"
python3 -c "import matplotlib" 2>/dev/null || pip install --quiet matplotlib
```

`matplotlib` is the only extra dep beyond what `setup` installed. Install on
first use; subsequent runs are a no-op.

## The one idiom every analytics query uses

A tag is **active at time `T`** when:

```sql
tagged_at <= T AND (removed_at IS NULL OR removed_at > T)
```

This is the engine. Every burndown, CFD, time-in-status, "as-of" snapshot,
and historical roll-up uses it.

To filter to *currently* active tags, use the simpler form:

```sql
removed_at IS NULL
```

## Output styles

- **Numbers / small tables** — return as a markdown table.
- **Time series ≥ 5 points** — render a chart with matplotlib. Save to
  `~/.yorph/taggy/charts/<slug>-<yyyymmdd-hhmmss>.png`, show the user the
  path, and narrate one paragraph explaining the shape.
- **Always lead with the headline.** ("Velocity is up 30% sprint over
  sprint." Then the chart. Then the table.)

Chart directory:

```bash
mkdir -p "${YORPH_TAGGY_HOME:-$HOME/.yorph/taggy}/charts"
```

---

## Pattern: items "in status X" as of time T

```bash
psql "$TAGGY_RO" -v as_of='2026-04-15' -v status='status:in-progress' <<'SQL'
SELECT i.key, i.title
FROM items i
JOIN tags t ON t.item = i.key
WHERE t.tag = :'status'
  AND t.tagged_at <= :'as_of'::timestamptz
  AND (t.removed_at IS NULL OR t.removed_at > :'as_of'::timestamptz);
SQL
```

## Pattern: cumulative flow diagram

For each date in a window, count items where each `status:*` tag was active.
SQL emits a long-format result; matplotlib stacks it.

```bash
WINDOW_START='2026-03-01'
WINDOW_END='2026-04-15'

psql "$TAGGY_RO" -v ws="$WINDOW_START" -v we="$WINDOW_END" -At -F$'\t' <<'SQL' > /tmp/taggy-cfd.tsv
WITH days AS (
  SELECT generate_series(:'ws'::date, :'we'::date, interval '1 day')::date AS d
),
statuses AS (
  SELECT DISTINCT tag FROM tags WHERE tag LIKE 'status:%'
)
SELECT d.d::text, s.tag, count(*) FILTER (
  WHERE t.tagged_at <= d.d + interval '1 day'
    AND (t.removed_at IS NULL OR t.removed_at > d.d + interval '1 day')
)
FROM days d
CROSS JOIN statuses s
LEFT JOIN tags t ON t.tag = s.tag
GROUP BY d.d, s.tag
ORDER BY d.d, s.tag;
SQL

python3 - <<'PY'
import csv, os, pathlib
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime

rows = list(csv.reader(open("/tmp/taggy-cfd.tsv"), delimiter="\t"))
days = sorted({r[0] for r in rows})
statuses = sorted({r[1] for r in rows})
series = defaultdict(lambda: [0]*len(days))
day_idx = {d: i for i, d in enumerate(days)}
for d, s, n in rows:
    series[s][day_idx[d]] = int(n)

x = [datetime.fromisoformat(d) for d in days]
fig, ax = plt.subplots(figsize=(10, 5))
ax.stackplot(x, [series[s] for s in statuses], labels=statuses, alpha=0.85)
ax.legend(loc="upper left", fontsize=8)
ax.set_title("Cumulative flow")
ax.set_ylabel("Items")
fig.autofmt_xdate()

out_dir = pathlib.Path(os.environ.get("YORPH_TAGGY_HOME") or
                       (pathlib.Path.home() / ".yorph" / "taggy")) / "charts"
out_dir.mkdir(parents=True, exist_ok=True)
out = out_dir / f"cfd-{datetime.now():%Y%m%d-%H%M%S}.png"
fig.savefig(out, dpi=140, bbox_inches="tight")
print(out)
PY
```

When narrating, look for the bottleneck: a status whose band is fattening
faster than the rest. "Review queue is growing while done is flat — review
capacity is the limiter." Don't make the user squint at the chart.

## Pattern: sprint burndown (remaining points by day)

Story points live as `points:N` tags. Sprint membership lives as `sprint:<id>`.
A point is **outstanding on day D** if its item was in-sprint on D and the
item was not yet `status:done`.

```bash
SPRINT='sprint:2026-q2-w1'
SPRINT_START='2026-04-07'
SPRINT_END='2026-04-18'

psql "$TAGGY_RO" -v sprint="$SPRINT" -v ss="$SPRINT_START" -v se="$SPRINT_END" -At -F$'\t' <<'SQL' > /tmp/taggy-burn.tsv
WITH days AS (
  SELECT generate_series(:'ss'::date, :'se'::date, interval '1 day')::date AS d
),
points AS (
  -- For each item, the most-recently-added active points tag at each day.
  -- Take the integer suffix.
  SELECT t.item,
         (regexp_replace(t.tag, '^points:', ''))::int AS pts,
         t.tagged_at, t.removed_at
  FROM tags t
  WHERE t.tag LIKE 'points:%'
)
SELECT d.d::text,
       coalesce(sum(p.pts), 0) AS remaining
FROM days d
LEFT JOIN tags s ON s.tag = :'sprint'
                AND s.tagged_at <= d.d + interval '1 day'
                AND (s.removed_at IS NULL OR s.removed_at > d.d + interval '1 day')
LEFT JOIN points p ON p.item = s.item
                  AND p.tagged_at <= d.d + interval '1 day'
                  AND (p.removed_at IS NULL OR p.removed_at > d.d + interval '1 day')
LEFT JOIN tags done ON done.item = s.item AND done.tag = 'status:done'
                   AND done.tagged_at <= d.d + interval '1 day'
                   AND (done.removed_at IS NULL OR done.removed_at > d.d + interval '1 day')
WHERE done.id IS NULL  -- exclude items already done by D
GROUP BY d.d
ORDER BY d.d;
SQL

python3 - <<'PY'
import csv, os, pathlib
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

rows = list(csv.reader(open("/tmp/taggy-burn.tsv"), delimiter="\t"))
days = [datetime.fromisoformat(r[0]) for r in rows]
remaining = [int(r[1]) for r in rows]

start = remaining[0] if remaining else 0
ideal = [start * (1 - i / max(1, len(remaining)-1)) for i in range(len(remaining))]

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(days, remaining, marker="o", label="actual")
ax.plot(days, ideal, linestyle="--", alpha=0.6, label="ideal")
ax.set_title(f"Burndown ({os.environ.get('SPRINT','')})")
ax.set_ylabel("Points remaining"); ax.legend()
fig.autofmt_xdate()

out = pathlib.Path(os.environ.get("YORPH_TAGGY_HOME") or
                   (pathlib.Path.home() / ".yorph" / "taggy")) / "charts" / \
      f"burndown-{datetime.now():%Y%m%d-%H%M%S}.png"
out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out, dpi=140, bbox_inches="tight")
print(out)
PY
```

Narration: compare actual vs. ideal. Flag flat stretches (no progress) and
late-sprint cliffs (large drop in last 1–2 days = work being marked done in
batches, not steadily).

## Pattern: story points by engineer over last N sprints

```bash
psql "$TAGGY_RO" -v n='4' <<'SQL'
WITH recent_sprints AS (
  SELECT DISTINCT tag, max(tagged_at) AS last_seen
  FROM tags
  WHERE tag LIKE 'sprint:%' AND removed_at IS NULL
  GROUP BY tag
  ORDER BY last_seen DESC
  LIMIT :'n'::int
),
items_in_sprint AS (
  SELECT s.tag AS sprint, t.item
  FROM recent_sprints s
  JOIN tags t ON t.tag = s.tag AND t.removed_at IS NULL
),
assignees AS (
  SELECT item, tag AS handle FROM tags
  WHERE tag LIKE '@%' AND removed_at IS NULL
),
points AS (
  SELECT item, (regexp_replace(tag, '^points:', ''))::int AS pts FROM tags
  WHERE tag LIKE 'points:%' AND removed_at IS NULL
)
SELECT a.handle, i.sprint, coalesce(sum(p.pts), 0) AS pts
FROM items_in_sprint i
JOIN assignees a ON a.item = i.item
LEFT JOIN points p ON p.item = i.item
GROUP BY a.handle, i.sprint
ORDER BY i.sprint, a.handle;
SQL
```

Format as a markdown pivot: rows = engineers, columns = sprints (oldest to
newest). Headline the trend: "Alice's velocity is climbing; Bob's dipped two
sprints ago and recovered."

## Pattern: time-in-status (cycle time)

For each item that hit `status:done` in the window, compute how long it
spent in `status:in-progress` end-to-end (sum of all interval(s) that tag
was active).

```bash
psql "$TAGGY_RO" -v ws='2026-03-01' -v we='2026-04-15' <<'SQL'
WITH done_in_window AS (
  SELECT item FROM tags
  WHERE tag = 'status:done'
    AND tagged_at >= :'ws'::timestamptz
    AND tagged_at <  :'we'::timestamptz
    AND removed_at IS NULL
),
in_progress_intervals AS (
  SELECT item,
         coalesce(removed_at, now()) - tagged_at AS span
  FROM tags
  WHERE tag = 'status:in-progress'
)
SELECT i.key, i.title,
       sum(p.span) AS total_in_progress,
       extract(epoch FROM sum(p.span)) / 3600 AS hours
FROM done_in_window d
JOIN in_progress_intervals p ON p.item = d.item
JOIN items i ON i.key = d.item
GROUP BY i.key, i.title
ORDER BY total_in_progress DESC;
SQL
```

Headline: median, p90, top three slowest items.

## Pattern: what shipped in release X

```bash
psql "$TAGGY_RO" -v rel='release:2026-w16' <<'SQL'
SELECT i.key, i.title,
       coalesce(string_agg(t.tag, ' ' ORDER BY t.tag) FILTER (WHERE t.tag LIKE 'proj:%' OR t.tag LIKE '#%'), '') AS labels,
       (SELECT tagged_by FROM tags WHERE item = i.key AND tag = :'rel' AND removed_at IS NULL LIMIT 1) AS shipped_by
FROM items i
JOIN tags r ON r.item = i.key AND r.tag = :'rel' AND r.removed_at IS NULL
LEFT JOIN tags t ON t.item = i.key AND t.removed_at IS NULL
GROUP BY i.key, i.title
ORDER BY i.key::int;
SQL
```

Group by `proj:*` in narration. Lead with a count and a one-paragraph
summary that pulls from item bodies. Then the bulleted list of
`#KEY — title`.

---

## "Show me my team"

A team can be modeled two ways. Sniff which the team uses before assuming:

```bash
psql "$TAGGY_RO" -At -c "
SELECT
  (SELECT count(*) FROM tags WHERE tag LIKE 'team:%' AND removed_at IS NULL) AS team_tags,
  (SELECT count(*) FROM items WHERE key IN (SELECT item FROM tags WHERE tag LIKE 'team:%')) AS items_with_team_tag"
```

- **Mode A**: items carry `team:<slug>` tags directly. Filter by that tag.
- **Mode B**: a meta-item with title `team:<slug>` exists; its active
  `@<handle>` tags are the members. Filter items to those whose `@<handle>`
  matches a member.

If neither mode is in use, ask the user how they want to define their team.

---

## Saving generated charts

Every chart goes to `${YORPH_TAGGY_HOME:-$HOME/.yorph/taggy}/charts/`. Show
the user the absolute path so they can open it. Don't try to embed PNGs in
chat — pasting the file path is cleaner.
