# yorph-automate — Plugin Instructions

## What this plugin is

A local workflow-automation engine for Claude Code. Workflows are DAGs of
**nodes**, each node references a reusable **template** by id and supplies
`config` values. A local Python server (`server.py`) executes workflows, and a
read-only browser viewer at `http://localhost:8766` shows workflows, diagrams,
and run history. AI-powered steps (`claude_prompt`) execute by spawning
`claude -p` as a subprocess — they use the user's logged-in CLI subscription,
never an API key.

All state lives at `~/.yorph/automate/`:
- `workflows/<slug>.json` — user DAGs
- `templates/<slug>.json` — user-defined templates (built-ins live in the plugin dir)
- `runs.db` — SQLite run history
- `config.json` — port, claude binary path, etc.

## Which skill to use

- User says **"set up automate", "open the automate viewer", "start the server"**
  → load `yorph-automate:setup`.
- User wants to **create, edit, or describe a workflow or template**
  → load `yorph-automate:compose`.
- User asks **"what automations / workflows / templates do I have"**, or wants
  to see recent runs → load `yorph-automate:list`.
- User says **"run the <X> workflow", "trigger <X>", "fire it now"**
  → load `yorph-automate:run`.
- User asks about a **past run — why it failed, what a node returned, etc.**
  → load `yorph-automate:inspect-run`.
- User wants to **undo / revert / roll back what a run did** — "revert the last run", "undo that", "roll back run <id>"
  → load `yorph-automate:revert`.

## Core rules

1. **Never hand-edit workflow or template JSON without the `compose` skill.**
   `compose` validates against the template registry and checks that edges
   reference declared inputs/outputs. Bypassing it produces workflows that fail
   at runtime in confusing ways.
2. **Always read the existing file first** before proposing edits. Do not
   regenerate a workflow from scratch unless the user explicitly asks.
3. **Show the user a diff** (or the full new JSON for new files) before
   writing. Workflows are user property — they should see what changes.
4. **Resolve templates against both locations**: the plugin-bundled
   `templates/` dir AND the user's `~/.yorph/automate/templates/` dir. The
   bundled set is the source of truth for primitive node types.
5. **Secrets** (config fields marked `secret: true` in a template) should
   never be echoed back to the chat in full. Show `••••` with the last 4 chars.
6. **If the server isn't running**, the `run` skill should fall back to
   executing the DAG in-process via `python3 server.py --run-once <workflow_id>`
   rather than silently failing.

## Transparency

Every workflow, template, and run is human-readable JSON on disk. When the user
asks "what did that workflow actually do", point them at the JSON and the run
detail in the viewer. No opaque state.
