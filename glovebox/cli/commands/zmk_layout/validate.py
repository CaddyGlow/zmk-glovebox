"""ZMK Layout validate command - Enhanced validation using zmk-layout library."""

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
from glovebox.layout.zmk_layout_service import create_zmk_layout_service


logger = get_struct_logger(__name__)
console = get_themed_console()


@with_metrics("zmk_layout.validate")
@with_profile()
@handle_errors
def validate_layout(
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
            help="Keyboard profile to use for validation",
        ),
    ] = None,
    strict: Annotated[
        bool,
        typer.Option(
            "--strict",
            help="Enable strict validation mode",
        ),
    ] = False,
    show_details: Annotated[
        bool,
        typer.Option(
            "--details",
            help="Show detailed validation information",
        ),
    ] = False,
    format: Annotated[
        str,
        typer.Option(
            "-f",
            "--format",
            help="Output format for validation results",
        ),
    ] = "table",
    quiet: Annotated[
        bool,
        typer.Option(
            "-q",
            "--quiet",
            help="Suppress success messages (only show errors)",
        ),
    ] = False,
) -> None:
    """Validate JSON layout using zmk-layout library validation rules.

    This command provides comprehensive layout validation through the
    zmk-layout library, checking syntax, structure, behaviors, and
    keyboard-specific constraints.

    **Examples:**

    \b
    # Validate layout file
    glovebox zmk-layout validate my_layout.json

    \b
    # Validate with strict mode and details
    glovebox zmk-layout validate layout.json --strict --details

    \b
    # Validate from stdin with specific profile
    cat layout.json | glovebox zmk-layout validate - -p glove80

    \b
    # JSON output format for automation
    glovebox zmk-layout validate layout.json -f json
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
                source = "stdin"
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
                source = str(input_path)
            except json.JSONDecodeError as e:
                console.console.print(
                    f"[red]Error:[/red] Invalid JSON in {input_path}: {e}",
                    style="error",
                )
                ctx.exit(1)

        # Get keyboard profile for zmk-layout service
        app_context = ctx.obj
        keyboard_profile = app_context.keyboard_profile

        # Create zmk-layout service
        zmk_service = create_zmk_layout_service(
            keyboard_id=keyboard_profile.keyboard_name if keyboard_profile else None
        )

        # Convert dict to LayoutData
        layout_data = LayoutData.model_validate(layout_dict)

        # Validate using zmk-layout service
        validation_errors = zmk_service.validate_layout(layout_data)

        # Prepare validation results
        is_valid = len(validation_errors) == 0

        if format == "json":
            # JSON output for automation
            result = {
                "valid": is_valid,
                "source": source,
                "keyboard": keyboard_profile.keyboard_name
                if keyboard_profile
                else None,
                "errors": validation_errors,
                "error_count": len(validation_errors),
                "strict_mode": strict,
            }
            console.console.print(json.dumps(result, indent=2), highlight=False)

        elif format == "table" and validation_errors:
            # Table format for errors
            table = Table(
                title="Validation Errors", show_header=True, header_style="bold red"
            )
            table.add_column("Error", style="red", no_wrap=False)
            table.add_column("Severity", style="yellow", justify="center")

            for error in validation_errors:
                # Try to determine severity (this could be enhanced with more sophisticated parsing)
                severity = (
                    "ERROR"
                    if strict
                    or "invalid" in error.lower()
                    or "missing" in error.lower()
                    else "WARNING"
                )
                table.add_row(error, severity)

            console.console.print(table)

        else:
            # Simple text format
            if show_details or not quiet:
                info_panel = Panel(
                    f"[blue]Source:[/blue] {source}\n"
                    f"[blue]Keyboard:[/blue] {keyboard_profile.keyboard_name if keyboard_profile else 'auto-detect'}\n"
                    f"[blue]Profile:[/blue] {profile or 'default'}\n"
                    f"[blue]Strict Mode:[/blue] {'enabled' if strict else 'disabled'}",
                    title="[bold blue]Validation Settings[/bold blue]",
                    expand=False,
                )
                console.console.print(info_panel)

            if validation_errors:
                console.console.print(
                    f"\n[red]✗ Validation failed with {len(validation_errors)} error(s):[/red]"
                )
                for i, error in enumerate(validation_errors, 1):
                    console.console.print(f"  {i:2d}. {error}", style="error")
            else:
                if not quiet:
                    console.console.print(
                        "[green]✓ Layout validation passed successfully![/green]"
                    )

        # Additional details if requested
        if show_details and format != "json":
            try:
                info = zmk_service.get_compiler_info()
                console.console.print("\n[blue]Validation Engine Details:[/blue]")
                console.console.print(f"  Library: {info.get('library', 'unknown')}")
                console.console.print(f"  Version: {info.get('version', 'unknown')}")

                capabilities = info.get("capabilities", [])
                if capabilities:
                    console.console.print(f"  Capabilities: {', '.join(capabilities)}")

            except Exception as e:
                logger.debug("failed_to_get_validation_details", error=str(e))

        # Log validation results
        logger.info(
            "zmk_layout_validation_completed",
            source=source,
            valid=is_valid,
            errors_count=len(validation_errors),
            strict_mode=strict,
        )

        # Exit with error code if validation failed
        if validation_errors:
            ctx.exit(1)

    except Exception as e:
        logger.error("zmk_layout_validation_failed", error=str(e), exc_info=True)
        console.console.print(f"[red]Error:[/red] {e}", style="error")
        ctx.exit(1)
