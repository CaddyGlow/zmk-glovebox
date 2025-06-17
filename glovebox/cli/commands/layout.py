"""Layout-related CLI commands."""

import json
import logging
from pathlib import Path
from typing import Annotated

import typer

from glovebox.cli.decorators import handle_errors, with_profile
from glovebox.cli.helpers import (
    print_error_message,
    print_list_item,
    print_success_message,
)
from glovebox.cli.helpers.parameters import OutputFormatOption, ProfileOption
from glovebox.cli.helpers.profile import get_keyboard_profile_from_context
from glovebox.layout.service import create_layout_service
from glovebox.layout.version_manager import create_version_manager


logger = logging.getLogger(__name__)

# Create a typer app for layout commands
layout_app = typer.Typer(
    name="layout",
    help="""Layout management commands.

Convert JSON layouts to ZMK files, extract/merge layers, validate layouts,
and display visual representations of keyboard layouts.""",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@layout_app.command(name="compile")
@handle_errors
@with_profile()
def layout_compile(
    ctx: typer.Context,
    output_file_prefix: Annotated[
        str,
        typer.Argument(
            help="Output directory and base filename (e.g., 'config/my_glove80')"
        ),
    ],
    json_file: Annotated[
        str,
        typer.Argument(help="Path to keymap JSON file"),
    ],
    profile: ProfileOption = None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
    output_format: OutputFormatOption = "text",
) -> None:
    """Compile ZMK keymap and config files from a JSON keymap file.

    Takes a JSON layout file (exported from Layout Editor) and generates
    ZMK .keymap and .conf files ready for firmware compilation.

    ---

    Examples:

    * glovebox layout compile layout.json output/glove80 --profile glove80/v25.05

    * cat layout.json | glovebox layout compile - output/glove80 --profile glove80/v25.05
    """

    # Generate keymap using the file-based service method
    keymap_service = create_layout_service()

    # The @with_profile decorator injects keyboard_profile parameter
    keyboard_profile = get_keyboard_profile_from_context(ctx)

    try:
        result = keymap_service.generate_from_file(
            profile=keyboard_profile,
            json_file_path=Path(json_file),
            output_file_prefix=output_file_prefix,
            force=force,
        )

        if result.success:
            if output_format.lower() == "json":
                # JSON output for automation
                output_files = result.get_output_files()
                result_data = {
                    "success": True,
                    "message": "Layout generated successfully",
                    "output_files": output_files,
                    "messages": result.messages if hasattr(result, "messages") else [],
                }
                from glovebox.cli.helpers.output_formatter import OutputFormatter

                formatter = OutputFormatter()
                print(formatter.format(result_data, "json"))
            else:
                # Rich text output (default)
                print_success_message("Layout generated successfully")
                output_files = result.get_output_files()

                if output_format.lower() == "table":
                    # Table format for file listing
                    file_data = [
                        {"Type": file_type, "Path": str(file_path)}
                        for file_type, file_path in output_files.items()
                    ]
                    from glovebox.cli.helpers.output_formatter import OutputFormatter

                    formatter = OutputFormatter()
                    formatter.print_formatted(file_data, "table")
                else:
                    # Text format (default)
                    for file_type, file_path in output_files.items():
                        print_list_item(f"{file_type}: {file_path}")
        else:
            print_error_message("Layout generation failed")
            for error in result.errors:
                print_list_item(error)
            raise typer.Exit(1)

    except Exception as e:
        print_error_message(f"Layout generation failed: {str(e)}")
        raise typer.Exit(1) from None


@layout_app.command()
@handle_errors
@with_profile()
def decompose(
    ctx: typer.Context,
    keymap_file: Annotated[Path, typer.Argument(help="Path to keymap JSON file")],
    output_dir: Annotated[
        Path, typer.Argument(help="Directory to save extracted files")
    ],
    profile: ProfileOption = None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
    output_format: OutputFormatOption = "text",
) -> None:
    """Decompose layers from a keymap file into individual layer files."""

    # Use the file-based service method
    keymap_service = create_layout_service()

    # The @with_profile decorator injects keyboard_profile via context
    keyboard_profile = get_keyboard_profile_from_context(ctx)

    try:
        result = keymap_service.decompose_components_from_file(
            profile=keyboard_profile,
            json_file_path=keymap_file,
            output_dir=output_dir,
            force=force,
        )

        if result.success:
            print_success_message(f"Layout layers decomposed to {output_dir}")
        else:
            print_error_message("Layout component decomposition failed")
            for error in result.errors:
                print_list_item(error)
            raise typer.Exit(1)
    except Exception as e:
        print_error_message(f"Layout component extraction failed: {str(e)}")
        raise typer.Exit(1) from None


@layout_app.command()
@handle_errors
@with_profile(default_profile="glove80/v25.05")
def compose(
    ctx: typer.Context,
    input_dir: Annotated[
        Path,
        typer.Argument(help="Directory with metadata.json and layers/ subdirectory"),
    ],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Output keymap JSON file path")
    ],
    profile: ProfileOption = None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
    output_format: OutputFormatOption = "text",
) -> None:
    """Compose layer files into a single keymap file."""

    # Use the file-based service method
    keymap_service = create_layout_service()

    # The @with_profile decorator injects keyboard_profile via context
    keyboard_profile = get_keyboard_profile_from_context(ctx)

    try:
        result = keymap_service.generate_from_directory(
            profile=keyboard_profile,
            components_dir=input_dir,
            output_file_prefix=output,
            force=force,
        )

        if result.success:
            print_success_message(f"Layout composed and saved to {output}")
        else:
            print_error_message("Layout composition failed")
            for error in result.errors:
                print_list_item(error)
            raise typer.Exit(1)
    except Exception as e:
        print_error_message(f"Layout composition failed: {str(e)}")
        raise typer.Exit(1) from None


@layout_app.command()
@handle_errors
@with_profile(default_profile="glove80/v25.05")
def validate(
    ctx: typer.Context,
    json_file: Annotated[Path, typer.Argument(help="Path to keymap JSON file")],
    profile: ProfileOption = None,
    output_format: OutputFormatOption = "text",
) -> None:
    """Validate keymap syntax and structure."""

    # Validate using the file-based service method
    keymap_service = create_layout_service()

    # The @with_profile decorator injects keyboard_profile via context
    keyboard_profile = get_keyboard_profile_from_context(ctx)

    try:
        if keymap_service.validate_from_file(
            profile=keyboard_profile, json_file_path=json_file
        ):
            print_success_message(f"Layout file {json_file} is valid")
        else:
            print_error_message(f"Layout file {json_file} is invalid")
            raise typer.Exit(1)
    except Exception as e:
        print_error_message(f"Layout validation failed: {str(e)}")
        raise typer.Exit(1) from None


@layout_app.command()
@handle_errors
@with_profile(default_profile="glove80/v25.05")
def show(
    ctx: typer.Context,
    json_file: Annotated[
        Path, typer.Argument(help="Path to keyboard layout JSON file")
    ],
    key_width: Annotated[
        int, typer.Option("--key-width", "-w", help="Width for displaying each key")
    ] = 10,
    view_mode: Annotated[
        str | None,
        typer.Option(
            "--view-mode", "-m", help="View mode (normal, compact, split, flat)"
        ),
    ] = None,
    layout: Annotated[
        str | None,
        typer.Option("--layout", "-l", help="Layout name to use for display"),
    ] = None,
    layer: Annotated[
        int | None, typer.Option("--layer", help="Show only specific layer index")
    ] = None,
    profile: ProfileOption = None,
    output_format: OutputFormatOption = "text",
) -> None:
    """Display keymap layout in terminal."""

    # Call the service
    keymap_service = create_layout_service()

    # The @with_profile decorator injects keyboard_profile via context
    keyboard_profile = get_keyboard_profile_from_context(ctx)

    try:
        # Get layout data first for formatting
        if output_format.lower() != "text":
            # For non-text formats, load and format the JSON data
            layout_data = json.loads(json_file.read_text())

            from glovebox.cli.helpers.output_formatter import LayoutDisplayFormatter

            formatter = LayoutDisplayFormatter()
            formatter.print_formatted(layout_data, output_format)
        else:
            # For text format, use the existing show method
            result = keymap_service.show_from_file(
                json_file_path=json_file,
                profile=keyboard_profile,
                key_width=key_width,
            )
            # The show method returns a string
            typer.echo(result)
    except NotImplementedError as e:
        print_error_message(str(e))
        raise typer.Exit(1) from e


@layout_app.command(name="import-master")
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
    version_manager = create_version_manager()

    try:
        result = version_manager.import_master(json_file, name, force)

        if output_format.lower() == "json":
            from glovebox.cli.helpers.output_formatter import OutputFormatter

            formatter = OutputFormatter()
            print(formatter.format(result, "json"))
        else:
            print_success_message(
                f"Imported master version '{name}' for {result['keyboard']}"
            )
            print_list_item(f"Title: {result['title']}")
            print_list_item(f"Stored: {result['path']}")

    except Exception as e:
        print_error_message(f"Failed to import master: {str(e)}")
        raise typer.Exit(1) from None


@layout_app.command()
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
    version_manager = create_version_manager()

    try:
        result = version_manager.upgrade_layout(
            custom_layout, to_master, output, strategy, from_master
        )

        if output_format.lower() == "json":
            from glovebox.cli.helpers.output_formatter import OutputFormatter

            formatter = OutputFormatter()
            print(formatter.format(result, "json"))
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
        print_error_message(f"Failed to upgrade layout: {str(e)}")
        raise typer.Exit(1) from None


@layout_app.command(name="list-masters")
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
    version_manager = create_version_manager()

    try:
        masters = version_manager.list_masters(keyboard)

        if not masters:
            print_error_message(f"No master versions found for keyboard '{keyboard}'")
            print_list_item(
                "Import a master version with: glovebox layout import-master"
            )
            return

        if output_format.lower() == "json":
            from glovebox.cli.helpers.output_formatter import OutputFormatter

            formatter = OutputFormatter()
            result_data = {"keyboard": keyboard, "masters": masters}
            print(formatter.format(result_data, "json"))
        elif output_format.lower() == "table":
            from glovebox.cli.helpers.output_formatter import OutputFormatter

            formatter = OutputFormatter()
            formatter.print_formatted(masters, "table")
        else:
            print_success_message(f"Master versions for {keyboard}:")
            for master in masters:
                date_str = master["date"][:10] if master["date"] else "Unknown"
                print_list_item(f"{master['name']} - {master['title']} ({date_str})")

    except Exception as e:
        print_error_message(f"Failed to list masters: {str(e)}")
        raise typer.Exit(1) from None


@layout_app.command()
@handle_errors
def diff(
    layout1: Annotated[Path, typer.Argument(help="First layout file to compare")],
    layout2: Annotated[Path, typer.Argument(help="Second layout file to compare")],
    output_format: OutputFormatOption = "summary",
) -> None:
    """Compare two layouts showing differences.

    Shows differences between two layout files, focusing on layers,
    behaviors, and configuration changes.

    Examples:
        # Compare two layout versions
        glovebox layout diff my-layout-v41.json my-layout-v42.json

        # Compare custom layout with master
        glovebox layout diff ~/.glovebox/masters/glove80/v41.json my-custom-v41.json
    """
    from glovebox.layout.version_manager import create_version_manager

    try:
        version_manager = create_version_manager()

        # Load both layouts
        layout1_data = version_manager._load_layout(layout1)
        layout2_data = version_manager._load_layout(layout2)

        # Simple diff implementation
        differences = []

        # Compare metadata
        if layout1_data.title != layout2_data.title:
            differences.append(
                f"Title: '{layout1_data.title}' → '{layout2_data.title}'"
            )
        if layout1_data.version != layout2_data.version:
            differences.append(
                f"Version: '{layout1_data.version}' → '{layout2_data.version}'"
            )

        # Compare layers
        layout1_layers = set(layout1_data.layer_names)
        layout2_layers = set(layout2_data.layer_names)

        added_layers = layout2_layers - layout1_layers
        removed_layers = layout1_layers - layout2_layers

        if added_layers:
            differences.append(f"Added layers: {', '.join(sorted(added_layers))}")
        if removed_layers:
            differences.append(f"Removed layers: {', '.join(sorted(removed_layers))}")

        # Compare behaviors
        layout1_behaviors = (
            len(layout1_data.hold_taps)
            + len(layout1_data.combos)
            + len(layout1_data.macros)
        )
        layout2_behaviors = (
            len(layout2_data.hold_taps)
            + len(layout2_data.combos)
            + len(layout2_data.macros)
        )

        if layout1_behaviors != layout2_behaviors:
            differences.append(f"Behaviors: {layout1_behaviors} → {layout2_behaviors}")

        # Compare config parameters
        layout1_config = len(layout1_data.config_parameters)
        layout2_config = len(layout2_data.config_parameters)

        if layout1_config != layout2_config:
            differences.append(
                f"Config parameters: {layout1_config} → {layout2_config}"
            )

        # Display results
        if not differences:
            print_success_message("No significant differences found")
        else:
            print_success_message(f"Found {len(differences)} difference(s):")
            for diff in differences:
                print_list_item(diff)

    except Exception as e:
        print_error_message(f"Failed to compare layouts: {str(e)}")
        raise typer.Exit(1) from None


def register_commands(app: typer.Typer) -> None:
    """Register layout commands with the main app.

    Args:
        app: The main Typer app
    """
    app.add_typer(layout_app, name="layout")
