"""Core layout CLI commands (compile, decompose, compose, validate, show)."""

import json
import logging
from pathlib import Path
from tempfile import gettempdir, tempdir
from typing import TYPE_CHECKING, Annotated, Any

import typer

from glovebox.cli.commands.layout.base import LayoutOutputCommand
from glovebox.cli.commands.layout.dependencies import create_full_layout_service
from glovebox.cli.decorators import (
    handle_errors,
    with_layout_context,
    with_metrics,
    with_profile,
)
from glovebox.cli.helpers import (
    print_error_message,
    print_list_item,
    print_success_message,
)
from glovebox.cli.helpers.auto_profile import (
    resolve_json_file_path,
    resolve_profile_with_auto_detection,
)
from glovebox.cli.helpers.parameter_factory import ParameterFactory
from glovebox.cli.helpers.parameters import (
    KeyWidthOption,
    LayerOption,
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
@with_profile(required=True, firmware_optional=False, support_auto_detection=True)
@with_metrics("compile")
def compile_layout(
    ctx: typer.Context,
    json_file: ParameterFactory.json_file_argument(),  # type: ignore[valid-type]
    output: ParameterFactory.output_file(  # type: ignore[valid-type]
        help_text="Output directory and base filename (e.g., 'config/my_glove80'). If not specified, generates smart default filenames."
    ) = None,
    profile: ProfileOption = None,
    no_auto: Annotated[
        bool,
        typer.Option(
            "--no-auto",
            help="Disable automatic profile detection from JSON keyboard field",
        ),
    ] = False,
    force: ParameterFactory.force_overwrite() = False,  # type: ignore[valid-type]
    output_format: ParameterFactory.output_format() = "text",  # type: ignore[valid-type]
) -> None:
    """Compile ZMK keymap and config files from a JSON keymap file, library reference, or stdin.

    Takes a JSON layout file (exported from Layout Editor), library reference (@name or @uuid),
    or JSON data from stdin and generates ZMK .keymap and .conf files ready for firmware compilation.

    \\b
    Input sources:
    - File path: glovebox layout compile layout.json
    - Library reference: glovebox layout compile @my-layout-name
    - Library UUID: glovebox layout compile @12345678-1234-1234-1234-123456789abc
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

    * glovebox layout compile @my-gaming-layout  # Compile from library by name

    * glovebox layout compile @12345678-1234-1234-1234-123456789abc  # Compile from library by UUID

    * cat layout.json | glovebox layout compile - --profile glove80/v25.05

    * echo '{"keyboard": "glove80", ...}' | glovebox layout compile -

    * GLOVEBOX_JSON_FILE=layout.json glovebox layout compile -o output/glove80

    * glovebox layout compile layout.json --output output/glove80 --no-auto --profile glove80/v25.05
    """
    command = LayoutOutputCommand()

    # Create composer and execute compilation
    from glovebox.cli.commands.layout.composition import create_layout_command_composer

    composer = create_layout_command_composer()

    def compilation_operation(layout_file: Path) -> dict[str, Any]:
        """Compilation operation that returns structured results."""
        # Handle stdin input or resolve file path
        from glovebox.cli.helpers.stdin_utils import (
            is_stdin_input,
            read_json_input,
            resolve_input_source_with_env,
        )

        # Resolve input source (file, stdin, or environment variable)
        input_source = resolve_input_source_with_env(json_file, "GLOVEBOX_JSON_FILE")

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

        # Profile is already handled by the @with_profile decorator
        keyboard_profile = get_keyboard_profile_from_context(ctx)

        # Ensure keyboard_profile is not None
        if keyboard_profile is None:
            raise ValueError("Keyboard profile is required for compilation")

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
                if resolved_json_file is None:
                    ctx.fail("No JSON file path provided")
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
            if layout_data is None:
                raise ValueError("Layout data should not be None for stdin input")
            result = keymap_service.compile(
                profile=keyboard_profile,
                keymap_data=layout_data,
                output_file_prefix=output_file_prefix_final,
                session_metrics=ctx.obj.session_metrics,
                force=force,
            )
        else:
            # Use file-based service method for file input
            assert resolved_json_file is not None  # Already checked above
            result = keymap_service.generate_from_file(
                profile=keyboard_profile,
                json_file_path=resolved_json_file,
                output_file_prefix=output_file_prefix_final,
                session_metrics=ctx.obj.session_metrics,
                force=force,
            )

        if result.success:
            output_files = result.get_output_files()
            return {
                "success": True,
                "message": "Layout generated successfully",
                "output_files": {k: str(v) for k, v in output_files.items()},
                "messages": result.messages if hasattr(result, "messages") else [],
            }
        else:
            raise ValueError(f"Layout generation failed: {'; '.join(result.errors)}")

    try:
        composer.execute_compilation_operation(
            layout_file=Path("dummy"),  # Not used in compilation operation
            operation=compilation_operation,
            operation_name="compile layout",
            output_format=output_format,
            session_metrics=ctx.obj.session_metrics,
        )
    except Exception as e:
        command.handle_service_error(e, "compile layout")


@handle_errors
@with_layout_context(needs_json=True, needs_profile=True, validate_json=True)
def validate(
    ctx: typer.Context,
    json_file: ParameterFactory.json_file_argument(),  # type: ignore[valid-type]
    profile: ProfileOption = None,
    no_auto: Annotated[
        bool,
        typer.Option(
            "--no-auto",
            help="Disable automatic profile detection from JSON keyboard field",
        ),
    ] = False,
    output_format: ParameterFactory.output_format() = "text",  # type: ignore[valid-type]
) -> None:
    """Validate keymap syntax and structure.

    Validates layout files, library references (@name or @uuid), or stdin input.

    \\b
    Profile precedence (highest to lowest):
    1. CLI --profile flag (overrides all)
    2. Auto-detection from JSON keyboard field (unless --no-auto)
    3. GLOVEBOX_PROFILE environment variable
    4. User config default profile
    5. Hardcoded fallback profile

    Examples:
        # Validate from file
        glovebox layout validate my-layout.json

        # Validate from library by name
        glovebox layout validate @my-gaming-layout

        # Validate from library by UUID
        glovebox layout validate @12345678-1234-1234-1234-123456789abc
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
@with_profile(required=True, firmware_optional=True, support_auto_detection=True)
def show(
    ctx: typer.Context,
    json_file: ParameterFactory.json_file_argument(),  # type: ignore[valid-type]
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
    output_format: ParameterFactory.output_format() = "text",  # type: ignore[valid-type]
) -> None:
    """Display keymap layout in terminal.

    Accepts layout files, library references (@name or @uuid), or stdin input.

    \b
    Profile precedence (highest to lowest):
    1. CLI --profile flag (overrides all)
    2. Auto-detection from JSON keyboard field (unless --no-auto)
    3. GLOVEBOX_PROFILE environment variable
    4. User config default profile
    5. Hardcoded fallback profile

    Examples:
        # Display from file
        glovebox layout show my-layout.json

        # Display from library by name
        glovebox layout show @my-gaming-layout

        # Display from library by UUID
        glovebox layout show @12345678-1234-1234-1234-123456789abc

        # Display specific layer
        glovebox layout show @my-layout --layer 2
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
        # Profile is already handled by the @with_profile decorator
        keyboard_profile = get_keyboard_profile_from_context(ctx)

        # Ensure keyboard_profile is not None
        if keyboard_profile is None:
            raise ValueError("Keyboard profile is required for show command")

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
                        left_row: list[int] = []
                        left_row.extend(row_segments[0])
                        left_row.extend(row_segments[1])
                        all_rows.append(left_row)
                    else:
                        combined_row: list[int] = []
                        for segment in row_segments:
                            combined_row.extend(segment)
                        all_rows.append(combined_row)
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
