"""Core layout CLI commands (compile, decompose, compose, validate, show)."""

import json
import logging
from pathlib import Path
from typing import Annotated

import typer

from glovebox.cli.commands.layout.base import LayoutOutputCommand
from glovebox.cli.decorators import handle_errors, with_profile
from glovebox.cli.helpers import (
    print_error_message,
    print_list_item,
    print_success_message,
)
from glovebox.cli.helpers.auto_profile import (
    resolve_json_file_path,
    resolve_profile_with_auto_detection,
)
from glovebox.cli.helpers.parameters import OutputFormatOption, ProfileOption
from glovebox.cli.helpers.profile import (
    create_profile_from_option,
    get_keyboard_profile_from_context,
    get_user_config_from_context,
)
from glovebox.layout.formatting import ViewMode
from glovebox.layout.service import create_layout_service


logger = logging.getLogger(__name__)


@handle_errors
def compile_layout(
    ctx: typer.Context,
    output_file_prefix: Annotated[
        str,
        typer.Argument(
            help="Output directory and base filename (e.g., 'config/my_glove80')"
        ),
    ],
    json_file: Annotated[
        str | None,
        typer.Argument(help="Path to keymap JSON file. Can use GLOVEBOX_JSON_FILE env var."),
    ] = None,
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
    """Compile ZMK keymap and config files from a JSON keymap file.

    Takes a JSON layout file (exported from Layout Editor) and generates
    ZMK .keymap and .conf files ready for firmware compilation.

    \b
    Profile precedence (highest to lowest):
    1. CLI --profile flag (overrides all)
    2. Auto-detection from JSON keyboard field (unless --no-auto)
    3. GLOVEBOX_PROFILE environment variable
    4. User config default profile
    5. Hardcoded fallback profile

    Examples:

    * glovebox layout compile layout.json output/glove80 --profile glove80/v25.05

    * glovebox layout compile layout.json output/glove80  # Auto-detect profile from JSON

    * GLOVEBOX_JSON_FILE=layout.json glovebox layout compile output/glove80

    * glovebox layout compile layout.json output/glove80 --no-auto --profile glove80/v25.05
    """
    command = LayoutOutputCommand()

    # Access session metrics from CLI context
    from glovebox.cli.app import AppContext

    app_ctx: AppContext = ctx.obj
    metrics = app_ctx.session_metrics

    # Track layout compilation metrics
    layout_counter = metrics.Counter(
        "layout_operations_total", "Total layout operations", ["operation", "status"]
    )
    layout_duration = metrics.Histogram(
        "layout_operation_duration_seconds", "Layout operation duration"
    )

    try:
        with layout_duration.time():
            # Get user config for auto-profile detection
            user_config = get_user_config_from_context(ctx)

            # Resolve JSON file path (supports environment variable)
            resolved_json_file = resolve_json_file_path(json_file, "GLOVEBOX_JSON_FILE")

            if resolved_json_file is None:
                print_error_message(
                    "JSON file is required. Provide as argument or set GLOVEBOX_JSON_FILE environment variable."
                )
                raise typer.Exit(1)

            # Handle profile detection with auto-detection support
            effective_profile = resolve_profile_with_auto_detection(
                profile, resolved_json_file, no_auto, user_config
            )

            # Create keyboard profile using effective profile
            keyboard_profile = create_profile_from_option(effective_profile, user_config)

            # Generate keymap using the file-based service method
            keymap_service = create_layout_service()

            result = keymap_service.generate_from_file(
                profile=keyboard_profile,
                json_file_path=resolved_json_file,
                output_file_prefix=output_file_prefix,
                force=force,
            )

        if result.success:
            # Track successful compilation
            layout_counter.labels("compile", "success").inc()

            if output_format.lower() == "json":
                # JSON output for automation
                output_files = result.get_output_files()
                result_data = {
                    "success": True,
                    "message": "Layout generated successfully",
                    "output_files": {k: str(v) for k, v in output_files.items()},
                    "messages": result.messages if hasattr(result, "messages") else [],
                }
                command.format_output(result_data, "json")
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
                    command.format_output(file_data, "table")
                else:
                    # Text format (default)
                    for file_type, file_path in output_files.items():
                        print_list_item(f"{file_type}: {file_path}")
        else:
            # Track failed compilation
            layout_counter.labels("compile", "failure").inc()

            print_error_message("Layout generation failed")
            for error in result.errors:
                print_list_item(error)
            raise typer.Exit(1)

    except Exception as e:
        # Track exception errors
        layout_counter.labels("compile", "error").inc()
        command.handle_service_error(e, "compile layout")


@handle_errors
def validate(
    ctx: typer.Context,
    json_file: Annotated[
        str | None, typer.Argument(help="Path to keymap JSON file. Can use GLOVEBOX_JSON_FILE env var.")
    ] = None,
    profile: ProfileOption = None,
    no_auto: Annotated[
        bool,
        typer.Option(
            "--no-auto",
            help="Disable automatic profile detection from JSON keyboard field",
        ),
    ] = False,
    output_format: OutputFormatOption = "text",
) -> None:
    """Validate keymap syntax and structure.

    \b
    Profile precedence (highest to lowest):
    1. CLI --profile flag (overrides all)
    2. Auto-detection from JSON keyboard field (unless --no-auto)
    3. GLOVEBOX_PROFILE environment variable
    4. User config default profile
    5. Hardcoded fallback profile
    """
    # Get user config for auto-profile detection
    user_config = get_user_config_from_context(ctx)

    # Resolve JSON file path (supports environment variable)
    resolved_json_file = resolve_json_file_path(json_file, "GLOVEBOX_JSON_FILE")

    if resolved_json_file is None:
        print_error_message(
            "JSON file is required. Provide as argument or set GLOVEBOX_JSON_FILE environment variable."
        )
        raise typer.Exit(1)

    command = LayoutOutputCommand()
    command.validate_layout_file(resolved_json_file)

    try:
        # Handle profile detection with auto-detection support
        effective_profile = resolve_profile_with_auto_detection(
            profile, resolved_json_file, no_auto, user_config
        )

        # Create keyboard profile using effective profile
        keyboard_profile = create_profile_from_option(effective_profile, user_config)

        # Validate using the file-based service method
        keymap_service = create_layout_service()

        if keymap_service.validate_from_file(
            profile=keyboard_profile, json_file_path=resolved_json_file
        ):
            print_success_message(f"Layout file {resolved_json_file} is valid")
        else:
            print_error_message(f"Layout file {resolved_json_file} is invalid")
            raise typer.Exit(1)

    except Exception as e:
        command.handle_service_error(e, "validate layout")


@handle_errors
def show(
    ctx: typer.Context,
    json_file: Annotated[
        str | None, typer.Argument(help="Path to keyboard layout JSON file. Can use GLOVEBOX_JSON_FILE env var.")
    ] = None,
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
        typer.Option(
            "--layout",
            "-l",
            help="Layout name to use for display (NotImplementedError)",
        ),
    ] = None,
    layer: Annotated[
        int | None,
        typer.Option(
            "--layer", help="Show only specific layer index (NotImplementedError)"
        ),
    ] = None,
    profile: ProfileOption = None,
    no_auto: Annotated[
        bool,
        typer.Option(
            "--no-auto",
            help="Disable automatic profile detection from JSON keyboard field",
        ),
    ] = False,
    output_format: OutputFormatOption = "text",
) -> None:
    """Display keymap layout in terminal.

    \b
    Profile precedence (highest to lowest):
    1. CLI --profile flag (overrides all)
    2. Auto-detection from JSON keyboard field (unless --no-auto)
    3. GLOVEBOX_PROFILE environment variable
    4. User config default profile
    5. Hardcoded fallback profile
    """
    # Get user config for auto-profile detection
    user_config = get_user_config_from_context(ctx)

    # Resolve JSON file path (supports environment variable)
    resolved_json_file = resolve_json_file_path(json_file, "GLOVEBOX_JSON_FILE")

    if resolved_json_file is None:
        print_error_message(
            "JSON file is required. Provide as argument or set GLOVEBOX_JSON_FILE environment variable."
        )
        raise typer.Exit(1)

    command = LayoutOutputCommand()
    command.validate_layout_file(resolved_json_file)

    try:
        # Handle profile detection with auto-detection support
        effective_profile = resolve_profile_with_auto_detection(
            profile, resolved_json_file, no_auto, user_config
        )

        # Create keyboard profile using effective profile
        keyboard_profile = create_profile_from_option(effective_profile, user_config)

        # Call the service
        keymap_service = create_layout_service()

        # Get layout data first for formatting
        if output_format.lower() != "text":
            # For non-text formats, load and format the JSON data
            import json
            layout_data = json.loads(resolved_json_file.read_text())
            command.format_output(layout_data, output_format)
        else:
            view_mode_typed = ViewMode.NORMAL

            try:
                if view_mode is not None:
                    view_mode_typed = ViewMode(view_mode.lower())
            except ValueError:
                logger.warning(
                    "Invalid view mode: %s", view_mode.lower() if view_mode else "None"
                )

            # For text format, use the existing show method
            result = keymap_service.show_from_file(
                json_file_path=resolved_json_file,
                profile=keyboard_profile,
                key_width=key_width,
                view_mode=view_mode_typed,
            )
            # The show method returns a string
            typer.echo(result)

    except NotImplementedError as e:
        command.handle_service_error(e, "show layout")
