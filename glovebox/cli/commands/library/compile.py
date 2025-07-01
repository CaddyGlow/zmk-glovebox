"""Library compile command for compiling layouts directly from the library."""

from pathlib import Path
from typing import Annotated

import typer

from glovebox.cli.decorators import handle_errors, with_metrics
from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context
from glovebox.config import create_user_config
from glovebox.library import create_library_service


compile_app = typer.Typer(help="Compile layouts from the library")


def complete_library_entries(incomplete: str) -> list[str]:
    """Tab completion for library entries (UUIDs and names)."""
    matches = []

    try:
        user_config = create_user_config()
        library_service = create_library_service(user_config._config)

        # Get local library entries
        local_entries = library_service.list_local_layouts()
        for entry in local_entries:
            if entry.uuid.startswith(incomplete):
                matches.append(entry.uuid)
            if entry.name.lower().startswith(incomplete.lower()):
                matches.append(entry.name)

        return matches[:20]  # Limit to 20 matches

    except Exception:
        return []


@compile_app.command("layout")
@handle_errors
@with_metrics("library_compile")
def compile_layout(
    ctx: typer.Context,
    source: Annotated[
        str,
        typer.Argument(
            help="UUID or name of layout in library to compile",
            autocompletion=complete_library_entries,
        ),
    ],
    output_dir: Annotated[
        Path,
        typer.Argument(help="Output directory for compiled files"),
    ],
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Keyboard/firmware profile (e.g., 'glove80/v25.05')",
        ),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="Custom name for the compiled output files",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing output files"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose output"),
    ] = False,
) -> None:
    """Compile a layout from the library.

    This command resolves the library entry to its file path and compiles
    it using the standard layout compilation process.

    Examples:
        # Compile by UUID
        glovebox library compile 12345678-1234-1234-1234-123456789abc output/ --profile glove80/v25.05

        # Compile by name with custom output name
        glovebox library compile "My Gaming Layout" builds/ --name gaming --profile glove80/v25.05

        # Compile with verbose output
        glovebox library compile work-layout output/ --profile glove80/v25.05 --verbose
    """
    icon_mode = get_icon_mode_from_context(ctx)

    try:
        # Create user config and library service
        user_config = create_user_config()
        library_service = create_library_service(user_config._config)

        # Find the source layout
        typer.echo(
            Icons.format_with_icon(
                "SEARCH", f"Finding layout in library: {source}", icon_mode
            )
        )

        # Try to find by UUID first, then by name
        source_entry = None
        local_entries = library_service.list_local_layouts()

        for entry in local_entries:
            if entry.uuid == source or entry.name == source:
                source_entry = entry
                break

        if not source_entry:
            typer.echo(
                Icons.format_with_icon(
                    "ERROR", f"Layout not found in library: {source}", icon_mode
                )
            )
            raise typer.Exit(1)

        # Check if source file exists
        if not source_entry.file_path.exists():
            typer.echo(
                Icons.format_with_icon(
                    "ERROR",
                    f"Source file not found: {source_entry.file_path}",
                    icon_mode,
                )
            )
            raise typer.Exit(1)

        # Show library source info
        typer.echo(Icons.format_with_icon("INFO", "Compiling from library:", icon_mode))
        typer.echo(f"   Name: {source_entry.name}")
        if source_entry.title:
            typer.echo(f"   Title: {source_entry.title}")
        if source_entry.creator:
            typer.echo(f"   Creator: {source_entry.creator}")
        typer.echo(f"   UUID: {source_entry.uuid}")
        typer.echo(f"   Source: {source_entry.source.value}")
        if source_entry.tags:
            typer.echo(f"   Tags: {', '.join(source_entry.tags)}")

        # Import the layout compilation command
        from glovebox.cli.commands.layout.compilation import (
            compile_layout as layout_compile,
        )

        # Call the layout compile command with resolved path
        typer.echo(
            Icons.format_with_icon("COMPILE", "Starting compilation...", icon_mode)
        )

        # Create a new context for the layout command
        layout_ctx = typer.Context(layout_compile)
        layout_ctx.parent = ctx

        # Call the layout compile function directly
        layout_compile(
            ctx=layout_ctx,
            input_file=source_entry.file_path,
            output_dir=output_dir,
            profile=profile,
            name=name,
            force=force,
            verbose=verbose,
        )

    except Exception as e:
        typer.echo(
            Icons.format_with_icon("ERROR", f"Compilation failed: {e}", icon_mode)
        )
        raise typer.Exit(1) from e


# Make the main command available as default
@compile_app.callback(invoke_without_command=True)
def compile_default(
    ctx: typer.Context,
    source: Annotated[
        str | None,
        typer.Argument(
            help="UUID or name of layout to compile",
            autocompletion=complete_library_entries,
        ),
    ] = None,
    output_dir: Annotated[
        Path | None, typer.Argument(help="Output directory for compiled files")
    ] = None,
    profile: Annotated[str | None, typer.Option("--profile", "-p")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n")] = None,
    force: Annotated[bool, typer.Option("--force", "-f")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Compile a layout from the library."""
    if ctx.invoked_subcommand is None:
        if source is None or output_dir is None:
            typer.echo("Error: Missing required arguments: source and output_dir")
            raise typer.Exit(1)

        # Call the main compile command
        compile_layout(ctx, source, output_dir, profile, name, force, verbose)
