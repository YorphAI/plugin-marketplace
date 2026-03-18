# yorph-cc-convo-to-demo

Generate embeddable HTML demo widgets from Claude Code conversations.
Extracts human-readable conversation turns from JSONL session logs and renders
them as self-contained HTML files styled like the Claude Desktop chat interface.

## Project structure

```
yorph-cc-convo-to-demo/
  .claude-plugin/plugin.json
  CLAUDE.md
  skills/
    make-demo/
      SKILL.md              # Skill instructions
      scripts/
        extract.py          # Parse JSONL → conversation turns JSON
        render.py           # Conversation turns JSON → HTML file
```

## How it works

1. `/make-demo` scans the current conversation and identifies demo-worthy segments
2. The user confirms which turns to include/exclude
3. `extract.py` reads the JSONL session log, strips tool calls/thinking/system
   reminders, and outputs a clean JSON array of conversation turns
4. `render.py` takes the JSON turns and produces a standalone HTML file plus an
   embeddable snippet, both styled to match the Claude Desktop chat UI
5. Output is saved to `<project-root>/demos/<name>.html`
