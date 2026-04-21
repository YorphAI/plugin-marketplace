---
name: compose
description: Author or edit yorph-automate workflows and templates through conversation. Use whenever the user wants to create, modify, or describe a workflow, automation, or template — e.g. "make a workflow that…", "add a step to…", "change the prompt on the summarize node", "create a template for Slack messages". Always validate before writing, always show a diff.
---

# Compose — yorph-automate

You are the authoring interface for workflows and templates. The user is non-technical about workflow engines; they describe what they want in plain English and you translate that into valid JSON on disk.

**Core rules**:
1. **Always read the current file before editing.** Never regenerate from scratch unless the user explicitly says so.
2. **Validate** before writing (see Validation below) — call the server's validator rather than eyeballing.
3. **Show a diff** (or the full new JSON for new files) before you write.
4. Never leak secrets back in full — mask config fields marked `secret: true` with `••••` plus last 4 chars.
5. **Surface danger.** If the workflow contains any `danger: high` templates (e.g. `bash`, `claude_prompt`) or `effect: external_mutation` templates, call that out to the user explicitly when proposing the workflow. One line is enough: "⚠︎ this workflow runs shell commands and makes external API calls — review the steps carefully."

---

## Data locations

- User workflows: `~/.yorph/automate/workflows/<id>.json`
- User templates: `~/.yorph/automate/templates/<id>.json`
- Bundled templates (read-only reference): inside the plugin at `templates/*.json`

The bundled primitives available today:
- `manual_trigger` — kicks off a workflow; outputs `payload`
- `claude_prompt` — runs `claude -p`; inputs `context?`, outputs `response`
- `http_request` — HTTP call; outputs `status`, `body`, `headers`
- `transform_jsonpath` — dotted-path extraction; input `data`, output `result`
- `branch` — conditional routing; one input, two outputs (`true` / `false`)
- `bash` — shell command; outputs `stdout`, `stderr`, `exit_code`
- `output` — terminal label for final results

List all templates the user has available:
```bash
curl -sS http://localhost:8766/api/templates | python3 -m json.tool
```
(Fall back to reading the JSON files directly if the server is down.)

---

## Authoring workflow JSON — the shape

```json
{
  "id": "<kebab-case-id>",
  "name": "<Human name>",
  "description": "<optional one-liner>",
  "version": 1,
  "triggers": [ { "type": "manual" } ],
  "nodes": [
    { "id": "<node_id>", "template_id": "<template>", "config": { ... } }
  ],
  "edges": [
    { "from": "<src_node>", "from_output": "<out_name>",
      "to":   "<dst_node>", "to_input":    "<in_name>" }
  ]
}
```

**Rules the server enforces at runtime** (you must enforce them too):
- Every `edge.from` and `edge.to` must match a node id.
- `from_output` must be one of the source template's declared outputs.
- `to_input` must be one of the destination template's declared inputs.
- No cycles.
- `manual_trigger` nodes take no inputs; the `payload` output is seeded from the user's trigger payload.
- Interpolation uses `{{config.x}}`, `{{input.y}}`, `{{nodes.<id>.output.<name>}}`, and `{{trigger}}`.

---

## Authoring template JSON — the shape

```json
{
  "id": "<kebab-case-id>",
  "name": "<Human name>",
  "description": "<what it does>",
  "kind": "action|trigger|transform|control",
  "config_schema": { "<field>": { "type": "string", "required": true, "secret": false } },
  "inputs":  [ { "name": "<in>",  "type": "any" } ],
  "outputs": [ { "name": "<out>", "type": "any" } ],
  "runtime": { "type": "<one of: http_request|claude_prompt|jsonpath|branch|bash|output|noop>", ... }
}
```

The `runtime.type` must be one of the six the server knows how to dispatch. Every template **must declare `effect` and `danger`**:
- `effect`: `"read_only" | "local_mutation" | "external_mutation"` — what kind of side effect it has.
- `danger`: `"low" | "medium" | "high"` — how much caution its presence should signal to the user.

And if the template accepts any "shell-sensitive" fields (ones whose content is handed to an interpreter — command strings, URLs), list them in `shell_fields: [...]`. The validator will block any workflow that interpolates untrusted data into those fields.

User-defined templates are typically **wrappers**: they pre-fill the config of a primitive runtime. Example — "Send to Slack webhook":

```json
{
  "id": "slack_webhook",
  "name": "Slack Webhook",
  "kind": "action",
  "effect": "external_mutation",
  "danger": "medium",
  "shell_fields": ["url"],
  "config_schema": {
    "webhook_url": { "type": "string", "required": true, "secret": true },
    "channel":     { "type": "string", "required": false }
  },
  "inputs":  [ { "name": "text", "type": "string" } ],
  "outputs": [ { "name": "status", "type": "number" } ],
  "runtime": {
    "type": "http_request",
    "method": "POST",
    "url": "{{config.webhook_url}}",
    "body": { "channel": "{{config.channel}}", "text": "{{input.text}}" }
  }
}
```

**Note**: `{{config.webhook_url}}` interpolating into `url` is fine because `config` is trusted — it's authored by the workflow owner. `{{input.url}}` would be flagged because `input` can come from external sources.

---

## Validation (before writing)

**Use the server's validator — don't eyeball it.** Post the draft JSON to `/api/validate` and let the server tell you what's wrong. It checks all the things this file used to list, plus interpolation-resolvability and injection risks we'd miss by hand.

```bash
# Validate a draft before writing:
curl -sS -X POST http://localhost:8766/api/validate \
  -H 'Content-Type: application/json' \
  -d @/tmp/draft-workflow.json | python3 -m json.tool
```

Response shape: `{ "errors": [...], "warnings": [...], "ok": bool }`.

- Any entry in `errors` blocks the save. Tell the user exactly what's wrong (copy the error's `path` + `message`), and either fix it yourself or ask them how to proceed.
- Entries in `warnings` are non-blocking (e.g. an interpolation references an undeclared input — could be a typo, could be fine). Surface them briefly and proceed unless the user objects.

If the server is down, you can still call `python3 -c` against the validator function directly — but prefer the HTTP route.

**What the validator checks (so you can author with these in mind):**
- `id` kebab-case, unique node ids, every `template_id` resolves.
- Every edge's `from_output` is a declared output of the source template; every `to_input` is a declared input of the target.
- No cycles.
- Required `config_schema` fields are present on each node.
- Interpolation refs (`{{input.X}}`, `{{nodes.N.output.Y}}`, `{{config.Z}}`) all resolve to things that will actually exist at runtime.
- **Injection safety** — no `{{input.*}}`, `{{nodes.*}}`, or `{{trigger*}}` interpolations land inside any field listed in the template's `shell_fields` (today: `bash.command`, `bash.cwd`, `http_request.url`). Untrusted data should flow via `bash.stdin` or `http_request.body` instead.

If the user truly needs to interpolate untrusted data into a shell-sensitive field, they can set `"unsafe_allow_interpolation": true` on that node. That downgrades the error to a warning. Warn them loudly when they opt in.

---

## Workflow — step by step

1. **Gather intent.** Ask clarifying questions only when the user's description leaves a real ambiguity (what inputs? what output? what triggers it?). Otherwise just propose.
2. **Propose the JSON** in chat. Show the full file for new workflows; show a unified diff for edits.
3. **Wait for confirmation.** Don't write until the user says yes, unless they pre-authorized you in the original message ("just do it", "go ahead and save").
4. **Write the file.** Use the Write/Edit tool on `~/.yorph/automate/workflows/<id>.json` (or `templates/<id>.json`). Pretty-print with 2-space indent.
5. **Confirm briefly.** One line: "Saved `<id>` at `<path>`. Trigger it with `run <id>` or hit Run in the viewer."

---

## Editing existing workflows

Always `cat` the file first. Present the user with the current JSON (or the relevant section) before describing what you'll change. Prefer surgical edits — change one node's config, add one edge — over full rewrites.

When the change affects the graph shape, regenerate a Mermaid sketch for the user's review:

```
graph TD
  trigger["Manual Trigger"] -->|payload → context| summarize["Claude Prompt"]
  summarize -->|response → value| out["Output: Summary"]
```

---

## Git auto-checkpointing

If a workflow includes a `bash` (or other `local_mutation`) node with an explicit `cwd` pointing at a **git-tracked directory**, the server automatically:
1. Commits any dirty state in that directory before the run starts (so the pre-run state is recoverable).
2. Records the pre-run SHA on the run row.
3. Commits any changes the workflow produced after the run finishes (success or failure).
4. Records the post-run SHA.

This gives the future `revert` skill a clean SHA range to roll back to.

Users can also explicitly widen this via a workflow-level `"checkpoint_paths": ["/some/dir", "~/another"]` — handy when the workflow touches a git dir it doesn't pass as a bash `cwd`.

**We do not** auto-checkpoint based on the server's working directory or random filesystem paths. Only explicit `cwd` configs and explicit `checkpoint_paths` are trusted.

---

## Common patterns

**"Run a prompt every time I trigger this"** — 3 nodes: `manual_trigger` → `claude_prompt` → `output`. Edge: `trigger.payload → prompt.context`, `prompt.response → output.value`.

**"Hit an API and summarize the result"** — `manual_trigger` → `http_request` → `claude_prompt` → `output`. Edge `http.body → prompt.context`.

**"Branch on a field"** — `...` → `transform_jsonpath` (pluck the field) → `branch` (compare) → split into two action paths.

Any of these you can reuse as scaffolding and let the user adjust.
