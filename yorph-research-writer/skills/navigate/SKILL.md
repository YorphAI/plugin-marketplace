---
name: navigate
description: Navigate a LaTeX paper's structure using a progressive skeleton index. Builds and maintains a .yorph-writer/skeleton.md file that caches the paper's structure at increasing levels of detail — avoiding full file reads. Use for any task involving paper structure, section lookup, summarization, or targeted editing.
---

# Navigate

The navigate skill never loads entire `.tex` files into context. Instead, it maintains a **skeleton** — a progressively enriched index of the paper cached at `.yorph-writer/skeleton.md`. The skeleton is the source of truth for structure. Files are only read when the skeleton lacks the detail needed for the current task.

---

## The skeleton file

Location: `<project-root>/.yorph-writer/skeleton.md`

The skeleton header tracks token cost:

```markdown
<!-- yorph-skeleton -->
<!-- updated: 2026-03-04T12:34:00 -->
<!-- skeleton-tokens: 820 | session-tokens: 1400 -->

[skeleton content]
```

- **skeleton-tokens**: approximate token count of this file (rough: chars / 4)
- **session-tokens**: running total of tokens consumed from files/greps *this session* (reset each session; used to warn if approaching context limits)

Update both counts after every enrichment step.

---

## Three skeleton levels

Each level is a superset of the previous. Enrich incrementally — never downgrade.

### Level 1 — Spine
*Abstract + chapter/section titles + file locations*

```markdown
## Abstract [main.tex:8]
Quality control for complex outputs...

## Chapter 1: Introduction [intro.tex:1]
## Chapter 2: Related Work [relatedwork.tex:1]
### 2.1 Inter-Annotator Agreement [relatedwork.tex:14]
### 2.2 Aggregation Methods [relatedwork.tex:52]
## Chapter 3: Method [sections/method.tex:1]
```

Cost: ~50–200 tokens of grep output. Almost free.

### Level 2 — Subsections
*Everything in Level 1, plus `\subsubsection` entries*

```markdown
### 2.1 Inter-Annotator Agreement [relatedwork.tex:14]
#### 2.1.1 IAA for Complex Annotations [relatedwork.tex:22]
#### 2.1.2 Related Work [relatedwork.tex:38]
```

Cost: one additional grep pass. Still cheap.

### Level 3 — First sentences
*Everything in Level 2, plus the first non-empty sentence of each section/subsection body*

```markdown
### 2.1 Inter-Annotator Agreement [relatedwork.tex:14]
> Inter-annotator agreement (IAA) measures the degree to which independent annotators produce similar labels for the same items.
#### 2.1.1 IAA for Complex Annotations [relatedwork.tex:22]
> Existing IAA measures such as Cohen's κ and Krippendorff's α assume categorical or ordinal label spaces.
```

Cost: read lines 1–5 after each section header. ~5–15 tokens per section. For a 30-section paper: ~300 tokens total.

---

## Algorithm: check before reading

**Before any file read, always check the skeleton first.**

```
task → what level of detail does it need?
     → is that level already in the skeleton for the relevant sections?
        YES → answer from skeleton, no file I/O
        NO  → enrich only the missing parts, then answer
```

Token guard: if session-tokens exceeds ~60,000, warn the user before reading more:
> "I've used ~60k tokens this session navigating this paper. Should I continue, or would you like me to work from what's already in the skeleton?"

---

## Enrichment procedures

### Build Level 1 (if skeleton is empty or missing)

```bash
# 1. Find all files in document order (follow \input/\include from main.tex)
grep -n '\\input\|\\include' <project>/main.tex

# 2. Extract abstract
grep -n '\\begin{abstract}' <project>/main.tex  # then read ~10 lines

# 3. Extract chapter/section titles from all files
grep -rn '\\chapter\|\\section' <project>/ --include="*.tex" \
  | grep -v '\\subsection' \
  | grep -v '%'
```

Parse results into the skeleton format with `[file:line]` references. Write to `.yorph-writer/skeleton.md`.

### Enrich to Level 2 (add subsections)

```bash
grep -rn '\\subsection\|\\subsubsection' <project>/ --include="*.tex" \
  | grep -v '%'
```

Merge into the skeleton at the correct position under their parent section.

### Enrich to Level 3 (add first sentences)

For each section that needs a first sentence: read lines `[start_line : start_line + 8]` of the relevant file. Extract the first non-empty, non-command sentence. Add as a `>` blockquote in the skeleton.

Do this **only for sections relevant to the current task** — not the whole paper at once unless explicitly asked.

---

## Reading modes

Match the mode to the task:

| Mode | When to use | What to read | Approx tokens |
|------|-------------|--------------|---------------|
| **skim** | Structure tasks: TOC, "what's in this paper", navigation | Level 1 skeleton only. Grep if not built yet. | ~200 |
| **summarize** | Content tasks: "summarize ch3", "what does 4.2 argue" | Level 3 skeleton for target section. If missing: read first paragraph + last paragraph of section. | ~300–800 per section |
| **read** | Editing tasks: rewrite, fix, expand, critique a passage | Full section content for the specific target. Read from `[section start line]` to `[next section start line]`. | varies |

**Never use `read` mode on more than one section per task** unless the task explicitly requires it (e.g., "compare section 3 and section 5").

---

## Pulling a section for editing

When the user wants to edit a section:

1. Look up `[file:line]` from the skeleton
2. Find the line of the *next* same-level or higher-level section heading (the section boundary)
3. Read only those lines: `Read(file, offset=start_line, limit=end_line - start_line)`
4. Display it with a header: `--- sections/method.tex (lines 45–112) ---`
5. Ask what the user wants to change
6. Apply targeted edits with the Edit tool — never rewrite the whole section unless asked
7. Update session-tokens count

---

## Displaying the skeleton to the user

When asked for structure or a summary, render the skeleton as a clean outline — not raw markdown. Use the level of detail already in the skeleton; don't enrich further unless the user's question requires it.

For TOC + 1-sentence summaries, Level 3 is sufficient. Example output:

```
1  Introduction [intro.tex]
   Quality control for complex outputs is framed around agreement,
   aggregation, and confidence.

   1.1  Agreement
   1.2  Aggregation
   1.3  Confidence

2  Related Work [relatedwork.tex]
   Surveys IAA measures, aggregation models, and LLM confidence
   estimation, identifying gaps for complex output spaces.
   ...
```

---

## Updating the skeleton

After any enrichment, rewrite `.yorph-writer/skeleton.md` with updated content and header token counts. The skeleton is persistent across sessions — future tasks start from whatever level was already built.

If a `.tex` file is edited (by Claude or by the user via the browser editor), mark the affected sections in the skeleton with `[stale]` so future reads know to re-check those lines.
