"""
Yorph Semantic Layer Assistant — CLI entry point.

Usage:
  yorph serve          Start the MCP stdio server (default — used by Claude Code)
  yorph profile        Run the profiler standalone (useful for testing)
  yorph clear          Clear all local data (profiles, samples, documents, output)
  yorph status         Show what's saved locally

The MCP server communicates over stdin/stdout (stdio transport).
Claude Code connects to it via the plugin.json mcp_server config.
"""

from __future__ import annotations

import asyncio
import getpass
import json
import sys
from pathlib import Path

import click
import keyring
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

YORPH_DIR = Path.home() / ".yorph"

# Fields that contain secrets — prompted with masked input
_SECRET_KEYWORDS = {"PASSWORD", "SECRET", "PASSPHRASE", "TOKEN"}


# ── Main group ─────────────────────────────────────────────────────────────────

@click.group()
def main():
    """Yorph Semantic Layer Assistant."""
    pass


# ── serve ─────────────────────────────────────────────────────────────────────

@main.command()
def serve():
    """
    Start the MCP stdio server.

    This is the default command — called by Claude Code when the plugin launches.
    Communicates over stdin/stdout. Do not run this interactively unless testing.
    """
    from runtime.tools import main as run_server
    asyncio.run(run_server())


# ── connect ───────────────────────────────────────────────────────────────────

@main.command()
@click.argument("warehouse", type=click.Choice(
    ["snowflake", "bigquery", "redshift", "sql_server", "supabase", "postgres", "s3", "gcs"],
    case_sensitive=False,
))
@click.option("--auth-method", "-a", default=None,
              help="Auth method (e.g. key_pair, password, adc). Prompted if not set.")
def connect(warehouse: str, auth_method: str | None):
    """
    Securely save warehouse credentials to OS keychain.

    Run this BEFORE starting Claude Code so the MCP server auto-reconnects
    without credentials appearing in the chat.

    Passwords and secrets are masked (hidden) during input.

    Examples:
      yorph connect supabase
      yorph connect snowflake --auth-method key_pair
      yorph connect bigquery --auth-method adc
    """
    from runtime.credentials import CREDENTIAL_GUIDE

    if warehouse not in CREDENTIAL_GUIDE:
        console.print(f"[red]Unknown warehouse: '{warehouse}'[/red]")
        console.print(f"Supported: {', '.join(CREDENTIAL_GUIDE.keys())}")
        sys.exit(1)

    guide = CREDENTIAL_GUIDE[warehouse]
    methods = guide["auth_methods"]

    # Pick auth method
    if auth_method and auth_method not in methods:
        console.print(f"[red]Unknown auth method '{auth_method}' for {warehouse}.[/red]")
        console.print(f"Available: {', '.join(methods.keys())}")
        sys.exit(1)

    if not auth_method:
        if len(methods) == 1:
            auth_method = next(iter(methods))
        else:
            console.print(f"\n[bold]{guide['display']}[/bold] — choose an auth method:\n")
            method_list = list(methods.items())
            for i, (key, info) in enumerate(method_list, 1):
                console.print(f"  [bold]{i}[/bold]. {info['label']}  [dim][{key}][/dim]")
            console.print()
            choice = click.prompt("Enter number or name", type=str).strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(method_list):
                    auth_method = method_list[idx][0]
                else:
                    console.print("[red]Invalid choice.[/red]")
                    sys.exit(1)
            elif choice in methods:
                auth_method = choice
            else:
                console.print(f"[red]Invalid. Available: {', '.join(methods.keys())}[/red]")
                sys.exit(1)

    method_info = methods[auth_method]
    required_fields = method_info.get("required", {})
    optional_fields = method_info.get("optional", {})

    console.print(Panel(
        f"[bold]{guide['display']}[/bold] — {method_info['label']}",
        subtitle="Fields marked * are required. Passwords are hidden.",
    ))

    if "how_to_get" in method_info:
        console.print(f"[dim]{method_info['how_to_get']}[/dim]\n")

    creds = {"auth_method": auth_method}

    # Prompt required fields
    for field, desc in required_fields.items():
        value = _prompt_cred_field(field, desc, required=True)
        if value:
            creds[field] = value

    # Prompt optional fields
    if optional_fields:
        console.print("\n[dim]Optional fields (press Enter to skip):[/dim]\n")
        for field, desc in optional_fields.items():
            value = _prompt_cred_field(field, desc, required=False)
            if value:
                creds[field] = value

    # Save to keychain
    keychain_key = f"yorph_{warehouse}"
    try:
        keyring.set_password("yorph", keychain_key, json.dumps(creds))
        console.print(f"\n[green]✅ Credentials saved to OS keychain[/green] (key: {keychain_key})")
        console.print("   The MCP server will auto-reconnect using these next session.")
        console.print(f"   Run [bold]yorph creds-clear {warehouse}[/bold] to remove them.\n")
    except Exception as e:
        console.print(f"\n[red]⚠ Failed to save to keychain: {e}[/red]")
        sys.exit(1)


# ── creds-status ──────────────────────────────────────────────────────────────

@main.command("creds-status")
def creds_status():
    """Show which warehouses have saved credentials in the OS keychain."""
    from runtime.credentials import CREDENTIAL_GUIDE

    table = Table(title="Saved Credentials", show_header=True, header_style="bold")
    table.add_column("Warehouse")
    table.add_column("Auth Method")
    table.add_column("Fields")
    table.add_column("Status")

    found = False
    for wh, guide in CREDENTIAL_GUIDE.items():
        keychain_key = f"yorph_{wh}"
        saved = keyring.get_password("yorph", keychain_key)
        if saved:
            creds = json.loads(saved)
            auth = creds.get("auth_method", "unknown")
            fields = [k for k in creds if k != "auth_method"]
            table.add_row(
                guide["display"],
                auth,
                ", ".join(fields),
                "[green]saved[/green]",
            )
            found = True
        else:
            table.add_row(guide["display"], "—", "—", "[dim]not set[/dim]")

    console.print(table)
    if not found:
        console.print("\n[yellow]No saved credentials. Run:[/yellow] yorph connect <warehouse>\n")


# ── creds-clear ───────────────────────────────────────────────────────────────

@main.command("creds-clear")
@click.argument("warehouse")
@click.confirmation_option(prompt="Remove saved credentials?")
def creds_clear(warehouse: str):
    """Remove saved credentials for a warehouse from OS keychain."""
    keychain_key = f"yorph_{warehouse}"
    try:
        keyring.delete_password("yorph", keychain_key)
        console.print(f"[green]✅ Cleared credentials for {warehouse}.[/green]")
    except keyring.errors.PasswordDeleteError:
        console.print(f"[yellow]No saved credentials found for {warehouse}.[/yellow]")


# ── Credential field prompting helper ─────────────────────────────────────────

def _prompt_cred_field(field_name: str, description: str, required: bool) -> str | None:
    """Prompt for a single credential field, masking secrets."""
    upper = field_name.upper()
    is_secret = any(kw in upper for kw in _SECRET_KEYWORDS)
    is_file = "FILE" in upper or "PATH" in upper
    marker = "*" if required else " "

    prompt_text = f"  {marker} {field_name} ({description})"

    if is_secret:
        value = getpass.getpass(f"{prompt_text}: ")
    else:
        value = input(f"{prompt_text}: ")

    value = value.strip()
    if not value:
        if required:
            console.print(f"    [red]{field_name} is required.[/red]")
            return _prompt_cred_field(field_name, description, required)
        return None

    # Expand ~ in file paths
    if is_file:
        import os
        value = os.path.expanduser(value)

    return value


# ── profile (standalone) ──────────────────────────────────────────────────────

@main.command()
@click.option("--warehouse", "-w", required=True,
              type=click.Choice(["snowflake", "bigquery", "redshift", "sql_server", "supabase"]),
              help="Warehouse type to profile.")
@click.option("--credential-key", "-k", default=None,
              help="Keychain key for credentials. Defaults to the warehouse name.")
@click.option("--schema", "-s", multiple=True,
              help="Schemas to profile (repeat for multiple). Default: all schemas.")
@click.option("--sample-pct", default=10, show_default=True,
              help="TABLESAMPLE percentage for profiling queries.")
def profile(warehouse: str, credential_key: str | None, schema: tuple, sample_pct: int):
    """
    Run the profiler standalone — without going through Claude.

    Useful for:
      - Pre-generating profiles before a session
      - Testing profiler output
      - Debugging connection issues

    Example:
      yorph profile --warehouse snowflake --schema SALES --schema PRODUCT
    """
    import keyring

    key = credential_key or warehouse
    creds_json = keyring.get_password("yorph", key)
    if not creds_json:
        console.print(
            f"[red]No credentials found in keychain for key '{key}'.[/red]\n"
            "Connect through the Claude plugin UI first, or set credentials manually:\n"
            "  python -c \"import keyring, json; "
            "keyring.set_password('yorph', 'snowflake', json.dumps({...}))\""
        )
        sys.exit(1)

    creds = json.loads(creds_json)

    # Import profiler for the chosen warehouse
    if warehouse == "snowflake":
        from runtime.profiler.snowflake import SnowflakeProfiler
        profiler = SnowflakeProfiler(credentials=creds)
    else:
        console.print(f"[yellow]Profiler for '{warehouse}' not yet implemented.[/yellow]")
        sys.exit(1)

    console.print(Panel(f"[bold]Yorph Profiler[/bold] — {warehouse.upper()}"))

    with console.status("Connecting..."):
        profiler.connect()
    console.print("✅ Connected")

    schemas_list = list(schema) if schema else None
    label = ", ".join(schemas_list) if schemas_list else "all schemas"

    with console.status(f"Profiling {label}..."):
        profiles = asyncio.run(profiler.profile_all(schemas=schemas_list))

    console.print(f"✅ Profiled [bold]{len(profiles)}[/bold] tables → ~/.yorph/profiles/{warehouse}/")

    # Print compact summary
    table = Table(title="Table Profiles", show_header=True, header_style="bold cyan")
    table.add_column("Schema.Table", style="dim")
    table.add_column("Rows", justify="right")
    table.add_column("Columns")
    table.add_column("Nulls >20%")

    for p in profiles[:30]:  # show first 30
        high_null_cols = [c.name for c in p.columns if c.pct_null > 20]
        table.add_row(
            f"{p.schema_name}.{p.table_name}",
            f"{p.total_rows:,}",
            str(len(p.columns)),
            ", ".join(high_null_cols[:3]) + ("..." if len(high_null_cols) > 3 else ""),
        )

    if len(profiles) > 30:
        table.add_row(f"... and {len(profiles) - 30} more", "", "", "")

    console.print(table)
    profiler.disconnect()


# ── status ────────────────────────────────────────────────────────────────────

@main.command()
def status():
    """Show what's saved locally in ~/.yorph/."""
    if not YORPH_DIR.exists():
        console.print("[yellow]No ~/.yorph directory found. Run a profiling session first.[/yellow]")
        return

    console.print(Panel("[bold]Yorph Local Data[/bold]", subtitle=str(YORPH_DIR)))

    dirs = {
        "profiles":  YORPH_DIR / "profiles",
        "samples":   YORPH_DIR / "samples",
        "documents": YORPH_DIR / "documents",
        "output":    YORPH_DIR / "output",
        "sessions":  YORPH_DIR / "sessions",
    }

    table = Table(show_header=True, header_style="bold")
    table.add_column("Directory")
    table.add_column("Files", justify="right")
    table.add_column("Size")

    for name, path in dirs.items():
        if path.exists():
            files = list(path.rglob("*.*"))
            size_bytes = sum(f.stat().st_size for f in files if f.is_file())
            size_str = _format_size(size_bytes)
            table.add_row(f"~/.yorph/{name}/", str(len(files)), size_str)
        else:
            table.add_row(f"~/.yorph/{name}/", "—", "—")

    console.print(table)

    # List output files
    output_dir = YORPH_DIR / "output"
    if output_dir.exists():
        output_files = sorted(output_dir.glob("*"))
        if output_files:
            console.print("\n[bold]Output files:[/bold]")
            for f in output_files:
                size = _format_size(f.stat().st_size)
                console.print(f"  {f.name} ({size})")


# ── clear ─────────────────────────────────────────────────────────────────────

@main.command()
@click.option("--profiles", is_flag=True, help="Clear cached column profiles.")
@click.option("--samples", is_flag=True, help="Clear cached raw row samples.")
@click.option("--documents", is_flag=True, help="Clear processed document contexts.")
@click.option("--output", is_flag=True, help="Clear generated output files.")
@click.option("--all", "all_data", is_flag=True, help="Clear everything.")
@click.confirmation_option(prompt="This will delete local Yorph data. Continue?")
def clear(profiles: bool, samples: bool, documents: bool, output: bool, all_data: bool):
    """Clear local Yorph data from ~/.yorph/."""
    import shutil

    targets = {
        "profiles":  YORPH_DIR / "profiles",
        "samples":   YORPH_DIR / "samples",
        "documents": YORPH_DIR / "documents",
        "output":    YORPH_DIR / "output",
    }

    to_clear = []
    if all_data:
        to_clear = list(targets.keys())
    else:
        if profiles:
            to_clear.append("profiles")
        if samples:
            to_clear.append("samples")
        if documents:
            to_clear.append("documents")
        if output:
            to_clear.append("output")

    if not to_clear:
        console.print("[yellow]Nothing specified to clear. Use --all or a specific flag.[/yellow]")
        return

    for name in to_clear:
        path = targets[name]
        if path.exists():
            shutil.rmtree(path)
            path.mkdir(parents=True)
            console.print(f"✅ Cleared ~/.yorph/{name}/")
        else:
            console.print(f"[dim]~/.yorph/{name}/ — already empty[/dim]")



# ── validate (dev/test helper) ────────────────────────────────────────────────

@main.command()
@click.argument("format", type=click.Choice(["dbt", "snowflake", "json", "yaml", "osi_spec", "all"]))
@click.option("--fixture", "-f", default=None,
              help="Path to a JSON fixture file with mock agent_outputs. Uses built-in fixture if not set.")
@click.option("--out", "-o", default=None,
              help="Output directory. Default: ~/.yorph/output/test/")
def validate(format: str, fixture: str | None, out: str | None):
    """
    Test the renderer with mock agent outputs — no warehouse connection needed.

    Useful for:
      - Verifying the output format is correct
      - Testing changes to the renderer
      - Previewing what the output looks like before a real run

    Example:
      yorph validate dbt
      yorph validate all --fixture ./tests/fixtures/mock_agent_outputs.json
    """
    from runtime.output.renderer import OutputRenderer, build_semantic_layer_from_agent_outputs

    if fixture:
        with open(fixture) as f:
            agent_outputs = json.load(f)
    else:
        # Use built-in minimal fixture
        agent_outputs = _builtin_fixture()

    output_dir = Path(out) if out else YORPH_DIR / "output" / "test"

    for rec_number in (1, 2, 3):
        rec_names = {1: "Conservative", 2: "Comprehensive", 3: "Balanced"}
        layer = build_semantic_layer_from_agent_outputs(
            agent_outputs=agent_outputs,
            recommendation_number=rec_number,
            warehouse_type="snowflake",
            project_name="Test Project",
            description="Validation run using mock fixture data.",
        )

        renderer = OutputRenderer(layer, output_dir=output_dir)
        formats = ["dbt", "snowflake", "json", "yaml", "osi_spec"] if format == "all" else [format]

        for fmt in formats:
            written = renderer.render(fmt, filename_base=f"test_rec{rec_number}_{fmt}")
            for kind, path in written.items():
                console.print(f"✅ [{rec_names[rec_number]}] {kind}: {path}")

    console.print(f"\nAll test outputs written to: {output_dir}")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / 1024 ** 2:.1f} MB"


def _builtin_fixture() -> dict:
    """Minimal mock agent outputs for validation testing."""
    return {
        "joins": [
            {
                "join": "orders → order_items",
                "join_key": "order_id",
                "cardinality": "1:many",
                "safe": True,
                "notes": "Validated — 99.7% match rate, LEFT JOIN recommended.",
            },
            {
                "join": "orders → customers",
                "join_key": "customer_id",
                "cardinality": "many:1",
                "safe": True,
                "notes": "Clean FK, every order has a valid customer.",
            },
        ],
        "measures_mb1": [
            {
                "measure_id": "total_revenue",
                "label": "Total Revenue",
                "description": "Sum of revenue on completed orders.",
                "aggregation": "SUM",
                "source_table": "orders",
                "source_column": "revenue",
                "filter": "status = 'completed'",
                "additivity": "fully_additive",
                "domain": "Revenue & Growth",
                "is_certified": True,
            },
            {
                "measure_id": "order_count",
                "label": "Order Count",
                "description": "Count of completed orders.",
                "aggregation": "COUNT",
                "source_table": "orders",
                "source_column": "order_id",
                "filter": "status = 'completed'",
                "additivity": "fully_additive",
                "domain": "Revenue & Growth",
            },
        ],
        "measures_mb2": [
            {
                "measure_id": "total_revenue",
                "label": "Total Revenue",
                "description": "Sum of revenue on completed orders.",
                "aggregation": "SUM",
                "source_table": "orders",
                "source_column": "revenue",
                "filter": "status = 'completed'",
                "additivity": "fully_additive",
                "domain": "Revenue & Growth",
                "is_certified": True,
            },
            {
                "measure_id": "avg_order_value",
                "label": "Average Order Value",
                "description": "Average revenue per completed order.",
                "aggregation": "AVG",
                "source_table": "orders",
                "source_column": "revenue",
                "filter": "status = 'completed'",
                "additivity": "non_additive",
                "domain": "Revenue & Growth",
                "complexity": "simple",
            },
            {
                "measure_id": "refund_rate",
                "label": "Refund Rate",
                "description": "% of orders that were refunded.",
                "aggregation": "RATIO",
                "source_table": "orders",
                "numerator": "COUNT(order_id) WHERE status='refunded'",
                "denominator": "COUNT(order_id)",
                "additivity": "non_additive",
                "domain": "Revenue & Growth",
                "complexity": "moderate",
            },
        ],
        "measures_mb3": [
            {
                "measure_id": "total_revenue",
                "label": "Gross Revenue",
                "description": "Sum of revenue on completed orders. Excludes refunds.",
                "aggregation": "SUM",
                "source_table": "orders",
                "source_column": "revenue",
                "filter": "status = 'completed'",
                "domain": "Revenue & Growth",
                "is_certified": True,
            },
        ],
        "grain_gd1": [
            {
                "table": "orders",
                "grain": ["order_id"],
                "grain_description": "One row per order",
                "schema": "PUBLIC",
                "safe_dimensions": ["customers", "promotions"],
            },
            {
                "table": "order_items",
                "grain": ["order_id", "line_item_id"],
                "grain_description": "One row per line item within an order",
                "schema": "PUBLIC",
                "safe_dimensions": ["products"],
            },
        ],
        "grain_gd2": [
            {
                "table": "orders",
                "reporting_grain": ["order_date", "product_category", "region"],
                "grain_description": "Daily revenue by product category and region",
                "schema": "PUBLIC",
                "safe_dimensions": ["customers", "products", "promotions"],
            },
        ],
        "grain_gd3": [
            {
                "table": "orders",
                "grain": ["order_id"],
                "grain_description": "Atomic: one row per order",
                "schema": "PUBLIC",
                "safe_dimensions": ["customers", "products", "promotions"],
            },
            {
                "table": "daily_order_summary",
                "reporting_grain": ["order_date", "product_category"],
                "grain_description": "Pre-aggregated daily summary",
                "schema": "PUBLIC",
                "safe_dimensions": ["products"],
            },
        ],
        "business_rules": [
            "Revenue is only recognised when order_status = 'completed' AND payment_status = 'paid'",
            "A 'customer' is any user who has placed at least one completed order",
        ],
        "open_questions": [
            "Confirm whether draft orders should appear in order_count or be excluded",
            "Date spine not found — add a calendar table for gap-free time series metrics",
        ],
        "glossary": {
            "GMV": "Gross Merchandise Value — total order value before refunds and adjustments",
            "AOV": "Average Order Value — GMV divided by order count",
        },
    }


if __name__ == "__main__":
    main()
