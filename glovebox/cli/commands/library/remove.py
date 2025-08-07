"""Library remove command for deleting layouts from library."""

from typing import Annotated

import typer

from glovebox.cli.core.command_base import BaseCommand
from glovebox.cli.decorators import handle_errors, with_metrics
from glovebox.cli.helpers.theme import Icons, get_icon_mode_from_context
from glovebox.config import create_user_config
from glovebox.library import create_library_service


remove_app = typer.Typer(help="Remove layouts from library")


def complete_layout_name(incomplete: str) -> list[str]:
    """Tab completion for layout names and UUIDs."""
    try:
        user_config = create_user_config()
        library_service = create_library_service(user_config._config)
        entries = library_service.list_local_layouts()

        # Return both names and UUIDs that match
        matches = []
        for entry in entries:
            if entry.name.startswith(incomplete):
                matches.append(entry.name)
            if entry.uuid.startswith(incomplete):
                matches.append(entry.uuid)

        return matches[:10]  # Limit to 10 matches
    except Exception:
        return []


class RemoveLayoutCommand(BaseCommand):
    """Command to remove a layout from the library."""

    def execute(
        self,
        ctx: typer.Context,
        identifier: str,
        force: bool,
    ) -> None:
        """Execute the remove layout command."""
        icon_mode = get_icon_mode_from_context(ctx)

        try:
            # Create user config and library service
            user_config = create_user_config()
            library_service = create_library_service(user_config._config)

            # Try to find entry by UUID first, then by name
            entry = library_service.get_layout_entry(identifier)
            if entry is None:
                entry = library_service.get_layout_entry_by_name(identifier)

            if entry is None:
                self.console.print_error(f"Layout not found: {identifier}")
                self.console.print_info(
                    "Use 'glovebox library list' to see available layouts"
                )
                ctx.exit(1)

            # Show layout information
            self.console.print_info(f"Layout to remove: {entry.name}")
            if entry.title and entry.title != entry.name:
                self.print_operation_info(f"Title: {entry.title}")
            self.print_operation_info(f"UUID: {entry.uuid}")
            if entry.creator:
                self.print_operation_info(f"Creator: {entry.creator}")
            self.print_operation_info(f"Source: {entry.source.value}")
            self.print_operation_info(f"File: {entry.file_path}")

            # Confirm removal unless --force is used
            if not force:
                typer.echo("")
                confirm = typer.confirm(
                    Icons.format_with_icon(
                        "WARNING",
                        f"Are you sure you want to remove '{entry.name}'?",
                        icon_mode,
                    )
                )
                if not confirm:
                    self.console.print_info("Removal cancelled")
                    return

            # Perform removal
            success = library_service.remove_layout(entry.uuid)

            if success:
                self.console.print_success(
                    f"Layout '{entry.name}' removed successfully"
                )
            else:
                self.console.print_error(f"Failed to remove layout '{entry.name}'")
                ctx.exit(1)

        except Exception as e:
            self.handle_service_error(e, "remove layout")


@remove_app.command()
@handle_errors
@with_metrics("library_remove")
def remove(
    ctx: typer.Context,
    identifier: Annotated[
        str,
        typer.Argument(
            help="Layout UUID or name to remove", autocompletion=complete_layout_name
        ),
    ],
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Skip confirmation prompt")
    ] = False,
) -> None:
    """Remove a layout from the library.

    The identifier can be either a UUID or a layout name.
    This will delete the layout file and remove it from the library index.

    Examples:
        glovebox library remove my-layout
        glovebox library remove 12345678-1234-1234-1234-123456789abc
        glovebox library remove my-layout --force
    """
    command = RemoveLayoutCommand()
    command.execute(ctx, identifier, force)


# Make remove the default command
@remove_app.callback(invoke_without_command=True)
def remove_default(
    ctx: typer.Context,
    identifier: Annotated[
        str | None, typer.Argument(autocompletion=complete_layout_name)
    ] = None,
    force: Annotated[bool, typer.Option("--force", "-f")] = False,
) -> None:
    """Remove a layout from the library."""
    if ctx.invoked_subcommand is None:
        if identifier is None:
            typer.echo("Error: Missing layout identifier")
            ctx.exit(1)

        remove(ctx, identifier, force)
