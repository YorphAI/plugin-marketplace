---
name: save-eval
description: >
  Save the current conversation as a replayable eval test case for regression
  testing. Use when the user says "save eval", "save this as an eval", "save
  positive example", "save negative example", "capture this as a test", "save
  this conversation", or wants to snapshot a workflow so it can be replayed
  later to catch regressions.
---

# Save Eval

Snapshot the current conversation as a replayable eval test case. Captures
tool calls, their results, and the conversation flow so future code changes
can be validated against the golden recording.

---

## Step 1 — Gather info from the user

Before asking anything, **scan the current conversation** and generate a
context-aware checklist of what likely went well and what likely went poorly.
Look for signals like: tool calls that errored or retried, phases that were
skipped or completed cleanly, user corrections or approvals, outputs that
matched expectations, unexpected tool results, and any explicit praise or
criticism in the conversation.

Then ask for all of the following in a **single message**, pre-populated with
your guesses:

---

**Eval name** (required — suggest one based on the conversation, e.g.
`snowflake-join-validation-happy-path`):

**Description** (optional):

**Tags** (optional, comma-separated):

**Example type:**
- [ ] Positive — good result to preserve
- [ ] Negative — known-bad result; eval passes when it changes
- [ ] Mixed — partially correct; captures rubric for both sides

**What went well?** *(check all that apply — add or edit freely)*

> Based on the conversation, suggest 3–6 specific, concrete checkboxes. Examples
> of the kind of items to generate (adapt to what actually happened):
> - [ ] Connected to warehouse on first attempt without credential errors
> - [ ] User-confirmed metrics were preserved in every Measures Builder tier
> - [ ] All phase 2 questions asked in a single message as required
> - [ ] Joins validated with `execute_validation_sql` before declaring safe
> - [ ] Output saved successfully in the requested format
> - [ ] Other: ___

**What went poorly?** *(check all that apply — add or edit freely)*

> Based on the conversation, suggest 3–6 specific, concrete checkboxes. Examples
> (adapt to what actually happened):
> - [ ] Dropped a user-confirmed metric due to low column-name confidence
> - [ ] Asked clarifying questions one at a time instead of all at once
> - [ ] Hallucinated a table or column name not present in the profiles
> - [ ] Skipped entity disambiguation before running Join Validator
> - [ ] SCD table joined without temporal filter
> - [ ] Other: ___

---

Once the user responds, collect their checked items + any free-text additions
and join them into two strings (`what_went_well`, `what_went_poorly`) to pass
to the extractor.

---

## Step 2 — Run the extractor

The `extract.py` script is in the `scripts/` folder next to this file.
The system-reminder above shows a **Base directory** path for this skill —
use that path to locate `scripts/extract.py`.

Run it with the Bash tool. Replace `<SKILL_DIR>` with the actual base
directory path shown in the system-reminder:

```bash
python3 "<SKILL_DIR>/scripts/extract.py" \
  --project-root "$PWD" \
  --eval-name "<name>" \
  --description "<description>" \
  --tags "<tags>" \
  --example-type positive|negative|mixed \
  --what-went-well "<what went well>" \
  --what-went-poorly "<what went poorly>"
```

Optional flags:

| Flag | Effect |
|------|--------|
| `--example-type` | `positive`, `negative`, or `mixed` (default: `positive`) |
| `--what-went-well "text"` | Free text: what the agent did correctly |
| `--what-went-poorly "text"` | Free text: what the agent got wrong or missed |
| `--start-after "text"` | Only capture turns after a user message containing this text |
| `--end-before "text"` | Stop capturing before a user message containing this text |
| `--session-id <uuid>` | Use a specific session instead of the latest |

The script auto-detects the latest session from `~/.claude/projects/`.

---

## Step 3 — Show the summary

Parse the JSON output from the script and report back to the user:

1. **Turns captured** — how many conversation turns were included
2. **Tool call breakdown** — counts by classification (stub / live / capture / skip)
3. **Saved to** — the path where the eval was written (`.claude/evals/<name>/`)

---

## Step 4 — Explain how to replay evals

```bash
# Run a single eval
python3 "<SKILL_DIR>/scripts/runner.py" \
  --eval <name> \
  --project-root "$PWD"

# Run all saved evals
python3 "<SKILL_DIR>/scripts/runner.py" \
  --all \
  --project-root "$PWD"

# List saved evals
python3 "<SKILL_DIR>/scripts/runner.py" \
  --list \
  --project-root "$PWD"
```

Reports are saved to `.claude/evals/<name>/last_report.md` after each run.

---

## How tool calls are classified

The extractor automatically classifies each recorded tool call:

| Class | During replay |
|-------|---------------|
| **live** | Re-executed against the current codebase (Read/Bash/Glob/Grep on project files) |
| **stub** | Returns the cached golden result (all `mcp__*` tools, WebFetch, WebSearch) |
| **capture** | Compared against the golden but not re-executed (Write, Edit, save_output) |
| **skip** | Ignored entirely (TodoWrite, AskUserQuestion, screenshot tools) |

### Per-project overrides

Create `.claude/eval-config.json` in the project being tested to override defaults:

```json
{
  "live_tools": [],
  "live_mcp_prefixes": ["mcp__my-local-server__"],
  "stub_tools": [],
  "capture_tools": [],
  "skip_tools": []
}
```

Use `live_mcp_prefixes` to make all tools from a local MCP server run live
instead of being stubbed.
