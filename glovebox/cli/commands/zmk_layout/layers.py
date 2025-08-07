"""ZMK Layout layers command - Manage layers (add, remove, modify, reorder)."""

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from glovebox.cli.decorators import handle_errors, with_metrics, with_profile
from glovebox.cli.helpers.stdin_utils import is_stdin_input
from glovebox.cli.helpers.theme import get_themed_console
from glovebox.core.structlog_logger import get_struct_logger
from glovebox.layout.models import LayoutData


logger = get_struct_logger(__name__)
console = get_themed_console()

# Create layers sub-app
layers_app = typer.Typer(
    name="layers",
    help="""Manage layout layers.

Commands for adding, removing, modifying, and reordering layers
in ZMK layouts.
""",
    no_args_is_help=True,
)


@layers_app.command(name="list")
@with_metrics("zmk_layout.layers.list")
@with_profile()
@handle_errors
def list_layers(
    ctx: typer.Context,
    input_file: Annotated[
        str,
        typer.Argument(
            help="JSON layout file path or '-' for stdin", metavar="INPUT_FILE"
        ),
    ] = "-",
    format: Annotated[
        str,
        typer.Option(
            "-f",
            "--format",
            help="Output format: table, json, summary",
        ),
    ] = "table",
    show_bindings: Annotated[
        bool,
        typer.Option(
            "--bindings/--no-bindings",
            help="Show binding counts for each layer",
        ),
    ] = True,
    show_empty: Annotated[
        bool,
        typer.Option(
            "--empty/--no-empty",
            help="Show empty binding counts",
        ),
    ] = True,
) -> None:
    """List all layers in the layout.

    **Examples:**

    \b
    # List layers with binding information
    glovebox zmk-layout layers list my_layout.json

    \b
    # JSON output with summary
    glovebox zmk-layout layers list layout.json -f json

    \b
    # Summary without empty bindings
    glovebox zmk-layout layers list layout.json -f summary --no-empty
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
                ctx.exit(1)
            try:
                layout_dict = json.loads(content)
                source_name = "stdin"
            except json.JSONDecodeError as e:
                console.console.print(
                    f"[red]Error:[/red] Invalid JSON input: {e}", style="error"
                )
                ctx.exit(1)
        else:
            input_path = Path(input_file)
            if not input_path.exists():
                console.console.print(
                    f"[red]Error:[/red] Input file not found: {input_path}",
                    style="error",
                )
                ctx.exit(1)
            try:
                layout_dict = json.loads(input_path.read_text())
                source_name = input_path.name
            except json.JSONDecodeError as e:
                console.console.print(
                    f"[red]Error:[/red] Invalid JSON in {input_path}: {e}",
                    style="error",
                )
                ctx.exit(1)

        # Convert dict to LayoutData
        layout_data = LayoutData.model_validate(layout_dict)

        # Analyze layers
        layer_info = []
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

            # Count binding types
            total_bindings = len(bindings)
            empty_bindings = bindings.count("&trans") + bindings.count("&none")
            unique_bindings = len(set(bindings))

            # Find dominant behavior
            behaviors = {}
            for binding in bindings:
                if isinstance(binding, str) and binding.startswith("&"):
                    behavior = binding.split(" ")[0] if " " in binding else binding
                    behaviors[behavior] = behaviors.get(behavior, 0) + 1

            dominant_behavior = (
                max(behaviors.items(), key=lambda x: x[1])[0] if behaviors else "none"
            )

            layer_info.append(
                {
                    "index": i,
                    "name": layer_name,
                    "total_bindings": total_bindings,
                    "unique_bindings": unique_bindings,
                    "empty_bindings": empty_bindings,
                    "dominant_behavior": dominant_behavior,
                    "behavior_count": len(behaviors),
                }
            )

        if format == "json":
            # JSON output
            output = {
                "source": source_name,
                "layer_count": len(layer_info),
                "layers": layer_info,
            }
            console.console.print(json.dumps(output, indent=2), highlight=False)

        elif format == "summary":
            # Compact summary format
            console.console.print(
                Panel(
                    f"[bold blue]{source_name}[/bold blue] - [green]{len(layer_info)}[/green] layers\n"
                    + "\n".join(
                        [
                            f"[cyan]{info['name']}[/cyan]: {info['total_bindings']} bindings"
                            + (
                                f" ({info['empty_bindings']} empty)"
                                if show_empty and info["empty_bindings"] > 0
                                else ""
                            )
                            for info in layer_info
                        ]
                    ),
                    title="[bold blue]Layer Summary[/bold blue]",
                    expand=False,
                )
            )

        else:
            # Rich table format (default)
            console.console.print(
                Panel(
                    f"[bold blue]Layers in {source_name}[/bold blue]\n"
                    f"Total: [green]{len(layer_info)}[/green] layers",
                    expand=False,
                )
            )

            table = Table(show_header=True, header_style="bold blue")
            table.add_column("#", style="cyan", justify="center", width=4)
            table.add_column("Name", style="white")
            if show_bindings:
                table.add_column("Bindings", style="green", justify="right")
                table.add_column("Unique", style="yellow", justify="right")
                if show_empty:
                    table.add_column("Empty", style="red", justify="right")
            table.add_column("Top Behavior", style="magenta")

            for info in layer_info:
                row = [
                    str(info["index"]),
                    info["name"][:20],  # Truncate long names
                ]

                if show_bindings:
                    row.extend(
                        [
                            str(info["total_bindings"]),
                            str(info["unique_bindings"]),
                        ]
                    )
                    if show_empty:
                        row.append(str(info["empty_bindings"]))

                row.append(info["dominant_behavior"])
                table.add_row(*row)

            console.console.print(table)

        logger.info(
            "layers_listed",
            source=source_name,
            layer_count=len(layer_info),
            format=format,
        )

    except Exception as e:
        logger.error("list_layers_failed", error=str(e), exc_info=True)
        console.console.print(f"[red]Error:[/red] {e}", style="error")
        ctx.exit(1)


@layers_app.command(name="add")
@with_metrics("zmk_layout.layers.add")
@with_profile()
@handle_errors
def add_layer(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Name for the new layer")],
    input_file: Annotated[
        str,
        typer.Option(
            "-i",
            "--input",
            help="JSON layout file path or '-' for stdin",
        ),
    ] = "-",
    output_file: Annotated[
        str | None,
        typer.Option(
            "-o",
            "--output",
            help="Output file path (default: overwrite input)",
        ),
    ] = None,
    position: Annotated[
        int | None,
        typer.Option(
            "-p",
            "--position",
            help="Position to insert layer (default: end)",
        ),
    ] = None,
    template: Annotated[
        str,
        typer.Option(
            "-t",
            "--template",
            help="Template for new layer: empty, transparent, copy_base",
        ),
    ] = "transparent",
    copy_from: Annotated[
        int | None,
        typer.Option(
            "--copy-from",
            help="Layer index to copy from",
        ),
    ] = None,
) -> None:
    """Add a new layer to the layout.

    **Templates:**
    - empty: All bindings set to &none
    - transparent: All bindings set to &trans (default)
    - copy_base: Copy from layer 0

    **Examples:**

    \b
    # Add transparent layer at end
    glovebox zmk-layout layers add "gaming" -i layout.json

    \b
    # Add empty layer at specific position
    glovebox zmk-layout layers add "numpad" -i layout.json -p 2 -t empty

    \b
    # Copy layer from existing
    glovebox zmk-layout layers add "variant" -i layout.json --copy-from 1
    """
    try:
        # This is a placeholder implementation
        console.console.print(
            "[yellow]Note:[/yellow] The 'add' layer command is not yet fully implemented."
        )
        console.console.print("This would add a new layer to the layout.")
        console.console.print(f"Layer name: [cyan]{name}[/cyan]")
        console.console.print(f"Template: [cyan]{template}[/cyan]")

        if position is not None:
            console.console.print(f"Position: [cyan]{position}[/cyan]")
        if copy_from is not None:
            console.console.print(f"Copy from layer: [cyan]{copy_from}[/cyan]")

        console.console.print("\n[blue]Implementation would:[/blue]")
        console.console.print("  1. Load and parse the layout")
        console.console.print("  2. Create new layer with specified template")
        console.console.print("  3. Insert at specified position")
        console.console.print("  4. Update layer references if needed")
        console.console.print("  5. Save the modified layout")

    except Exception as e:
        logger.error("add_layer_failed", error=str(e), exc_info=True)
        console.console.print(f"[red]Error:[/red] {e}", style="error")
        ctx.exit(1)


@layers_app.command(name="remove")
@with_metrics("zmk_layout.layers.remove")
@with_profile()
@handle_errors
def remove_layer(
    ctx: typer.Context,
    layer_index: Annotated[int, typer.Argument(help="Layer index to remove")],
    input_file: Annotated[
        str,
        typer.Option(
            "-i",
            "--input",
            help="JSON layout file path or '-' for stdin",
        ),
    ] = "-",
    output_file: Annotated[
        str | None,
        typer.Option(
            "-o",
            "--output",
            help="Output file path (default: overwrite input)",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Force removal even if layer is referenced",
        ),
    ] = False,
    update_references: Annotated[
        bool,
        typer.Option(
            "--update-refs/--no-update-refs",
            help="Update layer references after removal",
        ),
    ] = True,
) -> None:
    """Remove a layer from the layout.

    **Examples:**

    \b
    # Remove layer by index
    glovebox zmk-layout layers remove 2 -i layout.json

    \b
    # Force remove with reference updates
    glovebox zmk-layout layers remove 1 -i layout.json --force --update-refs
    """
    try:
        # This is a placeholder implementation
        console.console.print(
            "[yellow]Note:[/yellow] The 'remove' layer command is not yet fully implemented."
        )
        console.console.print("This would remove the specified layer from the layout.")
        console.console.print(f"Layer index: [cyan]{layer_index}[/cyan]")
        console.console.print(f"Force: [cyan]{force}[/cyan]")
        console.console.print(f"Update references: [cyan]{update_references}[/cyan]")

    except Exception as e:
        logger.error("remove_layer_failed", error=str(e), exc_info=True)
        console.console.print(f"[red]Error:[/red] {e}", style="error")
        ctx.exit(1)


@layers_app.command(name="move")
@with_metrics("zmk_layout.layers.move")
@with_profile()
@handle_errors
def move_layer(
    ctx: typer.Context,
    from_index: Annotated[int, typer.Argument(help="Source layer index")],
    to_index: Annotated[int, typer.Argument(help="Target layer index")],
    input_file: Annotated[
        str,
        typer.Option(
            "-i",
            "--input",
            help="JSON layout file path or '-' for stdin",
        ),
    ] = "-",
    output_file: Annotated[
        str | None,
        typer.Option(
            "-o",
            "--output",
            help="Output file path (default: overwrite input)",
        ),
    ] = None,
    update_references: Annotated[
        bool,
        typer.Option(
            "--update-refs/--no-update-refs",
            help="Update layer references after move",
        ),
    ] = True,
) -> None:
    """Move/reorder a layer in the layout.

    **Examples:**

    \b
    # Move layer 2 to position 1
    glovebox zmk-layout layers move 2 1 -i layout.json

    \b
    # Move without updating references
    glovebox zmk-layout layers move 3 0 -i layout.json --no-update-refs
    """
    try:
        # This is a placeholder implementation
        console.console.print(
            "[yellow]Note:[/yellow] The 'move' layer command is not yet fully implemented."
        )
        console.console.print("This would move/reorder the layer in the layout.")
        console.console.print(f"From index: [cyan]{from_index}[/cyan]")
        console.console.print(f"To index: [cyan]{to_index}[/cyan]")
        console.console.print(f"Update references: [cyan]{update_references}[/cyan]")

    except Exception as e:
        logger.error("move_layer_failed", error=str(e), exc_info=True)
        console.console.print(f"[red]Error:[/red] {e}", style="error")
        ctx.exit(1)
