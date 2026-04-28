---
name: setup
description: Conversational one-time setup for yorph-taggy — provisions the Postgres database, the two roles (taggy_rw, taggy_ro), applies the schema, and writes ~/.yorph/taggy/config.json. Use when the user says "set up taggy", "install taggy", "create the database", "join an existing taggy", or asks "what's my actor handle". Idempotent — safe to re-run.
---

# Setup — yorph-taggy

One-time bootstrap. Conversational and AI-driven: ask the user where they want
to host, then run the right commands. End state: a working database, two
roles, and `~/.yorph/taggy/config.json`. Re-running is safe — `setup_db.py`
is idempotent.

## 0. Resolve the plugin path

`setup_db.py` and `schema.sql` live next to this skill, two levels up. The
plugin is typically installed at one of:

- `$HOME/Documents/Yorph/yorph-marketplace/plugins/yorph-taggy`
- `/Applications/Claude/plugins/yorph-taggy`

Resolve it once and reuse:

```bash
PLUGIN_DIR="$(ls -d "$HOME"/Documents/Yorph/yorph-marketplace/plugins/yorph-taggy 2>/dev/null \
              || ls -d /Applications/Claude/plugins/yorph-taggy 2>/dev/null \
              || echo NOT_FOUND)"
echo "$PLUGIN_DIR"
```

If `NOT_FOUND`, ask the user where they cloned the plugin.

## 1. Check whether they're already set up

```bash
test -f "${YORPH_TAGGY_HOME:-$HOME/.yorph/taggy}/config.json" \
  && echo "already configured" || echo "fresh install"
```

If already configured: tell them which actor handle is in the config, and ask
whether they want to **re-run init** (replaces the local config), **join a
different deployment**, or **leave it alone**.

```bash
python3 -c "import json,os,pathlib; p=pathlib.Path(os.environ.get('YORPH_TAGGY_HOME') or (pathlib.Path.home()/'.yorph'/'taggy'))/'config.json'; c=json.loads(p.read_text()); print('actor:', c['actor']); print('rw host:', c['db_url_rw'].split('@')[-1])"
```

## 2. Install pg8000 if missing

```bash
python3 -c "import pg8000" 2>/dev/null || pip install --quiet pg8000
```

If `pip` isn't available (rare), fall back to `python3 -m pip install pg8000`.

## 3. Decide: init or join

Ask the user:

> "Are you setting up a fresh taggy database, or joining one a teammate
> already created? If fresh, where do you want to host it — local Docker, GCP
> Cloud SQL, Supabase, Neon, or an existing Postgres you already have?"

The flow forks here.

---

## Path A — Fresh install (`init`)

You need an **admin connection URL** with rights to `CREATE DATABASE` and
`CREATE ROLE`. Ask the user for it (don't echo the password back — refer to it
as `<the URL you provided>`).

### A1. Local Docker (recommended for trial)

If they don't have Postgres yet and want the fastest path:

```bash
docker run -d --name taggy-pg \
  -e POSTGRES_PASSWORD=taggy-admin-pw \
  -p 5432:5432 \
  postgres:16
```

Wait for it to be ready:

```bash
until docker exec taggy-pg pg_isready -U postgres >/dev/null 2>&1; do sleep 1; done
echo ready
```

Their admin URL is `postgres://postgres:taggy-admin-pw@localhost:5432/postgres`.

### A2. GCP Cloud SQL / Supabase / Neon / existing Postgres

Ask for the admin connection URL. Verify it's reachable before running init:

```bash
python3 - <<'PY'
import os, sys, urllib.parse, pg8000.dbapi
url = os.environ["ADMIN_URL"]
p = urllib.parse.urlparse(url)
c = pg8000.dbapi.connect(user=p.username, password=p.password,
                          host=p.hostname, port=p.port or 5432,
                          database=(p.path or "/").lstrip("/") or "postgres")
c.cursor().execute("SELECT 1"); c.close()
print("ok")
PY
```

(Set `ADMIN_URL` in the bash env for that single command — don't write it to
disk.)

### A3. Ask for the user's display name (the "actor")

This goes into every `created_by` and `tagged_by` field. Use the user's
shortest reasonable handle: `alice`, `bob`, `git config user.name` lowered, etc.

```bash
git config user.name 2>/dev/null
```

Confirm the proposed actor with the user before continuing.

### A4. Run init

```bash
python3 "$PLUGIN_DIR/setup_db.py" init \
  --admin-url "$ADMIN_URL" \
  --db-name taggy \
  --actor "$ACTOR"
```

Two random secrets are generated for `taggy_rw` and `taggy_ro`. They are
written into `~/.yorph/taggy/config.json` (mode 0600) and never echoed.

### A5. Verify the read-only role really is read-only

This is acceptance criterion #6 from the spec.

```bash
python3 "$PLUGIN_DIR/setup_db.py" verify-ro
```

Expect: `ro role correctly refused: INSERT, UPDATE, DELETE, CREATE`.

---

## Path B — Joining an existing deployment

A teammate who already ran `init` shares the two connection strings out-of-band
(1Password, an encrypted message, etc.). Ask the user for:

- The `taggy_rw` URL.
- The `taggy_ro` URL.
- Their display name (their actor handle).

Then:

```bash
python3 "$PLUGIN_DIR/setup_db.py" join \
  --rw-url "$RW_URL" \
  --ro-url "$RO_URL" \
  --actor "$ACTOR"
```

The script verifies both connections before writing the config. If either
verification warns, surface the warning to the user before claiming success.

---

## 4. Quick smoke test

Confirm the agent can read and write through the roles:

```bash
. "$PLUGIN_DIR/bin/taggy-env"
psql "$TAGGY_RO" -c "SELECT count(*) FROM items"
```

Expect zero rows on a fresh install. If `psql` isn't installed, point the user
at https://www.postgresql.org/download/ and stop.

## 5. Confirm briefly

One short line, no tutorial:

> "Taggy is set up. Your config lives at `~/.yorph/taggy/config.json` (mode 0600).
> Just describe items in chat — say 'file a bug …' or 'show me what's open in
> sprint X' — and I'll handle the rest."

Stop here. Do not pre-create demo items.
