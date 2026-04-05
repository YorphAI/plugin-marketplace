---
name: setup
description: Walk the user through setting up the Yorph Research Writer for the first time, or when opening a new session. Checks dependencies, picks or creates a project, starts the local server, and opens the browser IDE. Use this skill when the user says anything like "open the writer", "start the IDE", "run the server", "open my paper", or "get started".
---

# Setup

The entry point for every session. Walks the user through dependency checks, project selection, and launching the browser IDE. Keep it conversational and fast — most steps should require no input from the user at all.

---

## 1. Check dependencies

Run these silently. Only surface failures.

```bash
# Check Python 3 (required)
python3 --version

# Check pdflatex (required for compilation, not for the IDE itself)
which pdflatex && pdflatex --version | head -1
```

**If `python3` is missing:** Stop. Python 3 is required to run the server. Ask the user to install it from https://python.org.

**If `pdflatex` is missing:**

The IDE — editor, file tree, PDF viewer — works fine without it. The user just won't be able to hit ▶ Compile until it's installed. The choice of package does not affect the UI in any way.

Tell the user:

> `pdflatex` isn't installed. You can still open and edit your project now, but compilation won't work until it's set up. Two options:
>
> **BasicTeX** (~100MB) — just the engine. Lean, fast to install. If your project uses less common `.sty` packages, you may need to install them individually after with `sudo tlmgr install <package-name>`.
> ```bash
> brew install --cask basictex
> ```
>
> **MacTeX** (~4GB) — the full TeX Live distribution. Includes everything. No package hunting.
> ```bash
> brew install --cask mactex
> ```
>
> Which would you prefer?

Wait for the user's answer. Then tell them to run the install command themselves in their terminal — the `.pkg` installer requires an interactive `sudo` password prompt that Claude cannot provide through its shell. Example:

> Run this in your terminal (not here), then come back:
> ```bash
> brew install --cask basictex
> ```

Once they confirm it's done, reload PATH and verify:

```bash
# After install, reload PATH (MacTeX/BasicTeX install to /Library/TeX/texbin)
eval "$(/usr/libexec/path_helper)"
which pdflatex && echo "pdflatex ready"
```

Once they confirm it's done, also scan the project for missing packages upfront (see **Missing packages** below) so the user can install everything in one shot before hitting ▶ Compile.

Note: the server is launched with the current shell's PATH. If pdflatex was just installed, **restart the server** after installing so it picks up the new PATH (see step 4 for the restart command).

If the user wants to skip TeX installation for now and just use the editor, that's fine — continue to step 2.

### Missing packages — scan upfront

Do NOT wait for compile errors to reveal missing packages one by one. After TeX is installed and a project is selected, proactively scan all `.tex` files for `\usepackage` declarations and check which ones aren't already installed:

```bash
# Extract all package names used in the project
grep -rh '\\usepackage' /path/to/project/ --include="*.tex" 2>/dev/null \
  | sed 's/.*\\usepackage[^{]*{\([^}]*\)}.*/\1/' \
  | tr ',' '\n' | sed 's/^ *//' | sed 's/ *$//' \
  | grep -v '^\[' | grep -v '^$' | sort -u

# Check which are already available
PATH="/Library/TeX/texbin:$PATH" kpsewhich <pkg1>.sty <pkg2>.sty ...
```

**Filtering:**
- Packages already found by `kpsewhich` → skip
- Packages with a `.sty` file already in the project folder → skip (bundled journal styles)
- Packages not found → need `tlmgr install`

Note that tlmgr package names sometimes differ from `.sty` names:
| `\usepackage{...}` | `tlmgr install` |
|--------------------|-----------------|
| `algorithm`        | `algorithms`    |
| `algpseudocode`    | `algorithmicx`  |
| `pgfplotstable`    | `pgfplots`      |
| `times`            | `psnfss`        |

**Do not install packages one by one.** Instead, install the standard TeX Live collections that cover virtually all academic paper packages — this is the practical middle ground between BasicTeX's minimal install and MacTeX's full 4GB download (~500MB total):

```bash
sudo tlmgr install collection-latexextra collection-fontsrecommended collection-science
```

Tell the user to run this in their terminal. After this, missing `.sty` errors should not occur for any normal academic paper.

If any packages still can't be found after this (journal-specific `.sty` files like `jair.sty`, `tacl2021v1.sty` that aren't on CTAN), tell the user they'll need to copy those files from the machine where the paper was originally compiled into the project folder alongside `main.tex`.

---

## 2. Ask: new project or existing?

Ask the user directly in the chat:

> "Do you want to open an existing LaTeX project, or start a new one from scratch?"

Based on their answer, go to step 3a or 3b.

---

## 3a. Existing project — open a folder picker

On **macOS**, invoke the native Finder folder picker:

```bash
osascript -e 'POSIX path of (choose folder with prompt "Select your LaTeX project folder:")'
```

This opens a native OS dialog. The output is the selected folder path (e.g. `/Users/alex/papers/my-paper`).

On **Linux**, try:
```bash
zenity --file-selection --directory --title="Select your LaTeX project folder" 2>/dev/null
```

If `zenity` is not available, ask the user to paste the path directly in the chat.

Once you have the path:
1. Verify it exists and contains at least one `.tex` file
2. Identify the main `.tex` file (contains `\documentclass`) — see the navigate skill for details
3. Create or update `.yorph-writer.json` if it doesn't already exist:
   ```json
   { "main": "main.tex", "engine": "pdflatex", "journal": null }
   ```

---

## 3b. New project — scaffold

Ask for a project name (one word or hyphenated, e.g. `my-paper`).

Ask where to put it, or default to the current working directory.

Then scaffold following the `new-project` command spec: create the folder, write `main.tex`, `references.bib`, and `.yorph-writer.json`.

---

## 4. Start the server

The server script is at `server.py` in the plugin root (two directories up from this skill file — `../../server.py` relative to `skills/setup/SKILL.md`).

### Check if already running

```bash
nc -z localhost 8765 2>/dev/null && echo "running" || echo "not running"
```

### Start if not running

```bash
python3 /path/to/yorph-research-writer/server.py --project /path/to/project &
```

Wait 1 second, then verify it started:
```bash
nc -z localhost 8765 2>/dev/null && echo "up" || echo "failed to start"
```

If it failed to start (port already in use), kill the old instance first:
```bash
lsof -ti:8765 | xargs kill 2>/dev/null
sleep 1
# then retry the start command above
```

If pdflatex was just installed in this session, always restart the server — it inherits PATH at launch time, so an already-running server won't see the newly installed binary.

### Open the browser

```bash
open http://localhost:8765      # macOS
xdg-open http://localhost:8765  # Linux
```

---

## 5. Confirm and orient the user

Once the browser is open, give a brief one-line summary:

> "You're all set. The IDE is open at http://localhost:8765 — your project is `my-paper/main.tex`. Hit ▶ Compile to build the PDF, or just start talking to me to edit sections."

Then stop. Don't enumerate features or give a tutorial unless asked. The user knows what they want.

---

## Session persistence

If the server is already running (step 4 check returns `running`), skip straight to opening the browser. Don't restart the server — it's stateless and the existing instance is fine.

If the user just wants to switch projects, stop the old server first:
```bash
# Find and kill the server on port 8765
lsof -ti:8765 | xargs kill 2>/dev/null
```
Then start a new one with the new project path.
