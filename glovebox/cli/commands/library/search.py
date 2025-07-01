"""Library search command for finding layouts via MoErgo API."""

from typing import Annotated

import typer

from glovebox.cli.decorators import handle_errors, with_metrics
from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context
from glovebox.config import create_user_config
from glovebox.library import SearchQuery, create_library_service


search_app = typer.Typer(help="Search for layouts using MoErgo API")


@search_app.command()
@handle_errors
@with_metrics("library_search")
def search(
    ctx: typer.Context,
    tags: Annotated[
        str | None,
        typer.Option("--tags", "-t", help="Filter by tags (comma-separated)"),
    ] = None,
    creator: Annotated[
        str | None, typer.Option("--creator", "-c", help="Filter by creator name")
    ] = None,
    title: Annotated[
        str | None, typer.Option("--title", help="Filter by title containing text")
    ] = None,
    limit: Annotated[
        int | None, typer.Option("--limit", "-l", help="Maximum number of results")
    ] = None,
    offset: Annotated[int, typer.Option("--offset", help="Offset for pagination")] = 0,
) -> None:
    """Search for layouts using MoErgo API.

    Examples:
        glovebox library search --tags glove80-standard
        glovebox library search --creator "Official" --limit 10
        glovebox library search --title "gaming" --tags gaming,macros
    """
    icon_mode = get_icon_mode_from_context(ctx)

    try:
        # Parse tags
        tag_list = None
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        # Create user config and library service
        user_config = create_user_config()
        library_service = create_library_service(user_config._config)

        # Create search query
        query = SearchQuery(
            tags=tag_list,
            creator=creator,
            title_contains=title,
            limit=limit,
            offset=offset,
        )

        typer.echo(
            Icons.format_with_icon("SEARCH", "Searching MoErgo layouts...", icon_mode)
        )

        # Perform search
        result = library_service.search_layouts(query)

        if result.success:
            if not result.layouts:
                typer.echo(
                    Icons.format_with_icon(
                        "INFO", "No layouts found matching criteria", icon_mode
                    )
                )
                return

            typer.echo(
                Icons.format_with_icon(
                    "SUCCESS", f"Found {len(result.layouts)} layouts:", icon_mode
                )
            )

            if result.total_count is not None:
                typer.echo(f"   Total available: {result.total_count}")

            typer.echo()

            for layout in result.layouts:
                typer.echo(f"   {Icons.get_icon('LAYOUT', icon_mode)} {layout.title}")
                typer.echo(f"      UUID: {layout.uuid}")
                typer.echo(f"      Creator: {layout.creator}")

                if layout.tags:
                    typer.echo(f"      Tags: {', '.join(layout.tags)}")

                if layout.notes:
                    typer.echo(f"      Notes: {layout.notes}")

                if layout.compiled:
                    typer.echo(
                        f"      {Icons.get_icon('BUILD', icon_mode)} Compiled on MoErgo servers"
                    )

                typer.echo()

            if result.has_more:
                typer.echo(
                    Icons.format_with_icon(
                        "INFO",
                        f"Use --offset {offset + len(result.layouts)} to see more results",
                        icon_mode,
                    )
                )

            typer.echo(
                Icons.format_with_icon(
                    "INFO",
                    "Use 'glovebox library fetch <UUID>' to download a layout",
                    icon_mode,
                )
            )

        else:
            typer.echo(Icons.format_with_icon("ERROR", "Search failed:", icon_mode))
            for error in result.errors:
                typer.echo(f"   {error}")
            raise typer.Exit(1)

    except Exception as e:
        typer.echo(Icons.format_with_icon("ERROR", f"Unexpected error: {e}", icon_mode))
        raise typer.Exit(1) from e


# Make search the default command
@search_app.callback(invoke_without_command=True)
def search_default(
    ctx: typer.Context,
    tags: Annotated[str | None, typer.Option("--tags", "-t")] = None,
    creator: Annotated[str | None, typer.Option("--creator", "-c")] = None,
    title: Annotated[str | None, typer.Option("--title")] = None,
    limit: Annotated[int | None, typer.Option("--limit", "-l")] = None,
    offset: Annotated[int, typer.Option("--offset")] = 0,
) -> None:
    """Search for layouts using MoErgo API."""
    if ctx.invoked_subcommand is None:
        search(ctx, tags, creator, title, limit, offset)
