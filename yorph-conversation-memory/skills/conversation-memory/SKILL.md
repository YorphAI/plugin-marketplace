---
name: conversation-memory
description: Save and recall conversation context that survives compaction. Use when the user says "checkpoint", "save memory", "recall", or when you need to look up specific details from earlier in a long conversation. No active sessions yet.
---

# Conversation Memory

Long conversations lose detail when the context window compacts. This skill writes structured memory to disk so you can look up specifics later.

## Active Sessions

_No sessions yet. Say "checkpoint" to create one._

<!-- SESSIONS_TABLE (this marker is used during checkpoint rewrites) -->

## Quick Reference

- **Save**: user says "checkpoint" (optionally "checkpoint as {name}") → read [instructions.md](instructions.md) § Checkpoint
- **Recall**: you need an earlier detail → scan the keywords in the table above, then read `.memory/{session}/{topic}.md`
- **Cleanup**: user says "clean up memory" or "delete session {name}" → read [instructions.md](instructions.md) § Cleanup

For full procedures, read [instructions.md](instructions.md).
