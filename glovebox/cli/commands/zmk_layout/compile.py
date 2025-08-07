"""ZMK Layout compile command - Enhanced compilation using zmk-layout library."""

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.panel import Panel

from glovebox.cli.decorators import handle_errors, with_metrics, with_profile

# Removed unused import: create_output_handler
from glovebox.cli.helpers.stdin_utils import is_stdin_input
from glovebox.cli.helpers.theme import get_themed_console
from glovebox.core.structlog_logger import get_struct_logger
from glovebox.layout.models import LayoutData
from glovebox.layout.zmk_layout_service import create_zmk_layout_service


logger = get_struct_logger(__name__)
console = get_themed_console()


@with_metrics("zmk_layout.compile")
@with_profile()
@handle_errors
def compile_layout(
    ctx: typer.Context,
    input_file: Annotated[
        str,
        typer.Argument(
            help="JSON layout file path or '-' for stdin", metavar="INPUT_FILE"
        ),
    ] = "-",
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output",
            help="Output directory for generated files",
            file_okay=False,
            dir_okay=True,
        ),
    ] = None,
    profile: Annotated[
        str | None,
        typer.Option(
            "-p",
            "--profile",
            help="Keyboard profile to use for compilation",
        ),
    ] = None,
    format: Annotated[
        str,
        typer.Option(
            "-f",
            "--format",
            help="Output format",
        ),
    ] = "keymap",
    show_warnings: Annotated[
        bool,
        typer.Option(
            "--warnings/--no-warnings",
            help="Show compilation warnings",
        ),
    ] = True,
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
            help="Force overwrite existing files",
        ),
    ] = False,
) -> None:
    """Compile JSON layout to ZMK files using zmk-layout library.

    This command provides enhanced compilation capabilities through the
    zmk-layout library integration, offering more features than the
    standard glovebox compiler.

    **Examples:**

    \b
    # Compile layout to keymap output
    glovebox zmk-layout compile my_layout.json

    \b
    # Compile with output directory
    glovebox zmk-layout compile layout.json -o ./output/

    \b
    # Compile from stdin with specific profile
    cat layout.json | glovebox zmk-layout compile - -p glove80

    \b
    # Verbose compilation with warnings
    glovebox zmk-layout compile layout.json -v --warnings
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

        if verbose:
            console.console.print(
                Panel(
                    f"[blue]Using zmk-layout library for compilation[/blue]\n"
                    f"Keyboard: {keyboard_profile.keyboard_name if keyboard_profile else 'auto-detect'}\n"
                    f"Profile: {profile or 'default'}\n"
                    f"Format: {format}",
                    title="[bold blue]Compilation Settings[/bold blue]",
                    expand=False,
                )
            )

        # Convert dict to LayoutData
        layout_data = LayoutData.model_validate(layout_dict)

        # Compile using zmk-layout service
        result = zmk_service.compile_layout(layout_data, output_dir)

        if not result.success:
            console.console.print("[red]Compilation failed:[/red]", style="error")
            for error in result.errors:
                console.console.print(f"  • {error}", style="error")
            ctx.exit(1)

        # Handle output
        if output_dir:
            # Direct file operations instead of output_handler

            # Write keymap file
            if result.keymap_content:
                keymap_file = output_dir / f"{keyboard_profile.keyboard_name}.keymap"
                if keymap_file.exists() and not force:
                    console.console.print(
                        f"[red]Error:[/red] File exists: {keymap_file}"
                    )
                    console.console.print("Use --force to overwrite")
                    ctx.exit(1)
                keymap_file.write_text(result.keymap_content)
                console.console.print(
                    f"[green]✓[/green] Keymap written to {keymap_file}"
                )

            # Write config file if present
            if result.config_content:
                config_file = output_dir / f"{keyboard_profile.keyboard_name}.conf"
                if config_file.exists() and not force:
                    console.console.print(
                        f"[red]Error:[/red] File exists: {config_file}"
                    )
                    console.console.print("Use --force to overwrite")
                    ctx.exit(1)
                config_file.write_text(result.config_content)
                console.console.print(
                    f"[green]✓[/green] Config written to {config_file}"
                )
        else:
            # Output to stdout
            if format == "keymap" and result.keymap_content:
                console.console.print(result.keymap_content, highlight=False)
            elif format == "config" and result.config_content:
                console.console.print(result.config_content, highlight=False)
            elif format == "json":
                console.console.print(
                    json.dumps(result.json_content, indent=2), highlight=False
                )
            else:
                console.console.print(result.keymap_content, highlight=False)

        # Show warnings if enabled
        if show_warnings and result.warnings:
            console.console.print("\n[yellow]Warnings:[/yellow]")
            for warning in result.warnings:
                console.console.print(f"  ⚠ {warning}", style="warning")

        # Show success messages
        if verbose and result.messages:
            console.console.print("\n[green]Messages:[/green]")
            for message in result.messages:
                console.console.print(f"  • {message}", style="info")

        logger.info(
            "zmk_layout_compilation_completed",
            success=result.success,
            errors_count=len(result.errors),
            warnings_count=len(result.warnings),
            output_dir=str(output_dir) if output_dir else None,
        )

    except Exception as e:
        logger.error("zmk_layout_compilation_failed", error=str(e), exc_info=True)
        console.console.print(f"[red]Error:[/red] {e}", style="error")
        ctx.exit(1)
