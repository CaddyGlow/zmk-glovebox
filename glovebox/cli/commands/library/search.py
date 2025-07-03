"""Library search command for finding layouts via MoErgo API."""

from typing import Annotated

import typer

from glovebox.cli.core.command_base import BaseCommand
from glovebox.cli.decorators import handle_errors, with_metrics
from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context
from glovebox.config import create_user_config
from glovebox.library import SearchQuery, create_library_service


search_app = typer.Typer(help="Search for layouts using MoErgo API")


class SearchLayoutCommand(BaseCommand):
    """Command to search for layouts using MoErgo API."""

    def execute(
        self,
        ctx: typer.Context,
        tags: str | None,
        creator: str | None,
        title: str | None,
        limit: int | None,
        offset: int,
    ) -> None:
        """Execute the search layout command."""
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

            self.console.print_info("Searching MoErgo layouts...")

            # Perform search
            result = library_service.search_layouts(query)

            if result.success:
                if not result.layouts:
                    self.console.print_info("No layouts found matching criteria")
                    return

                self.console.print_success(f"Found {len(result.layouts)} layouts:")

                if result.total_count is not None:
                    self.print_operation_info(f"Total available: {result.total_count}")

                typer.echo("")

                for layout in result.layouts:
                    icon = Icons.get_icon("LAYOUT", icon_mode)
                    typer.echo(f"   {icon} {layout.title}")
                    self.print_operation_info(f"UUID: {layout.uuid}")
                    self.print_operation_info(f"Creator: {layout.creator}")

                    if layout.tags:
                        self.print_operation_info(f"Tags: {', '.join(layout.tags)}")

                    if layout.notes:
                        self.print_operation_info(f"Notes: {layout.notes}")

                    if layout.compiled:
                        build_icon = Icons.get_icon("BUILD", icon_mode)
                        self.print_operation_info(
                            f"{build_icon} Compiled on MoErgo servers"
                        )

                    typer.echo("")

                if result.has_more:
                    self.console.print_info(
                        f"Use --offset {offset + len(result.layouts)} to see more results"
                    )

                self.console.print_info(
                    "Use 'glovebox library fetch <UUID>' to download a layout"
                )

            else:
                self.console.print_error("Search failed:")
                for error in result.errors:
                    self.print_operation_info(f"  {error}")
                raise typer.Exit(1)

        except Exception as e:
            self.handle_service_error(e, "search layouts")


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
    command = SearchLayoutCommand()
    command.execute(ctx, tags, creator, title, limit, offset)


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
