"""ZMK Layout parse command - Parse ZMK keymap files using zmk-layout library."""

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel

from glovebox.cli.decorators import handle_errors, with_metrics, with_profile
from glovebox.cli.helpers.stdin_utils import is_stdin_input
from glovebox.cli.helpers.theme import get_themed_console
from glovebox.core.structlog_logger import get_struct_logger
from glovebox.layout.zmk_layout_service import create_zmk_layout_service


logger = get_struct_logger(__name__)
console = get_themed_console()


@with_metrics("zmk_layout.parse")
@with_profile()
@handle_errors
def parse_keymap(
    ctx: typer.Context,
    input_file: Annotated[
        str,
        typer.Argument(
            help="ZMK keymap file path or '-' for stdin", metavar="INPUT_FILE"
        ),
    ] = "-",
    output_file: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output",
            help="Output JSON file path (default: stdout)",
        ),
    ] = None,
    profile: Annotated[
        str | None,
        typer.Option(
            "-p",
            "--profile",
            help="Keyboard profile to use for parsing",
        ),
    ] = None,
    format: Annotated[
        str,
        typer.Option(
            "-f",
            "--format",
            help="Output format (json|pretty)",
        ),
    ] = "pretty",
    verbose: Annotated[
        bool,
        typer.Option(
            "-v",
            "--verbose",
            help="Enable verbose output",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Force overwrite existing output file",
        ),
    ] = False,
) -> None:
    """Parse ZMK keymap file to JSON format using zmk-layout library.

    This command uses the zmk-layout library's Layout.from_string() method
    to parse ZMK keymap files, providing more accurate parsing than the
    internal glovebox parser.

    **Examples:**

    \\b
    # Parse keymap file to JSON
    glovebox zmk-layout parse my_keymap.keymap

    \\b
    # Parse with specific keyboard profile
    glovebox zmk-layout parse keymap.keymap -p glove80

    \\b
    # Parse from stdin and save to file
    cat keymap.keymap | glovebox zmk-layout parse - -o layout.json

    \\b
    # Verbose parsing with compact JSON output
    glovebox zmk-layout parse keymap.keymap -v -f json
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
            source = "stdin"
        else:
            input_path = Path(input_file)
            if not input_path.exists():
                console.console.print(
                    f"[red]Error:[/red] Input file not found: {input_path}",
                    style="error",
                )
                ctx.exit(1)
            content = input_path.read_text()
            source = str(input_path)

        # Get keyboard profile for zmk-layout service
        app_context = ctx.obj
        keyboard_profile = app_context.keyboard_profile

        # Create zmk-layout service
        zmk_service = create_zmk_layout_service(
            keyboard_id=keyboard_profile.keyboard_name if keyboard_profile else None
        )

        if verbose:
            console.console.print(
                Panel(
                    f"[blue]Using zmk-layout library for parsing[/blue]\n"
                    f"Source: {source}\n"
                    f"Keyboard: {keyboard_profile.keyboard_name if keyboard_profile else 'auto-detect'}\n"
                    f"Profile: {profile or 'default'}\n"
                    f"Format: {format}",
                    title="[bold blue]Parse Settings[/bold blue]",
                    expand=False,
                )
            )

        # Parse keymap using zmk-layout service
        result = zmk_service.parse_keymap(content, profile=profile)

        if not result.success:
            console.console.print("[red]Parsing failed:[/red]", style="error")
            for error in result.errors:
                console.console.print(f"  • {error}", style="error")
            ctx.exit(1)

        # Format output
        if format == "json":
            output_content = json.dumps(
                result.json_content, indent=None, separators=(",", ":")
            )
        else:  # pretty format (default)
            output_content = json.dumps(result.json_content, indent=2)

        # Handle output
        if output_file:
            if output_file.exists() and not force:
                console.console.print(
                    f"[red]Error:[/red] Output file exists: {output_file}"
                )
                console.console.print("Use --force to overwrite")
                ctx.exit(1)

            output_file.write_text(output_content)
            console.console.print(
                f"[green]✓[/green] Parsed layout written to {output_file}"
            )
        else:
            # Output to stdout
            console.console.print(output_content, highlight=False)

        # Show warnings if any
        if result.warnings:
            console.console.print("\n[yellow]Warnings:[/yellow]")
            for warning in result.warnings:
                console.console.print(f"  ⚠ {warning}", style="warning")

        # Show success messages if verbose
        if verbose and result.messages:
            console.console.print("\n[green]Messages:[/green]")
            for message in result.messages:
                console.console.print(f"  • {message}", style="info")

        logger.info(
            "zmk_layout_parsing_completed",
            success=result.success,
            source=source,
            errors_count=len(result.errors),
            warnings_count=len(result.warnings),
            output_file=str(output_file) if output_file else None,
        )

    except Exception as e:
        logger.error("zmk_layout_parsing_failed", error=str(e), exc_info=True)
        console.console.print(f"[red]Error:[/red] {e}", style="error")
        ctx.exit(1)
