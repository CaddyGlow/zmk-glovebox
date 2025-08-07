"""ZMK Layout stats command - Show detailed layout statistics and analysis."""

import json
from collections import Counter
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from glovebox.cli.decorators import handle_errors, with_metrics, with_profile
from glovebox.cli.helpers.stdin_utils import is_stdin_input
from glovebox.cli.helpers.theme import get_themed_console
from glovebox.core.structlog_logger import get_struct_logger
from glovebox.layout.models import LayoutData


logger = get_struct_logger(__name__)
console = get_themed_console()


def analyze_layout_statistics(layout_data: LayoutData) -> dict[str, Any]:
    """Analyze layout and generate comprehensive statistics."""
    stats: dict[str, Any] = {
        "basic": {
            "keyboard": getattr(layout_data, "keyboard", "unknown"),
            "layer_count": len(layout_data.layers),
            "total_bindings": 0,
            "unique_bindings": set(),
        },
        "layers": [],
        "behaviors": Counter(),
        "modifiers": Counter(),
        "keys": Counter(),
        "combos": 0,
        "macros": 0,
    }

    # Analyze each layer
    for i, layer in enumerate(layout_data.layers):
        layer_name = getattr(layer, "name", f"layer_{i}")
        layer_bindings = getattr(layer, "bindings", layer)

        # Handle different layer formats
        if isinstance(layer_bindings, dict):
            bindings = layer_bindings.get("bindings", [])
        elif isinstance(layer_bindings, list):
            bindings = layer_bindings
        else:
            bindings = []

        layer_stats = {
            "name": layer_name,
            "index": i,
            "binding_count": len(bindings),
            "unique_bindings": len(set(bindings)),
            "empty_bindings": bindings.count("&trans") + bindings.count("&none"),
            "behaviors": Counter(),
        }

        # Analyze bindings
        for binding in bindings:
            if isinstance(binding, str):
                stats["basic"]["unique_bindings"].add(binding)

                # Parse behavior from binding
                if binding.startswith("&"):
                    if " " in binding:
                        behavior = binding.split(" ")[0]
                        params = binding.split(" ")[1:]
                    else:
                        behavior = binding
                        params = []

                    stats["behaviors"][behavior] += 1
                    layer_stats["behaviors"][behavior] += 1

                    # Categorize special behaviors
                    if behavior in ("&kp", "&key_press"):
                        if params:
                            stats["keys"][params[0]] += 1
                    elif behavior in ("&mt", "&mod_tap"):
                        stats["modifiers"]["mod_tap"] += 1
                    elif behavior in ("&lt", "&layer_tap"):
                        stats["modifiers"]["layer_tap"] += 1
                    elif behavior.startswith("&macro"):
                        stats["macros"] += 1
                    elif behavior.startswith("&combo"):
                        stats["combos"] += 1

        stats["basic"]["total_bindings"] += len(bindings)
        stats["layers"].append(layer_stats)

    # Convert set to list for JSON serialization
    stats["basic"]["unique_bindings"] = len(stats["basic"]["unique_bindings"])

    return stats


@with_metrics("zmk_layout.stats")
@with_profile()
@handle_errors
def stats_layout(
    ctx: typer.Context,
    input_file: Annotated[
        str,
        typer.Argument(
            help="JSON layout file path or '-' for stdin", metavar="INPUT_FILE"
        ),
    ] = "-",
    profile: Annotated[
        str | None,
        typer.Option(
            "-p",
            "--profile",
            help="Keyboard profile for additional context",
        ),
    ] = None,
    format: Annotated[
        str,
        typer.Option(
            "-f",
            "--format",
            help="Output format: table, json, summary",
        ),
    ] = "table",
    show_layers: Annotated[
        bool,
        typer.Option(
            "--layers/--no-layers",
            help="Show per-layer statistics",
        ),
    ] = True,
    show_behaviors: Annotated[
        bool,
        typer.Option(
            "--behaviors/--no-behaviors",
            help="Show behavior usage statistics",
        ),
    ] = True,
    show_keys: Annotated[
        bool,
        typer.Option(
            "--keys/--no-keys",
            help="Show key usage statistics",
        ),
    ] = False,
    top_n: Annotated[
        int,
        typer.Option(
            "--top",
            help="Show top N items in usage statistics",
        ),
    ] = 10,
) -> None:
    """Show detailed layout statistics and analysis.

    This command analyzes JSON layouts and provides comprehensive
    statistics including layer information, behavior usage, key
    frequency, and structural analysis.

    **Examples:**

    \b
    # Basic layout statistics
    glovebox zmk-layout stats my_layout.json

    \b
    # Detailed statistics with key usage
    glovebox zmk-layout stats layout.json --keys --top 15

    \b
    # JSON output for automation
    glovebox zmk-layout stats layout.json -f json

    \b
    # Summary format with layers
    glovebox zmk-layout stats layout.json -f summary --layers
    """
    try:
        # Handle input
        if input_file == "-" or is_stdin_input(input_file):
            import sys

            content = sys.stdin.read().strip()
            if not content:
                console.console.print(
                    "[red]Error:[/red] No input provided via stdin", style="error"
                )
                raise typer.Exit(1)
            try:
                layout_dict = json.loads(content)
                source_name = "stdin"
            except json.JSONDecodeError as e:
                console.console.print(
                    f"[red]Error:[/red] Invalid JSON input: {e}", style="error"
                )
                raise typer.Exit(1) from None
        else:
            input_path = Path(input_file)
            if not input_path.exists():
                console.console.print(
                    f"[red]Error:[/red] Input file not found: {input_path}",
                    style="error",
                )
                raise typer.Exit(1)
            try:
                layout_dict = json.loads(input_path.read_text())
                source_name = input_path.name
            except json.JSONDecodeError as e:
                console.console.print(
                    f"[red]Error:[/red] Invalid JSON in {input_path}: {e}",
                    style="error",
                )
                raise typer.Exit(1) from None

        # Get keyboard profile
        app_context = ctx.obj
        keyboard_profile = app_context.keyboard_profile

        # Show analysis progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console.console,
            transient=True,
        ) as progress:
            task = progress.add_task("Analyzing layout...", total=None)

            # Convert dict to LayoutData
            layout_data = LayoutData.model_validate(layout_dict)

            # Analyze statistics
            stats = analyze_layout_statistics(layout_data)

            progress.update(task, description="Analysis complete!")

        if format == "json":
            # JSON output for automation
            output = {
                "source": source_name,
                "analysis_timestamp": None,  # Could add timestamp
                "keyboard_profile": keyboard_profile.keyboard_name
                if keyboard_profile
                else None,
                "statistics": stats,
            }
            console.console.print(
                json.dumps(output, indent=2, default=str), highlight=False
            )

        elif format == "summary":
            # Compact summary format
            basic = stats["basic"]
            console.console.print(
                Panel(
                    f"[bold blue]{source_name}[/bold blue]\n"
                    f"Keyboard: [cyan]{basic['keyboard']}[/cyan]\n"
                    f"Layers: [green]{basic['layer_count']}[/green] | "
                    f"Total Bindings: [green]{basic['total_bindings']}[/green] | "
                    f"Unique: [green]{basic['unique_bindings']}[/green]\n"
                    f"Top Behaviors: [yellow]{', '.join([f'{b}({c})' for b, c in stats['behaviors'].most_common(3)])}[/yellow]",
                    title="[bold blue]Layout Summary[/bold blue]",
                    expand=False,
                )
            )

        else:
            # Rich table format (default)
            console.console.print(
                Panel(
                    f"[bold blue]Layout Statistics: {source_name}[/bold blue]",
                    expand=False,
                )
            )

            # Basic statistics table
            basic_table = Table(show_header=False, box=None, padding=(0, 1))
            basic_table.add_column("Property", style="cyan", width=20)
            basic_table.add_column("Value", style="white")

            basic = stats["basic"]
            basic_table.add_row("Keyboard", basic["keyboard"])
            basic_table.add_row("Layers", str(basic["layer_count"]))
            basic_table.add_row("Total Bindings", f"{basic['total_bindings']:,}")
            basic_table.add_row("Unique Bindings", str(basic["unique_bindings"]))
            basic_table.add_row("Macros", str(stats["macros"]))
            basic_table.add_row("Combos", str(stats["combos"]))

            console.console.print(basic_table)

            # Layer statistics
            if show_layers and stats["layers"]:
                console.console.print("\n[bold blue]Layer Statistics[/bold blue]")

                layer_table = Table(show_header=True, header_style="bold blue")
                layer_table.add_column("Layer", style="cyan")
                layer_table.add_column("Bindings", style="green", justify="right")
                layer_table.add_column("Unique", style="yellow", justify="right")
                layer_table.add_column("Empty", style="red", justify="right")
                layer_table.add_column("Top Behavior", style="white")

                for layer in stats["layers"]:
                    top_behavior = layer["behaviors"].most_common(1)
                    top_behavior_str = (
                        f"{top_behavior[0][0]} ({top_behavior[0][1]})"
                        if top_behavior
                        else "none"
                    )

                    layer_table.add_row(
                        layer["name"][:15],  # Truncate long names
                        str(layer["binding_count"]),
                        str(layer["unique_bindings"]),
                        str(layer["empty_bindings"]),
                        top_behavior_str,
                    )

                console.console.print(layer_table)

            # Behavior usage statistics
            if show_behaviors and stats["behaviors"]:
                console.console.print(
                    f"\n[bold blue]Behavior Usage (Top {top_n})[/bold blue]"
                )

                behavior_table = Table(show_header=True, header_style="bold blue")
                behavior_table.add_column("Behavior", style="cyan")
                behavior_table.add_column("Count", style="green", justify="right")
                behavior_table.add_column("Percentage", style="yellow", justify="right")

                total_behaviors = sum(stats["behaviors"].values())
                for behavior, count in stats["behaviors"].most_common(top_n):
                    percentage = (
                        (count / total_behaviors) * 100 if total_behaviors > 0 else 0
                    )
                    behavior_table.add_row(behavior, str(count), f"{percentage:.1f}%")

                console.console.print(behavior_table)

            # Key usage statistics
            if show_keys and stats["keys"]:
                console.console.print(
                    f"\n[bold blue]Key Usage (Top {top_n})[/bold blue]"
                )

                key_table = Table(show_header=True, header_style="bold blue")
                key_table.add_column("Key", style="cyan")
                key_table.add_column("Count", style="green", justify="right")
                key_table.add_column("Layers", style="yellow", justify="right")

                total_keys = sum(stats["keys"].values())
                for key, count in stats["keys"].most_common(top_n):
                    # Calculate how many layers use this key
                    layers_with_key = sum(
                        1
                        for layer in stats["layers"]
                        for behavior in layer["behaviors"]
                        if key in behavior
                    )

                    key_table.add_row(key, str(count), str(layers_with_key))

                console.console.print(key_table)

        # Log statistics analysis
        logger.info(
            "layout_statistics_generated",
            source=source_name,
            layer_count=stats["basic"]["layer_count"],
            total_bindings=stats["basic"]["total_bindings"],
            unique_bindings=stats["basic"]["unique_bindings"],
            format=format,
        )

    except Exception as e:
        logger.error("layout_statistics_failed", error=str(e), exc_info=True)
        console.console.print(f"[red]Error:[/red] {e}", style="error")
        raise typer.Exit(1) from None
