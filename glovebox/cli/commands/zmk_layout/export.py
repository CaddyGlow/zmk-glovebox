"""ZMK Layout export command - Export to multiple formats."""

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


@with_metrics("zmk_layout.export")
@with_profile()
@handle_errors
def export_layout(
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
            help="Export format: keymap, config, json, all",
        ),
    ] = "all",
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "-o",
            "--output",
            help="Output directory for exported files",
            file_okay=False,
            dir_okay=True,
        ),
    ] = None,
    profile: Annotated[
        str | None,
        typer.Option(
            "-p",
            "--profile",
            help="Keyboard profile to use for export",
        ),
    ] = None,
    prefix: Annotated[
        str | None,
        typer.Option(
            "--prefix",
            help="File prefix for exported files",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Force overwrite existing files",
        ),
    ] = False,
    pretty: Annotated[
        bool,
        typer.Option(
            "--pretty/--no-pretty",
            help="Pretty-print JSON output",
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
) -> None:
    """Export layout to multiple formats (keymap, config, JSON).

    This command exports layouts to various formats using the zmk-layout
    library, supporting keymap files, configuration files, and enhanced
    JSON formats.

    **Export Formats:**
    - keymap: ZMK .keymap file
    - config: ZMK .conf configuration file
    - json: Enhanced JSON with metadata
    - all: Export all formats

    **Examples:**

    \b
    # Export all formats to directory
    glovebox zmk-layout export layout.json -f all -o ./output/

    \b
    # Export only keymap to stdout
    glovebox zmk-layout export layout.json -f keymap

    \b
    # Export with custom prefix
    glovebox zmk-layout export layout.json -o ./build/ --prefix my_layout

    \b
    # Export from stdin with specific profile
    cat layout.json | glovebox zmk-layout export - -f all -p glove80
    """
    try:
        # Validate format
        valid_formats = {"keymap", "config", "json", "all"}
        if format not in valid_formats:
            console.console.print(
                f"[red]Error:[/red] Invalid format '{format}'. Must be one of: {', '.join(valid_formats)}",
                style="error",
            )
            ctx.exit(1)

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
                source_name = input_path.stem
            except json.JSONDecodeError as e:
                console.console.print(
                    f"[red]Error:[/red] Invalid JSON in {input_path}: {e}",
                    style="error",
                )
                ctx.exit(1)

        # Get keyboard profile for zmk-layout service
        app_context = ctx.obj
        keyboard_profile = app_context.keyboard_profile

        # Determine file prefix
        file_prefix = (
            prefix or keyboard_profile.keyboard_name
            if keyboard_profile
            else source_name
        )

        # Create zmk-layout service
        zmk_service = create_zmk_layout_service(
            keyboard_id=keyboard_profile.keyboard_name if keyboard_profile else None
        )

        if verbose:
            console.console.print(
                Panel(
                    f"[blue]Exporting layout using zmk-layout library[/blue]\n"
                    f"Source: {source_name}\n"
                    f"Keyboard: {keyboard_profile.keyboard_name if keyboard_profile else 'auto-detect'}\n"
                    f"Format: {format}\n"
                    f"Prefix: {file_prefix}",
                    title="[bold blue]Export Settings[/bold blue]",
                    expand=False,
                )
            )

        # Convert dict to LayoutData
        layout_data = LayoutData.model_validate(layout_dict)

        # Compile using zmk-layout service to get all outputs
        result = zmk_service.compile_layout(layout_data, output_dir)

        if not result.success:
            console.console.print(
                "[red]Export failed during compilation:[/red]", style="error"
            )
            for error in result.errors:
                console.console.print(f"  • {error}", style="error")
            ctx.exit(1)

        # Prepare exports
        exports: dict[str, tuple[str, str]] = {}  # format -> (content, extension)

        if format in ("keymap", "all") and result.keymap_content:
            exports["keymap"] = (result.keymap_content, ".keymap")

        if format in ("config", "all") and result.config_content:
            exports["config"] = (result.config_content, ".conf")

        if format in ("json", "all"):
            json_content = json.dumps(
                result.json_content, indent=2 if pretty else None, sort_keys=True
            )
            exports["json"] = (json_content, ".json")

        if not exports:
            console.console.print(
                "[yellow]Warning:[/yellow] No content available for requested format(s)",
                style="warning",
            )
            return

        # Handle output
        if output_dir:
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)
            # Direct file operations instead of output_handler

            # Export summary table
            if verbose:
                table = Table(
                    title="Export Summary", show_header=True, header_style="bold green"
                )
                table.add_column("Format", style="cyan")
                table.add_column("File", style="blue")
                table.add_column("Size", style="green", justify="right")
                table.add_column("Status", justify="center")

            exported_files = []
            for export_format, (content, extension) in exports.items():
                filename = f"{file_prefix}{extension}"
                filepath = output_dir / filename

                try:
                    output_handler.write_file(filepath, content)
                    exported_files.append(filepath)

                    if verbose:
                        table.add_row(
                            export_format,
                            filename,
                            f"{len(content):,} chars",
                            "[green]✓[/green]",
                        )
                    else:
                        console.console.print(
                            f"[green]✓[/green] {export_format.capitalize()} exported to {filepath}"
                        )

                except Exception as e:
                    if verbose:
                        table.add_row(
                            export_format,
                            filename,
                            f"{len(content):,} chars",
                            "[red]✗[/red]",
                        )
                    console.console.print(
                        f"[red]✗[/red] Failed to export {export_format}: {e}",
                        style="error",
                    )

            if verbose and exports:
                console.console.print(table)

            console.console.print(
                f"\n[green]Exported {len(exported_files)} file(s) to {output_dir}[/green]"
            )

        else:
            # Output to stdout - only one format allowed
            if len(exports) > 1:
                console.console.print(
                    "[red]Error:[/red] Multiple formats cannot be output to stdout. Use -o option or specify single format.",
                    style="error",
                )
                ctx.exit(1)

            export_format, (content, _) = next(iter(exports.items()))
            console.console.print(content, highlight=False)

        # Show warnings if any
        if result.warnings and verbose:
            console.console.print("\n[yellow]Warnings:[/yellow]")
            for warning in result.warnings:
                console.console.print(f"  ⚠ {warning}", style="warning")

        logger.info(
            "zmk_layout_export_completed",
            formats=list(exports.keys()),
            files_count=len(exports),
            output_dir=str(output_dir) if output_dir else None,
            prefix=file_prefix,
        )

    except Exception as e:
        logger.error("zmk_layout_export_failed", error=str(e), exc_info=True)
        console.console.print(f"[red]Error:[/red] {e}", style="error")
        ctx.exit(1)
