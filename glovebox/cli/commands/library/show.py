"""Library show command for displaying layouts directly from the library."""

from typing import Annotated

import typer

from glovebox.cli.decorators import handle_errors, with_metrics
from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context
from glovebox.config import create_user_config
from glovebox.library import create_library_service


show_app = typer.Typer(help="Show layouts from the library")


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


@show_app.command("layout")
@handle_errors
@with_metrics("library_show")
def show_layout(
    ctx: typer.Context,
    source: Annotated[
        str,
        typer.Argument(
            help="UUID or name of layout in library to show",
            autocompletion=complete_library_entries,
        ),
    ],
    layers: Annotated[
        bool,
        typer.Option("--layers", "-l", help="Show layer information"),
    ] = False,
    behaviors: Annotated[
        bool,
        typer.Option("--behaviors", "-b", help="Show behavior analysis"),
    ] = False,
    format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format",
        ),
    ] = "table",
    grid: Annotated[
        bool,
        typer.Option("--grid", "-g", help="Show keyboard grid layout"),
    ] = False,
    compact: Annotated[
        bool,
        typer.Option("--compact", "-c", help="Use compact display format"),
    ] = False,
) -> None:
    """Show a layout from the library.

    This command resolves the library entry to its file path and displays
    it using the standard layout display process, with additional library metadata.

    Examples:
        # Show basic layout info
        glovebox library show "My Gaming Layout"

        # Show with layers and behaviors
        glovebox library show work-layout --layers --behaviors

        # Show in JSON format
        glovebox library show gaming-layout --format json

        # Show keyboard grid
        glovebox library show work-layout --grid
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

        # Show library metadata first (unless JSON format)
        if format.lower() != "json":
            typer.echo(
                Icons.format_with_icon("INFO", "Library Entry Information:", icon_mode)
            )
            typer.echo(f"   Name: {source_entry.name}")
            if source_entry.title:
                typer.echo(f"   Title: {source_entry.title}")
            if source_entry.creator:
                typer.echo(f"   Creator: {source_entry.creator}")
            typer.echo(f"   UUID: {source_entry.uuid}")
            typer.echo(f"   Source: {source_entry.source.value}")
            if source_entry.source_reference:
                typer.echo(f"   Original Source: {source_entry.source_reference}")
            typer.echo(f"   Downloaded: {source_entry.downloaded_at}")
            if source_entry.tags:
                typer.echo(f"   Tags: {', '.join(source_entry.tags)}")
            if source_entry.notes:
                typer.echo(f"   Notes: {source_entry.notes}")
            typer.echo(f"   File: {source_entry.file_path}")
            typer.echo()  # Empty line separator

        # Import the layout show command
        from glovebox.cli.commands.layout.display import show_layout as layout_show

        # Call the layout show command with resolved path
        typer.echo(Icons.format_with_icon("DISPLAY", "Layout Content:", icon_mode))

        # Create a new context for the layout command
        layout_ctx = typer.Context(layout_show)
        layout_ctx.parent = ctx

        # Call the layout show function directly
        layout_show(
            ctx=layout_ctx,
            input_file=source_entry.file_path,
            layers=layers,
            behaviors=behaviors,
            format=format,
            grid=grid,
            compact=compact,
        )

    except Exception as e:
        typer.echo(Icons.format_with_icon("ERROR", f"Display failed: {e}", icon_mode))
        raise typer.Exit(1) from e


# Make the main command available as default
@show_app.callback(invoke_without_command=True)
def show_default(
    ctx: typer.Context,
    source: Annotated[
        str | None,
        typer.Argument(
            help="UUID or name of layout to show",
            autocompletion=complete_library_entries,
        ),
    ] = None,
    layers: Annotated[bool, typer.Option("--layers", "-l")] = False,
    behaviors: Annotated[bool, typer.Option("--behaviors", "-b")] = False,
    format: Annotated[str, typer.Option("--format", "-f")] = "table",
    grid: Annotated[bool, typer.Option("--grid", "-g")] = False,
    compact: Annotated[bool, typer.Option("--compact", "-c")] = False,
) -> None:
    """Show a layout from the library."""
    if ctx.invoked_subcommand is None:
        if source is None:
            typer.echo("Error: Missing required argument: source")
            raise typer.Exit(1)

        # Call the main show command
        show_layout(ctx, source, layers, behaviors, format, grid, compact)
