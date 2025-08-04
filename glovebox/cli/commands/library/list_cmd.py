"""Library list command for showing local library contents."""

from typing import Annotated

import typer

from glovebox.cli.core.command_base import BaseCommand
from glovebox.cli.decorators import handle_errors, with_metrics
from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context
from glovebox.config import create_user_config
from glovebox.library import LibrarySource, create_library_service


list_app = typer.Typer(help="List layouts in local library")


class ListLayoutCommand(BaseCommand):
    """Command to list layouts in the local library."""

    def execute(
        self,
        ctx: typer.Context,
        source: str | None,
        tags: str | None,
        format_type: str,
    ) -> None:
        """Execute the list layout command."""
        icon_mode = get_icon_mode_from_context(ctx)

        try:
            # Parse source filter
            source_filter = None
            if source:
                try:
                    source_filter = LibrarySource(source)
                except ValueError:
                    valid_sources = [s.value for s in LibrarySource]
                    self.console.print_error(
                        f"Invalid source '{source}'. Valid sources: {', '.join(valid_sources)}"
                    )
                    raise typer.Exit(1) from None

            # Parse tags filter
            tag_filter = None
            if tags:
                tag_filter = [tag.strip() for tag in tags.split(",") if tag.strip()]

            # Create user config and library service
            user_config = create_user_config()
            library_service = create_library_service(user_config._config)

            # Get library entries
            entries = library_service.list_local_layouts(
                source_filter=source_filter,
                tag_filter=tag_filter,
            )

            if not entries:
                self.console.print_info("No layouts found in library")
                self.console.print_info(
                    "Use 'glovebox library fetch <source>' to add layouts"
                )
                return

            if format_type == "json":
                import json

                output_data = []
                for entry in entries:
                    output_data.append(entry.model_dump(mode="json"))
                typer.echo(json.dumps(output_data, indent=2, default=str))
                return

            # Table format
            self.console.print_success(f"Library contains {len(entries)} layouts:")
            typer.echo("")

            for entry in entries:
                icon = Icons.get_icon("LAYOUT", icon_mode)
                typer.echo(f"   {icon} {entry.name}")
                if entry.title and entry.title != entry.name:
                    self.print_operation_info(f"Title: {entry.title}")
                self.print_operation_info(f"UUID: {entry.uuid}")
                if entry.creator:
                    self.print_operation_info(f"Creator: {entry.creator}")
                self.print_operation_info(f"Source: {entry.source.value}")
                self.print_operation_info(
                    f"Downloaded: {entry.downloaded_at.strftime('%Y-%m-%d %H:%M')}"
                )

                if entry.tags:
                    self.print_operation_info(f"Tags: {', '.join(entry.tags)}")

                self.print_operation_info(f"File: {entry.file_path}")
                typer.echo("")

            # Show usage hints
            self.console.print_info(
                "Use 'glovebox library info <uuid>' for detailed information"
            )
            self.console.print_info(
                "Use 'glovebox library remove <uuid>' to remove a layout"
            )

        except Exception as e:
            self.handle_service_error(e, "list layouts")


@list_app.command()
@handle_errors
@with_metrics("library_list")
def list_layouts(
    ctx: typer.Context,
    source: Annotated[
        str | None,
        typer.Option(
            "--source",
            "-s",
            help="Filter by source type (moergo_uuid, moergo_url, http_url, local_file)",
        ),
    ] = None,
    tags: Annotated[
        str | None,
        typer.Option(
            "--tags",
            "-t",
            help="Filter by tags (comma-separated, entry must have all tags)",
        ),
    ] = None,
    format_type: Annotated[
        str, typer.Option("--format", "-f", help="Output format")
    ] = "table",
) -> None:
    """List layouts in the local library.

    Examples:
        glovebox library list
        glovebox library list --source moergo_uuid
        glovebox library list --tags glove80-standard,gaming
        glovebox library list --format json
    """
    command = ListLayoutCommand()
    command.execute(ctx, source, tags, format_type)


# Make list the default command
@list_app.callback(invoke_without_command=True)
def list_default(
    ctx: typer.Context,
    source: Annotated[str | None, typer.Option("--source", "-s")] = None,
    tags: Annotated[str | None, typer.Option("--tags", "-t")] = None,
    format_type: Annotated[str, typer.Option("--format", "-f")] = "table",
) -> None:
    """List layouts in the local library."""
    if ctx.invoked_subcommand is None:
        list_layouts(ctx, source, tags, format_type)
