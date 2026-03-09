# Conversation Memory — Full Instructions

## Overview

Memory is stored at `.memory/` in the project root. Each **session** is a named folder containing topic files and an INDEX.md.

```
.memory/
  {session-name}/
    INDEX.md
    {topic-a}.md
    {topic-b}.md
```

The SKILL.md file's description and Active Sessions section are rewritten at every checkpoint so the session index appears directly in the system prompt on subsequent turns — including after compaction.

---

## Checkpoint

Triggered when the user says "checkpoint", "save memory", "checkpoint as {name}", or similar.

### Steps

1. **Determine session name.**
   - If the user provides a name: use it, lowercased with hyphens (e.g., "data migration" → `data-migration`).
   - If no name given and an active session exists for this conversation: reuse it.
   - If no name given and no active session: derive a short descriptive name from the work so far.

2. **Create the session directory** if it doesn't exist:
   ```
   mkdir -p .memory/{session-name}
   ```

3. **Categorize what you know** into topics. Good topic boundaries:

   | Topic type | What goes in it | Example filename |
   |---|---|---|
   | Schema / data shape | Column names, types, nullability, FK relationships, sample values | `data-schema.md` |
   | Decisions | Choices made and why, rejected alternatives | `decisions.md` |
   | Errors & fixes | Problems encountered, root causes, solutions applied | `errors-resolved.md` |
   | Findings / analysis | Key numbers, patterns, intermediate results | `findings.md` |
   | Plan / progress | Current plan state, what's done, what's next | `plan.md` |
   | Configuration | Connection strings, env setup, tool versions | `config.md` |
   | Open questions | Unresolved issues, things to investigate | `open-questions.md` |

   Use judgment — not every checkpoint needs all topics. Only write topics where you have meaningful content. Merge small topics rather than creating many thin files.

4. **Write each topic file.** Format:

   ```markdown
   # {Topic Title}
   Last updated: {YYYY-MM-DD HH:MM}

   ## {Subtopic or category}
   - Concrete facts, specific values, exact names
   - Reference column names, file paths, error messages verbatim
   - Note reasoning and trade-offs, not just conclusions

   ## {Another subtopic}
   ...
   ```

   Rules:
   - Be specific. Write `customer_id (INT, FK→orders.id, not null)` not "the customer ID column."
   - Include both the fact and the reasoning. "Chose LEFT JOIN because source has orphan records (14% of rows)" is better than "used LEFT JOIN."
   - If updating an existing topic file: update in place. Don't append duplicates — replace stale content with current state.

5. **Write INDEX.md** for the session:

   ```markdown
   # {Session Name}
   Last checkpoint: {YYYY-MM-DD HH:MM}

   ## Topics
   - `{topic-a}.md` — one-line description of what's in it
   - `{topic-b}.md` — one-line description of what's in it
   ```

6. **Rewrite SKILL.md** to update the system prompt index. The rewritten file must preserve all sections but update two things:

   **a. The `description` field in frontmatter.**

   Include session names with aggregated keywords — these are the search index that lets the agent match a user's question to the right memory. Format:
   ```
   description: Save and recall conversation context that survives compaction. Active sessions — {name} ({kw1}, {kw2}, {kw3}, ...); {name2} ({kw4}, {kw5}). Use when the user says "checkpoint", "save memory", "recall", or when you need to look up specific details from earlier work.
   ```
   **Budget: keep the description under 512 characters** (half the 1024-char limit, to leave headroom for future sessions). Pick ~5–10 of the most distinctive keywords per session — terms the user or agent would likely say when they need that information back. Prefer proper nouns, tool names, error types, and concept names over generic words. If many sessions exist, list only the 2–3 most recent and add "(+ N more in .memory/)".

   **b. The Active Sessions section.**

   Replace the content between `## Active Sessions` and `<!-- SESSIONS_TABLE -->` with a table that has **one row per topic** with a keywords column:

   ```markdown
   ## Active Sessions

   | Session | Topic | Keywords | Updated |
   |---------|-------|----------|---------|
   | {name} | {topic-a} | {keyword1}, {keyword2}, {keyword3}, ... | {YYYY-MM-DD HH:MM} |
   | {name} | {topic-b} | {keyword4}, {keyword5}, ... | {YYYY-MM-DD HH:MM} |

   <!-- SESSIONS_TABLE (this marker is used during checkpoint rewrites) -->
   ```

   **Keyword guidelines:**
   - 3–8 keywords per topic row
   - Use terms the user actually said or would say, not internal jargon
   - Include proper nouns, tool names, column names, error types — anything distinctive
   - If a concept was discussed under multiple names (e.g., "hooks" and "callbacks"), include both
   - Keywords should enable matching: if the user later says "what about the vector store idea", the keyword "vector store" in a topic row should make the match obvious

   **c. Preserve everything else** (the intro paragraph, Quick Reference section, etc.) exactly as-is.

7. **Confirm to the user**: list what was saved, how many topics, and the session name.

---

## Recall

Use this whenever you need a specific detail that isn't in your current context — either because compaction removed it or because it was from a previous session.

### Steps

1. **Check the SKILL.md Active Sessions table** (already in your system prompt if you read the skill, or visible in the description keywords). Scan the Keywords column for terms matching what you need.

2. **Read the topic file**: `.memory/{session}/{topic}.md`
   - If you're unsure which topic: read `.memory/{session}/INDEX.md` for one-line descriptions.
   - If you need to search across topics: use Grep on `.memory/{session}/` for a keyword.

3. **Use the recalled information** in your response. Reference the source if relevant ("per the earlier schema analysis, `customer_id` is an INT FK to orders").

### When to recall proactively

If all of these are true, proactively check memory before answering:
- The conversation has a compacted summary (you see a summary but no detailed early turns)
- `.memory/` is referenced in SKILL.md Active Sessions
- The user's question involves specifics (exact names, values, decisions) that the summary might have compressed

---

## Cleanup

Triggered when the user says "clean up memory", "delete session {name}", or "clear all sessions."

### Delete a specific session

1. Delete the folder: `rm -rf .memory/{session-name}`
2. Rewrite SKILL.md to remove that session's rows from the description and Active Sessions table.
3. If no sessions remain, restore the "No sessions yet" placeholder.

### Delete all sessions

1. Delete the entire memory directory: `rm -rf .memory`
2. Rewrite SKILL.md to the initial state (no sessions, placeholder text).

### Prune old sessions

If the user asks to clean up but doesn't specify which:
1. List all sessions with their last checkpoint date.
2. Suggest deleting sessions older than 7 days.
3. Wait for user confirmation before deleting.

---

## Edge Cases

- **Same session name, new checkpoint**: update existing topic files in place. Don't create a second folder.
- **Multiple sessions**: each is independent. The SKILL.md table lists all of them.
- **Very large topic file**: if a topic exceeds ~200 lines, split it into subtopics (e.g., `data-schema-source.md` and `data-schema-target.md`).
- **Conflicting information**: if a new checkpoint contradicts an earlier one, overwrite the old content. Add a note: "Previously: X. Updated to Y because Z."
- **Memory directory doesn't exist**: create it. `mkdir -p .memory/{session-name}`.
- **SKILL.md was manually edited**: preserve any manual additions outside the Active Sessions section and description field.

---

## Gitignore

On first checkpoint, if `.memory/` is not already in `.gitignore`, add it:

```
# Conversation memory (agent working context)
.memory/
```

This keeps session-specific working context out of version control.
