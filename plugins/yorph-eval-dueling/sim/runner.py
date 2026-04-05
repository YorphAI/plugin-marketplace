#!/usr/bin/env python3
"""
Yorph Semantic Layer Simulator — runner CLI.

Usage:
    python runner.py --scenario ecommerce_medium --persona skeptic
    python runner.py --list
    python runner.py --scenario saas_simple --persona expert --output ./sim_output/

What it does:
  1. Seeds a DuckDB database with the chosen scenario
  2. Runs the real profiler against it (produces genuine statistical profiles)
  3. Writes profiles to ~/.yorph/profiles/simulation/  (agent reads from here)
  4. Writes scenario metadata to ~/.yorph/sim/scenario.json
  5. Outputs:
       - context_summary.md   — what the agent will see via get_context_summary
       - persona_script.md    — conversation script to paste into Claude
       - ground_truth.json    — expected joins/measures for scoring
       - scenario_brief.md    — data quality issues + table descriptions

The agent connects with: connect_warehouse(warehouse_type="simulation")
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# ── Path setup ─────────────────────────────────────────────────────────────────
# Add the semantic layer runtime to sys.path so we can import the profiler
SIM_DIR = Path(__file__).parent
EVALS_DIR = SIM_DIR.parent
REPO_ROOT = EVALS_DIR.parent
SLA_RUNTIME = REPO_ROOT / "yorph-semantic-layer-assistant" / "runtime"
sys.path.insert(0, str(SLA_RUNTIME.parent))  # adds yorph-semantic-layer-assistant/

from scenarios import ALL_SCENARIOS
from personas import ALL_PERSONAS
from scenarios.base import Scenario, GroundTruth

YORPH_HOME = Path.home() / ".yorph"
SIM_HOME = YORPH_HOME / "sim"
PROFILES_DIR = YORPH_HOME / "profiles" / "simulation"


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Yorph Semantic Layer Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--scenario", "-s",
        choices=list(ALL_SCENARIOS.keys()),
        help="Scenario to seed and profile.",
    )
    parser.add_argument(
        "--persona", "-p",
        choices=list(ALL_PERSONAS.keys()),
        default="expert",
        help="User persona script to generate (default: expert).",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Directory for output files (default: ./sim_output/<scenario>_<persona>/).",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all available scenarios and personas.",
    )
    parser.add_argument(
        "--skip-profile",
        action="store_true",
        help="Skip profiling (re-use existing profiles in ~/.yorph/profiles/simulation/).",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable coloured terminal output.",
    )

    args = parser.parse_args()

    if args.list:
        _print_list()
        return

    if not args.scenario:
        parser.print_help()
        sys.exit(1)

    run(
        scenario_name=args.scenario,
        persona_name=args.persona,
        output_dir=Path(args.output) if args.output else None,
        skip_profile=args.skip_profile,
        color=not args.no_color,
    )


def run(
    scenario_name: str,
    persona_name: str,
    output_dir: Path | None = None,
    skip_profile: bool = False,
    color: bool = True,
) -> dict[str, Path]:
    """
    Run the simulator for a given scenario + persona.
    Returns a dict of output file paths.
    """
    scenario = ALL_SCENARIOS[scenario_name]
    persona = ALL_PERSONAS[persona_name]

    if output_dir is None:
        output_dir = SIM_DIR / "sim_output" / f"{scenario_name}_{persona_name}"
    output_dir.mkdir(parents=True, exist_ok=True)

    _print_header(scenario, persona, color)

    # ── Step 1: Seed DuckDB ────────────────────────────────────────────────────
    db_path = SIM_HOME / "current.duckdb"
    SIM_HOME.mkdir(parents=True, exist_ok=True)

    if not skip_profile:
        _print_step(1, "Seeding DuckDB", color)
        try:
            db_path = scenario.seed(db_path)
            _print_ok(f"Database seeded: {db_path}", color)
        except Exception as e:
            _print_err(f"Failed to seed database: {e}", color)
            raise

    # ── Step 2: Run profiler ───────────────────────────────────────────────────
    if not skip_profile:
        _print_step(2, "Profiling schema", color)
        try:
            sim_profiler = scenario.make_profiler(db_path)
            profiler = sim_profiler.profiler
            # Override profiles directory to ~/.yorph/profiles/simulation/
            PROFILES_DIR.mkdir(parents=True, exist_ok=True)
            profiler._profiles_dir = YORPH_HOME / "profiles"

            profiles = asyncio.run(profiler.profile_all(schemas=scenario.schemas))
            _print_ok(f"Profiled {len(profiles)} tables", color)

        except Exception as e:
            _print_err(f"Profiling failed: {e}", color)
            raise
    else:
        _print_step(2, "Profiling skipped (--skip-profile)", color)
        profiles = []

    # ── Step 3: Write scenario metadata ───────────────────────────────────────
    _print_step(3, "Writing scenario metadata", color)
    meta = {
        "name": scenario.name,
        "domain": scenario.domain,
        "complexity": scenario.complexity,
        "description": scenario.description,
        "schemas": scenario.schemas,
        "db_path": str(db_path),
        "tables": list(scenario.table_descriptions.keys()),
        "data_quality_issues": [
            {
                "table": dqi.table,
                "column": dqi.column,
                "issue_type": dqi.issue_type,
                "description": dqi.description,
                "prevalence": dqi.prevalence,
            }
            for dqi in scenario.data_quality_issues
        ],
    }
    meta_path = SIM_HOME / "scenario.json"
    meta_path.write_text(json.dumps(meta, indent=2))
    _print_ok(f"Metadata: {meta_path}", color)

    # ── Step 4: Generate context summary ──────────────────────────────────────
    _print_step(4, "Generating context summary", color)
    context_summary = _build_context_summary(scenario, profiles, color)
    cs_path = output_dir / "context_summary.md"
    cs_path.write_text(context_summary)
    _print_ok(f"Context summary: {cs_path}", color)

    # ── Step 5: Generate persona script ───────────────────────────────────────
    _print_step(5, "Generating persona script", color)
    scenario_ctx = _build_scenario_context(scenario)
    persona_script = persona.render_script(scenario_ctx)
    ps_path = output_dir / "persona_script.md"
    ps_path.write_text(persona_script)
    _print_ok(f"Persona script: {ps_path}", color)

    # ── Step 6: Write ground truth ────────────────────────────────────────────
    _print_step(6, "Writing ground truth", color)
    gt_path = output_dir / "ground_truth.json"
    gt_path.write_text(_serialize_ground_truth(scenario.ground_truth))
    _print_ok(f"Ground truth: {gt_path}", color)

    # ── Step 7: Write scenario brief ──────────────────────────────────────────
    _print_step(7, "Writing scenario brief", color)
    brief_path = output_dir / "scenario_brief.md"
    brief_path.write_text(_build_scenario_brief(scenario))
    _print_ok(f"Scenario brief: {brief_path}", color)

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    _print_banner("READY TO TEST", color)
    print(f"""
Agent is now configured with scenario: {_bold(scenario.name, color)}
Persona script: {_bold(persona.title, color)} ({persona.name})

To start the stress test:
  1. Open Claude with the semantic layer agent
  2. Open: {ps_path}
  3. Follow the conversation script turn by turn
  4. Compare agent output to: {gt_path}

The agent will connect with:
  connect_warehouse(warehouse_type="simulation")

Profiles written to: {PROFILES_DIR}/
DuckDB at: {db_path}
""")

    return {
        "context_summary": cs_path,
        "persona_script": ps_path,
        "ground_truth": gt_path,
        "scenario_brief": brief_path,
        "scenario_meta": meta_path,
    }


# ── Context summary builder ────────────────────────────────────────────────────

def _build_context_summary(scenario: Scenario, profiles: list, color: bool) -> str:
    """Build a markdown context summary showing what the agent will see."""
    if not profiles:
        return (
            "# Context Summary\n\n"
            "*Profiles not generated (--skip-profile). "
            "Run without --skip-profile to generate.*"
        )

    try:
        from runtime.documents.context import MergedDocumentContext
        from runtime.documents.enricher import build_enriched_profiles, enriched_context_summary

        enriched = build_enriched_profiles(profiles)
        merged = MergedDocumentContext([])
        summary = enriched_context_summary(enriched, merged, batch_index=0)
        return f"# Context Summary — {scenario.name}\n\n{summary}"
    except Exception as e:
        # Fall back to a simple summary
        lines = [f"# Context Summary — {scenario.name}", ""]
        for p in profiles:
            lines.append(f"## {p.schema_name}.{p.table_name}")
            lines.append(f"Rows: {p.total_rows:,} | Columns: {len(p.columns)}")
            lines.append("")
        return "\n".join(lines)


# ── Scenario context for persona templates ─────────────────────────────────────

def _build_scenario_context(scenario: Scenario) -> dict:
    tables = list(scenario.table_descriptions.keys())
    primary_table = tables[0] if tables else "orders"

    # Build a bulleted list of data quality issues
    dqi_lines = []
    for dqi in scenario.data_quality_issues:
        dqi_lines.append(
            f"- **{dqi.table}.{dqi.column}** ({dqi.issue_type}): {dqi.description}"
        )

    return {
        "scenario_name": scenario.name,
        "domain": scenario.domain,
        "complexity": scenario.complexity,
        "description": scenario.description,
        "primary_table": primary_table,
        "table_list": ", ".join(tables[:8]) + ("..." if len(tables) > 8 else ""),
        "data_quality_issues": "\n".join(dqi_lines) if dqi_lines else "None documented.",
    }


# ── Scenario brief ─────────────────────────────────────────────────────────────

def _build_scenario_brief(scenario: Scenario) -> str:
    lines = [
        f"# Scenario Brief: {scenario.name}",
        f"",
        f"**Domain:** {scenario.domain} | **Complexity:** {scenario.complexity}",
        f"",
        f"{scenario.description}",
        f"",
        f"---",
        f"",
        f"## Tables",
        f"",
    ]
    for table, desc in scenario.table_descriptions.items():
        lines.append(f"- **{table}**: {desc}")
    lines.append("")

    if scenario.data_quality_issues:
        lines += [
            "---",
            "",
            "## Data Quality Issues (deliberately injected)",
            "",
            "These are known issues the agent MUST discover and surface:",
            "",
        ]
        for dqi in scenario.data_quality_issues:
            lines += [
                f"### {dqi.table}.{dqi.column} — `{dqi.issue_type}`",
                f"",
                f"{dqi.description}",
                f"",
                f"**Prevalence:** {dqi.prevalence}",
                f"",
            ]

    gt = scenario.ground_truth
    if gt.expected_joins:
        lines += ["---", "", "## Expected Joins (ground truth)", ""]
        for j in gt.expected_joins:
            trap = f" ⚠ {j.trap_type} trap" if j.is_trap else ""
            lines.append(f"- `{j.left}` → `{j.right}` on `{j.key}` [{j.cardinality}]{trap}")
        lines.append("")

    if gt.expected_measures:
        lines += ["---", "", "## Expected Measures (ground truth)", ""]
        for m in gt.expected_measures:
            filt = f" WHERE {', '.join(m.filters)}" if m.filters else ""
            lines.append(f"- **{m.label}**: {m.aggregation}({m.source_table}.{m.source_column or '*'}){filt}")
        lines.append("")

    if gt.business_rules:
        lines += ["---", "", "## Expected Business Rules", ""]
        for rule in gt.business_rules:
            lines.append(f"- {rule}")
        lines.append("")

    return "\n".join(lines)


# ── Ground truth serialisation ─────────────────────────────────────────────────

def _serialize_ground_truth(gt: GroundTruth) -> str:
    return json.dumps({
        "expected_joins": [
            {
                "left": j.left, "right": j.right, "key": j.key,
                "cardinality": j.cardinality, "is_trap": j.is_trap,
                "trap_type": j.trap_type,
            }
            for j in gt.expected_joins
        ],
        "expected_measures": [
            {
                "measure_id": m.measure_id, "label": m.label,
                "aggregation": m.aggregation, "source_table": m.source_table,
                "source_column": m.source_column, "filters": m.filters,
                "domain": m.domain,
            }
            for m in gt.expected_measures
        ],
        "business_rules": gt.business_rules,
        "open_questions": gt.open_questions,
        "grain_per_table": gt.grain_per_table,
    }, indent=2)


# ── List command ───────────────────────────────────────────────────────────────

def _print_list():
    from scenarios import ALL_SCENARIOS
    from personas import ALL_PERSONAS

    print("\nAvailable scenarios:\n")
    for name, s in ALL_SCENARIOS.items():
        print(f"  {name:<30} {s.domain:<15} {s.complexity}")

    print("\nAvailable personas:\n")
    for name, p in ALL_PERSONAS.items():
        print(f"  {name:<15} {p.title}")

    print()


# ── Terminal helpers ───────────────────────────────────────────────────────────

def _bold(text: str, color: bool) -> str:
    return f"\033[1m{text}\033[0m" if color else text

def _green(text: str, color: bool) -> str:
    return f"\033[32m{text}\033[0m" if color else text

def _red(text: str, color: bool) -> str:
    return f"\033[31m{text}\033[0m" if color else text

def _cyan(text: str, color: bool) -> str:
    return f"\033[36m{text}\033[0m" if color else text

def _print_step(n: int, label: str, color: bool):
    print(f"\n{_cyan(f'[{n}]', color)} {_bold(label, color)}")

def _print_ok(msg: str, color: bool):
    print(f"    {_green('✓', color)} {msg}")

def _print_err(msg: str, color: bool):
    print(f"    {_red('✗', color)} {msg}", file=sys.stderr)

def _print_header(scenario: Scenario, persona, color: bool):
    print()
    _print_banner(f"YORPH SIMULATOR", color)
    print(f"  Scenario : {_bold(scenario.name, color)} ({scenario.domain} / {scenario.complexity})")
    print(f"  Persona  : {_bold(persona.name, color)} ({persona.title})")
    print(f"  DB path  : {SIM_HOME / 'current.duckdb'}")

def _print_banner(text: str, color: bool):
    bar = "─" * (len(text) + 4)
    print(f"\n  ┌{bar}┐")
    print(f"  │  {_bold(text, color)}  │")
    print(f"  └{bar}┘\n")


if __name__ == "__main__":
    main()
