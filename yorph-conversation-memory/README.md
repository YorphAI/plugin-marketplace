# Yorph Conversation Memory

Conversation-scoped long-term memory for AI coding agents. Survives context window compaction in Cursor and Claude Code.

## Problem

Long conversations lose detail when the context window fills up and compacts. Post-compaction, the agent has a summary but no specifics — exact column names, error messages, decision rationale, intermediate values are all gone.

## Solution

A manually triggered checkpoint that writes structured memory to disk, organized by topic. The skill rewrites its own description to include a session index, so every subsequent turn — including after compaction — shows the agent what memory is available directly in the system prompt. The agent reads specific topic files on demand.

## How It Works

```
User: "checkpoint"  (or "checkpoint as data-migration")

  → Agent categorizes its knowledge into topic files:
      .memory/data-migration/
        INDEX.md
        data-schema.md
        decisions.md
        errors-resolved.md

  → Agent rewrites SKILL.md description:
      "Active sessions — data-migration: data-schema, decisions, errors-resolved"

  → Every future turn sees this in the system prompt
  → After compaction, agent reads the topic file it needs (one tool call)
```

## Installation

Copy the `skills/conversation-memory/` folder into your project's or personal skills directory:

```bash
# Personal (available across all projects)
cp -r skills/conversation-memory ~/.cursor/skills/conversation-memory

# Project-level (shared with collaborators)
cp -r skills/conversation-memory .cursor/skills/conversation-memory
```

## Usage

| Command | What it does |
|---------|--------------|
| "checkpoint" | Save current conversation knowledge — agent derives a session name from the topic |
| "checkpoint as {name}" | Same, but with a user-chosen session name |
| "recall" / ask for earlier details | Agent checks memory and reads the relevant topic file |
| "clean up memory" | List sessions, delete old ones |
| "delete session {name}" | Remove a specific session |

## Design

- **Host-agnostic**: works in Cursor and Claude Code — no cursor rules or host-specific hooks required
- **Lazy-loaded**: memory files sit on disk; only read when the agent needs a specific detail
- **Self-indexing**: the SKILL.md description is the index — always visible in the system prompt, zero-cost awareness
- **User-named sessions**: no auto-generated IDs; the user controls the namespace and cleanup
- **Gitignored**: `.memory/` is added to `.gitignore` on first checkpoint — working context stays out of version control
