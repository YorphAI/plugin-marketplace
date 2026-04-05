#!/usr/bin/env python3
"""
extract.py — snapshot a Claude Code conversation as an eval test case.

Reads the JSONL session log, classifies each tool call as stub/live/capture/skip,
and writes the eval case to <project>/.claude/evals/<name>/.

Usage:
    python3 extract.py \
        --project-root /path/to/your-plugin \
        --eval-name my-eval \
        [--description "What this tests"] \
        [--tags "tag1,tag2"] \
        [--example-type positive|negative|mixed] \
        [--what-went-well  "Free text: what the agent did correctly"] \
        [--what-went-poorly "Free text: what the agent did wrong or missed"] \
        [--start-after "substring in user message"] \
        [--end-before  "substring in user message"] \
        [--session-id  <uuid>]

--example-type:
  positive — good result to preserve; eval fails if future runs diverge
  negative — known-bad result; eval passes when the result changes (bug fixed)
  mixed    — partial success; records what went well and what went poorly
             as rubric criteria for future review
"""

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


# ── Tool classification ───────────────────────────────────────────────────────

DEFAULT_STUB_TOOLS = {"WebFetch", "WebSearch"}
DEFAULT_CAPTURE_TOOLS = {"Write", "Edit"}
DEFAULT_SKIP_TOOLS = {
    "TodoWrite", "AskUserQuestion", "Skill",
    "EnterPlanMode", "ExitPlanMode", "EnterWorktree",
    "Agent", "NotebookEdit",
}
_VOLATILE_FIELDS = {"timestamp", "session_id", "sessionId", "uuid", "requestId"}


def load_config(project_root: str) -> dict:
    """Load .claude/eval-config.json if present."""
    p = Path(project_root) / ".claude" / "eval-config.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


def classify(name: str, inp: dict, root: str, cfg: dict) -> str:
    """Return 'stub' | 'live' | 'capture' | 'skip'."""
    if name in cfg.get("live_tools", []):    return "live"
    if name in cfg.get("stub_tools", []):    return "stub"
    if name in cfg.get("capture_tools", []): return "capture"
    if name in cfg.get("skip_tools", []):    return "skip"

    if name.startswith("mcp__"):
        for pfx in cfg.get("live_mcp_prefixes", []):
            if name.startswith(pfx):
                return "live"

    if name in DEFAULT_SKIP_TOOLS:    return "skip"
    if name.startswith("mcp__") and "save_output" in name: return "capture"
    if name in DEFAULT_CAPTURE_TOOLS: return "capture"
    if name in DEFAULT_STUB_TOOLS:    return "stub"
    if name.startswith("mcp__"):      return "stub"

    if name == "Read":
        path = inp.get("file_path", "")
        return "live" if path.startswith(root.rstrip("/")) else "stub"

    if name in ("Glob", "Grep"):
        path = inp.get("path", root)
        return "live" if path.startswith(root.rstrip("/")) else "stub"

    if name == "Bash":
        return "live"

    return "live"


def det_key(name: str, inp: dict) -> str:
    """Deterministic 16-char hex key for a tool call."""
    clean = {k: v for k, v in inp.items() if k not in _VOLATILE_FIELDS}
    payload = json.dumps({"name": name, "input": clean}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ── JSONL parsing ─────────────────────────────────────────────────────────────


def parse_jsonl(path: Path) -> list:
    entries = []
    for i, line in enumerate(path.open(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"  [warn] skipping malformed line {i}", file=sys.stderr)
    return entries


def find_latest(session_dir: Path) -> Path:
    files = sorted(session_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    if not files:
        raise FileNotFoundError(f"No .jsonl files in {session_dir}")
    return files[-1]


def project_root_from_entries(entries: list) -> str:
    for e in entries:
        if e.get("type") == "user" and "cwd" in e:
            return e["cwd"]
    return ""


def session_id_from_entries(entries: list) -> str:
    for e in entries:
        if "sessionId" in e:
            return e["sessionId"]
    return ""


# ── Conversation reconstruction ───────────────────────────────────────────────


def extract_turns(entries: list, root: str, cfg: dict,
                  start_after=None, end_before=None) -> list:
    """
    Returns list of dicts: {role, text, tool_calls: [{id,name,input,result,is_error,cls}]}
    """
    # Keep only user/assistant; deduplicate assistant by message.id (last wins)
    raw = [e for e in entries if e.get("type") in ("user", "assistant")]

    last_idx: dict = {}
    for i, e in enumerate(raw):
        if e.get("type") == "assistant":
            mid = e.get("message", {}).get("id")
            if mid:
                last_idx[mid] = i

    deduped = []
    skipped: set = set()
    for i, e in enumerate(raw):
        if e.get("type") == "assistant":
            mid = e.get("message", {}).get("id")
            if mid and mid in skipped:
                continue
            if mid and last_idx.get(mid, i) != i:
                skipped.add(mid)
                continue
        deduped.append(e)

    turns = []
    pending: dict = {}   # tool_use_id → tool_call dict
    capturing = start_after is None

    for e in deduped:
        msg = e.get("message", {})
        role = msg.get("role", "")
        content = msg.get("content", [])

        if role == "user":
            text_parts = []
            if isinstance(content, str):
                text_parts = [content]
            elif isinstance(content, list):
                for blk in content:
                    if not isinstance(blk, dict):
                        continue
                    if blk.get("type") == "text":
                        text_parts.append(blk.get("text", ""))
                    elif blk.get("type") == "tool_result":
                        tid = blk.get("tool_use_id", "")
                        rc = blk.get("content", "")
                        is_err = blk.get("is_error", False)
                        if isinstance(rc, list):
                            result_text = "\n".join(
                                b.get("text", "") for b in rc
                                if isinstance(b, dict) and b.get("type") == "text"
                            )
                        elif isinstance(rc, str):
                            result_text = rc
                        else:
                            result_text = json.dumps(rc, default=str)
                        if tid in pending:
                            pending[tid]["result"] = result_text
                            pending[tid]["is_error"] = is_err

            user_text = "\n".join(text_parts).strip()
            if user_text:
                if not capturing and start_after and start_after in user_text:
                    capturing = True
                if capturing and end_before and end_before in user_text:
                    break
                if capturing:
                    turns.append({"role": "user", "text": user_text, "tool_calls": []})

        elif role == "assistant" and capturing:
            if not isinstance(content, list):
                content = []
            text_parts = []
            tool_calls = []
            for blk in content:
                if not isinstance(blk, dict):
                    continue
                if blk.get("type") == "text":
                    text_parts.append(blk.get("text", ""))
                elif blk.get("type") == "tool_use":
                    tc = {
                        "id": blk.get("id", ""),
                        "name": blk.get("name", ""),
                        "input": blk.get("input", {}),
                        "result": None,
                        "is_error": False,
                        "cls": classify(blk.get("name",""), blk.get("input",{}), root, cfg),
                    }
                    tool_calls.append(tc)
                    pending[tc["id"]] = tc
            turns.append({
                "role": "assistant",
                "text": "\n".join(text_parts),
                "tool_calls": tool_calls,
            })

    return turns


# ── Build and save eval case ──────────────────────────────────────────────────


def build_tool_cache(turns: list) -> dict:
    cache = {}
    for t in turns:
        for tc in t["tool_calls"]:
            if tc["cls"] in ("stub", "capture", "live"):
                k = det_key(tc["name"], tc["input"])
                cache[k] = {
                    "name": tc["name"],
                    "input": tc["input"],
                    "result": tc["result"],
                    "is_error": tc["is_error"],
                    "classification": tc["cls"],
                }
    return cache


def build_golden(entries: list, start_after=None, end_before=None) -> list:
    result = []
    capturing = start_after is None
    for e in entries:
        if e.get("type") not in ("user", "assistant"):
            continue
        if e.get("type") == "user":
            c = e.get("message", {}).get("content", "")
            if isinstance(c, str):
                ut = c
            elif isinstance(c, list):
                ut = " ".join(b.get("text","") for b in c
                              if isinstance(b, dict) and b.get("type") == "text")
            else:
                ut = ""
            if not capturing and start_after and start_after in ut:
                capturing = True
            if capturing and end_before and end_before in ut:
                break
        if capturing:
            if e.get("type") == "assistant":
                msg = e.get("message", {})
                c2 = msg.get("content", [])
                if isinstance(c2, list):
                    c2 = [b for b in c2 if not (isinstance(b,dict) and b.get("type")=="thinking")]
                    e = {**e, "message": {**msg, "content": c2}}
            result.append(e)
    return result


def save_case(out_dir: Path, metadata: dict, golden: list, cache: dict):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str))
    with (out_dir / "golden_conversation.jsonl").open("w") as f:
        for e in golden:
            f.write(json.dumps(e, default=str) + "\n")
    (out_dir / "tool_cache.json").write_text(json.dumps(cache, indent=2, default=str))
    if not (out_dir / "assertions.json").exists():
        (out_dir / "assertions.json").write_text("[]")


# ── CLI ───────────────────────────────────────────────────────────────────────


def main():
    p = argparse.ArgumentParser(description="Save a Claude Code conversation as an eval case.")
    p.add_argument("--project-root", required=True)
    p.add_argument("--eval-name", required=True)
    p.add_argument("--description", default="")
    p.add_argument("--tags", default="")
    p.add_argument(
        "--example-type", default="positive",
        choices=["positive", "negative", "mixed"],
        help="positive (preserve good result), negative (catch known bug), mixed (partial)",
    )
    p.add_argument("--what-went-well", default="",
                   help="Free text: what the agent did correctly in this conversation")
    p.add_argument("--what-went-poorly", default="",
                   help="Free text: what the agent did wrong or missed")
    # Backwards-compat alias kept for any existing scripts
    p.add_argument("--negative", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--start-after", default=None)
    p.add_argument("--end-before", default=None)
    p.add_argument("--session-id", default=None)
    p.add_argument("--evals-dir", default=None,
                   help="Where to store evals. Default: <project-root>/.claude/evals/")
    args = p.parse_args()

    root = args.project_root.rstrip("/")

    # Find session directory: ~/.claude/projects/<root-with-slashes-as-dashes>/
    proj_hash = root.replace("/", "-")
    session_dir = Path.home() / ".claude" / "projects" / proj_hash

    if not session_dir.is_dir():
        print(f"Error: session directory not found: {session_dir}", file=sys.stderr)
        print("Have you had at least one Claude Code conversation in this project?", file=sys.stderr)
        sys.exit(1)

    if args.session_id:
        jsonl_path = session_dir / f"{args.session_id}.jsonl"
        if not jsonl_path.exists():
            print(f"Error: {jsonl_path} not found", file=sys.stderr)
            sys.exit(1)
    else:
        jsonl_path = find_latest(session_dir)

    print(f"Parsing:      {jsonl_path.name}")

    entries = parse_jsonl(jsonl_path)
    detected_root = project_root_from_entries(entries) or root
    sid = session_id_from_entries(entries)
    cfg = load_config(detected_root)

    print(f"Project root: {detected_root}")
    print(f"Session ID:   {sid}")
    print(f"Entries:      {len(entries)}")

    turns = extract_turns(
        entries, detected_root, cfg,
        start_after=args.start_after,
        end_before=args.end_before,
    )

    stats: dict = defaultdict(int)
    for t in turns:
        for tc in t["tool_calls"]:
            stats[tc["cls"]] += 1

    user_n  = sum(1 for t in turns if t["role"] == "user")
    asst_n  = sum(1 for t in turns if t["role"] == "assistant")
    total_t = sum(stats.values())

    print(f"Turns:        {user_n} user, {asst_n} assistant")
    print(f"Tool calls:   {total_t} total — "
          f"{stats.get('stub',0)} stub, "
          f"{stats.get('live',0)} live, "
          f"{stats.get('capture',0)} capture, "
          f"{stats.get('skip',0)} skip")

    cache  = build_tool_cache(turns)
    golden = build_golden(entries, args.start_after, args.end_before)

    evals_dir = Path(args.evals_dir) if args.evals_dir else Path(detected_root) / ".claude" / "evals"
    out_dir   = evals_dir / args.eval_name

    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []

    # --negative is a legacy alias for --example-type negative
    example_type = args.example_type
    if args.negative and example_type == "positive":
        example_type = "negative"

    metadata = {
        "name":             args.eval_name,
        "description":      args.description,
        "tags":             tags,
        "session_id":       sid,
        "project_root":     detected_root,
        "example_type":     example_type,
        "is_negative":      example_type == "negative",   # kept for runner backwards-compat
        "what_went_well":   args.what_went_well,
        "what_went_poorly": args.what_went_poorly,
        "created_at":       datetime.now().isoformat(),
        "tool_stats":       dict(stats),
    }

    save_case(out_dir, metadata, golden, cache)

    print(f"\nSaved to:     {out_dir}")
    print(f"  metadata.json             ({len(metadata)} fields)")
    print(f"  golden_conversation.jsonl ({len(golden)} entries)")
    print(f"  tool_cache.json           ({len(cache)} tool calls)")
    print(f"  assertions.json           (empty — add custom assertions here)")


if __name__ == "__main__":
    main()
