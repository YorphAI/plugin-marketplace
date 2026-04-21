---
name: inspect-run
description: Fetch the full node-by-node trace of a past yorph-automate run for debugging. Use when the user asks "why did that fail", "what did the <node> node return", "show me the last run", "debug the latest failure", or references a specific run id.
---

# Inspect Run — yorph-automate

Pulls a run's per-node inputs, outputs, timings, and errors. The viewer shows the same data in a nicer format, but this skill is for when the user wants answers in chat or wants to chain further analysis.

---

## 1. Find the run id

If the user gave one, use it. Otherwise, grab the most recent run (or the most recent failure):

```bash
# latest run
curl -sS "http://localhost:8766/api/runs?limit=1" | python3 -c "import sys,json; print(json.load(sys.stdin)['runs'][0]['id'])"

# latest failure
curl -sS "http://localhost:8766/api/runs?limit=50" \
  | python3 -c "import sys,json; r=[x for x in json.load(sys.stdin)['runs'] if x['status']=='failed']; print(r[0]['id'] if r else '')"
```

If the server is down, query SQLite directly:

```bash
sqlite3 ~/.yorph/automate/runs.db \
  "SELECT id, workflow_id, status, error FROM runs ORDER BY started_at DESC LIMIT 10;"
```

---

## 2. Fetch the run

```bash
curl -sS http://localhost:8766/api/runs/<run_id> | python3 -m json.tool
```

Fallback with SQLite:
```bash
sqlite3 -json ~/.yorph/automate/runs.db \
  "SELECT * FROM runs WHERE id='<run_id>';"
sqlite3 -json ~/.yorph/automate/runs.db \
  "SELECT * FROM node_runs WHERE run_id='<run_id>' ORDER BY started_at;"
```

---

## 3. Present what matters

Always include:
- Workflow id, run id, status, duration.
- If failed: the first failing node's id, its template, and the error text.

For each node, a compact block:
```
<node_id>  (<template_id>)  <status>  <duration>
  inputs:  <summary>
  outputs: <summary>
  error:   <error if any>
```

Truncate long values (over ~200 chars) and tell the user you did. Do not dump the full `outputs_json` of every node in a long workflow — summarize unless asked.

---

## 4. Suggest next steps

- If a `claude_prompt` node returned empty / malformed JSON, surface the raw stdout. The user may want to change `output_format` or refine the prompt.
- If an `http_request` node returned a 4xx/5xx, show the response body and headers.
- If a `branch` node sent flow the "wrong way", show the evaluated condition values.
- Offer to call the `compose` skill to edit the workflow.
