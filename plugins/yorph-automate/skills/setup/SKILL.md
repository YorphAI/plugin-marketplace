---
name: setup
description: Start the yorph-automate local server and open the viewer in the browser. Use when the user says "open automate", "open the automate viewer", "start the automate server", "set up automate", or anything similar. Idempotent — safe to call even if the server is already running.
---

# Setup — yorph-automate

Minimal setup. Run silently, surface only what the user needs to know.

---

## 1. Check Python 3

```bash
python3 --version
```

If missing, tell the user to install Python 3 from https://python.org and stop.

---

## 2. Ensure the home directory exists

The server creates `~/.yorph/automate/` on first start, but we can do it proactively so the user sees where their data lives:

```bash
mkdir -p ~/.yorph/automate/workflows ~/.yorph/automate/templates
```

---

## 3. Resolve the plugin path

The server script is at `<plugin_root>/server.py`. This skill lives at `<plugin_root>/skills/setup/SKILL.md`, so `../../server.py` relative to this file. In practice the plugin is installed at:

```
/Users/<user>/Documents/Yorph/yorph-marketplace/plugins/yorph-automate/server.py
```

Resolve the exact path once and reuse it:

```bash
SERVER_PY="$(ls -d "$HOME"/Documents/Yorph/yorph-marketplace/plugins/yorph-automate/server.py 2>/dev/null \
            || ls -d /Applications/Claude/plugins/yorph-automate/server.py 2>/dev/null \
            || echo "NOT_FOUND")"
echo "$SERVER_PY"
```

If `NOT_FOUND`, ask the user for the path to the plugin.

---

## 4. Check whether the server is already running

```bash
curl -sS --max-time 1 http://localhost:8766/api/health | grep -q '"ok": *true' \
  && echo "running" || echo "not running"
```

- If `running`: skip to step 6.
- If `not running`: continue.

---

## 5. Start the server

Launch it in the background. Capture PID and give it a beat to come up:

```bash
nohup python3 "$SERVER_PY" --port 8766 > ~/.yorph/automate/server.log 2>&1 &
sleep 1
curl -sS --max-time 2 http://localhost:8766/api/health
```

If the health check fails, print the last 20 lines of the log for the user:

```bash
tail -20 ~/.yorph/automate/server.log
```

Common causes: port 8766 already taken by a different process; Python syntax error from a corrupted `server.py`.

---

## 6. Open the viewer

```bash
open http://localhost:8766      # macOS
# xdg-open http://localhost:8766  # Linux
```

---

## 7. Confirm briefly

One short line:

> "yorph-automate is up at http://localhost:8766. Data lives in `~/.yorph/automate/`. Describe a workflow in chat and I'll build it; say 'run <name>' to trigger one."

Stop. No tutorial.
