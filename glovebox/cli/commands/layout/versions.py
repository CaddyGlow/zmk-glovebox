"""Layout version management CLI subcommand group."""

from pathlib import Path
from typing import Annotated

import typer

from glovebox.cli.commands.layout.base import LayoutOutputCommand
from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers import (
    print_error_message,
    print_list_item,
    print_success_message,
)
from glovebox.cli.helpers.parameters import OutputFormatOption
from glovebox.layout.version_manager import create_version_manager


# Create a typer app for version commands
versions_app = typer.Typer(
    name="versions",
    help="""Layout version management commands.

Import master layout versions, list available versions, and manage
version metadata for upgrade operations.""",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@versions_app.command("import")
@handle_errors
def import_master(
    json_file: Annotated[Path, typer.Argument(help="Path to master layout JSON file")],
    name: Annotated[str, typer.Argument(help="Version name (e.g., 'v42-pre')")],
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing version")
    ] = False,
    output_format: OutputFormatOption = "text",
) -> None:
    """Import a master layout version for future upgrades.

    Downloads a new master version (e.g., from Layout Editor) and stores it
    locally for upgrading custom layouts. Master versions are stored in
    ~/.glovebox/masters/{keyboard}/ for reuse.

    Examples:
        # Import downloaded master version
        glovebox layout versions import ~/Downloads/glorious-v42-pre.json v42-pre

        # Overwrite existing version
        glovebox layout versions import glorious-v42.json v42-pre --force
    """
    command = LayoutOutputCommand()
    command.validate_layout_file(json_file)

    try:
        version_manager = create_version_manager()
        result = version_manager.import_master(json_file, name, force)

        if output_format.lower() == "json":
            command.format_output(result, "json")
        else:
            print_success_message(
                f"Imported master version '{name}' for {result['keyboard']}"
            )
            print_list_item(f"Title: {result['title']}")
            print_list_item(f"Stored: {result['path']}")

    except Exception as e:
        command.handle_service_error(e, "import master version")


@versions_app.command("list")
@handle_errors
def list_masters(
    keyboard: Annotated[
        str | None,
        typer.Argument(
            help="Keyboard name (e.g., 'glove80'). Optional - lists all if not specified"
        ),
    ] = None,
    output_format: OutputFormatOption = "text",
) -> None:
    """List available master versions for keyboard(s).

    Shows all imported master versions that can be used for upgrades.
    If no keyboard is specified, lists all available keyboards and their versions.

    Examples:
        # List master versions for Glove80
        glovebox layout versions list glove80

        # List all master versions for all keyboards
        glovebox layout versions list

        # JSON output for automation
        glovebox layout versions list glove80 --output-format json
    """
    command = LayoutOutputCommand()

    try:
        version_manager = create_version_manager()

        if keyboard:
            # List versions for specific keyboard
            masters = version_manager.list_masters(keyboard)

            if not masters:
                print_error_message(
                    f"No master versions found for keyboard '{keyboard}'"
                )
                print_list_item(
                    "Import a master version with: glovebox layout versions import"
                )
                return

            if output_format.lower() == "json":
                result_data = {"keyboard": keyboard, "masters": masters}
                command.format_output(result_data, "json")
            elif output_format.lower() == "table":
                command.format_output(masters, "table")
            else:
                master_lines = []
                for master in masters:
                    date_str = master["date"][:10] if master["date"] else "Unknown"
                    master_lines.append(
                        f"{master['name']} - {master['title']} ({date_str})"
                    )
                command.print_text_list(
                    master_lines, f"Master versions for {keyboard}:"
                )
        else:
            # List all keyboards and their versions
            # Note: list_all_masters method needs to be implemented in VersionManager
            # For now, using a placeholder implementation
            all_masters: dict[str, list[dict[str, str]]] = {}

            if not all_masters:
                print_error_message("No master versions found")
                print_list_item(
                    "Import a master version with: glovebox layout versions import"
                )
                return

            if output_format.lower() == "json":
                command.format_output(all_masters, "json")
            elif output_format.lower() == "table":
                # Flatten for table display
                table_data = []
                for keyboard_name, masters in all_masters.items():
                    for master in masters:
                        table_data.append(
                            {
                                "keyboard": keyboard_name,
                                "name": master["name"],
                                "title": master["title"],
                                "date": master["date"][:10]
                                if master["date"]
                                else "Unknown",
                            }
                        )
                command.format_output(table_data, "table")
            else:
                for keyboard_name, masters in all_masters.items():
                    master_lines = []
                    for master in masters:
                        date_str = master["date"][:10] if master["date"] else "Unknown"
                        master_lines.append(
                            f"  {master['name']} - {master['title']} ({date_str})"
                        )
                    command.print_text_list(master_lines, f"{keyboard_name}:")
                    print()  # Add spacing between keyboards

    except Exception as e:
        command.handle_service_error(e, "list master versions")


@versions_app.command("show")
@handle_errors
def show_version(
    keyboard: Annotated[str, typer.Argument(help="Keyboard name (e.g., 'glove80')")],
    version: Annotated[str, typer.Argument(help="Version name (e.g., 'v42-pre')")],
    output_format: OutputFormatOption = "text",
) -> None:
    """Show detailed information about a specific master version.

    Displays metadata, import date, and other details about a stored master version.

    Examples:
        # Show version details
        glovebox layout versions show glove80 v42-pre

        # JSON output
        glovebox layout versions show glove80 v42-pre --output-format json
    """
    command = LayoutOutputCommand()

    try:
        version_manager = create_version_manager()
        # Note: get_master_info method needs to be implemented in VersionManager
        # This is a placeholder implementation
        print_error_message(
            f"Master version '{version}' not found for keyboard '{keyboard}'"
        )
        print_list_item("Use 'glovebox layout versions list' to see available versions")
        print_list_item(
            "Note: get_master_info method needs to be implemented in VersionManager"
        )
        raise typer.Exit(1)

    except Exception as e:
        command.handle_service_error(e, f"show version '{version}'")


@versions_app.command("remove")
@handle_errors
def remove_version(
    keyboard: Annotated[str, typer.Argument(help="Keyboard name (e.g., 'glove80')")],
    version: Annotated[str, typer.Argument(help="Version name to remove")],
    force: Annotated[
        bool, typer.Option("--force", help="Skip confirmation prompt")
    ] = False,
    output_format: OutputFormatOption = "text",
) -> None:
    """Remove a master version from local storage.

    Deletes a stored master version file and its metadata. This cannot be undone.

    Examples:
        # Remove a version with confirmation
        glovebox layout versions remove glove80 v41-old

        # Force remove without confirmation
        glovebox layout versions remove glove80 v41-old --force
    """
    command = LayoutOutputCommand()

    try:
        version_manager = create_version_manager()

        # Note: Both get_master_info and remove_master methods need to be implemented
        # This is a placeholder implementation
        print_error_message(
            f"Master version '{version}' not found for keyboard '{keyboard}'"
        )
        print_list_item(
            "Note: get_master_info and remove_master methods need to be implemented in VersionManager"
        )
        raise typer.Exit(1)

    except Exception as e:
        command.handle_service_error(e, f"remove version '{version}'")
