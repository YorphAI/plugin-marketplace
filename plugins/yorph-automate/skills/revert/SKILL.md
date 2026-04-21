---
name: revert
description: Reverse the effects of a yorph-automate run. Use when the user says "undo that run", "revert the last run", "roll back <workflow>", "undo what that workflow did", "reverse the effects of run <id>", or similar. Reads the run's effect classes and git checkpoints, proposes a reversal plan, and executes it on explicit user confirmation. Handles partial reverts ("just undo the git changes").
---

# Revert — yorph-automate

True reversibility is only possible for some side effects. Your job: figure out what CAN be reverted, propose a concrete plan, and execute it only after the user explicitly says yes. Be honest about what can't be undone.

---

## The core trick

Every node in a run has:
- An `effect` class on its template (`read_only` / `local_mutation` / `external_mutation`).
- Stored `outputs` in `node_runs.outputs_json` — including HTTP response bodies with new resource ids, git SHAs, etc.
- `pre_run_git_checkpoints` and `post_run_git_checkpoints` on the run itself, when applicable.

Use these to reason about reversal. Don't invent — read the data first.

---

## 1. Identify the target run

If the user named a run id, use it. If they said "the last one" / "that one" / "what just happened", fetch the most recent run:

```bash
RUN_ID=$(curl -sS "http://localhost:8766/api/runs?limit=1" | python3 -c "import sys,json; print(json.load(sys.stdin)['runs'][0]['id'])")
```

If ambiguous (multiple recent runs, user didn't specify), list the last 5 with workflow_id and status, and ask which one.

---

## 2. Pull the full run data

```bash
curl -sS "http://localhost:8766/api/runs/$RUN_ID" > /tmp/revert-run.json
cat /tmp/revert-run.json | python3 -m json.tool | head -80
```

Key fields you'll use:
- `run.status` — if `failed`, fewer nodes actually did things (start from the last successful one and work backward).
- `run.pre_run_git_checkpoints` and `run.post_run_git_checkpoints` — git revert targets.
- `run.workflow_snapshot` — the workflow JSON that was used (important if the workflow has been edited since).
- `nodes[].template_id` — cross-reference `/api/templates` for each node's `effect` class.
- `nodes[].outputs` — for `external_mutation` nodes, contains the evidence you need to compose a reversal.

```bash
# template effects — cache once
curl -sS http://localhost:8766/api/templates > /tmp/templates.json
```

---

## 3. Build a reversal plan — per node, in REVERSE execution order

Walk the node list from last to first. For each one, classify:

### Read-only nodes
`manual_trigger`, `transform_jsonpath`, `branch`, `output` — nothing to revert. Skip.

### Local-mutation nodes (`bash` with a git-tracked `cwd`)
The git checkpoints did the work. You don't need to revert each bash node individually — just use the checkpoints.

If `pre_run_git_checkpoints` is present:
- For each `{repo_path: pre_sha}` pair, propose either:
  - **Hard reset** (destroys everything since): `git -C <repo_path> reset --hard <pre_sha>` — use when the user wants "undo everything including my hand-edits since the run."
  - **Revert commits** (preserves history, safer): `git -C <repo_path> revert --no-commit <pre_sha>..HEAD && git -C <repo_path> commit -m "Revert yorph-automate run <short_id>"` — use as the default.
- Check the current HEAD first. If it's already at `pre_sha`, there's nothing to revert.
- If the user has committed other things in that repo since the run's `post_sha`, warn them — those commits will either be lost (reset) or come out as revert commits (revert).

### Local-mutation nodes (`bash` WITHOUT a tracked cwd)
We have no snapshot. Tell the user honestly: "This bash node (`node_id`) ran `<command>` — I can't automatically undo it because the target wasn't in a git repo. You'll need to [handle manually, or we can try specific compensations if the command has a natural inverse like rm/mkdir]."

### External-mutation nodes (`http_request` non-GET, `claude_prompt`, custom action templates)
These are the hard cases. Look at the stored output:

- **`http_request` POST/PUT** — check the response body. If it contains an id field (`id`, `_id`, `uuid`, `ticket_id`, etc.), you can likely compose a compensating DELETE:
  ```
  POST https://api.example.com/orders → response {"id": "ord_123"}
  → compensate: DELETE https://api.example.com/orders/ord_123
  ```
  Propose the compensating request in the plan but DO NOT fire it without the user's explicit "yes, delete that." Include the credentials/headers the node was configured with (mask secrets when showing).

- **`http_request` DELETE** — usually not reversible (you'd need a backup). Tell the user.

- **`http_request` PATCH/PUT** — only reversible if you know the prior value. Sometimes the node's inputs contain "before" state; sometimes not. Be honest if you can't.

- **`claude_prompt`** — the LLM generation itself has no side effect. But if `allowed_tools` was set, the model may have called tools that did have side effects. Say so: "This node asked Claude to act with `[Bash, WebSearch]` tools — I can't be certain what Claude did. Check the response text for clues, or walk any git/filesystem changes separately."

- **Sent message / email / Slack / SMS etc.** (user-authored action templates) — almost always irreversible. Offer a follow-up action: "Want me to send a retraction?"

### Node status = `failed` or `skipped` or `reused`
- `failed`: the node attempted but didn't complete. If it's an external_mutation, the side effect *may* have partially landed — look at the outputs/error for clues. Be conservative.
- `skipped`: didn't run, nothing to revert.
- `reused`: didn't re-execute, but its effect already happened in the ORIGINAL run. If the user wants to revert the original run, target that one instead.

---

## 4. Present the plan

Show the user a numbered list of concrete actions, in the order you'll execute them. Include:
- The command or request for each step.
- What it'll undo.
- What it CAN'T undo (with honest reasons).
- Any safety concerns (uncommitted work, destructive flags).

Example:

> Here's the plan to revert run `abc12345`:
>
> **Will revert:**
> 1. `git -C /Users/me/projects/foo revert --no-commit c832e4c..f2e41d7 && git commit -m "Revert yorph-automate run abc12345"` — undoes the 2 commits made by the workflow, preserves history.
> 2. `curl -X DELETE "https://api.slack.com/messages/1699999999.001234" -H "Authorization: Bearer ••••4321"` — deletes the Slack message posted by node `notify_team`.
>
> **Cannot revert:**
> - Node `send_welcome_email` sent email to new-user@example.com. Email recall isn't supported by this provider. Want me to send a retraction email?
>
> Reply **yes** to execute steps 1–2, or tell me which steps to skip.

Wait for explicit confirmation. "Yes" / "go ahead" / "do it" = proceed. Anything else = stop and clarify.

---

## 5. Execute

Run each step sequentially. After each:
- Print the command + its stdout/stderr/exit-code.
- If it fails, STOP. Don't plow through. Tell the user what's broken and ask whether to continue.

For git operations, always confirm the new HEAD at the end so the user sees the state.

For HTTP compensations, show the response status + body.

---

## 6. Audit trail

Log the revert as its own entry so it's auditable later. One approach — write a small marker JSON to `~/.yorph/automate/reverts/<original_run_id>.json`:

```bash
mkdir -p ~/.yorph/automate/reverts
cat > ~/.yorph/automate/reverts/$RUN_ID.json <<EOF
{
  "reverted_run": "$RUN_ID",
  "reverted_at": "$(date -Iseconds)",
  "actions_executed": [ ... ],
  "actions_skipped":  [ ... ]
}
EOF
```

Mention the path to the user in your summary.

---

## Partial reverts

If the user asks for a scoped revert ("just undo the git changes", "only the slack message"), filter the plan to those actions. The rest stays in the world. Note loudly that the revert is partial so the user doesn't assume full undo.

---

## When there's nothing to revert

If every node in the run was `read_only` / `skipped`, or was `external_mutation` with no undo path, tell the user plainly:

> "Run `abc123` had no reversible effects. Its nodes all fell into one of: read-only (no effect), skipped (didn't run), or external-mutation with no compensation path (Claude prompt with no tools). Nothing to undo."

Don't invent work to look busy.

---

## Special case: the run is `running`

If the run's status is `running`, don't revert a live run. Tell the user to wait for it to finish, or to interrupt via Ctrl-C in the server terminal. Offer to revert once it terminates.
