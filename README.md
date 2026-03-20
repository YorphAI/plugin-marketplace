# Yorph Plugin Marketplace

Yorph builds AI-powered plugins for [Claude Code](https://claude.ai/code) that automate high-effort workflows. Each plugin is a self-contained Claude Code plugin you can install in minutes.

---

## Plugins

| Plugin | Description |
|---|---|
| [yorph-semantic-layer-builder](./yorph-semantic-layer-builder) | Connect to your data warehouse and any existing data dictionaries or documentation to co-author a fully-documented semantic layer — validated joins, certified metrics, business rules, and a plain-English companion doc — with the help of a 10-agent analysis DAG |
| [yorph-data-analyst](./yorph-data-analyst) | Describe what you want to know in plain English; two agents handle the rest — one plans and communicates, one writes and runs the transformation pipeline — no SQL required |
| [yorph-research-writer](./yorph-research-writer) | A full LaTeX authoring environment inside Claude Code: edit sections, compile to PDF, run a blind peer review, and explore the citation graph — in a local browser preview |
| [yorph-cc-convo-to-demo](./yorph-cc-convo-to-demo) | Extract the best moments from a Claude Code conversation and render them as a self-contained HTML widget styled like Claude Desktop — shareable, embeddable, no dependencies |
| [yorph-cc-convo-to-eval](./yorph-cc-convo-to-eval) | Snapshot a conversation that went well (or badly) as a replayable eval test case — so you can catch regressions automatically when you change your plugin's prompts or skills |
| [yorph-eval-dueling](./yorph-eval-dueling) | Run two skills head-to-head on the same inputs, judge outputs against a structured rubric, and get a ranked comparison — useful for deciding whether a prompt change is actually an improvement |
| [yorph-conversation-memory](./yorph-conversation-memory) | Persistent memory that survives context compaction — Claude remembers decisions, preferences, and context from earlier in long sessions even after the window rolls over |

---

## Installation

### Option A — GitHub marketplace (install any or all plugins)

In Claude Code: **Customize → Browse Plugins → Personal → + → Add Marketplace from GitHub** → enter `https://github.com/YorphAI/plugin-marketplace` → install the plugins you want.

### Option B — Upload a zip (install one plugin)

Each plugin has a prebuilt zip linked in its own README. Download it, then in Claude Code: **Customize → + next to Personal Plugins → upload zip**.

---

## Contributing

Issues and PRs welcome. Each plugin lives in its own directory with its own README.
