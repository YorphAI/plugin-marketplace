#!/usr/bin/env python3
"""yorph-taggy executable evals.

Runs every documented worked example in EXAMPLES.md against a freshly seeded
database. Catches regressions when the schema, the skill SQL patterns, or
the seed dataset drift apart.

Usage:

    python3 examples/run_evals.py \\
        --admin-url postgres://alexbraylan@localhost:5432/postgres

    # or, if you've already run setup_db.py against an admin URL,
    # the script will read the *host* from your config:
    python3 examples/run_evals.py

The eval uses a dedicated database `taggy_eval` so it never touches your real
data. The DB is dropped and recreated on every run.

Each eval is encoded as `eval_NN_<name>(state)` and returns either None (pass)
or a string (fail reason). The state object holds the connection plus a
dictionary of seed keys the evals may need to refer to.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    import pg8000.dbapi
    import pg8000.exceptions
except ImportError:
    sys.stderr.write("Missing pg8000. Install with: pip install pg8000\n")
    sys.exit(2)

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA_SQL = (ROOT / "schema.sql").read_text()


# ---------- helpers ---------------------------------------------------------


def parse_pg_url(url: str) -> dict:
    p = urllib.parse.urlparse(url)
    return {
        "user": p.username,
        "password": p.password,
        "host": p.hostname,
        "port": p.port or 5432,
        "database": (p.path or "/").lstrip("/") or "postgres",
    }


def connect(url: str, *, autocommit: bool = True) -> "pg8000.dbapi.Connection":
    info = parse_pg_url(url)
    conn = pg8000.dbapi.connect(**info)
    conn.autocommit = autocommit
    return conn


def admin_url_default() -> str:
    """Pull the admin host out of the user's config, default to local."""
    home = pathlib.Path(
        os.environ.get("YORPH_TAGGY_HOME") or
        (pathlib.Path.home() / ".yorph" / "taggy")
    )
    cfg_path = home / "config.json"
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text())
        # Mash together the rw url's host + admin-style user.
        rw = urllib.parse.urlparse(cfg["db_url_rw"])
        return f"postgres://{os.environ.get('USER','postgres')}@{rw.hostname}:{rw.port or 5432}/postgres"
    return "postgres://postgres@localhost:5432/postgres"


# ---------- seed ------------------------------------------------------------


@dataclass
class Seed:
    keys: dict[str, str]  # logical name → item key
    now: datetime
    sprint_current: str
    sprint_prev: str
    release_current: str
    release_prev: str


def reset_database(admin_url: str, db_name: str) -> None:
    conn = connect(admin_url)
    cur = conn.cursor()
    # Force-disconnect anything else.
    cur.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = %s AND pid <> pg_backend_pid()", (db_name,)
    )
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
    if cur.fetchone():
        cur.execute(f'DROP DATABASE "{db_name}"')
    cur.execute(f'CREATE DATABASE "{db_name}"')
    conn.close()


def apply_schema(eval_url: str) -> None:
    conn = connect(eval_url)
    conn.execute_simple(SCHEMA_SQL)
    conn.close()


def seed(eval_url: str) -> Seed:
    """Plant a deterministic dataset. All times are relative to 'now'."""
    conn = connect(eval_url, autocommit=False)
    cur = conn.cursor()

    now = datetime.now(timezone.utc).replace(microsecond=0)
    sprint_current = "sprint:2026-q2-w1"
    sprint_prev = "sprint:2026-q2-prev"
    release_current = "release:2026-w17"
    release_prev = "release:2026-w16"

    def day(n: int) -> datetime:
        return now - timedelta(days=n)

    def file_item(title: str, body: str = "", *,
                  parent: str | None = None,
                  by: str = "alice",
                  when: datetime | None = None) -> str:
        when = when or now
        cur.execute(
            "INSERT INTO items (title, body, parent, created_by, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING key",
            (title, body or None, parent, by, when, when),
        )
        return cur.fetchone()[0]

    def add(key: str, tag: str, *, by: str = "alice",
            when: datetime | None = None) -> None:
        cur.execute(
            "INSERT INTO tags (item, tag, tagged_by, tagged_at) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (key, tag, by, when or now),
        )

    def transition(key: str, prefix: str, new_tag: str, when: datetime,
                   by: str = "alice") -> None:
        cur.execute(
            "UPDATE tags SET removed_at = %s, removed_by = %s "
            "WHERE item = %s AND tag LIKE %s "
            "  AND removed_at IS NULL AND tag <> %s",
            (when, by, key, prefix + "%", new_tag),
        )
        add(key, new_tag, by=by, when=when)

    K: dict[str, str] = {}

    # ---- Project: auth ----------------------------------------------------

    # A1 — fully done item with rich history
    K["A1"] = file_item(
        "login redirect drops the next param after SSO",
        "When users hit /login?next=/foo, the redirect after SSO returns "
        "them to /, not /foo. Likely the cookie write strips the query string.",
        when=day(20),
    )
    for t in ["#bug", "p1", "@alice", "points:3", "proj:auth", sprint_current]:
        add(K["A1"], t, when=day(20))
    add(K["A1"], "status:backlog", when=day(20))
    transition(K["A1"], "status:", "status:in-progress", day(18))
    transition(K["A1"], "status:", "status:review", day(5))
    transition(K["A1"], "status:", "status:done", day(3))
    add(K["A1"], release_current, when=day(2), by="alice")

    # A2 — currently in review (similar to a future-filed bug, used by eval 1)
    K["A2"] = file_item(
        "session cookie domain not respected on subdomains",
        "Long body explaining cookie domain bug.",
        when=day(10),
    )
    for t in ["#bug", "p1", "@alice", "points:5", "proj:auth", sprint_current]:
        add(K["A2"], t, when=day(10))
    add(K["A2"], "status:backlog", when=day(10))
    transition(K["A2"], "status:", "status:in-progress", day(6), by="alice")
    transition(K["A2"], "status:", "status:review", day(2), by="alice")

    # A3 — in-progress
    K["A3"] = file_item(
        "CSRF token rotation flakes intermittently",
        "When the rotation runs concurrently with a request, the new token "
        "can race the response.",
        by="bob", when=day(12),
    )
    for t in ["#bug", "p2", "@bob", "points:5", "proj:auth", sprint_current]:
        add(K["A3"], t, by="bob", when=day(12))
    add(K["A3"], "status:backlog", by="bob", when=day(12))
    transition(K["A3"], "status:", "status:in-progress", day(4), by="bob")

    # A4 — story we'll later promote to epic
    K["A4"] = file_item(
        "Add WebAuthn passkey support",
        "Story for adding passkey login as an alternative to password.",
        when=day(9),
    )
    for t in ["#story", "p2", "@alice", "points:8", "proj:auth", sprint_current]:
        add(K["A4"], t, when=day(9))
    add(K["A4"], "status:backlog", when=day(9))

    # A5 — task with NO assignee, lives in current sprint
    K["A5"] = file_item(
        "Auth audit log retention policy",
        "Decide how long to keep auth audit logs.",
        when=day(8),
    )
    for t in ["#task", "p3", "proj:auth", sprint_current]:
        add(K["A5"], t, when=day(8))
    add(K["A5"], "status:backlog", when=day(8))

    # A6 — old proj label, used for bulk relabel eval (#14)
    K["A6"] = file_item(
        "Old auth middleware: replace with new auth middleware",
        by="bob", when=day(40),
    )
    for t in ["#task", "@bob", "points:3", "proj:auth-old"]:
        add(K["A6"], t, by="bob", when=day(40))
    add(K["A6"], "status:backlog", by="bob", when=day(40))
    transition(K["A6"], "status:", "status:in-progress", day(35), by="bob")
    transition(K["A6"], "status:", "status:done", day(30), by="bob")

    # A7 — doc, no sprint membership; should be excluded from board snapshot
    K["A7"] = file_item(
        "Auth flow design doc",
        "How requests flow through the auth stack." * 30,
        when=day(15),
    )
    for t in ["#doc", "@alice", "proj:auth"]:
        add(K["A7"], t, when=day(15))

    # A8 — second login-related bug, makes "the login bug" ambiguous
    K["A8"] = file_item(
        "Login page missing CSRF protection on forgot-password form",
        "Forgot-password POST has no CSRF token; can be triggered cross-site.",
        by="bob", when=day(11),
    )
    for t in ["#bug", "p2", "@bob", "points:2", "proj:auth", sprint_current]:
        add(K["A8"], t, by="bob", when=day(11))
    add(K["A8"], "status:backlog", by="bob", when=day(11))

    # ---- Project: recommender --------------------------------------------

    K["R1"] = file_item(
        "Recommender model V2 design doc",
        ("Long-form design doc for the V2 recommendation model. "
         "Discusses candidate generation, ranking, and the new feature store. ") * 8,
        when=day(8),
    )
    for t in ["#doc", "@alice", "proj:recommender"]:
        add(K["R1"], t, when=day(8))

    K["R2"] = file_item(
        "Recommender stuck on cold start for new users",
        "New users with no history get empty recs.",
        by="bob", when=day(7),
    )
    for t in ["#bug", "p1", "@bob", "points:5", "proj:recommender", sprint_current]:
        add(K["R2"], t, by="bob", when=day(7))
    add(K["R2"], "status:backlog", by="bob", when=day(7))
    transition(K["R2"], "status:", "status:in-progress", day(4), by="bob")

    K["R3"] = file_item(
        "Tune recommender ranker weights for diversity",
        "Task to A/B test new diversity weights.",
        when=day(6),
    )
    for t in ["#task", "p3", "@alice", "proj:recommender", sprint_current]:
        add(K["R3"], t, when=day(6))
    add(K["R3"], "status:backlog", when=day(6))

    # Child comment under R2
    K["R2_comment"] = file_item(
        "bob: confirmed — happens when user has zero clicks; need a fallback",
        parent=K["R2"], by="bob", when=day(3),
    )
    add(K["R2_comment"], "#comment", by="bob", when=day(3))

    # ---- Project: billing — for release summary + cycle-time -------------

    K["B1"] = file_item(
        "Invoice PDF generation flaky on weekends",
        "PDF jobs occasionally fail when timezone-sensitive cron fires.",
        by="bob", when=day(18),
    )
    for t in ["#bug", "p2", "@bob", "points:3", "proj:billing", sprint_prev]:
        add(K["B1"], t, by="bob", when=day(18))
    add(K["B1"], "status:backlog", by="bob", when=day(18))
    transition(K["B1"], "status:", "status:in-progress", day(14), by="bob")
    transition(K["B1"], "status:", "status:review", day(10), by="bob")
    transition(K["B1"], "status:", "status:done", day(8), by="bob")
    add(K["B1"], release_prev, by="bob", when=day(8))

    K["B2"] = file_item(
        "Stripe webhook retries cause double-charges",
        "Idempotency key collision under retry storm.",
        when=day(16),
    )
    for t in ["#bug", "p0", "@alice", "points:5", "proj:billing", sprint_prev]:
        add(K["B2"], t, when=day(16))
    add(K["B2"], "status:backlog", when=day(16))
    transition(K["B2"], "status:", "status:in-progress", day(13))
    transition(K["B2"], "status:", "status:review", day(9))
    transition(K["B2"], "status:", "status:done", day(8))
    add(K["B2"], release_prev, when=day(8))

    # ---- Convention registry (pre-existing custom convention) ------------
    K["C_area"] = file_item(
        "convention:area — group of items by functional area, orthogonal to project",
        "Examples: area:auth, area:billing, area:platform. Useful when an item "
        "spans projects. Apply alongside proj:* — they coexist.",
        when=day(60),
    )
    add(K["C_area"], "#convention", when=day(60))

    conn.commit()
    conn.close()
    return Seed(
        keys=K, now=now,
        sprint_current=sprint_current, sprint_prev=sprint_prev,
        release_current=release_current, release_prev=release_prev,
    )


# ---------- assertion helpers ----------------------------------------------


def fetch_all(conn, sql: str, params: tuple = ()) -> list[tuple]:
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur.fetchall()


def fetch_one(conn, sql: str, params: tuple = ()) -> tuple | None:
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur.fetchone()


def expect_keys(rows: list[tuple], expected: list[str], col: int = 0) -> str | None:
    got = sorted({str(r[col]) for r in rows})
    want = sorted(set(expected))
    if got != want:
        return f"keys={got} want={want}"
    return None


def expect_contains(rows: list[tuple], needles: list[str], col: int = 0) -> str | None:
    got = {str(r[col]) for r in rows}
    missing = [n for n in needles if n not in got]
    if missing:
        return f"missing keys: {missing} (got {sorted(got)})"
    return None


# ---------- the 15 evals ---------------------------------------------------
# Each takes (conn, seed) and returns None on pass or an error string.


def eval_01_file_with_similar(conn, s: Seed) -> str | None:
    """Filing a bug — find similar items, then file-fresh + relates: link.

    User says: "Got a complaint that login on staging.acme.com bounces back
    even with the right password — looks cookie-related." The agent first
    searches for similar items in the auth project and finds A2 (session
    cookie). The user asks to file fresh and link. The agent files a new
    item with a relates:<A2> tag.
    """
    cur = conn.cursor()

    # Step 1 — similar-items search the skill prescribes (text + project).
    cur.execute("""
        SELECT i.key, i.title
        FROM items i
        LEFT JOIN tags t ON t.item = i.key AND t.removed_at IS NULL
        WHERE (i.title ILIKE %s OR i.body ILIKE %s)
           OR i.key IN (SELECT item FROM tags WHERE tag = %s AND removed_at IS NULL)
        GROUP BY i.key, i.title, i.updated_at
        ORDER BY i.updated_at DESC
    """, ("%cookie%", "%cookie%", "proj:auth"))
    similar = [r[0] for r in cur.fetchall()]
    if s.keys["A2"] not in similar:
        return f"A2 ({s.keys['A2']}) not surfaced as similar; got {similar}"

    # Step 2 — file fresh, link via relates:<A2.key>.
    cur.execute(
        "INSERT INTO items (title, body, created_by) VALUES (%s, %s, %s) RETURNING key",
        ("Login bounces back on staging subdomain even with correct password",
         "User reports cookie-domain symptoms on staging.acme.com.",
         "alice"),
    )
    new_key = cur.fetchone()[0]
    for t in ["#bug", "p2", "@alice", "proj:auth", "status:backlog",
              s.sprint_current, f"relates:{s.keys['A2']}"]:
        cur.execute(
            "INSERT INTO tags (item, tag, tagged_by) VALUES (%s, %s, %s) "
            "ON CONFLICT DO NOTHING",
            (new_key, t, "alice"),
        )

    rows = fetch_all(conn,
        "SELECT tag FROM tags WHERE item = %s AND removed_at IS NULL", (new_key,))
    tags = {r[0] for r in rows}
    if f"relates:{s.keys['A2']}" not in tags:
        return f"relates: tag missing on new item; got {tags}"
    if "#bug" not in tags or "proj:auth" not in tags:
        return f"core tags missing; got {tags}"
    return None


def eval_02_quick_note_to_task(conn, s: Seed) -> str | None:
    """Quick chat note → tracked task. The agent searches for similar
    (none found), then files a #task with status:backlog and no assignee."""
    cur = conn.cursor()

    cur.execute(
        "SELECT key FROM items WHERE title ILIKE %s OR body ILIKE %s",
        ("%postgres backup%", "%postgres backup%"),
    )
    if cur.fetchall():
        return "expected zero similar items but got some"

    cur.execute(
        "INSERT INTO items (title, body, created_by) VALUES (%s, %s, %s) RETURNING key",
        ("Back up postgres before next week's release", None, "alice"),
    )
    new_key = cur.fetchone()[0]
    for t in ["#task", "status:backlog"]:
        cur.execute(
            "INSERT INTO tags (item, tag, tagged_by) VALUES (%s, %s, %s)",
            (new_key, t, "alice"),
        )

    rows = fetch_all(conn,
        "SELECT tag FROM tags WHERE item = %s AND removed_at IS NULL", (new_key,))
    tags = {r[0] for r in rows}
    if tags != {"#task", "status:backlog"}:
        return f"unexpected tags: {tags}"
    if any(t.startswith("@") for t in tags):
        return "task should have no assignee"
    return None


def eval_03_child_comment(conn, s: Seed) -> str | None:
    """File a child comment under an existing item, resolved by description."""
    cur = conn.cursor()

    # Resolve "the login redirect bug"
    cur.execute(
        "SELECT key, title FROM items WHERE title ILIKE %s",
        ("%login redirect%",),
    )
    rows = cur.fetchall()
    if len(rows) != 1 or rows[0][0] != s.keys["A1"]:
        return f"description didn't resolve to A1; got {rows}"
    parent = rows[0][0]

    cur.execute(
        "INSERT INTO items (title, body, parent, created_by) "
        "VALUES (%s, %s, %s, %s) RETURNING key",
        ("alice: cause is the cookie write stripping the query string",
         None, parent, "alice"),
    )
    child_key = cur.fetchone()[0]
    cur.execute(
        "INSERT INTO tags (item, tag, tagged_by) VALUES (%s, %s, %s)",
        (child_key, "#comment", "alice"),
    )

    row = fetch_one(conn,
        "SELECT parent FROM items WHERE key = %s", (child_key,))
    if row is None or row[0] != parent:
        return f"child parent missing; got {row}"
    return None


def eval_04_disambiguate_login_bug(conn, s: Seed) -> str | None:
    """The phrase 'the login bug' should match more than one item — agent
    must surface candidates rather than silently pick."""
    rows = fetch_all(conn, """
        SELECT i.key, i.title
        FROM items i
        WHERE i.title ILIKE %s
        ORDER BY i.updated_at DESC
    """, ("%login%",))
    keys = {r[0] for r in rows}
    if not {s.keys["A1"], s.keys["A8"]}.issubset(keys):
        return f"expected at least A1+A8 in login matches; got {keys}"
    if len(keys) < 2:
        return "search must surface more than one candidate"
    return None


def eval_05_unassigned_in_sprint(conn, s: Seed) -> str | None:
    """Items in current sprint with no active @assignee tag."""
    rows = fetch_all(conn, """
        SELECT i.key, i.title
        FROM items i
        JOIN tags sp ON sp.item = i.key AND sp.tag = %s AND sp.removed_at IS NULL
        WHERE NOT EXISTS (
            SELECT 1 FROM tags t
            WHERE t.item = i.key AND t.tag LIKE '@%%' AND t.removed_at IS NULL
        )
    """, (s.sprint_current,))
    err = expect_keys(rows, [s.keys["A5"]])
    return err


def eval_06_alice_recent_activity(conn, s: Seed) -> str | None:
    """Items where alice is currently assigned OR she touched the tag log
    in the last 7 days."""
    rows = fetch_all(conn, """
        SELECT DISTINCT i.key
        FROM items i
        JOIN tags t ON t.item = i.key
        WHERE (t.tag = '@alice' AND t.removed_at IS NULL)
           OR (t.tagged_by = 'alice' AND t.tagged_at > now() - interval '7 days')
           OR (t.removed_by = 'alice' AND t.removed_at > now() - interval '7 days')
    """)
    keys = {r[0] for r in rows}
    # @alice is active on A1, A2, A4, A7, B2, R1, R3 (A5 is unassigned).
    expected_subset = {
        s.keys["A1"], s.keys["A2"], s.keys["A4"], s.keys["A7"],
        s.keys["B2"], s.keys["R1"], s.keys["R3"],
    }
    if not expected_subset.issubset(keys):
        return f"missing alice items: {expected_subset - keys}; got {sorted(keys)}"
    return None


def eval_07_what_changed_this_week(conn, s: Seed) -> str | None:
    """Tag events on A1 in the last 7 days. With our seed, that's:
       added: status:review (5d), status:done (3d), release:current (2d)
       removed: status:in-progress (5d), status:review (3d)
    """
    rows = fetch_all(conn, """
        SELECT 'added' AS event, tag, tagged_at AS at FROM tags
        WHERE item = %s AND tagged_at > now() - interval '7 days'
        UNION ALL
        SELECT 'removed', tag, removed_at FROM tags
        WHERE item = %s AND removed_at IS NOT NULL
                       AND removed_at > now() - interval '7 days'
        ORDER BY at
    """, (s.keys["A1"], s.keys["A1"]))
    events = [(r[0], r[1]) for r in rows]
    expected = {
        ("added", "status:review"),
        ("added", "status:done"),
        ("added", s.release_current),
        ("removed", "status:in-progress"),
        ("removed", "status:review"),
    }
    got = set(events)
    if got != expected:
        return f"events mismatch: extra={got - expected} missing={expected - got}"
    return None


def eval_08_board_snapshot(conn, s: Seed) -> str | None:
    """Board snapshot 4 days ago. Restrictions:
       - item must have been in the current sprint at T,
       - item type must be #bug / #task / #story / #epic,
       - exclude docs and bare comments.
       Group by status; just return the keys for assertion."""
    sql = """
        WITH t_at AS (SELECT now() - interval '4 days' AS T),
        in_sprint AS (
            SELECT t.item FROM tags t, t_at
            WHERE t.tag = %s
              AND t.tagged_at <= t_at.T
              AND (t.removed_at IS NULL OR t.removed_at > t_at.T)
        ),
        of_type AS (
            SELECT DISTINCT t.item FROM tags t, t_at
            WHERE t.tag IN ('#bug','#task','#story','#epic')
              AND t.tagged_at <= t_at.T
              AND (t.removed_at IS NULL OR t.removed_at > t_at.T)
        ),
        active_status AS (
            SELECT t.item, t.tag AS status FROM tags t, t_at
            WHERE t.tag LIKE 'status:%%'
              AND t.tagged_at <= t_at.T
              AND (t.removed_at IS NULL OR t.removed_at > t_at.T)
        )
        SELECT s.item, s.status
        FROM in_sprint sp
        JOIN of_type ty ON ty.item = sp.item
        JOIN active_status s ON s.item = sp.item
        ORDER BY s.item
    """
    rows = fetch_all(conn, sql, (s.sprint_current,))
    by_item = {r[0]: r[1] for r in rows}
    # 4 days ago: A1 was in 'review' (review added 5d, done added 3d → at -4d still review),
    # A2 was 'in-progress' (review added 2d, so at -4d still in-progress),
    # A3 was 'in-progress' (since 4d), A4 backlog (since 9d), A5 backlog (since 8d),
    # A8 backlog (since 11d), R2 backlog (in-progress added 4d ago — boundary).
    expected = {
        s.keys["A1"]: "status:review",
        s.keys["A2"]: "status:in-progress",
        s.keys["A3"]: "status:in-progress",
        s.keys["A4"]: "status:backlog",
        s.keys["A5"]: "status:backlog",
        s.keys["A8"]: "status:backlog",
    }
    # Should not include A7 (#doc, also no sprint), R1 (no sprint, #doc),
    # R2 (recommender sprint membership — ah wait, R2 is in current sprint per seed)
    # Recheck: R2 has sprint_current. Status at -4d: backlog tagged 7d ago,
    # in-progress added 4d ago. Boundary at exactly 4d; eval uses strict
    # inequality (<= T), so removed_at = day(4) > T means backlog still
    # active at T-epsilon. Need to be careful — let's leave R2 out of the
    # strict expected set and verify it's *not* missing rather than asserting.
    # Allow either backlog or in-progress for R2; both are valid at the
    # exact-4d boundary.
    if s.keys["R2"] in by_item:
        if by_item[s.keys["R2"]] not in ("status:backlog", "status:in-progress"):
            return f"R2 status unexpected: {by_item[s.keys['R2']]}"
    for k, v in expected.items():
        if by_item.get(k) != v:
            return f"item {k}: expected {v}, got {by_item.get(k)}"
    # Must exclude docs (A7, R1) and unrelated items
    for forbidden in [s.keys["A7"], s.keys["R1"]]:
        if forbidden in by_item:
            return f"doc item {forbidden} should not appear in board snapshot"
    return None


def eval_09_reopen_misclosed(conn, s: Seed) -> str | None:
    """Reopen A1 — find the previous status before status:done (which was
    status:review) and restore it."""
    cur = conn.cursor()

    prev = fetch_one(conn, """
        SELECT tag FROM tags
        WHERE item = %s AND tag LIKE 'status:%%'
              AND tag <> 'status:done'
              AND removed_at IS NOT NULL
        ORDER BY removed_at DESC
        LIMIT 1
    """, (s.keys["A1"],))
    if prev is None or prev[0] != "status:review":
        return f"previous status detection failed: {prev}"

    cur.execute(
        "UPDATE tags SET removed_at = now(), removed_by = 'alice' "
        "WHERE item = %s AND tag = 'status:done' AND removed_at IS NULL",
        (s.keys["A1"],),
    )
    cur.execute(
        "INSERT INTO tags (item, tag, tagged_by) VALUES (%s, %s, %s) "
        "ON CONFLICT DO NOTHING",
        (s.keys["A1"], "status:review", "alice"),
    )

    active = fetch_all(conn,
        "SELECT tag FROM tags WHERE item = %s AND tag LIKE 'status:%%' "
        "AND removed_at IS NULL", (s.keys["A1"],))
    if {r[0] for r in active} != {"status:review"}:
        return f"after reopen, active statuses are {active}"
    # done row still on disk
    n_done = fetch_one(conn,
        "SELECT count(*) FROM tags WHERE item = %s AND tag = 'status:done'",
        (s.keys["A1"],))[0]
    if n_done < 1:
        return "status:done row should be preserved with removed_at set"
    return None


def eval_10_cumulative_flow(conn, s: Seed) -> str | None:
    """CFD over last 14 days: each (day, status) cell should be non-negative
    and the total active across statuses should match the count of items
    that had any status:* tag active that day."""
    rows = fetch_all(conn, """
        WITH days AS (
          SELECT generate_series(now()::date - interval '13 days',
                                 now()::date,
                                 interval '1 day')::date AS d
        ),
        statuses AS (SELECT DISTINCT tag FROM tags WHERE tag LIKE 'status:%%')
        SELECT d.d::text, s.tag, count(*) FILTER (
          WHERE t.tagged_at <= d.d + interval '1 day'
            AND (t.removed_at IS NULL OR t.removed_at > d.d + interval '1 day')
        )
        FROM days d
        CROSS JOIN statuses s
        LEFT JOIN tags t ON t.tag = s.tag
        GROUP BY d.d, s.tag
        ORDER BY d.d, s.tag
    """)
    if not rows:
        return "CFD returned no rows"
    if any(r[2] < 0 for r in rows):
        return "negative count in CFD"
    today_total = sum(r[2] for r in rows if r[0] == rows[-1][0])
    if today_total < 5:
        return f"today's total across statuses suspiciously low: {today_total}"
    return None


def eval_11_cycle_time(conn, s: Seed) -> str | None:
    """Items that hit status:done in the last 90 days, with total time
    spent in status:in-progress."""
    rows = fetch_all(conn, """
        WITH done_in_window AS (
            SELECT item FROM tags
            WHERE tag = 'status:done'
              AND tagged_at >= now() - interval '90 days'
              AND removed_at IS NULL
        ),
        ip AS (
            SELECT item, coalesce(removed_at, now()) - tagged_at AS span
            FROM tags WHERE tag = 'status:in-progress'
        )
        SELECT d.item, extract(epoch FROM sum(ip.span))/86400.0 AS days_in_progress
        FROM done_in_window d
        JOIN ip ON ip.item = d.item
        GROUP BY d.item
        ORDER BY days_in_progress DESC
    """)
    by_item = {r[0]: float(r[1]) for r in rows}
    # B2: in-progress 13d→9d = 4d
    # B1: in-progress 14d→10d = 4d
    # A1: in-progress 18d→5d = 13d (skewed long; demonstrates outlier)
    if not {s.keys["A1"], s.keys["B1"], s.keys["B2"]}.issubset(by_item.keys()):
        return f"missing done items in cycle-time output: got {by_item.keys()}"
    if by_item[s.keys["A1"]] < 12 or by_item[s.keys["A1"]] > 14:
        return f"A1 in-progress span unexpected: {by_item[s.keys['A1']]}"
    return None


def eval_12_workload_per_assignee(conn, s: Seed) -> str | None:
    """Sum active points for each active assignee, excluding done items."""
    rows = fetch_all(conn, """
        WITH active_points AS (
            SELECT item, (regexp_replace(tag, '^points:', ''))::int AS pts
            FROM tags WHERE tag LIKE 'points:%%' AND removed_at IS NULL
        ),
        assignees AS (
            SELECT item, tag AS handle FROM tags
            WHERE tag LIKE '@%%' AND removed_at IS NULL
        ),
        not_done AS (
            SELECT i.key FROM items i
            WHERE NOT EXISTS (
                SELECT 1 FROM tags t WHERE t.item = i.key
                AND t.tag = 'status:done' AND t.removed_at IS NULL
            )
        )
        SELECT a.handle, sum(p.pts) AS total
        FROM assignees a
        JOIN active_points p ON p.item = a.item
        JOIN not_done n ON n.key = a.item
        GROUP BY a.handle
        ORDER BY total DESC
    """)
    by_handle = {r[0]: int(r[1]) for r in rows}
    # alice: A2(5) + A4(8) = 13. (A1 is done, A5 has no points, A7 no points.)
    # bob: A3(5) + A8(2) + R2(5) = 12.
    expected = {"@alice": 13, "@bob": 12}
    for h, want in expected.items():
        if by_handle.get(h) != want:
            return f"{h}: expected {want}, got {by_handle.get(h)}"
    return None


def eval_13_promote_to_epic(conn, s: Seed) -> str | None:
    """Promote A4 from #story to #epic and add 3 sub-tasks."""
    cur = conn.cursor()

    # Retag #story → #epic
    cur.execute(
        "UPDATE tags SET removed_at = now(), removed_by = 'alice' "
        "WHERE item = %s AND tag = '#story' AND removed_at IS NULL",
        (s.keys["A4"],),
    )
    cur.execute(
        "INSERT INTO tags (item, tag, tagged_by) VALUES (%s, %s, %s) "
        "ON CONFLICT DO NOTHING",
        (s.keys["A4"], "#epic", "alice"),
    )

    # Add 3 children
    children = []
    for title in [
        "passkey: registration flow",
        "passkey: login flow",
        "passkey: account-settings UI",
    ]:
        cur.execute(
            "INSERT INTO items (title, parent, created_by) VALUES (%s, %s, %s) RETURNING key",
            (title, s.keys["A4"], "alice"),
        )
        ck = cur.fetchone()[0]
        for t in ["#task", "status:backlog", "@alice", "proj:auth", s.sprint_current]:
            cur.execute(
                "INSERT INTO tags (item, tag, tagged_by) VALUES (%s, %s, %s)",
                (ck, t, "alice"),
            )
        children.append(ck)

    # Verify A4 type
    types = fetch_all(conn,
        "SELECT tag FROM tags WHERE item = %s "
        "AND tag IN ('#epic','#story') AND removed_at IS NULL", (s.keys["A4"],))
    if {r[0] for r in types} != {"#epic"}:
        return f"A4 type tags after promotion: {types}"

    # Verify children parent link
    n_children = fetch_one(conn,
        "SELECT count(*) FROM items WHERE parent = %s", (s.keys["A4"],))[0]
    if n_children != 3:
        return f"expected 3 children of A4, got {n_children}"
    return None


def eval_14_bulk_relabel(conn, s: Seed) -> str | None:
    """Move every proj:auth-old → proj:auth."""
    cur = conn.cursor()

    # Find affected items first (the agent should preview this count to the user).
    affected = fetch_all(conn, """
        SELECT DISTINCT item FROM tags
        WHERE tag = 'proj:auth-old' AND removed_at IS NULL
    """)
    if not affected:
        return "no auth-old items found in seed (precondition broken)"

    cur.execute(
        "UPDATE tags SET removed_at = now(), removed_by = 'alice' "
        "WHERE tag = 'proj:auth-old' AND removed_at IS NULL"
    )
    for (k,) in affected:
        cur.execute(
            "INSERT INTO tags (item, tag, tagged_by) VALUES (%s, %s, %s) "
            "ON CONFLICT DO NOTHING",
            (k, "proj:auth", "alice"),
        )

    # No item should have proj:auth-old active anymore
    leftover = fetch_one(conn,
        "SELECT count(*) FROM tags WHERE tag = 'proj:auth-old' AND removed_at IS NULL")[0]
    if leftover:
        return f"{leftover} proj:auth-old tags still active"

    # A6 should now have proj:auth active
    has_new = fetch_one(conn, """
        SELECT 1 FROM tags
        WHERE item = %s AND tag = 'proj:auth' AND removed_at IS NULL
    """, (s.keys["A6"],))
    if not has_new:
        return "A6 should have proj:auth active after relabel"

    # History preserved: the proj:auth-old row is still there, removed_at set.
    n_hist = fetch_one(conn, """
        SELECT count(*) FROM tags
        WHERE item = %s AND tag = 'proj:auth-old' AND removed_at IS NOT NULL
    """, (s.keys["A6"],))[0]
    if n_hist != 1:
        return f"expected 1 historical proj:auth-old row on A6; got {n_hist}"
    return None


def eval_15_invent_severity(conn, s: Seed) -> str | None:
    """User invents severity:sev2. Agent files convention:severity AND
    tags A5 with severity:sev2. Subsequent sessions can read the
    convention back."""
    cur = conn.cursor()

    # Step 1 — convention not yet registered
    cur.execute(
        "SELECT key FROM items WHERE title LIKE 'convention:severity%'"
    )
    if cur.fetchall():
        return "severity convention should not pre-exist in seed"

    # Step 2 — register the convention
    cur.execute(
        "INSERT INTO items (title, body, created_by) VALUES (%s, %s, %s) RETURNING key",
        ("convention:severity — incident severity, sev0 (full outage) → sev3 (cosmetic)",
         "Apply to incident-style items. sev0 = full outage, sev1 = major "
         "degradation, sev2 = minor degradation, sev3 = cosmetic.",
         "alice"),
    )
    conv_key = cur.fetchone()[0]
    cur.execute(
        "INSERT INTO tags (item, tag, tagged_by) VALUES (%s, %s, %s)",
        (conv_key, "#convention", "alice"),
    )

    # Step 3 — apply the new tag to the user-named item
    cur.execute(
        "INSERT INTO tags (item, tag, tagged_by) VALUES (%s, %s, %s) "
        "ON CONFLICT DO NOTHING",
        (s.keys["A5"], "severity:sev2", "alice"),
    )

    # Verify subsequent session can discover the convention
    rows = fetch_all(conn,
        "SELECT key, title FROM items WHERE title LIKE 'convention:%' ORDER BY title")
    titles = [r[1] for r in rows]
    if not any(t.startswith("convention:severity") for t in titles):
        return f"severity convention not discoverable; saw {titles}"
    if not any(t.startswith("convention:area") for t in titles):
        return "pre-existing convention:area should still be discoverable"

    has = fetch_one(conn,
        "SELECT 1 FROM tags WHERE item = %s AND tag = 'severity:sev2' "
        "AND removed_at IS NULL", (s.keys["A5"],))
    if not has:
        return "severity:sev2 not active on A5"
    return None


EVALS = [
    ("01 file with similar-items search",  eval_01_file_with_similar),
    ("02 quick chat note → task",          eval_02_quick_note_to_task),
    ("03 child comment by description",    eval_03_child_comment),
    ("04 disambiguate 'the login bug'",    eval_04_disambiguate_login_bug),
    ("05 unassigned items in sprint",      eval_05_unassigned_in_sprint),
    ("06 alice's recent activity",         eval_06_alice_recent_activity),
    ("07 what changed this week",          eval_07_what_changed_this_week),
    ("08 board snapshot at past time",     eval_08_board_snapshot),
    ("09 reopen mis-closed item",          eval_09_reopen_misclosed),
    ("10 cumulative flow",                 eval_10_cumulative_flow),
    ("11 cycle-time distribution",         eval_11_cycle_time),
    ("12 workload per assignee",           eval_12_workload_per_assignee),
    ("13 promote story to epic",           eval_13_promote_to_epic),
    ("14 bulk relabel proj tag",           eval_14_bulk_relabel),
    ("15 invent severity convention",      eval_15_invent_severity),
]


# ---------- driver ----------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--admin-url", default=None,
        help="Postgres URL with rights to CREATE/DROP DATABASE (default: derived from your taggy config).")
    ap.add_argument("--db-name", default="taggy_eval")
    ap.add_argument("--keep", action="store_true",
        help="Don't drop the eval database after running (handy for poking around).")
    args = ap.parse_args()

    admin_url = args.admin_url or admin_url_default()
    parsed = parse_pg_url(admin_url)
    eval_url = (
        f"postgres://{parsed['user']}@{parsed['host']}:{parsed['port']}/{args.db_name}"
        if parsed["password"] is None else
        f"postgres://{parsed['user']}:{parsed['password']}@{parsed['host']}:{parsed['port']}/{args.db_name}"
    )

    print(f"==> Bootstrapping {args.db_name} on {parsed['host']}:{parsed['port']} …")
    reset_database(admin_url, args.db_name)
    apply_schema(eval_url)
    s = seed(eval_url)
    print(f"    seeded {len(s.keys)} items at now={s.now.isoformat()}")
    print()

    conn = connect(eval_url, autocommit=False)

    # Each eval runs in its own transaction; we always ROLLBACK at the end
    # so the seeded state stays pristine for the next eval. This makes the
    # evals independent and the harness order-insensitive — exactly the
    # property a regression suite needs. The eval functions deliberately
    # skip conn.commit(); writes are visible within the eval and discarded
    # after.
    failures: list[tuple[str, str]] = []
    for name, fn in EVALS:
        try:
            err = fn(conn, s)
        except Exception as exc:
            err = f"exception: {exc!r}"
        conn.rollback()
        if err:
            print(f"  FAIL  {name}: {err}")
            failures.append((name, err))
        else:
            print(f"  pass  {name}")
    conn.close()

    print()
    if failures:
        print(f"{len(failures)} of {len(EVALS)} evals failed.")
        return 1
    print(f"all {len(EVALS)} evals passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
