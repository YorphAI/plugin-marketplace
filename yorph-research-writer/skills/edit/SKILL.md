---
name: edit
description: Apply targeted changes to a section of the paper. Always clarifies approach before editing. Supports surgical insertions, moderate restructuring, full rewrites, and flag-only annotation. Use for any writing edit task.
---

# Edit

Applies writing changes to a LaTeX section with the author's prose protected by default. The golden rule: **never overwrite what the user wrote without explicit mandate.**

---

## Step 1 — Locate the section

Use the navigate skill to find the section:

1. Check the skeleton for `[file:line]` of the target section.
2. If the skeleton doesn't have it, grep for the section heading.
3. Read from the section start line to the next same-level or higher-level heading. Use `Read(file, offset=start, limit=length)`.
4. Display the section with a header: `--- intro.tex (lines 8–44) ---`

---

## Step 2 — Clarify approach (if not already specified)

If the instruction is vague or does not specify how to edit — trigger words include *rewrite*, *improve*, *buff up*, *fix pacing*, *enhance*, *make it better*, *clean up*, *strengthen*, *rework* — **stop and ask**:

```
How should I approach this?

  1. Surgical   — insert connecting sentences, examples, or transitions;
                  keep ~90% of the existing prose intact
  2. Moderate   — restructure paragraphs and smooth flow;
                  preserve the author's voice and arguments
  3. Full rewrite — rewrite the section from scratch following
                  the stated style guidelines
  4. Flag only  — mark issues with % TODO comments inline;
                  no content changes
```

Do not proceed until the user selects one.

If the instruction is specific and unambiguous (e.g., "add an example after paragraph 2," "fix the subject-verb disagreement in line 3," "insert a transition between the second and third paragraph"), skip the dialog and proceed with surgical mode.

---

## Step 3 — Execute according to mode

### Mode 1: Surgical

- Target only the specific lines that are too abrupt, unclear, or missing a connection.
- Use `Edit` to insert or adjust individual sentences. Do not replace whole paragraphs.
- Prefer adding *after* a sentence over replacing it.
- One `Edit` call per distinct location — do not batch unrelated changes.
- Show each proposed insertion as a quoted sentence before applying it:
  > I'll add after line 14: *"To make this concrete, consider a bounding box that is ten pixels off — it can be corrected in seconds, while one that misses the object entirely must be drawn from scratch."*

### Mode 2: Moderate

- Work at the paragraph level: reorder sentences, merge redundant ones, improve transitions.
- Before writing, show a brief before/after for the affected paragraph:
  ```
  BEFORE: "Agreement is often used at scale... [paragraph text]"
  AFTER:  "At scale, agreement measures..."
  ```
- Ask for confirmation if the change affects more than one paragraph.

### Mode 3: Full rewrite

- Write the new version in full.
- **Do not write to the file yet.** Show the rewritten text to the user first.
- Confirm: *"Should I replace the existing section with this version?"*
- Only write after explicit confirmation.

### Mode 4: Flag only

- Read the section and identify: unclear transitions, missing examples, abrupt jumps, passive constructions, unsupported claims, undefined terms.
- Insert `% TODO [brief note]` comments at the relevant lines using `Edit`.
- Do not modify any content — only add comment lines.
- Summarize the flags at the end: *"Added 4 TODO comments: lines 12, 19, 27, 35."*

---

## Step 4 — Report what changed

After every edit, output a brief change summary:

```
Changed: intro.tex
  + Line 14: added example sentence (bounding box correction)
  + Line 22: added transition ("That observation will recur...")
  ~ Line 31: softened claim ("always" → "often")

2 insertions, 1 modification. No deletions.
```

---

## Style notes (apply in all modes except flag-only)

These are defaults — override if the user specifies different preferences:

- **Oxford comma** in all lists.
- **Active voice** wherever natural.
- **Concrete before abstract**: introduce a concept with an example before naming it formally.
- **Define before use**: never use a technical term that hasn't been introduced yet in the chapter.
- Short sentences. When a sentence has two independent clauses, consider splitting it.
- Omit needless words (Strunk & White Rule 17).

---

## When to read before editing

Always read the full target section before proposing any edit. Never suggest or apply a change based only on the skeleton summary — the first sentence of a section does not represent the full paragraph.
