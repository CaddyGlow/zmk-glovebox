"""Core layout CLI commands (compile, decompose, compose, validate, show)."""

import json
import logging
from pathlib import Path
from tempfile import gettempdir, tempdir
from typing import Annotated

import typer

from glovebox.adapters import create_file_adapter, create_template_adapter
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
from glovebox.cli.helpers.parameters import (
    JsonFileArgument,
    KeyWidthOption,
    LayerOption,
    OutputFormatOption,
    ProfileOption,
    ViewModeOption,
)
from glovebox.cli.helpers.profile import (
    create_profile_from_option,
    get_keyboard_profile_from_context,
    get_user_config_from_context,
)
from glovebox.layout.behavior.formatter import BehaviorFormatterImpl
from glovebox.layout.behavior.service import create_behavior_registry
from glovebox.layout.component_service import create_layout_component_service
from glovebox.layout.display_service import create_layout_display_service
from glovebox.layout.formatting import ViewMode, create_grid_layout_formatter
from glovebox.layout.service import create_layout_service
from glovebox.layout.zmk_generator import ZmkFileContentGenerator


logger = logging.getLogger(__name__)


def _create_layout_service_with_dependencies():
    """Create a layout service with all required dependencies."""
    file_adapter = create_file_adapter()
    template_adapter = create_template_adapter()
    behavior_registry = create_behavior_registry()
    behavior_formatter = BehaviorFormatterImpl(behavior_registry)
    dtsi_generator = ZmkFileContentGenerator(behavior_formatter)
    layout_generator = create_grid_layout_formatter()
    component_service = create_layout_component_service(file_adapter)
    layout_display_service = create_layout_display_service(layout_generator)

    return create_layout_service(
        file_adapter=file_adapter,
        template_adapter=template_adapter,
        behavior_registry=behavior_registry,
        component_service=component_service,
        layout_service=layout_display_service,
        behavior_formatter=behavior_formatter,
        dtsi_generator=dtsi_generator,
    )


@handle_errors
def compile_layout(
    ctx: typer.Context,
    json_file: JsonFileArgument = None,
    output_file_prefix: Annotated[
        str | None,
        typer.Argument(
            help="Output directory and base filename (e.g., 'config/my_glove80')"
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
            keyboard_profile = create_profile_from_option(
                effective_profile, user_config
            )
            if output_file_prefix is None and json_file is not None:
                output_file_prefix = Path(json_file).stem + "_"
            else:
                tmp_dir = gettempdir()
                output_file_prefix = str(Path(tmp_dir) / keyboard_profile.keyboard_name)

            # Generate keymap using the file-based service method
            keymap_service = _create_layout_service_with_dependencies()

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
    json_file: JsonFileArgument = None,
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
        keymap_service = _create_layout_service_with_dependencies()

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
    json_file: JsonFileArgument = None,
    key_width: KeyWidthOption = 10,
    view_mode: ViewModeOption = None,
    layout: Annotated[
        str | None,
        typer.Option(
            "--layout",
            "-l",
            help="Layout name to use for display",
        ),
    ] = None,
    layer: LayerOption = None,
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
        keymap_service = _create_layout_service_with_dependencies()

        # Resolve layer parameter (can be index or name)
        resolved_layer_index = None
        if layer is not None:
            if layer.isdigit():
                # Numeric input - treat as layer index
                resolved_layer_index = int(layer)
            else:
                # String input - resolve layer name to index
                import json

                raw_layout_data = json.loads(resolved_json_file.read_text())
                layer_names = raw_layout_data.get("layer_names", [])

                # Case-insensitive search for layer name
                layer_lower = layer.lower()
                for i, name in enumerate(layer_names):
                    if name.lower() == layer_lower:
                        resolved_layer_index = i
                        break

                if resolved_layer_index is None:
                    print_error_message(
                        f"Layer '{layer}' not found. Available layers: {', '.join(layer_names)}"
                    )
                    raise typer.Exit(1)

        # Check if Rich format is requested
        if output_format.lower().startswith("rich"):
            # Use Rich formatter for enhanced display
            import json

            from glovebox.layout.formatting import LayoutConfig

            # Load and parse layout data into proper models
            from glovebox.layout.models import LayoutData
            from glovebox.layout.rich_formatter import create_rich_layout_formatter

            raw_layout_data = json.loads(resolved_json_file.read_text())
            # Parse into LayoutData model to get proper LayoutBinding objects
            layout_data = LayoutData.model_validate(raw_layout_data)

            # Create layout config from keyboard profile
            display_config = keyboard_profile.keyboard_config.display
            keymap_formatting = keyboard_profile.keyboard_config.keymap.formatting

            # Determine row structure (same logic as display_service.py)
            if keymap_formatting.rows is not None:
                all_rows = keymap_formatting.rows
            elif display_config.layout_structure is not None:
                layout_structure = display_config.layout_structure
                all_rows = []
                for row_segments in layout_structure.rows.values():
                    if len(row_segments) == 2:
                        row = []
                        row.extend(row_segments[0])
                        row.extend(row_segments[1])
                        all_rows.append(row)
                    else:
                        row = []
                        for segment in row_segments:
                            row.extend(segment)
                        all_rows.append(row)
            else:
                # Default layout rows
                all_rows = [
                    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                    [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21],
                    [22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33],
                    [34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45],
                ]

            layout_config = LayoutConfig(
                keyboard_name=keyboard_profile.keyboard_config.keyboard,
                key_width=key_width,
                key_gap=keymap_formatting.key_gap,
                key_position_map={},
                total_keys=keyboard_profile.keyboard_config.key_count,
                key_count=keyboard_profile.keyboard_config.key_count,
                rows=all_rows,
                formatting={
                    "key_gap": keymap_formatting.key_gap,
                    "base_indent": keymap_formatting.base_indent,
                },
            )

            # Create Rich formatter and render
            rich_formatter = create_rich_layout_formatter()
            rich_formatter.format_keymap_display(
                layout_data,
                layout_config,
                format_type=output_format.lower(),
                layer_index=resolved_layer_index,
            )
        elif output_format.lower() != "text":
            # For other non-text formats, load and format the JSON data
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
                layer_index=resolved_layer_index,
            )
            # The show method returns a string
            typer.echo(result)

    except Exception as e:
        command.handle_service_error(e, "show layout")
