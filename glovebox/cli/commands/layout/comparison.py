"""Layout comparison CLI commands."""

from pathlib import Path
from typing import Annotated, Any

import typer

from glovebox.adapters import create_file_adapter
from glovebox.cli.commands.layout.base import LayoutOutputCommand
from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers.auto_profile import resolve_json_file_path
from glovebox.cli.helpers.parameters import OutputFormatOption, ProfileOption
from glovebox.layout.comparison import create_layout_comparison_service


@handle_errors
def diff(
    ctx: typer.Context,
    layout2: Annotated[Path, typer.Argument(help="Second layout file to compare")],
    layout1: Annotated[
        Path | None,
        typer.Argument(
            help="First layout file to compare. Uses GLOVEBOX_JSON_FILE environment variable if not provided."
        ),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            help="Output format: summary (default), detailed, dtsi, pretty, or json",
        ),
    ] = "summary",
    compare_dtsi: Annotated[
        bool,
        typer.Option(
            "--compare-dtsi", help="Include detailed custom DTSI code comparison"
        ),
    ] = False,
    output_patch: Annotated[
        Path | None,
        typer.Option(
            "--output-patch",
            help="Create unified diff patch file for DTSI sections",
        ),
    ] = None,
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
    create unified diff patch files for DTSI sections.

    The first layout file can be provided as an argument or via the
    GLOVEBOX_JSON_FILE environment variable for convenience.

    Output Formats:
        summary  - Basic difference counts (default)
        detailed - Individual key differences within layers
        dtsi     - Detailed DTSI code differences with unified diff
        pretty   - Human-readable DeepDiff output
        json     - Structured data with exact key changes for automation

    The --compare-dtsi flag enables detailed custom DTSI code comparison
    for any output format. The --output-patch option creates a unified
    diff patch file (replaces the old create-patch command).

    Examples:
        # Basic comparison showing layer and config changes
        glovebox layout diff my-layout-v42.json my-layout-v41.json

        # Using environment variable for first layout
        export GLOVEBOX_JSON_FILE=my-layout.json
        glovebox layout diff my-layout-v42.json

        # Detailed view with individual key differences
        glovebox layout diff layout2.json layout1.json --format detailed

        # Include custom DTSI code differences
        glovebox layout diff layout2.json layout1.json --compare-dtsi

        # Create patch file for DTSI sections
        glovebox layout diff new.json old.json --output-patch changes.patch

        # Create patch for specific DTSI section
        glovebox layout diff new.json old.json --output-patch behaviors.patch --patch-section behaviors

        # JSON output with structured key change data
        glovebox layout diff layout2.json layout1.json --format json

        # Compare and create patch in one command
        glovebox layout diff layout2.json layout1.json --format detailed --output-patch changes.patch

        # Compare your custom layout with a master version
        glovebox layout diff my-custom.json ~/.glovebox/masters/glove80/v42-rc3.json --format detailed
    """
    # Resolve first layout file path (supports environment variable)
    resolved_layout1 = resolve_json_file_path(layout1, "GLOVEBOX_JSON_FILE")

    if resolved_layout1 is None:
        from glovebox.cli.helpers import print_error_message

        print_error_message(
            "First layout file is required. Provide as argument or set GLOVEBOX_JSON_FILE environment variable."
        )
        raise typer.Exit(1)

    # Validate layout files
    command = LayoutOutputCommand()
    command.validate_layout_file(resolved_layout1)
    command.validate_layout_file(layout2)

    # Create composer and execute comparison
    from glovebox.cli.commands.layout.composition import create_layout_command_composer

    composer = create_layout_command_composer()

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
            compare_dtsi=compare_dtsi,
        )

        # Handle patch creation if requested
        if output_patch:
            try:
                patch_result = comparison_service.create_dtsi_patch(
                    layout1_path=file1,
                    layout2_path=file2,
                    output=output_patch,
                    section=patch_section,
                )
                result["patch_created"] = patch_result
            except Exception as e:
                result["patch_error"] = str(e)

        return result

    composer.execute_comparison_operation(
        file1=resolved_layout1,
        file2=layout2,
        operation=comparison_operation,
        operation_name="compare layouts",
        output_format=output_format,
    )


@handle_errors
def patch(
    ctx: typer.Context,
    source_layout: Annotated[Path, typer.Argument(help="Source layout file to patch")],
    patch_file: Annotated[
        Path,
        typer.Argument(
            help="JSON diff file from 'glovebox layout diff --output-format json'"
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output path (default: source_layout with -patched suffix)",
        ),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
) -> None:
    """Apply a JSON diff patch to transform a layout.

    Takes a source layout and applies changes from a JSON diff file
    (generated by 'glovebox layout diff --output-format json') to create
    a new transformed layout.

    Examples:
        # Generate a diff
        glovebox layout diff old.json new.json --output-format json > changes.json

        # Apply the diff to transform another layout
        glovebox layout patch my-layout.json changes.json --output patched-layout.json

        # Apply diff with auto-generated output name
        glovebox layout patch my-layout.json changes.json
    """
    command = LayoutOutputCommand()
    command.validate_layout_file(source_layout)

    try:
        from glovebox.cli.helpers.profile import get_user_config_from_context
        from glovebox.config import create_user_config

        user_config = get_user_config_from_context(ctx) or create_user_config()
        file_adapter = create_file_adapter()
        comparison_service = create_layout_comparison_service(user_config, file_adapter)
        result = comparison_service.apply_patch(
            source_layout_path=source_layout,
            patch_file_path=patch_file,
            output=output,
            force=force,
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


# TODO: to be deleted - moved to LayoutOutputFormatter.format_detailed_comparison_text()
def _format_comparison_text(
    result: dict[str, Any], output_format: str, compare_dtsi: bool
) -> list[str]:
    """Format comparison result for text output."""
    # This function has been moved to LayoutOutputFormatter.format_detailed_comparison_text()
    # Temporarily delegating to maintain compatibility during refactoring
    from glovebox.cli.commands.layout.formatters import create_layout_output_formatter

    formatter = create_layout_output_formatter()
    return formatter.format_detailed_comparison_text(
        result, output_format, compare_dtsi
    )
