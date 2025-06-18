"""Layout version management CLI commands."""

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
        glovebox layout import-master ~/Downloads/glorious-v42-pre.json v42-pre

        # Overwrite existing version
        glovebox layout import-master glorious-v42.json v42-pre --force
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
        command.handle_service_error(e, "import master")


@handle_errors
def upgrade(
    custom_layout: Annotated[
        Path, typer.Argument(help="Path to custom layout to upgrade")
    ],
    to_master: Annotated[
        str, typer.Option("--to-master", help="Target master version name")
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output path (default: auto-generated)"),
    ] = None,
    from_master: Annotated[
        str | None,
        typer.Option(
            "--from-master",
            help="Source master version (auto-detected if not specified)",
        ),
    ] = None,
    strategy: Annotated[
        str, typer.Option("--strategy", help="Upgrade strategy")
    ] = "preserve-custom",
    output_format: OutputFormatOption = "text",
) -> None:
    """Upgrade custom layout to new master version preserving customizations.

    Merges your customizations with a new master version, preserving your
    custom layers, behaviors, and configurations while updating base layers.

    Examples:
        # Upgrade to new master version (auto-detects source version)
        glovebox layout upgrade my-custom-v41.json --to-master v42-pre

        # Manually specify source version for layouts without metadata
        glovebox layout upgrade my-layout.json --from-master v41 --to-master v42-pre

        # Specify output location
        glovebox layout upgrade my-layout.json --to-master v42-pre --output my-layout-v42.json
    """
    command = LayoutOutputCommand()
    command.validate_layout_file(custom_layout)

    try:
        version_manager = create_version_manager()
        result = version_manager.upgrade_layout(
            custom_layout, to_master, output, strategy, from_master
        )

        if output_format.lower() == "json":
            command.format_output(result, "json")
        else:
            print_success_message(
                f"Upgraded layout from {result['from_version']} to {result['to_version']}"
            )
            print_list_item(f"Output: {result['output_path']}")

            preserved = result["preserved_customizations"]
            if preserved["custom_layers"]:
                print_list_item(
                    f"Preserved custom layers: {', '.join(preserved['custom_layers'])}"
                )
            if preserved["custom_behaviors"]:
                print_list_item(
                    f"Preserved behaviors: {', '.join(preserved['custom_behaviors'])}"
                )
            if preserved["custom_config"]:
                print_list_item(
                    f"Preserved config: {', '.join(preserved['custom_config'])}"
                )

    except Exception as e:
        command.handle_service_error(e, "upgrade layout")


@handle_errors
def list_masters(
    keyboard: Annotated[str, typer.Argument(help="Keyboard name (e.g., 'glove80')")],
    output_format: OutputFormatOption = "text",
) -> None:
    """List available master versions for a keyboard.

    Shows all imported master versions that can be used for upgrades.

    Examples:
        # List master versions for Glove80
        glovebox layout list-masters glove80
    """
    command = LayoutOutputCommand()

    try:
        version_manager = create_version_manager()
        masters = version_manager.list_masters(keyboard)

        if not masters:
            print_error_message(f"No master versions found for keyboard '{keyboard}'")
            print_list_item(
                "Import a master version with: glovebox layout import-master"
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
            command.print_text_list(master_lines, f"Master versions for {keyboard}:")

    except Exception as e:
        command.handle_service_error(e, "list masters")
