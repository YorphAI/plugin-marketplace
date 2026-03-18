---
name: make-demo
description: >
  Generate a demo widget from the current conversation. Use when the user says
  "make demo", "make a demo", "create demo", "demo this conversation",
  "save demo", "export as demo", "demo widget", or wants to turn a conversation
  into an embeddable HTML chat replay styled like Claude Desktop.
---

# Make Demo

Turn the current conversation into an embeddable HTML demo widget that looks
like the Claude Desktop chat interface. Extracts human-readable turns, lets
the user curate which parts to include, and generates a self-contained HTML
file plus an embeddable snippet.

---

## Step 1 — Scan and propose

Before asking anything, **scan the full conversation** and identify segments
that would make a compelling demo. Look for:

- **Include** — substantive questions, clear explanations, interesting code
  examples, architectural insights, problem-solving narratives, feature
  demonstrations, aha moments
- **Exclude** — debugging loops, error recovery, typo corrections, tool call
  noise, meta-conversation about making the demo itself, system reminders,
  planning mode discussions, repetitive refinements

For each turn, write a one-line summary. Present everything in a **single
message** with checkboxes, grouped into three categories:

---

**Proposed inclusions** *(uncheck to exclude)*

> Generate 3–10 specific checkboxes based on what actually happened:
> - [x] Turn 0–1: User asks about X, Claude explains approach
> - [x] Turn 4–5: User requests code example, Claude provides implementation
> - [x] Turn 8: Claude summarizes the key takeaways

**Uncertain — please confirm** *(check to include)*

> Flag turns where it's not obvious whether they add to the demo narrative:
> - [ ] Turn 2–3: User clarifies a requirement — adds context but slows pacing?
> - [ ] Turn 6–7: Brief tangent about error handling — relevant or distracting?

**Proposed exclusions** *(check to override and include)*

> - [ ] Turn 9+: Meta-conversation about making this demo
> - [ ] Turn 3: User corrects a typo

**Demo title suggestion:** "Your Suggested Title Here"

**Description:** (optional one-liner)

---

Once the user responds, collect:
- The final list of turn indices to include
- The confirmed title
- An optional description

---

## Step 2 — Run the extractor

The `extract.py` script is in the `scripts/` folder next to this file.
The system-reminder above shows a **Base directory** path for this skill —
use that path to locate `scripts/extract.py`.

Run it with the Bash tool:

```bash
python3 "<SKILL_DIR>/scripts/extract.py" \
  --project-root "$PWD" \
  --include-turns "<comma-separated indices>" \
  --end-before "<text of the user message that invoked /make-demo>" \
  --output "/tmp/demo-turns.json"
```

Optional flags:

| Flag | Effect |
|------|--------|
| `--start-after "text"` | Only capture turns after a user message containing this text |
| `--end-before "text"` | Stop capturing before a user message containing this text |
| `--session-id <uuid>` | Use a specific session instead of the latest |
| `--include-turns "0,1,4,5"` | Whitelist specific turn indices |
| `--exclude-pattern "regex"` | Regex to exclude turns matching this text |

**Important:** Always use `--end-before` with the text of the user message
that triggered `/make-demo` so the demo-making conversation itself is excluded.

---

## Step 3 — Run the renderer

```bash
python3 "<SKILL_DIR>/scripts/render.py" \
  --input "/tmp/demo-turns.json" \
  --title "<title>" \
  --description "<description>" \
  --output "$PWD/demos/<slug>.html"
```

| Flag | Effect |
|------|--------|
| `--input <path>` | Path to the conversation JSON from extract.py |
| `--title "text"` | Demo title displayed at the top of the widget |
| `--description "text"` | Subtitle/description text (optional) |
| `--output <path>` | Where to write the HTML file |
| `--embed-only` | Output just the embeddable div (no DOCTYPE wrapper) |

The renderer automatically creates both:
- `demos/<name>.html` — standalone page you can open directly
- `demos/<name>.embed.html` — just the `<div>` for embedding in another page

---

## Step 4 — Show results

Report back to the user:

1. **Turns included** — how many conversation turns made it into the demo
2. **Saved to** — the path of the standalone HTML file
3. **Embed snippet** — the path of the embeddable version
4. **How to embed** — brief instructions:

```
To embed in your page, copy the contents of <name>.embed.html into your HTML:

<div id="my-demo-container">
  <!-- paste contents of <name>.embed.html here -->
</div>

The widget is fully self-contained with scoped CSS that won't affect
your page styles. It's responsive and works at any container width.
```

---

## Tips

- Aim for **5–15 turns** in a demo — enough to tell a story, short enough to
  hold attention.
- A good demo has a clear arc: problem → exploration → solution.
- User turns should be concise. If the user wrote very long messages, suggest
  summarizing them in the proposal (the user can then edit the extracted JSON
  before rendering).
- The HTML uses CSS custom properties, so the host page can override colors
  by setting `--cdw-bg`, `--cdw-text`, etc. on the container.
