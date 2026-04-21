---
name: list
description: List yorph-automate workflows, templates, or recent runs. Use when the user asks "what automations do I have", "show my workflows", "what templates are available", "what ran recently", "show run history", etc.
---

# List — yorph-automate

Just surfaces what exists. Keep output compact and scannable.

---

## 1. Prefer the server

```bash
curl -sS http://localhost:8766/api/workflows | python3 -m json.tool
curl -sS http://localhost:8766/api/templates | python3 -m json.tool
curl -sS "http://localhost:8766/api/runs?limit=20" | python3 -m json.tool
```

---

## 2. Fall back to the filesystem if the server is down

```bash
ls -1 ~/.yorph/automate/workflows/*.json 2>/dev/null
ls -1 ~/.yorph/automate/templates/*.json 2>/dev/null
```

And for templates bundled with the plugin:
```bash
ls -1 /Users/*/Documents/Yorph/yorph-marketplace/plugins/yorph-automate/templates/*.json 2>/dev/null
```

For runs without the server you'd need sqlite3 against `~/.yorph/automate/runs.db`:
```bash
sqlite3 ~/.yorph/automate/runs.db \
  "SELECT workflow_id, status, datetime(started_at, 'unixepoch'), error FROM runs ORDER BY started_at DESC LIMIT 20;"
```

---

## 3. Present it tersely

Workflows: one line per workflow — `<id>  <name>  <node_count> nodes  <last_run_status>`.

Templates: group by kind (trigger / action / transform / control), one line per template.

Runs: a small table with columns `when | workflow | status | duration`. If the user wants details on a specific run, suggest the `inspect-run` skill.

If they don't clearly ask for one category, ask which of the three they want (or show all three with compact headings).
