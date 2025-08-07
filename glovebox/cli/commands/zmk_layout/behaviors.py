"""ZMK Layout behaviors command - Manage behaviors (add, list, remove, validate)."""

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.panel import Panel
from rich.table import Table

from glovebox.cli.decorators import handle_errors, with_metrics, with_profile

# Removed unused import: create_output_handler
from glovebox.cli.helpers.stdin_utils import is_stdin_input
from glovebox.cli.helpers.theme import get_themed_console
from glovebox.core.structlog_logger import get_struct_logger
from glovebox.layout.models import LayoutData
from glovebox.layout.zmk_layout_service import create_zmk_layout_service


logger = get_struct_logger(__name__)
console = get_themed_console()

# Create behaviors sub-app
behaviors_app = typer.Typer(
    name="behaviors",
    help="""Manage layout behaviors.

Commands for adding, removing, listing, and validating behaviors
in ZMK layouts using the zmk-layout library.
""",
    no_args_is_help=True,
)


@behaviors_app.command(name="list")
@with_metrics("zmk_layout.behaviors.list")
@with_profile()
@handle_errors
def list_behaviors(
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
            help="Output format: table, json, list",
        ),
    ] = "table",
    sort_by: Annotated[
        str,
        typer.Option(
            "--sort",
            help="Sort behaviors by: name, count, type",
        ),
    ] = "count",
    show_usage: Annotated[
        bool,
        typer.Option(
            "--usage",
            help="Show usage counts for each behavior",
        ),
    ] = True,
) -> None:
    """List all behaviors used in the layout.

    **Examples:**

    \b
    # List behaviors with usage counts
    glovebox zmk-layout behaviors list my_layout.json

    \b
    # JSON output sorted by name
    glovebox zmk-layout behaviors list layout.json -f json --sort name
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
                raise typer.Exit(1) from None
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
                raise typer.Exit(1) from None
            try:
                layout_dict = json.loads(input_path.read_text())
                source_name = input_path.name
            except json.JSONDecodeError as e:
                console.console.print(
                    f"[red]Error:[/red] Invalid JSON in {input_path}: {e}",
                    style="error",
                )
                raise typer.Exit(1) from None

        # Convert dict to LayoutData
        layout_data = LayoutData.model_validate(layout_dict)

        # Extract behaviors from layout
        behaviors: dict[str, int] = {}
        behavior_types: dict[str, str] = {}

        for layer in layout_data.layers:
            layer_bindings = getattr(layer, "bindings", layer)
            if isinstance(layer_bindings, dict):
                bindings = layer_bindings.get("bindings", [])
            elif isinstance(layer_bindings, list):
                bindings = layer_bindings
            else:
                continue

            for binding in bindings:
                if isinstance(binding, str) and binding.startswith("&"):
                    behavior_name = binding.split(" ")[0] if " " in binding else binding
                    behaviors[behavior_name] = behaviors.get(behavior_name, 0) + 1

                    # Categorize behavior type
                    if behavior_name in ("&kp", "&key_press"):
                        behavior_types[behavior_name] = "key"
                    elif behavior_name in ("&mt", "&mod_tap"):
                        behavior_types[behavior_name] = "modifier"
                    elif behavior_name in ("&lt", "&layer_tap"):
                        behavior_types[behavior_name] = "layer"
                    elif behavior_name.startswith("&macro"):
                        behavior_types[behavior_name] = "macro"
                    elif behavior_name in ("&trans", "&transparent"):
                        behavior_types[behavior_name] = "transparent"
                    elif behavior_name in ("&none", "&no_op"):
                        behavior_types[behavior_name] = "none"
                    else:
                        behavior_types[behavior_name] = "custom"

        # Sort behaviors
        if sort_by == "name":
            sorted_behaviors = sorted(behaviors.items())
        elif sort_by == "type":
            sorted_behaviors = sorted(
                behaviors.items(),
                key=lambda x: (behavior_types.get(x[0], "unknown"), x[0]),
            )
        else:  # count (default)
            sorted_behaviors = sorted(
                behaviors.items(), key=lambda x: x[1], reverse=True
            )

        if format == "json":
            # JSON output
            output = {
                "source": source_name,
                "behavior_count": len(behaviors),
                "behaviors": [
                    {
                        "name": name,
                        "count": count if show_usage else None,
                        "type": behavior_types.get(name, "unknown"),
                    }
                    for name, count in sorted_behaviors
                ],
            }
            console.console.print(json.dumps(output, indent=2), highlight=False)

        elif format == "list":
            # Simple list format
            for name, count in sorted_behaviors:
                if show_usage:
                    console.console.print(f"{name} ({count})")
                else:
                    console.console.print(name)

        else:
            # Rich table format (default)
            console.console.print(
                Panel(
                    f"[bold blue]Behaviors in {source_name}[/bold blue]\n"
                    f"Total: [green]{len(behaviors)}[/green] unique behaviors",
                    expand=False,
                )
            )

            table = Table(show_header=True, header_style="bold blue")
            table.add_column("Behavior", style="cyan")
            table.add_column("Type", style="yellow", justify="center")
            if show_usage:
                table.add_column("Count", style="green", justify="right")

            for name, count in sorted_behaviors:
                behavior_type = behavior_types.get(name, "unknown")
                if show_usage:
                    table.add_row(name, behavior_type, str(count))
                else:
                    table.add_row(name, behavior_type)

            console.console.print(table)

        logger.info(
            "behaviors_listed",
            source=source_name,
            behavior_count=len(behaviors),
            format=format,
            sort_by=sort_by,
        )

    except Exception as e:
        logger.error("list_behaviors_failed", error=str(e), exc_info=True)
        console.console.print(f"[red]Error:[/red] {e}", style="error")
        raise typer.Exit(1) from None


@behaviors_app.command(name="validate")
@with_metrics("zmk_layout.behaviors.validate")
@with_profile()
@handle_errors
def validate_behaviors(
    ctx: typer.Context,
    input_file: Annotated[
        str,
        typer.Argument(
            help="JSON layout file path or '-' for stdin", metavar="INPUT_FILE"
        ),
    ] = "-",
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Enable strict behavior validation",
        ),
    ] = False,
    show_warnings: Annotated[
        bool,
        typer.Option(
            "--warnings/--no-warnings",
            help="Show behavior validation warnings",
        ),
    ] = True,
) -> None:
    """Validate behaviors in the layout.

    **Examples:**

    \b
    # Validate all behaviors
    glovebox zmk-layout behaviors validate layout.json

    \b
    # Strict validation with warnings
    glovebox zmk-layout behaviors validate layout.json --strict --warnings
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
                raise typer.Exit(1) from None
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
                raise typer.Exit(1) from None
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

        # Create zmk-layout service
        zmk_service = create_zmk_layout_service(
            keyboard_id=keyboard_profile.keyboard_name if keyboard_profile else None
        )

        # Convert dict to LayoutData and validate
        layout_data = LayoutData.model_validate(layout_dict)
        validation_errors = zmk_service.validate_layout(layout_data)

        # Filter behavior-specific errors
        behavior_errors = []
        behavior_warnings = []

        for error in validation_errors:
            error_lower = error.lower()
            if any(
                keyword in error_lower
                for keyword in ["behavior", "binding", "unknown", "invalid"]
            ):
                if strict or "invalid" in error_lower or "unknown" in error_lower:
                    behavior_errors.append(error)
                else:
                    behavior_warnings.append(error)

        # Report results
        if behavior_errors:
            console.console.print(
                f"[red]✗ Behavior validation failed with {len(behavior_errors)} error(s):[/red]"
            )
            for i, error in enumerate(behavior_errors, 1):
                console.console.print(f"  {i:2d}. {error}", style="error")

        if show_warnings and behavior_warnings:
            console.console.print(
                f"\n[yellow]⚠ Behavior warnings ({len(behavior_warnings)}):[/yellow]"
            )
            for i, warning in enumerate(behavior_warnings, 1):
                console.console.print(f"  {i:2d}. {warning}", style="warning")

        if not behavior_errors and (not behavior_warnings or not show_warnings):
            console.console.print("[green]✓ All behaviors are valid![/green]")

        logger.info(
            "behaviors_validated",
            source=source_name,
            errors=len(behavior_errors),
            warnings=len(behavior_warnings),
            strict_mode=strict,
        )

        # Exit with error if validation failed
        if behavior_errors:
            raise typer.Exit(1) from None

    except Exception as e:
        logger.error("validate_behaviors_failed", error=str(e), exc_info=True)
        console.console.print(f"[red]Error:[/red] {e}", style="error")
        raise typer.Exit(1) from None


@behaviors_app.command(name="add")
@with_metrics("zmk_layout.behaviors.add")
@with_profile()
@handle_errors
def add_behavior(
    ctx: typer.Context,
    behavior: Annotated[
        str, typer.Argument(help="Behavior to add (e.g., '&kp SPACE')")
    ],
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
    layer: Annotated[
        int | None,
        typer.Option(
            "-l",
            "--layer",
            help="Layer index to add behavior to",
        ),
    ] = None,
    position: Annotated[
        int | None,
        typer.Option(
            "-p",
            "--position",
            help="Position in layer to add behavior",
        ),
    ] = None,
    replace: Annotated[
        str | None,
        typer.Option(
            "--replace",
            help="Replace existing behavior with new one",
        ),
    ] = None,
) -> None:
    """Add a behavior to the layout.

    **Examples:**

    \b
    # Add behavior to specific position
    glovebox zmk-layout behaviors add "&kp SPACE" -i layout.json -l 0 -p 10

    \b
    # Replace existing behavior
    glovebox zmk-layout behaviors add "&kp TAB" -i layout.json --replace "&kp SPACE"
    """
    try:
        # This is a placeholder implementation
        # A full implementation would:
        # 1. Parse the input layout
        # 2. Modify the layout data structure
        # 3. Write back to file or stdout
        # 4. Validate the result

        console.console.print(
            "[yellow]Note:[/yellow] The 'add' behavior command is not yet fully implemented."
        )
        console.console.print("This would add the specified behavior to the layout.")
        console.console.print(f"Requested behavior: [cyan]{behavior}[/cyan]")

        if layer is not None:
            console.console.print(f"Target layer: [cyan]{layer}[/cyan]")
        if position is not None:
            console.console.print(f"Target position: [cyan]{position}[/cyan]")
        if replace:
            console.console.print(f"Replace: [cyan]{replace}[/cyan]")

        console.console.print("\n[blue]Implementation would:[/blue]")
        console.console.print("  1. Load and parse the layout")
        console.console.print("  2. Validate the new behavior")
        console.console.print("  3. Insert/replace at specified location")
        console.console.print("  4. Save the modified layout")
        console.console.print("  5. Validate the result")

    except Exception as e:
        logger.error("add_behavior_failed", error=str(e), exc_info=True)
        console.console.print(f"[red]Error:[/red] {e}", style="error")
        raise typer.Exit(1) from None


@behaviors_app.command(name="remove")
@with_metrics("zmk_layout.behaviors.remove")
@with_profile()
@handle_errors
def remove_behavior(
    ctx: typer.Context,
    behavior: Annotated[
        str, typer.Argument(help="Behavior to remove (e.g., '&kp SPACE')")
    ],
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
    all_instances: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Remove all instances of the behavior",
        ),
    ] = False,
    replace_with: Annotated[
        str,
        typer.Option(
            "--replace-with",
            help="Replace with this behavior instead of removing",
        ),
    ] = "&trans",
) -> None:
    """Remove a behavior from the layout.

    **Examples:**

    \b
    # Remove all instances of a behavior
    glovebox zmk-layout behaviors remove "&kp SPACE" -i layout.json --all

    \b
    # Replace behavior with another
    glovebox zmk-layout behaviors remove "&kp TAB" -i layout.json --replace-with "&kp SPACE"
    """
    try:
        # This is a placeholder implementation
        console.console.print(
            "[yellow]Note:[/yellow] The 'remove' behavior command is not yet fully implemented."
        )
        console.console.print(
            "This would remove the specified behavior from the layout."
        )
        console.console.print(f"Target behavior: [cyan]{behavior}[/cyan]")
        console.console.print(f"Replace with: [cyan]{replace_with}[/cyan]")
        console.console.print(f"All instances: [cyan]{all_instances}[/cyan]")

    except Exception as e:
        logger.error("remove_behavior_failed", error=str(e), exc_info=True)
        console.console.print(f"[red]Error:[/red] {e}", style="error")
        raise typer.Exit(1) from None
