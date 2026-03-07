#!/usr/bin/env python3
"""
Yorph Research Writer — local development server.

Pure Python standard library — no pip install required.

Usage:
    python3 server.py --project /path/to/project [--port 8765]

Example:
    python3 server.py --project ~/papers/my-paper
    python3 server.py --project . --port 9000
"""

import argparse
import email.utils
import json
import mimetypes
import os
import subprocess
import sys
import urllib.request
import urllib.parse as _urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

VIEWER_DIR = Path(__file__).parent / "viewer"

# File types surfaced in the file tree
PROJECT_EXTENSIONS = {".tex", ".bib", ".sty", ".cls", ".cfg", ".txt", ".md"}


class Handler(BaseHTTPRequestHandler):
    project_root: Path = None  # set by main() before server starts

    # ── Logging ───────────────────────────────────────────────────────────────

    def log_message(self, format, *args):
        # Only log errors, not every request
        if args and str(args[1]) >= "400":
            sys.stderr.write(f"[{args[1]}] {args[0] % args[2:]}\n")

    # ── Response helpers ──────────────────────────────────────────────────────

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_bytes(self, data: bytes, content_type: str, mtime: float = None, head_only=False):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        if mtime is not None:
            self.send_header("Last-Modified", email.utils.formatdate(mtime, usegmt=True))
        self.end_headers()
        if not head_only:
            self.wfile.write(data)

    def resolve(self, rel_path: str) -> Path:
        """Resolve a relative path inside the project root. Raises ValueError on traversal."""
        resolved = (self.project_root / rel_path).resolve()
        resolved.relative_to(self.project_root)  # raises ValueError if outside
        return resolved

    # ── Routing ───────────────────────────────────────────────────────────────

    def do_GET(self):
        self._route(head_only=False)

    def do_HEAD(self):
        self._route(head_only=True)

    def do_PUT(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        if parsed.path == "/api/file":
            self._api_put_file(qs.get("path", [""])[0])
        else:
            self.send_error(405)

    def do_POST(self):
        if self.path == "/api/compile":
            self._api_compile()
        elif self.path == "/api/commit":
            length = int(self.headers.get("Content-Length", 0))
            msg = self.rfile.read(length).decode("utf-8").strip() if length else ""
            self._api_commit(msg)
        elif self.path.startswith("/api/openalex/"):
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            if self.path == "/api/openalex/resolve":
                self._api_openalex_resolve(body)
            elif self.path == "/api/openalex/fetch":
                self._api_openalex_fetch(body)
            elif self.path == "/api/openalex/citations":
                self._api_openalex_citations(body)
            else:
                self.send_error(404)
        else:
            self.send_error(405)

    def _route(self, head_only=False):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            p = VIEWER_DIR / "index.html"
            self.send_bytes(p.read_bytes(), "text/html; charset=utf-8",
                            p.stat().st_mtime, head_only)

        elif path == "/api/files":
            self._api_files(head_only)

        elif path == "/api/file":
            self._api_get_file(qs.get("path", [""])[0], head_only)

        elif path == "/api/config":
            self._api_config(head_only)

        elif path == "/api/synctex/forward":
            self._api_synctex_forward(qs)

        elif path == "/api/synctex/inverse":
            self._api_synctex_inverse(qs)

        else:
            # Serve from project root (covers main.pdf, compiled assets, etc.)
            candidate = (self.project_root / path.lstrip("/")).resolve()
            try:
                candidate.relative_to(self.project_root)
                if candidate.is_file():
                    data = candidate.read_bytes()
                    mt = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
                    self.send_bytes(data, mt, candidate.stat().st_mtime, head_only)
                    return
            except (ValueError, PermissionError, OSError):
                pass
            self.send_error(404)

    # ── API handlers ──────────────────────────────────────────────────────────

    def _api_config(self, head_only=False):
        config_path = self.project_root / ".yorph-writer.json"
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            data = {"main": "main.tex", "engine": "pdflatex", "journal": None}
        if not head_only:
            self.send_json(data)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

    def _api_files(self, head_only=False):
        files = []
        for p in sorted(self.project_root.rglob("*")):
            if not p.is_file():
                continue
            if p.suffix not in PROJECT_EXTENSIONS:
                continue
            rel = p.relative_to(self.project_root)
            # Skip hidden directories (like .yorph-writer, .git)
            if any(part.startswith(".") for part in rel.parts):
                continue
            files.append({
                "path":  str(rel).replace("\\", "/"),
                "name":  p.name,
                "dir":   str(rel.parent).replace("\\", "/") if str(rel.parent) != "." else "",
                "mtime": p.stat().st_mtime,
            })
        if not head_only:
            self.send_json({"files": files})
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

    def _api_get_file(self, rel_path: str, head_only=False):
        if not rel_path:
            self.send_error(400)
            return
        try:
            path = self.resolve(rel_path)
        except ValueError:
            self.send_error(403)
            return
        if not path.exists():
            self.send_error(404)
            return
        try:
            stat = path.stat()
            if not head_only:
                content = path.read_text(encoding="utf-8", errors="replace")
                self.send_json({"content": content, "mtime": stat.st_mtime})
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Last-Modified", email.utils.formatdate(stat.st_mtime, usegmt=True))
                self.end_headers()
        except Exception as e:
            self.send_error(500, str(e))

    def _api_put_file(self, rel_path: str):
        if not rel_path:
            self.send_error(400)
            return
        try:
            path = self.resolve(rel_path)
        except ValueError:
            self.send_error(403)
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
            self.send_json({"ok": True, "mtime": path.stat().st_mtime})
        except Exception as e:
            self.send_error(500, str(e))

    def _synctex_pdf_path(self):
        config_path = self.project_root / ".yorph-writer.json"
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            main = cfg.get("main", "main.tex")
        except Exception:
            main = "main.tex"
        return self.project_root / (Path(main).stem + ".pdf")

    def _api_synctex_forward(self, qs):
        """Editor → PDF: given file + line, return the PDF page number."""
        file_rel = qs.get("file", [""])[0]
        line     = qs.get("line", ["1"])[0]
        pdf_path = self._synctex_pdf_path()
        file_abs = str((self.project_root / file_rel).resolve())
        try:
            r = subprocess.run(
                ["synctex", "view", "-i", f"{line}:0:{file_abs}", "-o", str(pdf_path)],
                capture_output=True, text=True, timeout=5,
            )
            page = None
            for ln in r.stdout.splitlines():
                if ln.startswith("Page:"):
                    page = int(ln.split(":")[1].strip())
                    break
            if page:
                self.send_json({"page": page})
            else:
                self.send_json({"error": "no sync point found"})
        except Exception as e:
            self.send_json({"error": str(e)})

    def _api_synctex_inverse(self, qs):
        """PDF → editor: given page + x + y (in PDF pts), return file + line."""
        page = qs.get("page", ["1"])[0]
        x    = qs.get("x",    ["0"])[0]
        y    = qs.get("y",    ["0"])[0]
        pdf_path = self._synctex_pdf_path()
        try:
            r = subprocess.run(
                ["synctex", "edit", "-o", f"{page}:{x}:{y}:{pdf_path}"],
                capture_output=True, text=True, timeout=5,
            )
            input_file = line_num = None
            for ln in r.stdout.splitlines():
                if ln.startswith("Input:"):
                    input_file = ln[6:].strip()
                elif ln.startswith("Line:"):
                    try: line_num = int(ln[5:].strip())
                    except ValueError: pass
            if input_file and line_num is not None:
                # Return path relative to project root
                try:
                    rel = str(Path(input_file).resolve().relative_to(self.project_root))
                except ValueError:
                    rel = Path(input_file).name
                self.send_json({"file": rel, "line": line_num})
            else:
                self.send_json({"error": "no sync point found"})
        except Exception as e:
            self.send_json({"error": str(e)})

    def _api_commit(self, message: str):
        if not message:
            import datetime
            message = f"checkpoint {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
        cwd = str(self.project_root)
        try:
            subprocess.run(["git", "add", "-A"], cwd=cwd, capture_output=True)
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=cwd, capture_output=True, text=True,
            )
            if result.returncode == 0:
                # Extract short hash from first line of output
                first_line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
                self.send_json({"success": True, "detail": first_line or message})
            else:
                out = (result.stdout + result.stderr).strip()
                # "nothing to commit" is not an error worth surfacing as failure
                if "nothing to commit" in out:
                    self.send_json({"success": True, "detail": "Nothing to commit"})
                else:
                    self.send_json({"success": False, "detail": out})
        except Exception as e:
            self.send_json({"success": False, "detail": str(e)})

    # ── OpenAlex API handlers ─────────────────────────────────────────────

    def _api_openalex_resolve(self, body):
        """Search OpenAlex for papers by title. Parallelized for speed."""
        titles = body.get("titles", [])
        if not titles:
            self.send_json({"results": []})
            return

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {pool.submit(_resolve_one_title, t): t for t in titles}
            results = []
            for f in as_completed(futures):
                results.append(f.result())

        # Re-sort to match input order
        title_order = {t: i for i, t in enumerate(titles)}
        results.sort(key=lambda r: title_order.get(r["query_title"], 999))

        self.send_json({"results": results})

    def _api_openalex_fetch(self, body):
        """Batch-fetch OpenAlex works by ID. Returns full metadata."""
        ids = body.get("ids", [])  # short IDs like "W2123456789"
        if not ids:
            self.send_json({"works": []})
            return

        works = []
        # OpenAlex allows up to 50 IDs per filter query
        for start in range(0, len(ids), 50):
            batch = ids[start:start + 50]
            filter_str = "|".join(batch)
            url = _openalex_url("/works", {
                "filter": f"openalex:{filter_str}",
                "per_page": "200",
            })
            try:
                data = _openalex_get(url)
                for work in data.get("results", []):
                    works.append(_extract_work(work))
            except Exception:
                pass

        self.send_json({"works": works, "total": len(works)})

    def _api_openalex_citations(self, body):
        """Get forward citations (papers that cite the given works), sorted by impact."""
        ids = body.get("ids", [])  # short IDs
        max_results = min(body.get("max_results", 200), 200)
        if not ids:
            self.send_json({"citations": []})
            return

        all_citations = []
        seen = set()
        # Batch IDs into groups of 25 for the cites: filter
        for start in range(0, len(ids), 25):
            batch = ids[start:start + 25]
            filter_str = "|".join(batch)
            url = _openalex_url("/works", {
                "filter": f"cites:{filter_str}",
                "per_page": str(max_results),
                "sort": "cited_by_count:desc",
            })
            try:
                data = _openalex_get(url)
                for work in data.get("results", []):
                    wid = work.get("id", "")
                    if wid not in seen:
                        seen.add(wid)
                        all_citations.append(_extract_work(work))
            except Exception:
                pass

        # Sort all by citation count descending
        all_citations.sort(key=lambda w: w.get("cited_by_count", 0), reverse=True)

        self.send_json({
            "citations": all_citations[:max_results],
            "total": len(all_citations),
        })

    # ── Compile ──────────────────────────────────────────────────────────

    def _api_compile(self):
        config_path = self.project_root / ".yorph-writer.json"
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            main = config.get("main", "main.tex")
        except Exception:
            main = "main.tex"

        stem = Path(main).stem  # e.g. "main" from "main.tex"
        tex_args = ["pdflatex", "-interaction=nonstopmode", "-file-line-error", "-synctex=1", main]
        cwd = str(self.project_root)
        full_log = ""

        def run_step(cmd, timeout=120):
            result = subprocess.run(
                cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
            )
            return result.stdout + result.stderr, result.returncode

        try:
            # Pass 1 — generate .aux (citations/refs unresolved, that's expected)
            log1, _ = run_step(tex_args)
            full_log += f"=== pdflatex pass 1 ===\n{log1}\n"

            # BibTeX pass — run if a .aux with \bibdata exists (non-fatal if absent)
            aux_path = self.project_root / f"{stem}.aux"
            needs_bibtex = aux_path.exists() and "\\bibdata" in aux_path.read_text(errors="ignore")
            if needs_bibtex:
                log_bib, _ = run_step(["bibtex", stem])
                full_log += f"=== bibtex ===\n{log_bib}\n"

            # Pass 2 — resolve citations
            log2, _ = run_step(tex_args)
            full_log += f"=== pdflatex pass 2 ===\n{log2}\n"

            # Pass 3 — resolve cross-references
            log3, rc3 = run_step(tex_args)
            full_log += f"=== pdflatex pass 3 ===\n{log3}\n"

            success = rc3 == 0
            errors = _parse_errors(log3)  # report errors from final pass only

            self.send_json({
                "success": success,
                "log": full_log,
                "errors": errors,
                "main": main,
            })

        except FileNotFoundError:
            self.send_json({
                "success": False,
                "log": "pdflatex not found in PATH.",
                "errors": ["pdflatex not found. Is TeX Live or MacTeX installed?"],
                "main": main,
            })
        except subprocess.TimeoutExpired:
            self.send_json({
                "success": False,
                "log": full_log + "\n[timed out]",
                "errors": ["Compilation timed out (120s per pass)."],
                "main": main,
            })


def _parse_errors(log: str) -> list:
    """Extract human-readable error lines from a pdflatex log."""
    errors = []
    lines = log.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("!"):
            # Collect the error block (! line + l.N continuation)
            block = [line]
            j = i + 1
            while j < len(lines) and j < i + 5:
                next_line = lines[j]
                if next_line.startswith("!"):
                    break
                if next_line.strip():
                    block.append(next_line.rstrip())
                j += 1
            errors.append("\n".join(block))
            i = j
        else:
            # file-line-error format: ./foo.tex:42: message
            parts = line.split(":", 2)
            if (
                len(parts) >= 3
                and ".tex" in parts[0]
                and parts[1].strip().isdigit()
                and not line.startswith("(")
            ):
                errors.append(line.rstrip())
            i += 1
    return errors


# ── OpenAlex helpers ──────────────────────────────────────────────────────────

OPENALEX_BASE = "https://api.openalex.org"


def _openalex_url(path, params=None):
    """Build an OpenAlex API URL."""
    url = f"{OPENALEX_BASE}{path}"
    if params:
        url += "?" + _urlparse.urlencode(params, doseq=True)
    return url


def _openalex_get(url):
    """GET JSON from OpenAlex."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "yorph-research-writer/1.0",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _reconstruct_abstract(inverted_index):
    """Reconstruct plain text from OpenAlex's inverted-index abstract format."""
    if not inverted_index:
        return ""
    positions = []
    for word, idxs in inverted_index.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    return " ".join(w for _, w in positions)


def _extract_work(work):
    """Pull relevant fields from an OpenAlex work object."""
    authors = []
    for a in work.get("authorships", [])[:6]:
        name = a.get("author", {}).get("display_name", "")
        if name:
            authors.append(name)
    return {
        "openalex_id": work.get("id", ""),
        "title": work.get("title", ""),
        "authors": authors,
        "year": work.get("publication_year"),
        "cited_by_count": work.get("cited_by_count", 0),
        "abstract": _reconstruct_abstract(work.get("abstract_inverted_index")),
        "referenced_works": [r.split("/")[-1] for r in work.get("referenced_works", [])],
        "doi": work.get("doi", ""),
    }


def _resolve_one_title(title):
    """Search OpenAlex for a single title, return best match or None."""
    try:
        # Try title.search filter first (more precise), fall back to generic search
        url = _openalex_url("/works", {
            "filter": f"title.search:{title}",
            "per_page": "3",
        })
        data = _openalex_get(url)
        hits = data.get("results", [])
        if not hits:
            # Fallback: generic search (broader, catches partial matches)
            url = _openalex_url("/works", {"search": title, "per_page": "3"})
            data = _openalex_get(url)
            hits = data.get("results", [])
        if hits:
            return {"query_title": title, "match": _extract_work(hits[0])}
        return {"query_title": title, "match": None}
    except Exception as e:
        return {"query_title": title, "match": None, "error": str(e)}


GITIGNORE = """\
# LaTeX build artifacts
*.aux
*.bbl
*.bcf
*.blg
*.fdb_latexmk
*.fls
*.lof
*.log
*.lot
*.out
*.run.xml
*.synctex.gz
*.toc
*.pdf

# Yorph writer internal state
.yorph-writer/
"""

def ensure_git_repo(project_root: Path):
    """Init a git repo with a LaTeX .gitignore if one doesn't exist yet."""
    if (project_root / ".git").exists():
        return
    cwd = str(project_root)
    gitignore = project_root / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(GITIGNORE)
        print("  Created  : .gitignore")
    subprocess.run(["git", "init", "-q"], cwd=cwd)
    subprocess.run(["git", "add", "-A"], cwd=cwd, capture_output=True)
    result = subprocess.run(
        ["git", "commit", "-q", "-m", "yorph-writer: initial commit"],
        cwd=cwd, capture_output=True, text=True,
    )
    if result.returncode == 0:
        print("  Git      : initialized + initial commit")
    else:
        print(f"  Git      : init failed — {result.stderr.strip()}")


def main():
    parser = argparse.ArgumentParser(
        description="Yorph Research Writer — local LaTeX IDE server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 server.py --project ~/papers/my-paper\n"
            "  python3 server.py --project . --port 9000\n"
        ),
    )
    parser.add_argument("--project", required=True,
                        help="Path to the LaTeX project directory")
    parser.add_argument("--port", type=int, default=8765,
                        help="Port to listen on (default: 8765)")
    args = parser.parse_args()

    project_root = Path(args.project).resolve()
    if not project_root.is_dir():
        print(f"Error: not a directory: {project_root}", file=sys.stderr)
        sys.exit(1)

    ensure_git_repo(project_root)
    Handler.project_root = project_root

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://localhost:{args.port}"

    print(f"\n  ◆ Yorph Research Writer")
    print(f"  Project : {project_root}")
    print(f"  Viewer  : {url}")
    print(f"  Stop    : Ctrl+C\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
