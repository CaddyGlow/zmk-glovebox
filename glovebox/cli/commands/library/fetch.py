"""Library fetch command for downloading layouts from various sources."""

from pathlib import Path
from typing import Annotated

import typer

from glovebox.cli.decorators import handle_errors, with_metrics
from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context
from glovebox.config import create_user_config
from glovebox.library import FetchRequest, create_library_service


fetch_app = typer.Typer(help="Fetch layouts from various sources")


def complete_layout_source(incomplete: str) -> list[str]:
    """Tab completion for layout sources (UUIDs from MoErgo search, local library, files)."""
    matches = []
    
    try:
        # Get local library entries for UUID completion
        user_config = create_user_config()
        library_service = create_library_service(user_config._config)
        
        # Local library UUIDs and names
        local_entries = library_service.list_local_layouts()
        for entry in local_entries:
            if entry.uuid.startswith(incomplete):
                matches.append(entry.uuid)
            if entry.name.startswith(incomplete):
                matches.append(entry.name)
        
        # Search MoErgo for public UUIDs (if incomplete looks like UUID start)
        if len(incomplete) >= 3 and all(c in "0123456789abcdef-" for c in incomplete.lower()):
            from glovebox.library.models import SearchQuery
            search_query = SearchQuery(limit=10, offset=0)
            search_result = library_service.search_layouts(search_query)
            
            if search_result.success:
                for layout in search_result.layouts:
                    if layout.uuid.startswith(incomplete):
                        matches.append(layout.uuid)
        
        # Local file completion (basic)
        if "/" in incomplete or "." in incomplete:
            try:
                from pathlib import Path
                
                # Basic file path completion
                path_part = Path(incomplete).expanduser()
                if path_part.is_dir():
                    for file_path in path_part.iterdir():
                        if file_path.suffix.lower() in [".json", ".keymap"]:
                            matches.append(str(file_path))
                elif path_part.parent.is_dir():
                    for file_path in path_part.parent.iterdir():
                        if str(file_path).startswith(str(path_part)) and file_path.suffix.lower() in [".json", ".keymap"]:
                            matches.append(str(file_path))
            except Exception:
                pass
                
        return matches[:20]  # Limit to 20 matches
        
    except Exception:
        return []


@fetch_app.command("layout")
@handle_errors
@with_metrics("library_fetch")
def fetch_layout(
    ctx: typer.Context,
    source: Annotated[
        str, typer.Argument(
            help="Source to fetch from (UUID, URL, or file path)",
            autocompletion=complete_layout_source
        )
    ],
    name: Annotated[
        str | None, typer.Option("--name", "-n", help="Custom name for the layout")
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Custom output path for the layout file"),
    ] = None,
    bookmark: Annotated[
        bool,
        typer.Option(
            "--bookmark", "-b", help="Create a bookmark for the fetched layout"
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing layout if it exists"),
    ] = False,
) -> None:
    """Fetch a layout from any supported source and add it to the library.

    Supported sources:
    - MoErgo UUID: e.g., '12345678-1234-1234-1234-123456789abc'
    - MoErgo URL: e.g., 'https://moergo.com/layout/12345678-1234-1234-1234-123456789abc'
    - HTTP URL: e.g., 'https://example.com/layout.json'
    - Local file: e.g., './my-layout.json' or '/path/to/layout.json'
    """
    icon_mode = get_icon_mode_from_context(ctx)

    try:
        # Create user config and library service
        user_config = create_user_config()
        library_service = create_library_service(user_config._config)

        # Create fetch request
        request = FetchRequest(
            source=source,
            name=name,
            output_path=output,
            create_bookmark=bookmark,
            force_overwrite=force,
        )

        typer.echo(
            Icons.format_with_icon(
                "DOWNLOAD", f"Fetching layout from: {source}", icon_mode
            )
        )

        # Perform fetch
        result = library_service.fetch_layout(request)

        if result.success and result.entry:
            typer.echo(
                Icons.format_with_icon(
                    "SUCCESS", "Layout fetched successfully!", icon_mode
                )
            )
            typer.echo(f"   Name: {result.entry.name}")
            if result.entry.title:
                typer.echo(f"   Title: {result.entry.title}")
            if result.entry.creator:
                typer.echo(f"   Creator: {result.entry.creator}")
            typer.echo(f"   UUID: {result.entry.uuid}")
            typer.echo(f"   Source: {result.entry.source.value}")
            typer.echo(f"   File: {result.entry.file_path}")

            if result.entry.tags:
                typer.echo(f"   Tags: {', '.join(result.entry.tags)}")

            if bookmark and result.entry:
                typer.echo(
                    Icons.format_with_icon(
                        "BOOKMARK", "Bookmark created successfully!", icon_mode
                    )
                )

            # Show warnings if any
            for warning in result.warnings:
                typer.echo(Icons.format_with_icon("WARNING", warning, icon_mode))

        else:
            typer.echo(
                Icons.format_with_icon("ERROR", "Failed to fetch layout:", icon_mode)
            )
            for error in result.errors:
                typer.echo(f"   {error}")
            raise typer.Exit(1)

    except Exception as e:
        typer.echo(Icons.format_with_icon("ERROR", f"Unexpected error: {e}", icon_mode))
        raise typer.Exit(1) from e


# Make the main command available as default
@fetch_app.callback(invoke_without_command=True)
def fetch_default(
    ctx: typer.Context,
    source: Annotated[
        str | None, 
        typer.Argument(
            help="Source to fetch from",
            autocompletion=complete_layout_source
        )
    ] = None,
    name: Annotated[str | None, typer.Option("--name", "-n")] = None,
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
    bookmark: Annotated[bool, typer.Option("--bookmark", "-b")] = False,
    force: Annotated[bool, typer.Option("--force", "-f")] = False,
) -> None:
    """Fetch a layout from any supported source."""
    if ctx.invoked_subcommand is None:
        if source is None:
            typer.echo("Error: Missing source argument")
            raise typer.Exit(1)

        # Call the main fetch command
        fetch_layout(ctx, source, name, output, bookmark, force)
