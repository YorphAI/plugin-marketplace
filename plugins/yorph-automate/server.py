#!/usr/bin/env python3
"""
yorph-automate — local workflow automation server.

Pure Python standard library. No pip installs required.

Usage:
    python3 server.py [--port 8766]
    python3 server.py --run-once <workflow_id> [--payload '<json>']

Storage lives at ~/.yorph/automate/ (workflows, templates, runs.db, config.json).
Built-in templates are loaded from <plugin_dir>/templates/.
"""

from __future__ import annotations

import argparse
import copy
import email.utils
import json
import mimetypes
import os
import re
import sqlite3
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

# ── Paths ────────────────────────────────────────────────────────────────────

PLUGIN_DIR = Path(__file__).parent.resolve()
BUNDLED_TEMPLATES_DIR = PLUGIN_DIR / "templates"
VIEWER_DIR = PLUGIN_DIR / "viewer"

HOME_DIR = Path(os.environ.get("YORPH_AUTOMATE_HOME", Path.home() / ".yorph" / "automate")).resolve()
WORKFLOWS_DIR = HOME_DIR / "workflows"
USER_TEMPLATES_DIR = HOME_DIR / "templates"
RUNS_DB = HOME_DIR / "runs.db"
CONFIG_FILE = HOME_DIR / "config.json"
PID_FILE = HOME_DIR / ".server.pid"

DEFAULT_CONFIG = {
    "port": 8766,
    "claude_binary": "claude",
    "claude_default_timeout": 600,
    "max_output_bytes": 10 * 1024 * 1024,  # 10 MB cap per captured string field
}


# ── Output truncation + secret masking ───────────────────────────────────────

def _truncate(s: Any, limit: int) -> Any:
    """Cap a string at `limit` bytes (UTF-8). Non-strings pass through unchanged."""
    if not isinstance(s, str):
        return s
    b = s.encode("utf-8", errors="replace")
    if len(b) <= limit:
        return s
    head = b[:limit].decode("utf-8", errors="replace")
    return head + f"\n[... truncated {len(b) - limit} bytes ...]"


def _mask_secrets_in_config(config: Dict[str, Any], template: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of `config` with any field declared `secret: true` masked."""
    if not isinstance(config, dict):
        return config
    schema = template.get("config_schema", {}) or {}
    out: Dict[str, Any] = {}
    for k, v in config.items():
        spec = schema.get(k) or {}
        if spec.get("secret") and isinstance(v, str) and v:
            out[k] = (f"••••{v[-4:]}" if len(v) >= 4 else "••••")
        else:
            out[k] = v
    return out


def _mask_workflow_for_response(workflow: Dict[str, Any],
                                templates: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Return a deep copy of workflow with secret config fields masked."""
    w = copy.deepcopy(workflow)
    for n in w.get("nodes", []):
        tpl = templates.get(n.get("template_id"))
        if tpl:
            n["config"] = _mask_secrets_in_config(n.get("config", {}), tpl)
    return w


_DANGER_RANK = {"low": 0, "medium": 1, "high": 2}


def _aggregate_danger(workflow: Dict[str, Any],
                      templates: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Compute the max danger and set of effects across a workflow's nodes."""
    max_danger = "low"
    effects = set()
    for n in workflow.get("nodes", []):
        tpl = templates.get(n.get("template_id"))
        if not tpl:
            continue
        d = tpl.get("danger", "low")
        if _DANGER_RANK.get(d, 0) > _DANGER_RANK.get(max_danger, 0):
            max_danger = d
        effects.add(tpl.get("effect", "read_only"))
    return {"danger": max_danger, "effects": sorted(effects)}


# ── Setup ────────────────────────────────────────────────────────────────────

def ensure_home() -> None:
    """Create ~/.yorph/automate/ and its subdirs. Idempotent."""
    HOME_DIR.mkdir(parents=True, exist_ok=True)
    WORKFLOWS_DIR.mkdir(exist_ok=True)
    USER_TEMPLATES_DIR.mkdir(exist_ok=True)
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
    ensure_db()


def load_config() -> Dict[str, Any]:
    try:
        cfg = json.loads(CONFIG_FILE.read_text())
    except Exception:
        cfg = {}
    merged = {**DEFAULT_CONFIG, **cfg}
    return merged


def ensure_db() -> None:
    conn = sqlite3.connect(RUNS_DB)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id              TEXT PRIMARY KEY,
                workflow_id     TEXT NOT NULL,
                status          TEXT NOT NULL,
                started_at      REAL NOT NULL,
                ended_at        REAL,
                trigger_type    TEXT,
                trigger_payload TEXT,
                final_outputs   TEXT,
                error           TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_runs_workflow ON runs(workflow_id, started_at DESC);

            CREATE TABLE IF NOT EXISTS node_runs (
                id           TEXT PRIMARY KEY,
                run_id       TEXT NOT NULL,
                node_id      TEXT NOT NULL,
                template_id  TEXT NOT NULL,
                status       TEXT NOT NULL,
                started_at   REAL,
                ended_at     REAL,
                inputs_json  TEXT,
                outputs_json TEXT,
                error        TEXT,
                FOREIGN KEY (run_id) REFERENCES runs(id)
            );
            CREATE INDEX IF NOT EXISTS idx_node_runs_run ON node_runs(run_id);
            """
        )
        # Migrations: add columns introduced after v0.
        existing = {r[1] for r in conn.execute("PRAGMA table_info(runs)")}
        for col in ("pre_run_git_checkpoints", "post_run_git_checkpoints",
                    "workflow_snapshot", "resumed_from"):
            if col not in existing:
                conn.execute(f"ALTER TABLE runs ADD COLUMN {col} TEXT")
        conn.commit()
    finally:
        conn.close()


# ── Git checkpointing ────────────────────────────────────────────────────────

def _git_run(root: str, *args: str, timeout: int = 10) -> Tuple[int, str, str]:
    r = subprocess.run(["git", "-C", root, *args],
                       capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def _git_root(path: str) -> Optional[str]:
    try:
        rc, out, _ = _git_run(path, "rev-parse", "--show-toplevel")
        if rc == 0 and out.strip():
            return out.strip()
    except Exception:
        pass
    return None


def _git_head(root: str) -> Optional[str]:
    try:
        rc, out, _ = _git_run(root, "rev-parse", "HEAD")
        if rc == 0 and out.strip():
            return out.strip()
    except Exception:
        pass
    return None


def _git_is_dirty(root: str) -> bool:
    try:
        rc, out, _ = _git_run(root, "status", "--porcelain")
        return rc == 0 and bool(out.strip())
    except Exception:
        return False


def _git_checkpoint(root: str, message: str) -> Optional[str]:
    """If the repo is dirty, add-and-commit. Return HEAD SHA either way."""
    if _git_is_dirty(root):
        _git_run(root, "add", "-A")
        _git_run(root, "commit", "-m", message)
    return _git_head(root)


def discover_checkpoint_roots(workflow: Dict[str, Any],
                              templates: Dict[str, Dict[str, Any]]) -> List[str]:
    """Return git roots the workflow is authorized to checkpoint.

    Two sources — both opt-in, never auto-scan the server CWD:
      1. workflow-level `checkpoint_paths: [...]`
      2. bash (or other local_mutation) nodes with an explicit `cwd` config
    """
    paths: set = set()
    for p in (workflow.get("checkpoint_paths") or []):
        if isinstance(p, str):
            paths.add(os.path.abspath(os.path.expanduser(p)))
    for n in workflow.get("nodes", []):
        tpl = templates.get(n.get("template_id")) or {}
        if tpl.get("effect") != "local_mutation":
            continue
        cwd = (n.get("config") or {}).get("cwd")
        if cwd and isinstance(cwd, str):
            paths.add(os.path.abspath(os.path.expanduser(cwd)))
    roots: set = set()
    for p in paths:
        r = _git_root(p)
        if r:
            roots.add(r)
    return sorted(roots)


# ── Template + workflow loading ──────────────────────────────────────────────

def load_templates() -> Dict[str, Dict[str, Any]]:
    """Load bundled + user templates. User templates override bundled by id."""
    templates: Dict[str, Dict[str, Any]] = {}
    for d in (BUNDLED_TEMPLATES_DIR, USER_TEMPLATES_DIR):
        if not d.exists():
            continue
        for p in sorted(d.glob("*.json")):
            try:
                t = json.loads(p.read_text())
                if "id" in t:
                    t["_source"] = "bundled" if d == BUNDLED_TEMPLATES_DIR else "user"
                    t["_path"] = str(p)
                    templates[t["id"]] = t
            except Exception as e:
                sys.stderr.write(f"[template load] {p}: {e}\n")
    return templates


def load_workflow(workflow_id: str) -> Optional[Dict[str, Any]]:
    p = WORKFLOWS_DIR / f"{workflow_id}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def list_workflows_summary() -> List[Dict[str, Any]]:
    out = []
    if not WORKFLOWS_DIR.exists():
        return out
    for p in sorted(WORKFLOWS_DIR.glob("*.json")):
        try:
            wf = json.loads(p.read_text())
            out.append({
                "id": wf.get("id", p.stem),
                "name": wf.get("name", p.stem),
                "description": wf.get("description", ""),
                "triggers": [t.get("type") for t in wf.get("triggers", [])],
                "node_count": len(wf.get("nodes", [])),
                "path": str(p),
            })
        except Exception as e:
            out.append({"id": p.stem, "name": p.stem, "error": str(e), "path": str(p)})
    return out


def last_run_status(workflow_id: str) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(RUNS_DB)
    try:
        row = conn.execute(
            "SELECT id, status, started_at, ended_at FROM runs "
            "WHERE workflow_id=? ORDER BY started_at DESC LIMIT 1",
            (workflow_id,),
        ).fetchone()
        if not row:
            return None
        return {"id": row[0], "status": row[1], "started_at": row[2], "ended_at": row[3]}
    finally:
        conn.close()


# ── Interpolation ────────────────────────────────────────────────────────────

INTERP_RE = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")


def _lookup(path: str, scope: Dict[str, Any]) -> Any:
    """Resolve a dotted path like `config.channel` or `nodes.n1.output.body` against scope."""
    cur: Any = scope
    for part in path.split("."):
        if part == "":
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
        if cur is None:
            return None
    return cur


def interpolate(value: Any, scope: Dict[str, Any]) -> Any:
    """Recursively interpolate {{...}} in strings within a value. Non-strings pass through."""
    if isinstance(value, str):
        # If the entire string is a single {{x}}, return the raw value (preserves type).
        m = INTERP_RE.fullmatch(value.strip())
        if m:
            return _lookup(m.group(1).strip(), scope)

        def sub(match: re.Match) -> str:
            v = _lookup(match.group(1).strip(), scope)
            if v is None:
                return ""
            if isinstance(v, (dict, list)):
                return json.dumps(v)
            return str(v)

        return INTERP_RE.sub(sub, value)
    if isinstance(value, list):
        return [interpolate(v, scope) for v in value]
    if isinstance(value, dict):
        return {k: interpolate(v, scope) for k, v in value.items()}
    return value


# ── Static validation ────────────────────────────────────────────────────────

WORKFLOW_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
UNTRUSTED_PREFIXES = ("input.", "nodes.", "trigger")  # sources of untrusted data
# "input", "nodes", "trigger" also match (whole-token refs)
UNTRUSTED_ROOTS = {"input", "nodes", "trigger"}


def _find_interp_refs(value: Any) -> List[str]:
    """Recursively collect every `{{...}}` path expression in a value."""
    refs: List[str] = []
    if isinstance(value, str):
        for m in INTERP_RE.finditer(value):
            refs.append(m.group(1).strip())
    elif isinstance(value, dict):
        for v in value.values():
            refs.extend(_find_interp_refs(v))
    elif isinstance(value, list):
        for v in value:
            refs.extend(_find_interp_refs(v))
    return refs


def _ref_is_untrusted(ref: str) -> bool:
    """True if the interpolation path draws from an untrusted source."""
    head = ref.split(".", 1)[0]
    return head in UNTRUSTED_ROOTS


def validate_workflow(workflow: Dict[str, Any],
                      templates: Dict[str, Dict[str, Any]]) -> Dict[str, List[Dict[str, str]]]:
    """Static-check a workflow. Returns {errors: [...], warnings: [...]}."""
    errors: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []

    def err(path: str, msg: str) -> None:
        errors.append({"path": path, "message": msg})

    def warn(path: str, msg: str) -> None:
        warnings.append({"path": path, "message": msg})

    # ── shape ────────────────────────────────────────────────────────────
    wid = workflow.get("id")
    if not wid or not isinstance(wid, str):
        err("id", "workflow id is required")
    elif not WORKFLOW_ID_RE.match(wid):
        err("id", f"workflow id must be kebab-case (matched by {WORKFLOW_ID_RE.pattern!r})")

    nodes = workflow.get("nodes")
    edges = workflow.get("edges")
    if not isinstance(nodes, list):
        err("nodes", "must be a list")
        nodes = []
    if not isinstance(edges, list):
        err("edges", "must be a list")
        edges = []

    # ── nodes ────────────────────────────────────────────────────────────
    seen_ids: set = set()
    node_by_id: Dict[str, Dict[str, Any]] = {}
    for i, n in enumerate(nodes):
        base = f"nodes[{i}]"
        if not isinstance(n, dict):
            err(base, "must be an object")
            continue
        nid = n.get("id")
        if not nid:
            err(f"{base}.id", "node id is required")
            continue
        if nid in seen_ids:
            err(f"{base}.id", f"duplicate node id '{nid}'")
        seen_ids.add(nid)
        node_by_id[nid] = n

        tpl_id = n.get("template_id")
        if not tpl_id:
            err(f"{base}.template_id", "required")
            continue
        tpl = templates.get(tpl_id)
        if not tpl:
            err(f"{base}.template_id", f"unknown template '{tpl_id}'")
            continue

        # required config fields
        config = n.get("config", {}) or {}
        schema = tpl.get("config_schema", {}) or {}
        for field, spec in schema.items():
            if spec.get("required") and field not in config:
                err(f"{base}.config.{field}",
                    f"required field '{field}' missing (template '{tpl_id}')")

        # interpolation-in-shell-fields check
        shell_fields = tpl.get("shell_fields", []) or []
        for sf in shell_fields:
            if sf not in config:
                continue
            for ref in _find_interp_refs(config[sf]):
                if _ref_is_untrusted(ref):
                    err(f"{base}.config.{sf}",
                        f"injection risk: '{{{{ {ref} }}}}' interpolates untrusted data into a "
                        f"shell-sensitive field. Move the data through stdin/body instead, "
                        f"or (if you truly mean it) set \"unsafe_allow_interpolation\": true on this node.")

    # allow per-node opt-out of injection check (escape hatch)
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            continue
        if n.get("unsafe_allow_interpolation"):
            base = f"nodes[{i}]"
            # drop the corresponding errors we raised above for THIS node.
            errors[:] = [e for e in errors
                         if not (e["path"].startswith(f"{base}.config.")
                                 and "injection risk" in e["message"])]
            warn(base, "unsafe_allow_interpolation=true — injection check bypassed for this node")

    # ── edges + graph integrity ──────────────────────────────────────────
    for i, e in enumerate(edges):
        base = f"edges[{i}]"
        if not isinstance(e, dict):
            err(base, "must be an object")
            continue
        src = e.get("from")
        dst = e.get("to")
        if src not in node_by_id:
            err(f"{base}.from", f"unknown node '{src}'")
            continue
        if dst not in node_by_id:
            err(f"{base}.to", f"unknown node '{dst}'")
            continue
        # from_output must be a declared output of src's template
        src_tpl = templates.get(node_by_id[src].get("template_id")) or {}
        dst_tpl = templates.get(node_by_id[dst].get("template_id")) or {}
        src_outs = {o.get("name") for o in src_tpl.get("outputs", [])}
        dst_ins = {i.get("name") for i in dst_tpl.get("inputs", [])}
        fo = e.get("from_output")
        ti = e.get("to_input")
        if fo not in src_outs:
            err(f"{base}.from_output",
                f"'{fo}' is not a declared output of template '{src_tpl.get('id')}' "
                f"(has: {sorted(src_outs)})")
        if ti not in dst_ins:
            err(f"{base}.to_input",
                f"'{ti}' is not a declared input of template '{dst_tpl.get('id')}' "
                f"(has: {sorted(dst_ins)})")

    # cycle check (only meaningful if edges reference real nodes)
    if node_by_id and not any(e["path"].startswith("edges[") for e in errors):
        try:
            topo_sort(list(node_by_id.values()), edges)
        except ValueError as ex:
            err("edges", str(ex))

    # ── interpolation resolvability ──────────────────────────────────────
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        tpl = templates.get(n.get("template_id")) or {}
        tpl_inputs = {x.get("name") for x in tpl.get("inputs", [])}
        for ref in _find_interp_refs(n.get("config", {}) or {}):
            head = ref.split(".")
            root = head[0]
            if root == "input":
                if len(head) < 2:
                    continue  # whole-input ref is fine
                if head[1] not in tpl_inputs:
                    warn(f"nodes[{i}].config",
                         f"'{{{{ {ref} }}}}' references input '{head[1]}' not declared by template "
                         f"'{tpl.get('id')}' (has: {sorted(tpl_inputs)})")
            elif root == "nodes":
                if len(head) < 4 or head[2] != "output":
                    warn(f"nodes[{i}].config",
                         f"'{{{{ {ref} }}}}' malformed node reference; expected "
                         f"'nodes.<id>.output.<name>'")
                    continue
                ref_node = head[1]
                ref_out = head[3]
                ref_n = node_by_id.get(ref_node)
                if not ref_n:
                    warn(f"nodes[{i}].config",
                         f"'{{{{ {ref} }}}}' references unknown node '{ref_node}'")
                else:
                    ref_tpl = templates.get(ref_n.get("template_id")) or {}
                    ref_outs = {o.get("name") for o in ref_tpl.get("outputs", [])}
                    if ref_out not in ref_outs:
                        warn(f"nodes[{i}].config",
                             f"'{{{{ {ref} }}}}' references output '{ref_out}' not declared by "
                             f"template '{ref_tpl.get('id')}' (has: {sorted(ref_outs)})")
            elif root == "config":
                if len(head) < 2:
                    continue
                if head[1] not in (n.get("config") or {}) and head[1] not in (tpl.get("config_schema") or {}):
                    warn(f"nodes[{i}].config",
                         f"'{{{{ {ref} }}}}' references config field '{head[1]}' "
                         f"not present on this node and not declared in template schema")

    return {"errors": errors, "warnings": warnings, "ok": len(errors) == 0}


# ── DAG execution ────────────────────────────────────────────────────────────

def topo_sort(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[str]:
    """Return node ids in topological order. Raises ValueError on cycles or unknown refs."""
    ids = {n["id"] for n in nodes}
    for e in edges:
        if e["from"] not in ids or e["to"] not in ids:
            raise ValueError(f"edge references unknown node: {e}")
    indeg: Dict[str, int] = {nid: 0 for nid in ids}
    outgoing: Dict[str, List[str]] = {nid: [] for nid in ids}
    for e in edges:
        indeg[e["to"]] += 1
        outgoing[e["from"]].append(e["to"])
    queue = [nid for nid, d in indeg.items() if d == 0]
    order: List[str] = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for m in outgoing[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    if len(order) != len(ids):
        raise ValueError("workflow has a cycle")
    return order


def gather_node_inputs(
    node_id: str,
    edges: List[Dict[str, Any]],
    node_outputs: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    inputs: Dict[str, Any] = {}
    for e in edges:
        if e["to"] != node_id:
            continue
        src_outputs = node_outputs.get(e["from"], {})
        from_out = e.get("from_output")
        to_in = e.get("to_input")
        if from_out is None or to_in is None:
            continue
        # Skip if upstream did not produce this output (e.g. branch inactive side).
        if from_out not in src_outputs or src_outputs.get(from_out) is _NOT_PRODUCED:
            continue
        inputs[to_in] = src_outputs[from_out]
    return inputs


_NOT_PRODUCED = object()


class ExecutionError(Exception):
    def __init__(self, message: str, node_id: str):
        super().__init__(message)
        self.node_id = node_id


def _load_prior_node_runs(run_id: str) -> Dict[str, Dict[str, Any]]:
    """Return {node_id: node_run_row_dict} for a prior run. Empty if run missing."""
    out: Dict[str, Dict[str, Any]] = {}
    conn = sqlite3.connect(RUNS_DB)
    try:
        rows = conn.execute(
            "SELECT node_id, template_id, status, outputs_json FROM node_runs WHERE run_id=?",
            (run_id,),
        ).fetchall()
    finally:
        conn.close()
    for r in rows:
        try:
            outputs = json.loads(r[3]) if r[3] else {}
        except Exception:
            outputs = {}
        out[r[0]] = {"template_id": r[1], "status": r[2], "outputs": outputs}
    return out


def run_workflow(
    workflow: Dict[str, Any],
    templates: Dict[str, Dict[str, Any]],
    config: Dict[str, Any],
    trigger_payload: Any = None,
    trigger_type: str = "manual",
    resume_from_run_id: Optional[str] = None,
) -> str:
    """Execute a workflow end-to-end. Returns the run_id.

    If `resume_from_run_id` is given, any node that previously succeeded AND
    whose entire upstream cone was also reused this run is marked `reused` —
    its outputs are copied from the prior run without re-executing. As soon as
    any node re-executes, all of its downstream dependents also re-execute.
    """
    prior_node_runs: Dict[str, Dict[str, Any]] = (
        _load_prior_node_runs(resume_from_run_id) if resume_from_run_id else {}
    )
    reused_this_run: set = set()
    run_id = str(uuid.uuid4())
    started = time.time()
    # ── git pre-run checkpoint ──────────────────────────────────────────
    # Capture the SHA of each git root this workflow is authorized to touch,
    # committing any dirty state first so the "before" state is recoverable.
    pre_checkpoints: Dict[str, Optional[str]] = {}
    for root in discover_checkpoint_roots(workflow, templates):
        pre_checkpoints[root] = _git_checkpoint(
            root, f"yorph-automate: pre-run checkpoint for {workflow['id']} ({run_id[:8]})"
        )
    conn = sqlite3.connect(RUNS_DB)
    conn.execute(
        "INSERT INTO runs (id, workflow_id, status, started_at, trigger_type, "
        "trigger_payload, pre_run_git_checkpoints, workflow_snapshot, resumed_from) "
        "VALUES (?, ?, 'running', ?, ?, ?, ?, ?, ?)",
        (run_id, workflow["id"], started, trigger_type,
         json.dumps(trigger_payload) if trigger_payload is not None else None,
         json.dumps(pre_checkpoints) if pre_checkpoints else None,
         json.dumps(workflow),
         resume_from_run_id),
    )
    conn.commit()

    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    node_by_id = {n["id"]: n for n in nodes}

    try:
        order = topo_sort(nodes, edges)
    except ValueError as e:
        conn.execute(
            "UPDATE runs SET status='failed', ended_at=?, error=? WHERE id=?",
            (time.time(), f"DAG error: {e}", run_id),
        )
        conn.commit()
        conn.close()
        return run_id

    # Scope visible to interpolation: config, input (per-node), nodes (cumulative outputs).
    node_outputs: Dict[str, Dict[str, Any]] = {}
    final_outputs: Dict[str, Any] = {}  # from `output` template nodes

    try:
        for nid in order:
            node = node_by_id[nid]
            template_id = node.get("template_id")
            template = templates.get(template_id)
            if not template:
                raise ExecutionError(f"unknown template: {template_id}", nid)

            # Resume: reuse a prior node's outputs iff it succeeded AND every
            # upstream edge source was also reused this run (contiguous prefix).
            # This must run BEFORE the manual_trigger special-case — otherwise
            # `t` never enters reused_this_run and downstream can't reuse.
            prior = prior_node_runs.get(nid)
            if prior and prior.get("status") == "succeeded" \
                    and prior.get("template_id") == template_id:
                incoming = [e for e in edges if e["to"] == nid]
                all_upstream_reused = all(e["from"] in reused_this_run for e in incoming)
                if all_upstream_reused:
                    outputs = prior.get("outputs") or {}
                    node_outputs[nid] = outputs
                    reused_this_run.add(nid)
                    _record_node(conn, run_id, nid, template_id, "reused",
                                 {}, outputs, None, time.time(), time.time())
                    # terminal `output` nodes still need their label populated
                    # for the run's final_outputs bag.
                    if template_id == "output":
                        raw_inputs = gather_node_inputs(nid, edges, node_outputs)
                        label = (node.get("config") or {}).get("label", nid)
                        final_outputs[label] = raw_inputs.get("value")
                    continue

            # Seed manual_trigger from trigger_payload.
            if template_id == "manual_trigger":
                outputs = {"payload": trigger_payload}
                node_outputs[nid] = outputs
                _record_node(conn, run_id, nid, template_id, "succeeded",
                             {}, outputs, None, time.time(), time.time())
                continue

            # If ANY incoming edge is gated off by an upstream branch that took
            # the other side, skip this node entirely and propagate the gated
            # state to its declared outputs.
            incoming = [e for e in edges if e["to"] == nid]
            gated = False
            for e in incoming:
                src_outputs = node_outputs.get(e["from"], {})
                from_out = e.get("from_output")
                if from_out in src_outputs and src_outputs[from_out] is _NOT_PRODUCED:
                    gated = True
                    break
            if gated:
                skipped_outputs = {o["name"]: _NOT_PRODUCED
                                   for o in template.get("outputs", [])}
                node_outputs[nid] = skipped_outputs
                _record_node(conn, run_id, nid, template_id, "skipped",
                             {}, {}, None, time.time(), time.time())
                continue

            raw_inputs = gather_node_inputs(nid, edges, node_outputs)

            scope = {
                "config": node.get("config", {}),
                "input": raw_inputs,
                "nodes": {oid: {"output": out} for oid, out in node_outputs.items()},
                "trigger": trigger_payload,
            }
            # Interpolate both the node config and the template runtime spec.
            node_config = interpolate(node.get("config", {}), scope)
            scope["config"] = node_config  # refresh with interpolated values
            runtime_spec = interpolate(copy.deepcopy(template.get("runtime", {})), scope)

            n_started = time.time()
            try:
                outputs = dispatch(runtime_spec, node_config, raw_inputs, scope, config, template)
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                _record_node(conn, run_id, nid, template_id, "failed",
                             raw_inputs, None, err, n_started, time.time())
                raise ExecutionError(err, nid) from e

            node_outputs[nid] = outputs or {}
            _record_node(conn, run_id, nid, template_id, "succeeded",
                         raw_inputs, outputs, None, n_started, time.time())

            # Terminal: output nodes go into the run's final_outputs bag.
            if template_id == "output":
                label = node_config.get("label", nid)
                final_outputs[label] = raw_inputs.get("value")

        post_checkpoints = _post_run_checkpoints(pre_checkpoints, workflow["id"], run_id, "succeeded")
        conn.execute(
            "UPDATE runs SET status='succeeded', ended_at=?, final_outputs=?, "
            "post_run_git_checkpoints=? WHERE id=?",
            (time.time(), json.dumps(final_outputs, default=str),
             json.dumps(post_checkpoints) if post_checkpoints else None, run_id),
        )
        conn.commit()
    except ExecutionError as e:
        post_checkpoints = _post_run_checkpoints(pre_checkpoints, workflow["id"], run_id, "failed")
        conn.execute(
            "UPDATE runs SET status='failed', ended_at=?, error=?, "
            "post_run_git_checkpoints=? WHERE id=?",
            (time.time(), f"node {e.node_id}: {e}",
             json.dumps(post_checkpoints) if post_checkpoints else None, run_id),
        )
        conn.commit()
    except Exception as e:
        post_checkpoints = _post_run_checkpoints(pre_checkpoints, workflow["id"], run_id, "failed")
        conn.execute(
            "UPDATE runs SET status='failed', ended_at=?, error=?, "
            "post_run_git_checkpoints=? WHERE id=?",
            (time.time(), f"internal: {e}\n{traceback.format_exc()}",
             json.dumps(post_checkpoints) if post_checkpoints else None, run_id),
        )
        conn.commit()
    finally:
        conn.close()

    return run_id


def _post_run_checkpoints(pre: Dict[str, Optional[str]],
                          workflow_id: str, run_id: str, status: str) -> Dict[str, Optional[str]]:
    """After a run, commit any dirty state in each checkpointed root and return the new SHA map."""
    post: Dict[str, Optional[str]] = {}
    for root in pre.keys():
        post[root] = _git_checkpoint(
            root, f"yorph-automate: post-run ({status}) for {workflow_id} ({run_id[:8]})"
        )
    return post


def _sanitize(obj: Any) -> Any:
    """Strip internal sentinels (e.g. _NOT_PRODUCED) before JSON serialization."""
    if obj is _NOT_PRODUCED:
        return None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items() if v is not _NOT_PRODUCED}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj if v is not _NOT_PRODUCED]
    return obj


def _record_node(conn, run_id, node_id, template_id, status,
                 inputs, outputs, error, started, ended) -> None:
    conn.execute(
        "INSERT INTO node_runs (id, run_id, node_id, template_id, status, "
        "started_at, ended_at, inputs_json, outputs_json, error) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), run_id, node_id, template_id, status,
         started, ended,
         json.dumps(_sanitize(inputs), default=str) if inputs is not None else None,
         json.dumps(_sanitize(outputs), default=str) if outputs is not None else None,
         error),
    )
    conn.commit()


# ── Runtime dispatch ─────────────────────────────────────────────────────────

def dispatch(
    runtime_spec: Dict[str, Any],
    node_config: Dict[str, Any],
    raw_inputs: Dict[str, Any],
    scope: Dict[str, Any],
    server_config: Dict[str, Any],
    template: Dict[str, Any],
) -> Dict[str, Any]:
    rt_type = runtime_spec.get("type", "noop")

    if rt_type == "noop":
        return {}

    if rt_type == "http_request":
        return _run_http(runtime_spec, node_config, raw_inputs)

    if rt_type == "claude_prompt":
        return _run_claude_prompt(node_config, raw_inputs, scope, server_config)

    if rt_type == "jsonpath":
        return _run_jsonpath(node_config, raw_inputs)

    if rt_type == "branch":
        return _run_branch(node_config, raw_inputs)

    if rt_type == "bash":
        return _run_bash(node_config, raw_inputs)

    if rt_type == "output":
        # output node has no outputs; final_outputs handled in run_workflow.
        return {}

    raise ValueError(f"unknown runtime type: {rt_type}")


def _run_http(runtime_spec, node_config, raw_inputs) -> Dict[str, Any]:
    method = (node_config.get("method") or runtime_spec.get("method") or "GET").upper()
    url = node_config.get("url") or runtime_spec.get("url")
    if not url:
        raise ValueError("http_request: missing url")
    headers = node_config.get("headers") or {}
    body = raw_inputs.get("body")
    if body is None:
        body = node_config.get("body")
    timeout = node_config.get("timeout_seconds", 30)

    data: Optional[bytes] = None
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body).encode("utf-8")
            headers.setdefault("Content-Type", "application/json")
        elif isinstance(body, bytes):
            data = body
        else:
            data = str(body).encode("utf-8")

    cap = load_config().get("max_output_bytes", 10 * 1024 * 1024)
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            # Read capped — +1 so we can detect overflow.
            raw = resp.read(cap + 1)
            over = len(raw) > cap
            if over:
                raw = raw[:cap]
            resp_headers = dict(resp.headers.items())
            ct = (resp_headers.get("Content-Type") or "").lower()
            if "json" in ct and not over:
                try:
                    parsed = json.loads(raw.decode("utf-8"))
                except Exception:
                    parsed = raw.decode("utf-8", errors="replace")
            else:
                parsed = raw.decode("utf-8", errors="replace")
                if over:
                    parsed = parsed + f"\n[... truncated, response exceeded {cap} bytes ...]"
            return {"status": resp.status, "body": parsed, "headers": resp_headers}
    except urllib.error.HTTPError as e:
        raw = e.read(cap + 1) if hasattr(e, "read") else b""
        over = len(raw) > cap
        if over:
            raw = raw[:cap]
        try:
            parsed = json.loads(raw.decode("utf-8")) if not over else raw.decode("utf-8", errors="replace")
        except Exception:
            parsed = raw.decode("utf-8", errors="replace") if raw else ""
        if over and isinstance(parsed, str):
            parsed = parsed + f"\n[... truncated, response exceeded {cap} bytes ...]"
        return {"status": e.code, "body": parsed, "headers": dict(e.headers.items()) if e.headers else {}}


def _run_claude_prompt(node_config, raw_inputs, scope, server_config) -> Dict[str, Any]:
    prompt = node_config.get("prompt", "")
    if not prompt:
        raise ValueError("claude_prompt: missing prompt")
    output_format = (node_config.get("output_format") or "json").lower()
    timeout = node_config.get("timeout_seconds", server_config.get("claude_default_timeout", 600))
    claude_bin = server_config.get("claude_binary", "claude")

    cmd = [claude_bin, "-p", prompt]
    if output_format in ("json", "text"):
        cmd += ["--output-format", output_format]
    allowed = node_config.get("allowed_tools")
    if allowed:
        if isinstance(allowed, list):
            cmd += ["--allowedTools", ",".join(allowed)]
        elif isinstance(allowed, str):
            cmd += ["--allowedTools", allowed]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise RuntimeError(f"claude binary not found: {claude_bin}. "
                           f"Set 'claude_binary' in ~/.yorph/automate/config.json.")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"claude_prompt timed out after {timeout}s")

    if result.returncode != 0:
        raise RuntimeError(f"claude exited {result.returncode}: {result.stderr.strip()[:500]}")

    raw_out = result.stdout
    if output_format == "json":
        try:
            parsed = json.loads(raw_out)
            # The CLI's json mode returns {"result": "...", ...}; fall back to raw.
            response = parsed.get("result") if isinstance(parsed, dict) else raw_out
            if response is None:
                response = raw_out
        except Exception:
            response = raw_out
    else:
        response = raw_out
    cap = server_config.get("max_output_bytes", 10 * 1024 * 1024)
    return {"response": _truncate(response, cap)}


def _run_jsonpath(node_config, raw_inputs) -> Dict[str, Any]:
    expr = node_config.get("expr", "")
    data = raw_inputs.get("data")
    if not expr:
        return {"result": data}
    cur: Any = data
    for part in expr.split("."):
        if part == "":
            continue
        if part == "*":
            # Flatten one level of lists.
            if isinstance(cur, list):
                cur = [item for sub in cur for item in (sub if isinstance(sub, list) else [sub])]
            continue
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                cur = None
        else:
            cur = None
        if cur is None:
            break
    return {"result": cur}


BRANCH_OP_RE = re.compile(r"^\s*(.+?)\s*(==|!=|>=|<=|>|<)\s*(.+?)\s*$")


def _eval_operand(tok: str, input_value: Any) -> Any:
    tok = tok.strip()
    if tok.lower() == "input" or tok.lower() == "data":
        return input_value
    if tok.startswith("input."):
        return _lookup(tok[len("input."):], {**({"_": input_value} if not isinstance(input_value, dict) else input_value)}) \
            if isinstance(input_value, dict) else None
    # JSON-parseable literal?
    try:
        return json.loads(tok)
    except Exception:
        pass
    # Bare string
    return tok.strip("'\"")


def _run_branch(node_config, raw_inputs) -> Dict[str, Any]:
    cond = node_config.get("condition", "")
    input_value = raw_inputs.get("data")
    result = False
    cond = cond.strip()

    m = BRANCH_OP_RE.match(cond)
    if m:
        left = _eval_operand(m.group(1), input_value)
        op = m.group(2)
        right = _eval_operand(m.group(3), input_value)
        try:
            if op == "==":   result = left == right
            elif op == "!=": result = left != right
            elif op == ">":  result = left > right
            elif op == ">=": result = left >= right
            elif op == "<":  result = left < right
            elif op == "<=": result = left <= right
        except TypeError:
            result = False
    else:
        # Truthiness of the bound value.
        val = _eval_operand(cond, input_value) if cond else input_value
        result = bool(val)

    if result:
        return {"true": input_value, "false": _NOT_PRODUCED}
    else:
        return {"true": _NOT_PRODUCED, "false": input_value}


def _run_bash(node_config, raw_inputs) -> Dict[str, Any]:
    command = node_config.get("command", "")
    if not command:
        raise ValueError("bash: missing command")
    cwd = node_config.get("cwd") or None
    timeout = node_config.get("timeout_seconds", 120)
    stdin = raw_inputs.get("stdin")
    try:
        result = subprocess.run(
            ["/bin/bash", "-c", command],
            cwd=cwd, capture_output=True, text=True, timeout=timeout,
            input=stdin if isinstance(stdin, str) else None,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"bash timed out after {timeout}s")
    cap = load_config().get("max_output_bytes", 10 * 1024 * 1024)
    return {
        "stdout": _truncate(result.stdout, cap),
        "stderr": _truncate(result.stderr, cap),
        "exit_code": result.returncode,
    }


# ── Mermaid generation ───────────────────────────────────────────────────────

def workflow_to_mermaid(workflow: Dict[str, Any], templates: Dict[str, Dict[str, Any]]) -> str:
    lines = ["graph TD"]
    for n in workflow.get("nodes", []):
        tpl = templates.get(n.get("template_id"), {})
        tpl_name = tpl.get("name", n.get("template_id", "?"))
        label = f'{tpl_name}<br/><i>{n.get("id","")}</i>'
        safe = label.replace('"', "&quot;")
        lines.append(f'  {n["id"]}["{safe}"]')
    for e in workflow.get("edges", []):
        from_out = e.get("from_output", "")
        to_in = e.get("to_input", "")
        lbl = f"{from_out} → {to_in}" if from_out or to_in else ""
        if lbl:
            lines.append(f'  {e["from"]} -->|{lbl}| {e["to"]}')
        else:
            lines.append(f'  {e["from"]} --> {e["to"]}')
    return "\n".join(lines)


# ── HTTP server ──────────────────────────────────────────────────────────────

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # BaseHTTPRequestHandler passes (request_line, code, size) in args.
        try:
            code = str(args[1]) if len(args) >= 2 else ""
            if code >= "400":
                sys.stderr.write(f"[{code}] {args[0]}\n")
        except Exception:
            pass

    # ── response helpers ─────────────────────────────────────────────────────

    def _send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, data: bytes, content_type: str, mtime: Optional[float] = None) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        if mtime is not None:
            self.send_header("Last-Modified", email.utils.formatdate(mtime, usegmt=True))
        self.end_headers()
        self.wfile.write(data)

    # ── routing ──────────────────────────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)

        try:
            if path in ("/", "/index.html"):
                self._serve_viewer("index.html", "text/html; charset=utf-8")
            elif path == "/styles.css":
                self._serve_viewer("styles.css", "text/css; charset=utf-8")
            elif path == "/app.js":
                self._serve_viewer("app.js", "application/javascript; charset=utf-8")
            elif path == "/api/workflows":
                self._api_list_workflows()
            elif path.startswith("/api/workflows/"):
                wid = path[len("/api/workflows/"):]
                self._api_get_workflow(wid)
            elif path == "/api/templates":
                self._api_list_templates()
            elif path == "/api/runs":
                self._api_list_runs(qs)
            elif path.startswith("/api/runs/"):
                rid = path[len("/api/runs/"):]
                self._api_get_run(rid)
            elif path == "/api/health":
                self._send_json({"ok": True, "pid": os.getpid()})
            elif path.startswith("/api/workflows/") and path.endswith("/validate"):
                wid = path[len("/api/workflows/"):-len("/validate")]
                self._api_validate_by_id(wid)
            else:
                self.send_error(404)
        except Exception as e:
            self._send_json({"error": f"{type(e).__name__}: {e}"}, status=500)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            body = {}

        try:
            if path == "/api/runs":
                self._api_trigger_run(body)
            elif path == "/api/validate":
                self._api_validate_body(body)
            else:
                self.send_error(405)
        except Exception as e:
            self._send_json({"error": f"{type(e).__name__}: {e}"}, status=500)

    # ── viewer files ─────────────────────────────────────────────────────────

    def _serve_viewer(self, name: str, content_type: str) -> None:
        p = VIEWER_DIR / name
        if not p.exists():
            self.send_error(404, f"viewer file missing: {name}")
            return
        self._send_bytes(p.read_bytes(), content_type, p.stat().st_mtime)

    # ── API handlers ─────────────────────────────────────────────────────────

    def _api_list_workflows(self) -> None:
        summaries = list_workflows_summary()
        templates = load_templates()
        # attach last-run status + aggregate danger/effects
        for s in summaries:
            s["last_run"] = last_run_status(s["id"])
            wf = load_workflow(s["id"])
            if wf:
                aggregate = _aggregate_danger(wf, templates)
                s.update(aggregate)
        self._send_json({"workflows": summaries})

    def _api_get_workflow(self, workflow_id: str) -> None:
        wf = load_workflow(workflow_id)
        if wf is None:
            self.send_error(404, f"workflow not found: {workflow_id}")
            return
        templates = load_templates()
        masked = _mask_workflow_for_response(wf, templates)
        self._send_json({
            "workflow": masked,
            "mermaid": workflow_to_mermaid(wf, templates),
            **_aggregate_danger(wf, templates),
        })

    def _api_list_templates(self) -> None:
        templates = load_templates()
        out = []
        for t in templates.values():
            out.append({
                "id": t["id"], "name": t.get("name", t["id"]),
                "description": t.get("description", ""),
                "kind": t.get("kind", "action"),
                "config_schema": t.get("config_schema", {}),
                "inputs": t.get("inputs", []),
                "outputs": t.get("outputs", []),
                "source": t.get("_source", "bundled"),
            })
        out.sort(key=lambda x: (x["kind"], x["id"]))
        self._send_json({"templates": out})

    def _api_list_runs(self, qs: Dict[str, List[str]]) -> None:
        workflow_id = qs.get("workflow_id", [None])[0]
        limit = min(int(qs.get("limit", ["50"])[0]), 500)
        conn = sqlite3.connect(RUNS_DB)
        try:
            if workflow_id:
                rows = conn.execute(
                    "SELECT id, workflow_id, status, started_at, ended_at, error FROM runs "
                    "WHERE workflow_id=? ORDER BY started_at DESC LIMIT ?",
                    (workflow_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, workflow_id, status, started_at, ended_at, error FROM runs "
                    "ORDER BY started_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        finally:
            conn.close()
        self._send_json({
            "runs": [
                {"id": r[0], "workflow_id": r[1], "status": r[2],
                 "started_at": r[3], "ended_at": r[4], "error": r[5]}
                for r in rows
            ]
        })

    def _api_get_run(self, run_id: str) -> None:
        conn = sqlite3.connect(RUNS_DB)
        try:
            row = conn.execute(
                "SELECT id, workflow_id, status, started_at, ended_at, trigger_type, "
                "trigger_payload, final_outputs, error, pre_run_git_checkpoints, "
                "post_run_git_checkpoints, resumed_from FROM runs WHERE id=?",
                (run_id,),
            ).fetchone()
            if not row:
                self.send_error(404, f"run not found: {run_id}")
                return
            nodes = conn.execute(
                "SELECT node_id, template_id, status, started_at, ended_at, "
                "inputs_json, outputs_json, error FROM node_runs "
                "WHERE run_id=? ORDER BY started_at",
                (run_id,),
            ).fetchall()
        finally:
            conn.close()

        def _try_json(s):
            if s is None:
                return None
            try:
                return json.loads(s)
            except Exception:
                return s

        self._send_json({
            "run": {
                "id": row[0], "workflow_id": row[1], "status": row[2],
                "started_at": row[3], "ended_at": row[4],
                "trigger_type": row[5],
                "trigger_payload": _try_json(row[6]),
                "final_outputs": _try_json(row[7]),
                "error": row[8],
                "pre_run_git_checkpoints":  _try_json(row[9]),
                "post_run_git_checkpoints": _try_json(row[10]),
                "resumed_from":             row[11],
            },
            "nodes": [
                {
                    "node_id": n[0], "template_id": n[1], "status": n[2],
                    "started_at": n[3], "ended_at": n[4],
                    "inputs": _try_json(n[5]),
                    "outputs": _try_json(n[6]),
                    "error": n[7],
                }
                for n in nodes
            ],
        })

    def _api_trigger_run(self, body: Dict[str, Any]) -> None:
        workflow_id = body.get("workflow_id")
        if not workflow_id:
            self._send_json({"error": "workflow_id required"}, status=400)
            return
        wf = load_workflow(workflow_id)
        if wf is None:
            self._send_json({"error": f"workflow not found: {workflow_id}"}, status=404)
            return
        templates = load_templates()
        # ── pre-flight: static validation. Errors block the run entirely. ──
        v = validate_workflow(wf, templates)
        if v["errors"]:
            self._send_json({
                "error": "validation failed",
                "errors": v["errors"],
                "warnings": v["warnings"],
            }, status=400)
            return
        config = load_config()
        payload = body.get("payload")
        resume_from = body.get("resume_from")
        # Run synchronously; for large DAGs the server is threaded, so this only
        # blocks the one connection.
        run_id = run_workflow(wf, templates, config,
                              trigger_payload=payload,
                              trigger_type="manual",
                              resume_from_run_id=resume_from)
        resp = {"run_id": run_id}
        if resume_from:
            resp["resumed_from"] = resume_from
        if v["warnings"]:
            resp["warnings"] = v["warnings"]
        self._send_json(resp)

    def _api_validate_by_id(self, workflow_id: str) -> None:
        wf = load_workflow(workflow_id)
        if wf is None:
            self.send_error(404, f"workflow not found: {workflow_id}")
            return
        templates = load_templates()
        self._send_json(validate_workflow(wf, templates))

    def _api_validate_body(self, body: Dict[str, Any]) -> None:
        """Validate a workflow provided inline (before it's saved to disk)."""
        templates = load_templates()
        self._send_json(validate_workflow(body, templates))


# ── PID handling ─────────────────────────────────────────────────────────────

def _server_already_running(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as r:
            data = json.loads(r.read().decode("utf-8"))
            return bool(data.get("ok"))
    except Exception:
        return False


def _write_pid() -> None:
    try:
        PID_FILE.write_text(str(os.getpid()))
    except Exception:
        pass


def _clear_pid() -> None:
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="yorph-automate local server")
    parser.add_argument("--port", type=int, default=None,
                        help="Port to listen on (default from config.json or 8766)")
    parser.add_argument("--run-once", metavar="WORKFLOW_ID",
                        help="Execute a workflow once and exit (does not start the HTTP server).")
    parser.add_argument("--payload", default=None,
                        help="JSON payload for --run-once manual trigger.")
    args = parser.parse_args()

    ensure_home()
    cfg = load_config()
    port = args.port or cfg.get("port", 8766)

    if args.run_once:
        wf = load_workflow(args.run_once)
        if wf is None:
            print(f"workflow not found: {args.run_once}", file=sys.stderr)
            return 2
        payload = json.loads(args.payload) if args.payload else None
        templates = load_templates()
        run_id = run_workflow(wf, templates, cfg, trigger_payload=payload, trigger_type="manual")
        # Print the final run summary.
        conn = sqlite3.connect(RUNS_DB)
        try:
            row = conn.execute(
                "SELECT status, final_outputs, error FROM runs WHERE id=?", (run_id,)
            ).fetchone()
        finally:
            conn.close()
        out = {
            "run_id": run_id,
            "status": row[0] if row else "unknown",
            "final_outputs": json.loads(row[1]) if row and row[1] else None,
            "error": row[2] if row else None,
        }
        print(json.dumps(out, indent=2))
        return 0 if out["status"] == "succeeded" else 1

    if _server_already_running(port):
        print(f"yorph-automate already running on http://localhost:{port}")
        return 0

    _write_pid()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://localhost:{port}"
    print(f"\n  ◆ yorph-automate")
    print(f"  Home    : {HOME_DIR}")
    print(f"  Viewer  : {url}")
    print(f"  Stop    : Ctrl+C\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        _clear_pid()
    return 0


if __name__ == "__main__":
    sys.exit(main())
