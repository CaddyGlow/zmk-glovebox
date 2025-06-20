"""Layout upgrade CLI command."""

from pathlib import Path
from typing import Annotated

import typer

from glovebox.cli.commands.layout.base import LayoutOutputCommand
from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers import print_list_item, print_success_message
from glovebox.cli.helpers.parameters import OutputFormatOption
from glovebox.layout.version_manager import create_version_manager


@handle_errors
def upgrade(
    custom_layout: Annotated[
        Path, typer.Argument(help="Path to custom layout to upgrade")
    ],
    to: Annotated[str, typer.Option("--to", help="Target master version name")],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output path (default: auto-generated)"),
    ] = None,
    from_version: Annotated[
        str | None,
        typer.Option(
            "--from",
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

    This command was simplified from the previous upgrade command to use
    cleaner option names (--to instead of --to-master, --from instead of --from-master).

    Examples:
        # Upgrade to new master version (auto-detects source version)
        glovebox layout upgrade my-custom-v41.json --to v42-pre

        # Manually specify source version for layouts without metadata
        glovebox layout upgrade my-layout.json --from v41 --to v42-pre

        # Specify output location
        glovebox layout upgrade my-layout.json --to v42-pre --output my-layout-v42.json

        # Use different upgrade strategy
        glovebox layout upgrade my-layout.json --to v42-pre --strategy merge-conflicts
    """
    command = LayoutOutputCommand()
    command.validate_layout_file(custom_layout)

    try:
        version_manager = create_version_manager()
        result = version_manager.upgrade_layout(
            custom_layout, to, output, strategy, from_version
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
