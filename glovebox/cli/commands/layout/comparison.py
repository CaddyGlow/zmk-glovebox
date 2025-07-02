"""Layout comparison CLI commands."""

from pathlib import Path
from typing import Annotated, Any, TypeAlias

import typer

from glovebox.adapters import create_file_adapter
from glovebox.cli.commands.layout.base import LayoutOutputCommand
from glovebox.cli.decorators import handle_errors, with_metrics
from glovebox.cli.helpers.auto_profile import resolve_json_file_path
from glovebox.cli.helpers.library_resolver import resolve_parameter_value
from glovebox.cli.helpers.parameter_factory import ParameterFactory
from glovebox.cli.helpers.parameters import ProfileOption
from glovebox.layout.comparison import create_layout_comparison_service


@handle_errors
@with_metrics("diff")
def diff(
    ctx: typer.Context,
    layout2: ParameterFactory.input_file_with_stdin_optional(  # type: ignore[valid-type]
        help_text="Second layout file to compare or @library-name/uuid",
        library_resolvable=True
    ),
    layout1: ParameterFactory.input_file_with_stdin_optional(  # type: ignore[valid-type]
        env_var="GLOVEBOX_JSON_FILE",
        help_text="First layout file to compare or @library-name/uuid",
        library_resolvable=True
    ),
    output_format: ParameterFactory.output_format() = "text",  # type: ignore[valid-type]
    detailed: Annotated[
        bool,
        typer.Option("--detailed", help="Show detailed key changes within layers"),
    ] = False,
    include_dtsi: Annotated[
        bool,
        typer.Option(
            "--include-dtsi", help="Include custom DTSI fields in diff output"
        ),
    ] = False,
    output: ParameterFactory.output_file_path_only(  # type: ignore[valid-type]
        help_text="Create LayoutDiff patch file for later application"
    ) = None,
    patch_section: Annotated[
        str,
        typer.Option(
            "--patch-section",
            help="DTSI section for patch: behaviors, devicetree, or both",
        ),
    ] = "both",
) -> None:
    """Compare two layouts showing differences with optional patch creation.

    Shows differences between two layout files, focusing on layers,
    behaviors, custom DTSI code, and configuration changes. Can also
    create LayoutDiff patch files for later application.

    The first layout file can be provided as an argument or via the
    GLOVEBOX_JSON_FILE environment variable for convenience.

    Output Formats:
        text     - Summary with change counts (default)
        json     - LayoutDiff structure for automation/patching
        table    - Tabular view of changes
    Use --detailed to show individual key differences within layers.
    Use --include-dtsi to include custom DTSI fields in diffs.

    Examples:
        # Basic comparison showing layer and config changes
        glovebox layout diff my-layout-v42.json my-layout-v41.json

        # Using environment variable for first layout
        export GLOVEBOX_JSON_FILE=my-layout.json
        glovebox layout diff my-layout-v42.json

        # Detailed view with individual key differences
        glovebox layout diff layout2.json layout1.json --detailed

        # Include custom DTSI code differences
        glovebox layout diff layout2.json layout1.json --include-dtsi

        # Create diff file for later patching
        glovebox layout diff new.json old.json --output changes.json

        # JSON output with LayoutDiff structure
        glovebox layout diff layout2.json layout1.json --output-format json

        # Detailed comparison with DTSI and diff file creation
        glovebox layout diff layout2.json layout1.json --detailed --include-dtsi --output changes.json

        # Compare your custom layout with a master version
        glovebox layout diff my-custom.json ~/.glovebox/masters/glove80/v42-rc3.json --detailed
    """
    # Resolve library references for both layout files
    try:
        # Resolve layout1 (supports environment variable and library references)
        resolved_layout1_param = resolve_parameter_value(layout1) if layout1 else None
        if resolved_layout1_param is None:
            # Try environment variable fallback
            resolved_layout1_param = resolve_json_file_path(layout1, "GLOVEBOX_JSON_FILE")

        if resolved_layout1_param is None:
            from glovebox.cli.helpers import print_error_message

            print_error_message(
                "First layout file is required. Provide as argument or set GLOVEBOX_JSON_FILE environment variable."
            )
            raise typer.Exit(1)

        # Convert to Path if it's a string
        if isinstance(resolved_layout1_param, Path):
            resolved_layout1 = resolved_layout1_param
        else:
            resolved_layout1 = Path(resolved_layout1_param)

        # Resolve layout2 (library references)
        resolved_layout2_param = resolve_parameter_value(layout2)
        if isinstance(resolved_layout2_param, Path):
            resolved_layout2 = resolved_layout2_param
        else:
            resolved_layout2 = Path(resolved_layout2_param) if resolved_layout2_param else None

        if resolved_layout2 is None:
            from glovebox.cli.helpers import print_error_message

            print_error_message(f"Second layout file not found: {layout2}")
            raise typer.Exit(1)

    except Exception as e:
        from glovebox.cli.helpers import print_error_message

        print_error_message(f"Error resolving layout files: {e}")
        raise typer.Exit(1) from e

    # Validate layout files
    command = LayoutOutputCommand()
    command.validate_layout_file(resolved_layout1)
    command.validate_layout_file(resolved_layout2)

    # Create composer and execute comparison
    from glovebox.cli.commands.layout.composition import create_layout_command_composer

    # Get icon mode from context for proper display
    from glovebox.cli.helpers.theme import get_icon_mode_from_context

    icon_mode = get_icon_mode_from_context(ctx)

    composer = create_layout_command_composer(icon_mode)

    def comparison_operation(file1: Path, file2: Path) -> dict[str, Any]:
        """Comparison operation that returns structured results."""
        from glovebox.cli.helpers.profile import get_user_config_from_context
        from glovebox.config import create_user_config

        user_config = get_user_config_from_context(ctx) or create_user_config()
        file_adapter = create_file_adapter()
        comparison_service = create_layout_comparison_service(user_config, file_adapter)

        result = comparison_service.compare_layouts(
            layout1_path=file1,
            layout2_path=file2,
            output_format=output_format,
            include_dtsi=include_dtsi,
            detailed=detailed,
        )

        # Handle diff file creation if requested
        if output:
            try:
                patch_result = comparison_service.create_diff_file(
                    layout1_path=file1,
                    layout2_path=file2,
                    output_path=output,
                    include_dtsi=include_dtsi,
                )
                result["diff_file_created"] = patch_result
            except Exception as e:
                result["diff_file_error"] = str(e)

        return result

    composer.execute_comparison_operation(
        file1=resolved_layout1,
        file2=resolved_layout2,
        operation=comparison_operation,
        operation_name="compare layouts",
        output_format=output_format,
    )


@handle_errors
@with_metrics("patch")
def patch(
    ctx: typer.Context,
    layout_file: ParameterFactory.input_file_with_stdin_optional(  # type: ignore[valid-type]
        help_text="Source layout file to patch or @library-name/uuid",
        library_resolvable=True
    ),
    patch_file: ParameterFactory.input_file_with_stdin_optional(  # type: ignore[valid-type]
        help_text="JSON diff file from 'glovebox layout diff --output changes.json' or @library-name/uuid",
        library_resolvable=True
    ),
    output: ParameterFactory.output_file_path_only(  # type: ignore[valid-type]
        help_text="Output path (default: source_layout with -patched suffix)"
    ) = None,
    force: ParameterFactory.force_overwrite() = False,  # type: ignore[valid-type]
    exclude_dtsi: Annotated[
        bool,
        typer.Option(
            "--exclude-dtsi", help="Exclude DTSI changes even if present in patch"
        ),
    ] = False,
) -> None:
    """Apply a JSON diff patch to transform a layout.

    Takes a source layout and applies changes from a JSON diff file
    (generated by 'glovebox layout diff --output changes.json') to create
    a new transformed layout.

    Examples:
        # Generate a diff
        glovebox layout diff old.json new.json --output changes.json

        # Apply the diff to transform another layout
        glovebox layout patch my-layout.json changes.json --output patched-layout.json

        # Apply diff with auto-generated output name
        glovebox layout patch my-layout.json changes.json
    """
    # Resolve library references for both files
    try:
        # Resolve layout_file (library references)
        resolved_layout_param = resolve_parameter_value(layout_file)
        if isinstance(resolved_layout_param, Path):
            resolved_layout_file = resolved_layout_param
        else:
            resolved_layout_file = Path(resolved_layout_param) if resolved_layout_param else None

        if resolved_layout_file is None:
            from glovebox.cli.helpers import print_error_message

            print_error_message(f"Layout file not found: {layout_file}")
            raise typer.Exit(1)

        # Resolve patch_file (library references)
        resolved_patch_param = resolve_parameter_value(patch_file)
        if isinstance(resolved_patch_param, Path):
            resolved_patch_file = resolved_patch_param
        else:
            resolved_patch_file = Path(resolved_patch_param) if resolved_patch_param else None

        if resolved_patch_file is None:
            from glovebox.cli.helpers import print_error_message

            print_error_message(f"Patch file not found: {patch_file}")
            raise typer.Exit(1)

    except Exception as e:
        from glovebox.cli.helpers import print_error_message

        print_error_message(f"Error resolving files: {e}")
        raise typer.Exit(1) from e

    command = LayoutOutputCommand()
    command.validate_layout_file(resolved_layout_file)

    try:
        from glovebox.cli.helpers.profile import get_user_config_from_context
        from glovebox.config import create_user_config

        user_config = get_user_config_from_context(ctx) or create_user_config()
        file_adapter = create_file_adapter()
        comparison_service = create_layout_comparison_service(user_config, file_adapter)
        result = comparison_service.apply_patch(
            source_layout_path=resolved_layout_file,
            patch_file_path=resolved_patch_file,
            output=output,
            force=force,
            skip_dtsi=exclude_dtsi,
        )

        # Show success with details
        command.print_operation_success(
            "Applied patch successfully",
            {
                "source": result["source"],
                "patch": result["patch"],
                "output": result["output"],
                # "applied_changes": result["total_changes"],
            },
        )

    except Exception as e:
        command.handle_service_error(e, "apply patch")
