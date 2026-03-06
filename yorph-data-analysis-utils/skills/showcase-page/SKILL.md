---
name: showcase-page
description: Use this skill when a user wants to create a showcase, demo, or explainer page for a tool, technique, plugin, or method — especially one that involves a before/after transformation, a naive-vs-smart comparison, or a concrete before/after narrative. Triggers include: "make a page for this skill", "showcase this technique", "build a demo page", "create a landing page for this method", "document this tool for builders", "make an explainer page". The output is a single self-contained HTML file using the Yorph design system.
---

# Showcase Page

A single-page HTML document that explains a tool or method to a technical, skeptical audience. The core pattern is always **before vs. after**: what breaks without this, what works with it. No marketing language. No vague claims. Every number on the page must be traceable to data shown on the page.

---

## Step 1: Understand the tool

Before writing anything, establish:

1. **What problem does it solve?** Name the specific failure mode — not a category ("handles edge cases") but a concrete outcome ("returns the wrong answer because X").
2. **What does it actually do?** Describe it mechanically. When does it run? What does it consume? What does it produce? How often is expensive work done — once, per item, per pair?
3. **What's the before/after contrast?** For each example: what does the naive approach return and why is it wrong, and what does the skill return?
4. **What's the scale or efficiency story?** If there is one — explain the mechanism, not just a ratio or claim.
5. **Is there a source paper or prior work?** Credit it with a link.

If any of these are unclear, ask before writing.

---

## Step 2: Choose examples

Pick 1–2 concrete examples. For each:

- Use a realistic dataset appropriate to the domain — real-looking column names, plausible values
- Show actual before/after rows — not hypothetical descriptions
- Pick a question a real user of this tool would actually ask
- The naive approach must demonstrably fail or mislead — not just "be slower"
- The skill result must be clearly better in the same unit (a count, a dollar amount, a time, an error rate)

Pick examples that maximize the contrast between naive and skill approaches. The failure mode in the naive case should be obvious and embarrassing — wrong by a lot, not just slightly off. Use the minimum number of rows needed to make the point; 5–8 rows per table is usually enough.

---

## Step 3: Write the page

Build a single self-contained HTML file. Use the Yorph design system (see Design System section below). Structure:

### Nav
```html
<nav>
  <div class="nav-title">[Tool Name]</div>
  <div class="nav-meta">Claude Plugin · by Yorph AI</div>
</nav>
```

### Hero

**Headline:** Name the pain, in the user's language. Not aspirational — specific.
- ✓ Concrete failure, written the way the user would describe it
- ✗ "Unlock the full power of your [domain]."
- ✗ "Seamlessly handle [problem category]."

**Sub copy (3–4 sentences max):**
1. Name 1–2 specific failure modes with concrete examples
2. `**Solution:**` [mechanism] — describe what the tool actually does, not what it aspires to

Crisper is always better. Cut adjectives. Cut "which means". Lead with the failure.

**CTA:** If no real link exists, use a greyed-out "coming soon" button. Don't make up a link.

**Never put accuracy percentages in the hero.** Use counts or concrete measurable outcomes if you need a stat.

### Examples & What It Handles

The problem/solution contrast is the heart of the page — lead with it, right after the hero. Don't bury it behind a technique explanation.

Use 1–2 examples. For each, choose a structure that serves the story. Some common shapes:

- **Before table → after table → A/B analysis cards**: works well when the tool transforms or enriches data
- **Two input tables → A/B analysis card**: works well when the tool resolves something across sources
- **Problem cards + inline examples**: works well when the tool addresses several distinct failure modes that don't share a single dataset

These are suggestions, not a rigid template. Mix and match based on what makes the contrast clearest.

**Useful components:**

*Eyebrow* — label the example type and number:
```html
<div class="example-num">Example 01</div>
<div class="section-label">[Operation or Problem Type]</div>
```

*Section title* — concrete, with real numbers. Describe the situation, not the solution.

*Before table* — raw input. Show only what exists before the tool runs.

*After table* — same rows, new or changed columns highlighted green (`.ec.new`). Header: "After — [what was produced]".

*Problem cards* — useful for cataloguing the failure modes the tool addresses. **All must be framed as problems**, not features. If a card title sounds like a benefit, rewrite it as the failure that exists without the tool. Suggested structure: label (category of problem) → title (problem statement) → body (2 sentences on what breaks) → code block with `.ok` / `.warn` / `.messy` annotations.

*A/B analysis cards* — one card per question:
- `❌ Naive/baseline approach` · dashed red border
- `✓ With [Tool Name]` · solid green border
- **Method tag**: actual code or command, not prose
- **Result**: big number, red+strikethrough for bad, green for good
- **Result note**: one sentence — don't re-explain what the number says

The cardinal rule: anything you show has to contribute to the overarching narrative. Don't add a card, chart, or table because it's interesting — only if it earns its place in the story.

### Technique

How it works, explained mechanically. Put this *after* the examples — readers who've seen the before/after will now care about the mechanism. Readers who don't care can skip it.

Describe what the tool does at each step. The steps will differ by tool — don't force a rigid structure, but 3 phases works well if the tool has a natural decomposition. The section subtitle describes the mechanism concretely, not aspirationally.

Include a paper credit if there's a source:
```html
<div class="paper-credit">
  Based on <a href="[url]">[Paper Title]</a> — [Authors] · [Institution] · [ID] · [Year].
  [One sentence on what the paper demonstrated.]
</div>
```

### Caveats

What are the potential downsides? Be honest but don't tank the narrative.

### Links

```html
<a href="[report-page]">Technical Report</a>
<a href="[paper-or-source]">Source Paper</a>
```

Only include links that exist. Don't fabricate.

### Footer

```html
<footer>
  <span>[Tool Name] · Claude Plugin</span>
  <span>by Yorph AI</span>
  <span>Based on [Source] · [Year]</span>
</footer>
```

---

## Step 4: Self-check before delivering

- [ ] Hero sub is ≤4 sentences and ends with `**Solution:**` + mechanism
- [ ] No accuracy percentages anywhere on the page
- [ ] Every number is derivable from data shown on the page
- [ ] Any problem cards are framed as failures, not features or benefits
- [ ] Method tags show actual syntax/code, not prose descriptions
- [ ] Every element on the page earns its place in the narrative
- [ ] Analysis cards only reference data that appears in the shown tables
- [ ] Technique section comes *after* the examples, not before
- [ ] Scale callout (if present) explains the mechanism, not just a ratio
- [ ] No "unlock", "seamlessly", "powerful", or other vague marketing language
- [ ] Stats include a denominator where relevant ("8 of 10" not "8")

---

## Design System

### Palette

| Token | Value | Use |
|-------|-------|-----|
| `--bg-page` | `#f5f0e8` | Page background |
| `--bg-card` | `#ffffff` | Cards |
| `--bg-cream` | `#ede8dc` | Callout sections, table headers |
| `--bg-code` | `#1a1a18` | Code blocks, method tags |
| `--text-primary` | `#1a1a18` | Body text |
| `--text-muted` | `#8a8578` | Subtitles, labels, notes |
| `--text-code` | `#e8c97a` | Code text |
| `--accent-red` | `#c84b2f` | Section labels, error states, naive result borders |
| `--accent-green` | `#2a5f4f` | After table headers, skill results, paper credit |
| `--accent-blue` | `#5b9bd5` | Bar chart fills (secondary) |
| `--accent-orange` | `#e8a040` | Warnings, flagged states |
| `--border` | `#c8c2b4` | Card borders, table lines |
| `--border-strong` | `#1a1a18` | Hero bottom border, section dividers |

### Fonts

```html
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=IBM+Plex+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
```

| Font | Role |
|------|------|
| Playfair Display | H1, section titles, result numbers, card titles |
| IBM Plex Mono | Labels, method tags, nav, phase tags, all uppercase metadata |
| DM Sans 300 | Body copy, challenge descriptions |

### Key components

**Section label** — red, mono, 10px, uppercase, 0.25em letter-spacing. Used above every section title.

**Method tag** — dark background (`--bg-code`), code text (`--text-code`), 10px mono, inline-block. Always contains actual syntax or a command, never a prose description.

**Phase tag** — green, mono, 9px, uppercase. Shows cost or complexity callout relevant to this tool's mechanism.

**Challenge code block** — dark background, mono 11px, line-height 1.8. Use `.ok` (green `#a8e6a0`) for resolved/good output, `.warn` (orange) for flagged/uncertain, `.messy` (red) for raw/problematic input.

**Before table header:** `background: var(--text-primary); color: var(--bg-page)`
**After table header:** `background: var(--accent-green); color: var(--bg-page)`
**New/changed columns:** `.ec.new` → `background: #e8f4ef; color: var(--accent-green); font-weight: 500`
**Problematic input:** `.ec.messy` → `color: var(--accent-red)`

**Naive result container:** `background: #fdf6f4; border: 1px dashed #e0b0a0`
**Skill result container:** `background: #f2f8f5; border: 1px solid #a8d4c2`

**Result number — good:** `color: var(--accent-green); font-family: Playfair Display; font-size: 2rem; font-weight: 700`
**Result number — bad:** same + `text-decoration: line-through; opacity: 0.6; color: var(--accent-red)`

**Hero border:** `border-bottom: 3px double var(--border-strong)`
**Footer border:** `border-top: 3px double var(--border-strong)`

### Layout

- Max content width: 1080px, centered, 56px horizontal padding (24px on mobile)
- Hero: single column text block
- Analysis cards: `grid-template-columns: 1fr 1fr`, 20px gap
- Challenge grid: `grid-template-columns: 1fr 1fr`, 12px gap
- Phase grid: `grid-template-columns: repeat(3, 1fr)`, 32px gap
- Split tables (two inputs side by side): `grid-template-columns: 1fr 1fr`, 12px gap

### Animations

```css
.fade-in { opacity: 0; transform: translateY(14px); animation: fadeUp 0.55s forwards; }
.d1 { animation-delay: 0.1s; }
.d2 { animation-delay: 0.2s; }
.d3 { animation-delay: 0.3s; }
@keyframes fadeUp { to { opacity: 1; transform: none; } }
```

Apply `.fade-in` to hero, technique section, example sections, and scale callout. Stagger with `.d1`, `.d2`, `.d3`.

---

## Anti-patterns

| ❌ Don't | ✓ Instead |
|---------|-----------|
| "Unlock the power of [domain]" | Name the specific failure mode that goes away |
| Accuracy percentages | Counts, dollar amounts, time savings, error rates |
| Numbers not derivable from visible data | Only cite what's in the shown tables |
| Challenge card titles that sound like benefits | Rewrite as the failure: what goes wrong without this tool |
| Downstream analysis without upstream data | Only show what the shown data supports |
| Vague scale claims ("10× faster", "drastically reduces") | Explain the mechanism — what expensive step is eliminated or batched |
| Long hero sub | 3–4 sentences: failure modes → `**Solution:**` + mechanism |
| Stats without denominators | "8 of 10" not "8" |
| Aspirational phase descriptions | Describe what the tool literally does at each step |
