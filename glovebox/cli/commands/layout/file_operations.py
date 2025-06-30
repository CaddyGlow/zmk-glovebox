"""Layout file manipulation CLI commands (split, merge, export, import)."""

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from glovebox.cli.commands.layout.base import LayoutOutputCommand
from glovebox.cli.commands.layout.dependencies import create_full_layout_service
from glovebox.cli.decorators import handle_errors, with_metrics, with_profile
from glovebox.cli.helpers.auto_profile import (
    resolve_json_file_path,
    resolve_profile_with_auto_detection,
)
from glovebox.cli.helpers.parameters import (
    JsonFileArgument,
    OutputFormatOption,
    ProfileOption,
)
from glovebox.cli.helpers.profile import (
    create_profile_from_option,
    get_keyboard_profile_from_context,
    get_user_config_from_context,
)
from glovebox.layout.layer import create_layout_layer_service
from glovebox.layout.service import LayoutService


@handle_errors
@with_profile(required=True, firmware_optional=True, support_auto_detection=True)
def split(
    ctx: typer.Context,
    output_dir: Annotated[Path, typer.Argument(help="Directory to save split files")],
    layout_file: JsonFileArgument = None,
    profile: ProfileOption = None,
    no_auto: Annotated[
        bool,
        typer.Option(
            "--no-auto",
            help="Disable automatic profile detection from JSON keyboard field",
        ),
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
    output_format: OutputFormatOption = "text",
) -> None:
    """Split layout into separate component files.

    Breaks down a layout JSON file into individual component files:
    - metadata.json (layout metadata)
    - layers/ directory with individual layer files
    - behaviors.dtsi (custom behaviors, if any)
    - devicetree.dtsi (custom device tree, if any)

    \b
    Profile precedence (highest to lowest):
    1. CLI --profile flag (overrides all)
    2. Auto-detection from JSON keyboard field (unless --no-auto)
    3. GLOVEBOX_PROFILE environment variable
    4. User config default profile
    5. Hardcoded fallback profile

    Examples:
        # Split layout into components with auto-profile detection
        glovebox layout split my-layout.json ./components/

        # Use environment variable for JSON file
        GLOVEBOX_JSON_FILE=layout.json glovebox layout split ./components/

        # Disable auto-detection and specify profile
        glovebox layout split layout.json ./out/ --no-auto --profile glove80/v25.05
    """
    # Resolve JSON file path (supports environment variable)
    resolved_layout_file = resolve_json_file_path(layout_file, "GLOVEBOX_JSON_FILE")

    if resolved_layout_file is None:
        from glovebox.cli.helpers import print_error_message

        print_error_message(
            "Layout file is required. Provide as argument or set GLOVEBOX_JSON_FILE environment variable."
        )
        raise typer.Exit(1)

    command = LayoutOutputCommand()
    command.validate_layout_file(resolved_layout_file)

    try:
        # Profile is already handled by the @with_profile decorator
        keyboard_profile = get_keyboard_profile_from_context(ctx)

        layout_service = create_full_layout_service()

        result = layout_service.split_components_from_file(
            profile=keyboard_profile,
            json_file_path=resolved_layout_file,
            output_dir=output_dir,
            force=force,
        )

        if result.success:
            if output_format.lower() == "json":
                result_data = {
                    "success": True,
                    "source_file": str(resolved_layout_file),
                    "output_directory": str(output_dir),
                    "components_created": result.messages
                    if hasattr(result, "messages")
                    else [],
                }
                command.format_output(result_data, "json")
            else:
                command.print_operation_success(
                    "Layout split into components",
                    {
                        "source": resolved_layout_file,
                        "output_directory": output_dir,
                        "components": "metadata.json, layers/, behaviors, devicetree",
                    },
                )
        else:
            from glovebox.cli.app import AppContext
            from glovebox.cli.helpers import print_error_message, print_list_item
            from glovebox.cli.helpers.theme import get_icon_mode_from_context

            icon_mode = get_icon_mode_from_context(ctx)

            print_error_message("Layout split failed", icon_mode=icon_mode)
            for error in result.errors:
                print_list_item(error, icon_mode=icon_mode)
            raise typer.Exit(1)

    except Exception as e:
        command.handle_service_error(e, "split layout")


@handle_errors
@with_profile(default_profile="glove80/v25.05", required=True, firmware_optional=True)
@with_metrics("merge")
def merge(
    ctx: typer.Context,
    input_dir: Annotated[
        Path,
        typer.Argument(help="Directory with metadata.json and layers/ subdirectory"),
    ],
    output_file: Annotated[Path, typer.Argument(help="Output layout JSON file path")],
    profile: ProfileOption = None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
    output_format: OutputFormatOption = "text",
) -> None:
    """Merge component files into a single layout JSON file.

    Combines component files (created by split) back into a complete layout:
    - Reads metadata.json for layout metadata
    - Combines all files in layers/ directory
    - Includes custom behaviors and device tree if present

    This was previously called 'compose' but renamed for clarity.

    Examples:
        # Merge components back into layout
        glovebox layout merge ./components/ merged-layout.json

        # Force overwrite existing output file
        glovebox layout merge ./split/ layout.json --force

        # Specify keyboard profile
        glovebox layout merge ./components/ layout.json --profile glove80/v25.05
    """
    command = LayoutOutputCommand()

    try:
        layout_service = create_full_layout_service()
        keyboard_profile = get_keyboard_profile_from_context(ctx)

        result = layout_service.compile_from_directory(
            profile=keyboard_profile,
            components_dir=input_dir,
            output_file_prefix=output_file,
            session_metrics=ctx.obj.session_metrics,
            force=force,
        )

        if result.success:
            if output_format.lower() == "json":
                result_data = {
                    "success": True,
                    "source_directory": str(input_dir),
                    "output_file": str(output_file),
                    "components_merged": result.messages
                    if hasattr(result, "messages")
                    else [],
                }
                command.format_output(result_data, "json")
            else:
                command.print_operation_success(
                    "Components merged into layout",
                    {
                        "source_directory": input_dir,
                        "output_file": output_file,
                        "status": "Layout file created successfully",
                    },
                )
        else:
            from glovebox.cli.helpers import print_error_message, print_list_item
            from glovebox.cli.helpers.theme import get_icon_mode_from_context

            icon_mode = get_icon_mode_from_context(ctx)

            print_error_message("Layout merge failed", icon_mode=icon_mode)
            for error in result.errors:
                print_list_item(error, icon_mode=icon_mode)
            raise typer.Exit(1)

    except Exception as e:
        command.handle_service_error(e, "merge layout")
