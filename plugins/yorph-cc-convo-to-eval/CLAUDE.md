# claude-eval

Conversation eval system for Claude Code plugins. Captures real conversations as regression test cases and replays key checkpoints to catch regressions when plugin code changes.

## Project structure

```
claude_eval/
  __init__.py       # Package init
  models.py         # Dataclasses: ToolRecord, ConversationTurn, CheckpointResult, EvalReport
  constants.py      # classify_tool() — generic rules + per-project config overrides
  extract.py        # JSONL parser → eval case builder
  runner.py         # Checkpoint-based eval runner (re-executes live tools)
  judge.py          # Diff classifier (pass/regression/drift/improvement)
  cli.py            # CLI entry point: claude-eval save|run|list|delete|init

tests/
  test_extract.py   # Unit tests for parsing + classification
  test_runner.py    # Unit tests for checkpoint runner

.claude-plugin/
  plugin.json       # Claude plugin definition
  skills/
    save-eval/
      SKILL.md      # /save-eval skill instructions
```

## How it works

1. `/save-eval` or `claude-eval save` reads the current Claude Code session's JSONL log
2. Each tool call is classified: **live** (re-execute), **stub** (cache), **capture** (compare), **skip** (ignore)
3. The eval case is saved to `<project>/.claude/evals/<name>/`
4. `claude-eval run <name>` re-executes live tool calls against the current codebase and compares results

## Tool classification defaults

- All `mcp__*` tools → stub (external state, cached from golden run)
- `Read`/`Glob`/`Grep` on project files → live (tests your current code)
- `Bash` → live (re-runs local scripts)
- `Write`/`Edit` → capture (compared against golden, not persisted)
- `WebFetch`/`WebSearch` → stub
- `TodoWrite`/`AskUserQuestion`/etc. → skip

Override via `.claude/eval-config.json` in the target project.

## Running tests

```bash
cd /Users/alexbraylan/Documents/Yorph/claude-eval
pip install -e ".[test]"
pytest -v
```
