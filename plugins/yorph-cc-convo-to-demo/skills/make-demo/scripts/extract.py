#!/usr/bin/env python3
"""
extract.py — Extract demo-worthy conversation turns from a Claude Code session.

Reads the JSONL session log, strips tool calls / thinking blocks / system
reminders, and outputs a clean JSON array of human-readable turns.

Usage:
    python3 extract.py \
        --project-root /path/to/project \
        --output /tmp/demo-turns.json \
        [--start-after "substring in user message"] \
        [--end-before  "substring in user message"] \
        [--include-turns "0,1,4,5"] \
        [--exclude-pattern "make demo|make-demo"] \
        [--session-id <uuid>]
"""

import argparse
import json
import re
import sys
from pathlib import Path


# ── JSONL parsing (ported from yorph-claude-eval) ────────────────────────────


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


# ── System-reminder stripping ────────────────────────────────────────────────

_SYS_REMINDER_RE = re.compile(
    r"<system-reminder>.*?</system-reminder>", re.DOTALL
)


def strip_system_reminders(text: str) -> str:
    return _SYS_REMINDER_RE.sub("", text).strip()


# ── AskUserQuestion answer parsing ───────────────────────────────────────────

_AUQ_ANSWER_RE = re.compile(r'"([^"]+?)"="([^"]*?)"')


def _build_tool_use_index(entries: list) -> dict:
    """Build a map of tool_use_id → {name, input} from all assistant messages."""
    index: dict = {}
    for e in entries:
        if e.get("type") != "assistant":
            continue
        content = e.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for blk in content:
            if isinstance(blk, dict) and blk.get("type") == "tool_use":
                index[blk.get("id", "")] = {
                    "name": blk.get("name", ""),
                    "input": blk.get("input", {}),
                }
    return index


def _format_auq_answer(tool_input: dict, result_text: str) -> str:
    """Format an AskUserQuestion tool_result as readable text.

    Parses the 'User has answered your questions: "Q"="A", ...' format and
    correlates with the original question headers to produce:
        **Header:** Answer
    """
    # Build header lookup from the original questions
    header_for_question: dict = {}
    questions = tool_input.get("questions", [])
    for q in questions:
        header_for_question[q.get("question", "")] = q.get("header", "")

    # Parse "question"="answer" pairs from the result string
    pairs = _AUQ_ANSWER_RE.findall(result_text)
    if not pairs:
        return ""

    lines = []
    for question_text, answer_text in pairs:
        header = header_for_question.get(question_text, "")
        if header:
            lines.append(f"**{header}:** {answer_text}")
        else:
            # Fallback: use a truncated question as label
            short_q = question_text[:60] + ("..." if len(question_text) > 60 else "")
            lines.append(f"**{short_q}:** {answer_text}")

    return "\n".join(lines)


# ── Turn extraction ─────────────────────────────────────────────────────────


def extract_demo_turns(
    entries: list,
    start_after: str | None = None,
    end_before: str | None = None,
    include_turns: set[int] | None = None,
    exclude_pattern: re.Pattern | None = None,
) -> list:
    """
    Extract human-readable text turns from JSONL entries.

    Keeps only user/assistant text. Strips tool_use, thinking blocks, and
    <system-reminder> tags. Converts AskUserQuestion tool_result blocks into
    readable text so guided Q&A flows appear in the demo.
    """
    # Build tool_use index so we can correlate tool_results back to questions
    tool_index = _build_tool_use_index(entries)

    # Filter to user/assistant entries only
    raw = [e for e in entries if e.get("type") in ("user", "assistant")]

    # Deduplicate assistant messages by message.id (keep last)
    last_idx: dict = {}
    for i, e in enumerate(raw):
        if e.get("type") == "assistant":
            mid = e.get("message", {}).get("id")
            if mid:
                last_idx[mid] = i

    deduped = []
    seen_ids: set = set()
    for i, e in enumerate(raw):
        if e.get("type") == "assistant":
            mid = e.get("message", {}).get("id")
            if mid and mid in seen_ids:
                continue
            if mid and last_idx.get(mid, i) != i:
                seen_ids.add(mid)
                continue
        deduped.append(e)

    turns = []
    turn_index = 0
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
                        # Check if this is an AskUserQuestion response
                        tid = blk.get("tool_use_id", "")
                        tool_info = tool_index.get(tid, {})
                        if tool_info.get("name") == "AskUserQuestion":
                            rc = blk.get("content", "")
                            if isinstance(rc, list):
                                rc = "\n".join(
                                    b.get("text", "") for b in rc
                                    if isinstance(b, dict) and b.get("type") == "text"
                                )
                            if isinstance(rc, str):
                                formatted = _format_auq_answer(tool_info["input"], rc)
                                if formatted:
                                    text_parts.append(formatted)

            user_text = strip_system_reminders("\n".join(text_parts).strip())
            if not user_text:
                continue

            if not capturing:
                if start_after and start_after in user_text:
                    capturing = True
                else:
                    continue

            if capturing and end_before and end_before in user_text:
                break

            turns.append({"role": "user", "text": user_text, "turn_index": turn_index})
            turn_index += 1

        elif role == "assistant" and capturing:
            # Extract only text blocks (skip tool_use, thinking)
            if not isinstance(content, list):
                content = []

            text_parts = []
            for blk in content:
                if isinstance(blk, dict) and blk.get("type") == "text":
                    text_parts.append(blk.get("text", ""))

            asst_text = strip_system_reminders("\n".join(text_parts).strip())
            if not asst_text:
                continue

            turns.append({"role": "assistant", "text": asst_text, "turn_index": turn_index})
            turn_index += 1

    # Apply filters
    if include_turns is not None:
        turns = [t for t in turns if t["turn_index"] in include_turns]

    if exclude_pattern:
        turns = [t for t in turns if not exclude_pattern.search(t["text"])]

    return turns


# ── CLI ──────────────────────────────────────────────────────────────────────


def main():
    p = argparse.ArgumentParser(
        description="Extract demo conversation turns from a Claude Code session."
    )
    p.add_argument("--project-root", required=True)
    p.add_argument("--output", required=True, help="Output JSON file path")
    p.add_argument("--start-after", default=None,
                   help="Only capture turns after a user message containing this text")
    p.add_argument("--end-before", default=None,
                   help="Stop capturing before a user message containing this text")
    p.add_argument("--session-id", default=None,
                   help="Use a specific session instead of the latest")
    p.add_argument("--include-turns", default=None,
                   help="Comma-separated turn indices to include (e.g. '0,1,4,5')")
    p.add_argument("--exclude-pattern", default=None,
                   help="Regex pattern: exclude turns whose text matches")
    args = p.parse_args()

    root = args.project_root.rstrip("/")

    # Resolve session directory
    proj_hash = root.replace("/", "-")
    session_dir = Path.home() / ".claude" / "projects" / proj_hash

    if not session_dir.is_dir():
        print(f"Error: session directory not found: {session_dir}", file=sys.stderr)
        print("Have you had at least one Claude Code conversation in this project?",
              file=sys.stderr)
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
    print(f"Entries:      {len(entries)}")

    # Parse include-turns into a set
    include_set = None
    if args.include_turns:
        include_set = {int(x.strip()) for x in args.include_turns.split(",")}

    # Compile exclude pattern
    exclude_re = None
    if args.exclude_pattern:
        exclude_re = re.compile(args.exclude_pattern, re.IGNORECASE)

    turns = extract_demo_turns(
        entries,
        start_after=args.start_after,
        end_before=args.end_before,
        include_turns=include_set,
        exclude_pattern=exclude_re,
    )

    user_n = sum(1 for t in turns if t["role"] == "user")
    asst_n = sum(1 for t in turns if t["role"] == "assistant")
    print(f"Turns:        {user_n} user, {asst_n} assistant")

    # Write output
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(turns, indent=2, ensure_ascii=False))
    print(f"Wrote:        {out_path}")


if __name__ == "__main__":
    main()
