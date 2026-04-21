# yorph-automate

Zapier/n8n-style workflow automation for Claude Code. Author workflows through
chat. Run them locally. Use your Claude CLI subscription for AI steps — no API
key required.

## Quick start

1. Install the plugin (drop it in your Claude Code plugins directory).
2. In Claude Code, say: **"open the automate viewer"** — the `setup` skill
   starts the local server and opens `http://localhost:8766` in your browser.
3. Say: **"make a workflow that runs `echo hello` and shows the output"**.
   Claude uses the `compose` skill to write a workflow JSON at
   `~/.yorph/automate/workflows/hello.json`.
4. Click **Run** in the viewer, or say **"run the hello workflow"**.

## How it works

- A workflow is a DAG of nodes. Each node references a **template** by id and
  supplies `config` values. Edges carry named outputs of upstream nodes to
  named inputs of downstream nodes.
- Templates are reusable recipes (`manual_trigger`, `claude_prompt`,
  `http_request`, `transform_jsonpath`, `branch`, `bash`, `output`, and any you
  add). Each declares a `config_schema`, `inputs`, `outputs`, and a `runtime`
  spec.
- A local Python server (stdlib only — no pip installs) loads the DAG,
  topologically sorts the nodes, and executes them. `claude_prompt` steps
  spawn `claude -p '<prompt>'` as a subprocess and capture the response.
- State is persisted at `~/.yorph/automate/`. Run history is a SQLite DB.

## What you can do today (v0)

- Author and edit workflows + templates via chat.
- Trigger manual runs from the viewer or via a skill.
- See a Mermaid DAG diagram of every workflow.
- Inspect per-node inputs, outputs, and errors for any past run.

## Not yet (but the shape is ready)

- API-powered AI steps (alternative to CLI subscription).
- Scheduled (cron) triggers.
- Webhook triggers (for phone / Slack / WhatsApp).
- File-watch triggers.
- In-browser visual editor.
- Retry / backoff / parallel branch execution.

## Files

- `server.py` — HTTP server + DAG executor. Run directly:
  `python3 server.py --port 8766` (or `--run-once <workflow_id>` for a single
  CLI run).
- `templates/*.json` — the seven built-in primitives.
- `skills/` — the chat-facing interface Claude uses (setup / compose / list /
  run / inspect-run).
- `viewer/` — single-page read-only UI.

## License

MIT (same as other yorph-marketplace plugins).
