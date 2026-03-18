#!/usr/bin/env python3
"""
runner.py — replay eval checkpoints against the current codebase.

Standalone script — no external package dependencies.

Usage:
    python3 runner.py --eval <name>                # run one eval
    python3 runner.py --all                        # run all evals
    python3 runner.py --list                       # list saved evals
    python3 runner.py --eval <name> --evals-dir /path/to/evals
    python3 runner.py --all --project-root /path/to/project
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


# ── Data models ───────────────────────────────────────────────────────────────


@dataclass
class CheckpointResult:
    tool_name: str
    input: dict
    golden: Any
    actual: Any
    diff: Optional[str] = None
    passed: bool = True
    severity: str = "pass"   # pass | regression | drift | improvement
    notes: str = ""


@dataclass
class EvalReport:
    eval_name: str
    is_negative: bool = False
    example_type: str = "positive"      # positive | negative | mixed
    what_went_well: str = ""
    what_went_poorly: str = ""
    results: list = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def summary(self) -> dict:
        counts: dict = {"pass": 0, "regression": 0, "drift": 0, "improvement": 0}
        for r in self.results:
            counts[r.severity] = counts.get(r.severity, 0) + 1
        return counts

    @property
    def passed(self) -> bool:
        return self.summary.get("regression", 0) == 0

    def summary_text(self) -> str:
        s = self.summary
        parts = [f"{v} {k.upper()}" for k, v in s.items() if v > 0]
        return f"Eval '{self.eval_name}': {', '.join(parts)}"

    def to_markdown(self) -> str:
        status = "✅ PASS" if self.passed else "❌ FAIL"
        type_label = {
            "positive": "Positive example",
            "negative": "Negative example",
            "mixed":    "Mixed example",
        }.get(self.example_type, "Positive example")
        lines = [
            f"# Eval Report: {self.eval_name}",
            "",
            f"**Date:** {self.timestamp[:10]}",
            f"**Type:** {type_label}",
            f"**Result:** {status} — {self.summary_text()}",
        ]
        if self.what_went_well:
            lines += ["", f"**What went well:** {self.what_went_well}"]
        if self.what_went_poorly:
            lines += ["", f"**What went poorly:** {self.what_went_poorly}"]
        lines.append("")
        for severity in ("regression", "drift", "improvement", "pass"):
            group = [r for r in self.results if r.severity == severity]
            if not group:
                continue
            icon = {
                "regression": "!!",
                "drift": "~",
                "improvement": "+",
                "pass": "ok",
            }[severity]
            lines.append(f"## {severity.title()} ({len(group)})")
            lines.append("")
            for r in group:
                short_input = _truncate_json(r.input, 120)
                lines.append(f"### [{icon.upper()}] {r.tool_name}")
                lines.append(f"- **Input:** `{short_input}`")
                if r.diff:
                    lines.append(f"- **Diff:** {r.diff}")
                if r.notes:
                    lines.append(f"- **Notes:** {r.notes}")
                lines.append("")
        return "\n".join(lines)


def _truncate_json(obj: Any, max_len: int) -> str:
    s = json.dumps(obj, default=str)
    return s[: max_len - 3] + "..." if len(s) > max_len else s


# ── Tool re-executors ─────────────────────────────────────────────────────────


def _execute_read(inp: dict) -> str:
    file_path = inp.get("file_path", "")
    offset = inp.get("offset", 0)
    limit = inp.get("limit")

    path = Path(file_path)
    if not path.exists():
        return f"[ERROR] File not found: {file_path}"

    try:
        lines = path.read_text(errors="replace").splitlines()
    except Exception as e:
        return f"[ERROR] {e}"

    if offset:
        lines = lines[offset:]
    if limit:
        lines = lines[:limit]

    start = (offset or 0) + 1
    return "\n".join(f"{start + i:>6}\t{line}" for i, line in enumerate(lines))


def _execute_bash(inp: dict) -> str:
    command = inp.get("command", "")
    if not command:
        return "[ERROR] Empty command"

    timeout = min(inp.get("timeout", 60000) / 1000, 120)

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=inp.get("cwd"),
        )
        output = result.stdout
        if result.stderr:
            output += "\n" + result.stderr if output else result.stderr
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        return output.strip()
    except subprocess.TimeoutExpired:
        return f"[ERROR] Command timed out after {timeout}s"
    except Exception as e:
        return f"[ERROR] {e}"


def _execute_glob(inp: dict) -> str:
    pattern = inp.get("pattern", "")
    path = inp.get("path", ".")

    search_dir = Path(path)
    if not search_dir.exists():
        return f"[ERROR] Directory not found: {path}"

    try:
        matches = sorted(str(p) for p in search_dir.glob(pattern))
        return "\n".join(matches) if matches else "[no matches]"
    except Exception as e:
        return f"[ERROR] {e}"


def _execute_grep(inp: dict) -> str:
    pattern = inp.get("pattern", "")
    path = inp.get("path", ".")
    glob_filter = inp.get("glob")
    file_type = inp.get("type")
    output_mode = inp.get("output_mode", "files_with_matches")

    cmd = ["rg", pattern, path]
    if output_mode == "files_with_matches":
        cmd.append("-l")
    elif output_mode == "count":
        cmd.append("-c")
    if glob_filter:
        cmd.extend(["--glob", glob_filter])
    if file_type:
        cmd.extend(["--type", file_type])
    if inp.get("-i", False):
        cmd.append("-i")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.stdout.strip() if result.stdout else "[no matches]"
    except FileNotFoundError:
        return "[WARN] ripgrep not installed, skipping Grep checkpoint"
    except Exception as e:
        return f"[ERROR] {e}"


EXECUTORS = {
    "Read": _execute_read,
    "Bash": _execute_bash,
    "Glob": _execute_glob,
    "Grep": _execute_grep,
}


# ── Comparison ────────────────────────────────────────────────────────────────


def _compare(
    name: str, inp: dict, golden: Any, actual: Any
) -> CheckpointResult:
    g = str(golden).strip() if golden is not None else ""
    a = str(actual).strip() if actual is not None else ""

    if g == a:
        return CheckpointResult(
            tool_name=name, input=inp, golden=g, actual=a,
            passed=True, severity="pass",
        )

    if a.startswith("[ERROR]"):
        return CheckpointResult(
            tool_name=name, input=inp, golden=g, actual=a,
            diff=f"Execution error: {a}",
            passed=False, severity="regression",
            notes="Tool produced an error where golden succeeded.",
        )

    g_lines, a_lines = g.splitlines(), a.splitlines()
    g_set, a_set = set(g_lines), set(a_lines)
    added = sum(1 for l in a_lines if l not in g_set)
    removed = sum(1 for l in g_lines if l not in a_set)
    diff_summary = (
        f"{len(g_lines)} → {len(a_lines)} lines (+{added} added, -{removed} removed)"
    )

    if g.startswith("[ERROR]") and not a.startswith("[ERROR]"):
        severity = "improvement"
    elif removed > len(g_lines) * 0.5:
        severity = "regression"
    else:
        severity = "drift"

    return CheckpointResult(
        tool_name=name, input=inp, golden=g, actual=a,
        diff=diff_summary,
        passed=severity != "regression",
        severity=severity,
    )


# ── Judge — flip semantics for negative examples ──────────────────────────────


def _judge(result: CheckpointResult, is_negative: bool) -> CheckpointResult:
    if not is_negative:
        return result

    # For a negative example, a "regression" may mean the bad behaviour was fixed.
    if result.severity == "regression":
        return CheckpointResult(
            tool_name=result.tool_name, input=result.input,
            golden=result.golden, actual=result.actual, diff=result.diff,
            passed=True, severity="improvement",
            notes=(
                "Negative example: golden was known-bad and the result changed. "
                "This may indicate the issue was fixed."
            ),
        )

    # A "pass" on a negative example means the bad behaviour still reproduces.
    if result.severity == "pass":
        return CheckpointResult(
            tool_name=result.tool_name, input=result.input,
            golden=result.golden, actual=result.actual, diff=result.diff,
            passed=False, severity="regression",
            notes="Negative example: the known-bad behaviour still reproduces.",
        )

    return result


# ── Runner ────────────────────────────────────────────────────────────────────


def run_eval(eval_dir: Path) -> EvalReport:
    meta_path = eval_dir / "metadata.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"No metadata.json in {eval_dir}")

    metadata = json.loads(meta_path.read_text())
    example_type = metadata.get("example_type", "negative" if metadata.get("is_negative") else "positive")
    is_negative = example_type == "negative"

    cache_path = eval_dir / "tool_cache.json"
    tool_cache: dict = json.loads(cache_path.read_text()) if cache_path.exists() else {}

    results: list[CheckpointResult] = []

    for entry in tool_cache.values():
        cls = entry.get("classification", "stub")
        name = entry["name"]
        inp = entry["input"]
        golden = entry.get("result")

        if cls == "skip":
            continue

        elif cls == "live":
            executor = EXECUTORS.get(name)
            if executor:
                actual = executor(inp)
                result = _compare(name, inp, golden, actual)
            else:
                # No executor for this live tool — skip gracefully
                result = CheckpointResult(
                    tool_name=name, input=inp, golden=golden, actual=None,
                    passed=True, severity="pass",
                    notes=f"No executor for '{name}' — skipped.",
                )

        elif cls == "capture":
            result = CheckpointResult(
                tool_name=name, input=inp, golden=golden, actual=golden,
                passed=True, severity="pass",
                notes="Capture tool — golden input recorded for future comparison.",
            )

        else:  # stub
            result = CheckpointResult(
                tool_name=name, input=inp, golden=golden, actual=golden,
                passed=True, severity="pass",
                notes="Stubbed — cached golden result returned.",
            )

        results.append(_judge(result, is_negative))

    report = EvalReport(
        eval_name=metadata.get("name", eval_dir.name),
        is_negative=is_negative,
        example_type=example_type,
        what_went_well=metadata.get("what_went_well", ""),
        what_went_poorly=metadata.get("what_went_poorly", ""),
        results=results,
    )

    # Persist the report alongside the eval case
    report_path = eval_dir / "last_report.md"
    report_path.write_text(report.to_markdown())

    return report


# ── Discovery ─────────────────────────────────────────────────────────────────


def discover_evals(evals_dir: Path) -> list:
    if not evals_dir.exists():
        return []
    return sorted(
        d.name for d in evals_dir.iterdir()
        if d.is_dir() and (d / "metadata.json").exists()
    )


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> None:
    p = argparse.ArgumentParser(
        description="Run saved eval test cases against the current codebase."
    )
    p.add_argument("--eval", metavar="NAME", help="Name of the eval to run")
    p.add_argument("--all", action="store_true", help="Run all saved evals")
    p.add_argument("--list", action="store_true", help="List saved evals")
    p.add_argument(
        "--evals-dir", metavar="PATH", default=None,
        help="Path to the evals directory. Default: <project-root>/.claude/evals/",
    )
    p.add_argument(
        "--project-root", metavar="PATH", default=None,
        help="Project root used to locate .claude/evals/. Default: current directory.",
    )
    args = p.parse_args()

    root = args.project_root or "."
    evals_dir = (
        Path(args.evals_dir)
        if args.evals_dir
        else Path(root) / ".claude" / "evals"
    )

    # ── List ──────────────────────────────────────────────────────────────────
    if args.list:
        names = discover_evals(evals_dir)
        if not names:
            print(f"No evals found in {evals_dir}")
            return
        print(f"Saved evals in {evals_dir}:\n")
        for name in names:
            meta_path = evals_dir / name / "metadata.json"
            try:
                meta = json.loads(meta_path.read_text())
                kind = "NEGATIVE" if meta.get("is_negative") else "positive"
                desc = meta.get("description", "")
                created = meta.get("created_at", "")[:10]
                print(f"  {name:<40s}  [{kind}]  {created}  {desc}")
            except Exception:
                print(f"  {name}")
        return

    # ── Run all ───────────────────────────────────────────────────────────────
    if args.all:
        names = discover_evals(evals_dir)
        if not names:
            print(f"No evals found in {evals_dir}")
            return
        total_pass = total_fail = 0
        for name in names:
            try:
                report = run_eval(evals_dir / name)
                status = "PASS" if report.passed else "FAIL"
                print(f"  [{status}] {name} — {report.summary_text()}")
                if report.passed:
                    total_pass += 1
                else:
                    total_fail += 1
            except Exception as e:
                print(f"  [ERROR] {name} — {e}")
                total_fail += 1
        print(f"\n{total_pass + total_fail} evals: {total_pass} passed, {total_fail} failed")
        if total_fail > 0:
            sys.exit(1)
        return

    # ── Run single ────────────────────────────────────────────────────────────
    if args.eval:
        eval_dir = evals_dir / args.eval
        if not eval_dir.exists():
            print(
                f"Error: eval '{args.eval}' not found in {evals_dir}",
                file=sys.stderr,
            )
            sys.exit(1)
        report = run_eval(eval_dir)
        print(report.to_markdown())
        print(f"\nReport saved to: {eval_dir / 'last_report.md'}")
        if not report.passed:
            sys.exit(1)
        return

    p.print_help()


if __name__ == "__main__":
    main()
