---
name: compile
description: Start the Yorph Research Writer viewer server, and/or compile a LaTeX project using pdflatex — diagnosing and fixing errors in a loop until the build succeeds. Use when the user asks to open the viewer, start the IDE, compile, build, render, fix LaTeX errors, or generate a PDF.
---

# Compile

Two related responsibilities handled by this skill:

1. **Starting the viewer server** — launch the local IDE so the user can edit, compile, and preview from a browser
2. **Fixing compile errors** — when the user asks Claude to fix LaTeX errors (either from the viewer's log or from a paste), diagnose and fix them directly in the source files

---

## Starting the viewer server

The Yorph Research Writer is a browser-based local IDE served by a single Python script. No pip install — Python standard library only.

### Server location

The server script is `server.py` in the plugin root. Given this skill file is at:
```
<plugin-root>/skills/compile/SKILL.md
```
The server is at:
```
<plugin-root>/server.py
```

### How to start it

```bash
python3 /path/to/yorph-research-writer/server.py --project /path/to/project
```

Run in the background and open the browser:

```bash
# Check if already running on the default port
nc -z localhost 8765 2>/dev/null && echo "already running" || echo "not running"

# Start in background (if not already running)
python3 /path/to/yorph-research-writer/server.py --project /path/to/project &

# Open in browser
open http://localhost:8765        # macOS
xdg-open http://localhost:8765   # Linux
```

### For Claude Code
Use the Bash tool to run the commands above. Resolve the plugin path from the path of this skill file.

### For Claude Cowork
Use whatever shell execution mechanism is available — the command is identical. The server uses only Python stdlib and will work in any Python 3.6+ environment.

### Custom port
```bash
python3 server.py --project ./my-paper --port 9000
```
Then open `http://localhost:9000`.

### What the server does
- Serves the browser IDE at `http://localhost:8765/`
- Exposes `GET/PUT /api/file` for reading and writing `.tex` files
- Exposes `GET /api/files` for the file tree
- Exposes `POST /api/compile` for the compile button (runs `pdflatex` directly)
- Serves the compiled PDF so the viewer can auto-refresh it

After the server starts, the user controls compilation via the **▶ Compile** button in the browser. Claude does not need to run `pdflatex` directly unless the user pastes errors into the chat and asks for help.

---

## Fixing compile errors (conversational)

When the user shares compile errors from the viewer log (or asks Claude to fix them after a failed compile), use this process.

### 1. Locate the project

Read `.yorph-writer.json` for `main` (the entry `.tex` file). The project root is the directory containing this file.

### 2. Compile loop (up to 5 iterations)

If the user wants Claude to compile directly (e.g., no server running), run:

```bash
pdflatex -interaction=nonstopmode -file-line-error main.tex 2>&1
```

**Key flags:**
- `-interaction=nonstopmode` — don't stop for user input
- `-file-line-error` — emit errors as `./file.tex:LINE: message`

### 3. Parse and fix errors

**Error formats:**

```
! Undefined control sequence.
l.45   \somebadcommand

./sections/method.tex:45: Undefined control sequence.
./main.tex:88: Missing $ inserted.
```

**Common errors and fixes:**

| Error | Cause | Fix |
|-------|-------|-----|
| `Undefined control sequence` | Typo in command or missing package | Fix typo or add `\usepackage{...}` |
| `Missing $ inserted` | Math command outside math mode | Wrap in `$...$` or `\(...\)` |
| `File '*.sty' not found` | Package not installed | Check name; suggest `tlmgr install <pkg>` |
| `Runaway argument` | Unclosed brace `{` | Find and close the brace |
| `Extra }, or forgotten $` | Mismatched delimiters | Balance `{}` or `$$` |
| `\begin{env} ended by \end{other}` | Mismatched environment | Fix environment name |
| `Citation ... undefined` | BibTeX key missing | Add reference or fix key typo |
| `Overfull \hbox` | Line too long | Warning only — ignore unless severe |

**For each error:**
1. Open the indicated file and line with the Read tool
2. Understand the error in context
3. Apply a minimal fix with the Edit tool
4. Note the fix: `Fixed main.tex:88 — wrapped \frac in math mode`

### 4. Loop until clean

Repeat up to 5 iterations. If still failing after 5:
- Show the user the remaining errors
- Explain what was tried
- Ask if they want to continue or examine specific lines

### 5. Second pass for cross-references

After a clean compile, run once more to resolve `\ref{}`, `\cite{}`, and table of contents:

```bash
pdflatex -interaction=nonstopmode -file-line-error main.tex
```

If a `.bib` file is present, run BibTeX between passes:

```bash
bibtex main
pdflatex -interaction=nonstopmode -file-line-error main.tex
pdflatex -interaction=nonstopmode -file-line-error main.tex
```

### 6. Report

On success:
```
✓ Compiled successfully (2 passes)
  Output: main.pdf

Fixes applied:
  • main.tex:88 — wrapped \alpha in math mode
  • sections/method.tex:45 — closed unclosed brace
```

On failure after 5 iterations:
```
✗ Compile failed after 5 attempts. Remaining errors:

  ./main.tex:102: Undefined control sequence \mycommand
    → Not defined anywhere. Did you mean \textbf?

Would you like to fix these manually or should I keep trying?
```
