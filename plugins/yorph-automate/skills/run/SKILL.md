---
name: run
description: Trigger a manual run of a yorph-automate workflow, or resume a failed run from the point of failure. Use when the user says "run <workflow>", "trigger <workflow>", "fire the <name> automation", "execute <workflow>", "resume that", "re-run from where it failed", or similar. Returns the run result and surfaces any failure quickly.
---

# Run — yorph-automate

Fires a workflow. If the server is running, uses its HTTP API (fast, writes to the run DB, visible in the viewer). If not, falls back to `server.py --run-once` so the user still gets a result.

Two modes:
- **Fresh run** (the default): every node executes from scratch.
- **Resume from a prior run**: every node that succeeded in the prior run is reused (outputs copied, no re-execution), as long as its entire upstream cone was also reused. As soon as one node re-executes, all its downstream dependents also re-execute. Good for "analysis failed right after download — I don't want to re-download."

---

## 1. Identify the workflow

If the user named the workflow unambiguously, use it. If ambiguous (e.g. "run the slack one"), list matching ids from:

```bash
ls -1 ~/.yorph/automate/workflows/*.json | xargs -n1 basename | sed 's/\.json$//'
```

and confirm with the user.

---

## 2. Collect a payload if appropriate

`manual_trigger` nodes accept a `payload` that flows into the graph via the `trigger` scope. If the workflow's first node expects real input (inspect the JSON or ask Claude's `compose` knowledge), ask the user for the payload. Otherwise pass `null`.

Example quick-inspect of the trigger node:
```bash
python3 -c "import json,sys; w=json.load(open('$HOME/.yorph/automate/workflows/<id>.json')); print([n for n in w['nodes'] if n['template_id']=='manual_trigger'])"
```

---

## 3. Check server

```bash
curl -sS --max-time 1 http://localhost:8766/api/health | grep -q '"ok": *true' \
  && echo "up" || echo "down"
```

---

## 4a. Server up — POST /api/runs

```bash
curl -sS -X POST http://localhost:8766/api/runs \
  -H 'Content-Type: application/json' \
  -d '{"workflow_id":"<id>","payload":<payload_json_or_null>}' \
  | python3 -m json.tool
```

Response is `{"run_id": "…"}`. The v0 server executes synchronously on the request thread, so by the time the POST returns the run is already terminal (succeeded or failed). Immediately fetch the run detail:

```bash
curl -sS http://localhost:8766/api/runs/<run_id> | python3 -m json.tool
```

### Resume from a prior run

When the user says "resume" / "retry from where it failed" / "re-run but keep the data from last time", add a `resume_from` field pointing at the prior run's id:

```bash
# Find the last failed run for this workflow
PRIOR=$(curl -sS "http://localhost:8766/api/runs?workflow_id=<id>&limit=20" \
  | python3 -c "import sys,json; r=[x for x in json.load(sys.stdin)['runs'] if x['status']=='failed']; print(r[0]['id'] if r else '')")

# Resume
curl -sS -X POST http://localhost:8766/api/runs \
  -H 'Content-Type: application/json' \
  -d "{\"workflow_id\":\"<id>\",\"resume_from\":\"$PRIOR\"}" \
  | python3 -m json.tool
```

**Semantics**:
- Nodes with `succeeded` status in the prior run are reused (status `reused` in the new run), but only if **every** one of their upstream edge sources was also reused. As soon as one node re-executes, everything downstream re-executes.
- A node whose `template_id` changed between the prior workflow and the current one is NOT reused — it re-executes.
- The payload isn't required for resume; `manual_trigger` reuses its prior payload when reused (through the stored outputs).
- If the workflow was edited since the prior run (new nodes, different edges), the match is by node `id` + `template_id`. If you edited a node's `config` but kept the same id/template, the reused output will be from the **old** config — if that's wrong, trigger a fresh run instead.

Surface the reuse to the user in your summary. Example:
> "Resumed run `def789`. 3 nodes reused (`download_data`, `fetch_schema`, `parse`), re-executed `analyze` and downstream. Completed in 1.2s (vs 32s for the fresh run)."

---

## 4b. Server down — run-once CLI

```bash
python3 <plugin_root>/server.py --run-once <id> --payload '<json>'
```

This prints a JSON summary (`run_id`, `status`, `final_outputs`, `error`) and exits 0 on success, 1 on failure.

---

## 5. Present the result

- On success: show the `final_outputs` bag. If there's one labeled output, show that directly; if several, list them.
- On failure: show the failing node's name and its error. Point the user to the `inspect-run` skill for full node-by-node details.
- Always include the `run_id` so the user can look it up later.

Don't dump the full run JSON unless asked — it can be large.
