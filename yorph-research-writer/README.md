# Yorph Research Writer

A LaTeX research paper authoring environment that runs entirely through Claude. Write, compile, navigate, and critique academic papers without leaving your conversation — with a live browser-based PDF viewer that auto-refreshes every time you compile.

## What it does

- **Author in LaTeX** — draft and revise sections by describing what you want in plain English; Claude writes and edits the `.tex` directly
- **Compile with auto-fix** — the `/compile` command runs `pdflatex` in a loop, automatically diagnosing and fixing errors until the build succeeds
- **Live PDF viewer** — a browser-based viewer (PDF.js) opens alongside your session and reloads automatically on every successful compile
- **Navigate large papers** — the `/navigate` skill parses your section structure and pulls only the relevant chunks into context for any given task
- **Blind peer review** — `/critique` puts Claude in the role of an anonymous reviewer to stress-test your arguments before submission

## Quick start

```
/new-project my-paper          # scaffold a new LaTeX project
/open-project ./existing-paper # open an existing .tex project
/compile                       # compile to PDF and open the viewer
/navigate                      # show the paper's section structure
/critique                      # run a blind peer review
```

## Project structure

When you create or open a project, a `.yorph-writer.json` file is created at the project root:

```json
{
  "main": "main.tex",
  "engine": "pdflatex",
  "journal": null
}
```

A `.yorph-writer/` working directory is also created for viewer assets and the generated table of contents (`toc.json`). You can add `.yorph-writer/` to your `.gitignore`.

## Extending with skills

This plugin is designed to be extended. Future skills might include:

- `journal-format` — apply a specific journal's style template (NeurIPS, IEEE, ACM, APA)
- `citation-manager` — manage references and format BibTeX entries
- `literature-review` — structure a related work section from a list of papers
- `abstract-writer` — draft or refine an abstract given the full paper

## Installing as a Cursor plugin

- **Team marketplace (Cursor Teams/Enterprise):** In Cursor Dashboard → Settings → Plugins → Team Marketplaces, add this repository’s URL (the `yorph-marketplace` repo that contains `yorph-research-writer`). Then open the Plugins panel in Cursor and install **yorph-research-writer** from your team marketplace.
- **Public marketplace:** You can submit the plugin at [cursor.com/marketplace/publish](https://cursor.com/marketplace/publish) for review so others can install it from the main Cursor Marketplace.

After install, use `/compile`, `/navigate`, `/critique`, and the other skills from chat.

## Requirements

- `pdflatex` installed and on your PATH (comes with TeX Live or MacTeX)
- Python 3 (for the local HTTP server used by the PDF viewer)
- A modern browser (Chrome, Firefox, Safari)
