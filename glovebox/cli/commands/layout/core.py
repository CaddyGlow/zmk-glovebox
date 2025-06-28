"""Core layout CLI commands (compile, decompose, compose, validate, show)."""

import json
import logging
from pathlib import Path
from tempfile import gettempdir, tempdir
from typing import TYPE_CHECKING, Annotated, Any

import typer

from glovebox.cli.commands.layout.base import LayoutOutputCommand
from glovebox.cli.commands.layout.dependencies import create_full_layout_service
from glovebox.cli.decorators import handle_errors, with_layout_context, with_profile
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
from glovebox.config.profile import KeyboardProfile
from glovebox.layout.formatting import ViewMode
from glovebox.layout.service import LayoutService


logger = logging.getLogger(__name__)


@handle_errors
def compile_layout(
    ctx: typer.Context,
    json_file: JsonFileArgument = None,
    output: Annotated[
        str | None,
        typer.Option(
            "-o",
            "--output",
            help="Output directory and base filename (e.g., 'config/my_glove80'). If not specified, generates smart default filenames.",
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
    """Compile ZMK keymap and config files from a JSON keymap file or stdin.

    Takes a JSON layout file (exported from Layout Editor) or JSON data from stdin
    and generates ZMK .keymap and .conf files ready for firmware compilation.

    \\b
    Input sources:
    - File path: glovebox layout compile layout.json
    - Stdin: glovebox layout compile - (or pipe: cat layout.json | glovebox layout compile -)
    - Environment: GLOVEBOX_JSON_FILE=layout.json glovebox layout compile

    \\b
    Profile precedence (highest to lowest):
    1. CLI --profile flag (overrides all)
    2. Auto-detection from JSON keyboard field (unless --no-auto)
    3. GLOVEBOX_PROFILE environment variable
    4. User config default profile
    5. Hardcoded fallback profile

    Examples:

    * glovebox layout compile layout.json -o output/glove80 --profile glove80/v25.05

    * glovebox layout compile layout.json  # Generate smart default filenames

    * cat layout.json | glovebox layout compile - --profile glove80/v25.05

    * echo '{"keyboard": "glove80", ...}' | glovebox layout compile -

    * GLOVEBOX_JSON_FILE=layout.json glovebox layout compile -o output/glove80

    * glovebox layout compile layout.json --output output/glove80 --no-auto --profile glove80/v25.05
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

    metrics.Summary("compile_start", "Start to start compilation")

    # Create composer and execute compilation
    from glovebox.cli.commands.layout.composition import create_layout_command_composer

    composer = create_layout_command_composer()

    def compilation_operation(layout_file: Path) -> dict[str, Any]:
        """Compilation operation that returns structured results."""
        with layout_duration.time():
            # Handle stdin input or resolve file path
            from glovebox.cli.helpers.stdin_utils import (
                is_stdin_input,
                read_json_input,
                resolve_input_source_with_env,
            )

            # Resolve input source (file, stdin, or environment variable)
            input_source = resolve_input_source_with_env(
                json_file, "GLOVEBOX_JSON_FILE"
            )

            if input_source is None:
                raise ValueError(
                    "JSON input is required. Provide file path, '-' for stdin, or set GLOVEBOX_JSON_FILE environment variable."
                )

            # Determine if we're reading from stdin or file
            using_stdin = is_stdin_input(input_source)

            if using_stdin:
                # Read JSON data from stdin
                layout_dict = read_json_input(input_source)

                # Convert to LayoutData object
                from glovebox.layout.models import LayoutData

                layout_data = LayoutData.model_validate(layout_dict)

                # We don't have a real file path for stdin, use a dummy path for profile resolution
                resolved_json_file = None

            else:
                # Handle file input (existing behavior)
                resolved_json_file = resolve_json_file_path(
                    input_source, "GLOVEBOX_JSON_FILE"
                )

                if resolved_json_file is None:
                    raise ValueError(f"JSON file not found: {input_source}")

                layout_data = None  # Will be loaded by file-based service method

            # Use unified profile resolution with auto-detection support
            from glovebox.cli.helpers.parameters import (
                create_profile_from_param_unified,
            )

            # For stdin input, auto-detection can use the layout_data, for file input use the file path
            if using_stdin:
                # For stdin, we can try auto-detection from the loaded layout data
                json_file_for_profile = None
                # Create a temporary data dict for auto-detection if needed
                profile_auto_data = layout_dict if not no_auto else None
            else:
                json_file_for_profile = resolved_json_file
                profile_auto_data = None

            keyboard_profile = create_profile_from_param_unified(
                ctx=ctx,
                profile=profile,
                default_profile="glove80/v25.05",
                json_file=json_file_for_profile,
                no_auto=no_auto,
                # TODO: Add support for auto-detection from data dict in the profile utility
            )

            # Generate smart output prefix if not provided
            if output is not None:
                output_file_prefix_final = output
            else:
                # Use filename generation utility for smart defaults
                from glovebox.cli.helpers.profile import get_user_config_from_context
                from glovebox.cli.helpers.stdin_utils import (
                    get_input_filename_for_templates,
                )
                from glovebox.config import create_user_config
                from glovebox.utils.filename_generator import (
                    FileType,
                    generate_default_filename,
                )
                from glovebox.utils.filename_helpers import (
                    extract_layout_dict_data,
                    extract_profile_data,
                )

                user_config = get_user_config_from_context(ctx) or create_user_config()
                profile_data = extract_profile_data(keyboard_profile)

                # Get layout data for filename generation
                if using_stdin:
                    # Use the already-loaded layout data from stdin
                    filename_layout_data = extract_layout_dict_data(layout_dict)
                    original_filename = None  # No original filename for stdin
                else:
                    # Read layout data from file
                    try:
                        import json

                        with resolved_json_file.open() as f:
                            file_layout_dict = json.load(f)
                            filename_layout_data = extract_layout_dict_data(
                                file_layout_dict
                            )
                        original_filename = str(resolved_json_file)
                    except Exception:
                        # Fall back to basic data
                        filename_layout_data = {
                            "title": resolved_json_file.stem
                            if resolved_json_file
                            else "layout"
                        }
                        original_filename = (
                            str(resolved_json_file) if resolved_json_file else None
                        )

                # Generate keymap filename (without extension)
                keymap_filename = generate_default_filename(
                    FileType.KEYMAP,
                    user_config._config.filename_templates,
                    layout_data=filename_layout_data,
                    profile_data=profile_data,
                    original_filename=original_filename,
                )

                # Use the stem as output prefix
                output_file_prefix_final = Path(keymap_filename).stem

            # Generate keymap using appropriate service method
            keymap_service = create_full_layout_service()

            if using_stdin:
                # Use data-based service method for stdin input
                result = keymap_service.compile(
                    profile=keyboard_profile,
                    keymap_data=layout_data,
                    output_file_prefix=output_file_prefix_final,
                    session_metrics=metrics,
                    force=force,
                )
            else:
                # Use file-based service method for file input
                result = keymap_service.generate_from_file(
                    profile=keyboard_profile,
                    json_file_path=resolved_json_file,
                    output_file_prefix=output_file_prefix_final,
                    session_metrics=metrics,
                    force=force,
                )

            if result.success:
                # Track successful compilation
                layout_counter.labels("compile", "success").inc()

                output_files = result.get_output_files()
                return {
                    "success": True,
                    "message": "Layout generated successfully",
                    "output_files": {k: str(v) for k, v in output_files.items()},
                    "messages": result.messages if hasattr(result, "messages") else [],
                }
            else:
                # Track failed compilation
                layout_counter.labels("compile", "failure").inc()

                raise ValueError(
                    f"Layout generation failed: {'; '.join(result.errors)}"
                )

    try:
        composer.execute_compilation_operation(
            layout_file=Path("dummy"),  # Not used in compilation operation
            operation=compilation_operation,
            operation_name="compile layout",
            output_format=output_format,
            session_metrics=metrics,
        )
    except Exception as e:
        # Track exception errors
        layout_counter.labels("compile", "error").inc()
        command.handle_service_error(e, "compile layout")


@handle_errors
@with_layout_context(needs_json=True, needs_profile=True, validate_json=True)
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

    \\b
    Profile precedence (highest to lowest):
    1. CLI --profile flag (overrides all)
    2. Auto-detection from JSON keyboard field (unless --no-auto)
    3. GLOVEBOX_PROFILE environment variable
    4. User config default profile
    5. Hardcoded fallback profile
    """
    # Get values injected by the decorator from context
    resolved_json_file = ctx.meta.get("resolved_json_file")
    keyboard_profile = ctx.meta.get("keyboard_profile")

    # These are guaranteed to be non-None by the decorator
    assert resolved_json_file is not None
    assert keyboard_profile is not None

    # Create composer and execute validation
    from glovebox.cli.commands.layout.composition import create_layout_command_composer

    composer = create_layout_command_composer()

    def validation_operation(layout_file: Path) -> dict[str, Any]:
        """Validation operation that returns structured results."""
        keymap_service = create_full_layout_service()

        try:
            is_valid = keymap_service.validate_from_file(
                profile=keyboard_profile, json_file_path=layout_file
            )
            return {
                "valid": is_valid,
                "file": str(layout_file),
                "errors": [] if is_valid else ["Validation failed"],
            }
        except Exception as e:
            return {"valid": False, "file": str(layout_file), "errors": [str(e)]}

    composer.execute_validation_operation(
        layout_file=resolved_json_file,
        operation=validation_operation,
        operation_name="validate layout",
        output_format=output_format,
    )


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
        # Use unified profile resolution with auto-detection support
        from glovebox.cli.helpers.parameters import create_profile_from_param_unified

        keyboard_profile = create_profile_from_param_unified(
            ctx=ctx,
            profile=profile,
            default_profile="glove80/v25.05",
            json_file=resolved_json_file,
            no_auto=no_auto,
        )

        # Call the service
        keymap_service = create_full_layout_service()

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
