"""Layout file manipulation CLI commands (split, merge, export, import)."""

import logging
from pathlib import Path
from typing import Annotated

import typer

from glovebox.cli.commands.layout.dependencies import create_full_layout_service
from glovebox.cli.decorators import handle_errors, with_metrics, with_profile
from glovebox.cli.helpers.parameter_factory import ParameterFactory


@handle_errors
@with_profile(required=True, firmware_optional=True, support_auto_detection=True)
@with_metrics("split")
def split(
    ctx: typer.Context,
    input: ParameterFactory.create_input_parameter(
        help_text="JSON layout file, @library-ref, '-' for stdin, or env:GLOVEBOX_JSON_FILE"
    ),
    output_dir: Annotated[Path, typer.Argument(help="Directory to save split files")],
    profile: ParameterFactory.create_profile_parameter() = None,
    no_auto: Annotated[
        bool,
        typer.Option(
            "--no-auto",
            help="Disable automatic profile detection from JSON keyboard field",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f", help="Overwrite existing files without prompting"
        ),
    ] = False,
    format: Annotated[
        str,
        typer.Option("--format", help="Output format: text, json"),
    ] = "text",
) -> None:
    """Split layout into separate component files.

    Breaks down a layout JSON file into individual component files:
    - metadata.json (layout metadata)
    - layers/ directory with individual layer files
    - behaviors.dtsi (custom behaviors, if any)
    - devicetree.dtsi (custom device tree, if any)

    Examples:
        glovebox layout split my-layout.json ./components/
        glovebox layout split @my-gaming-layout ./out/
        cat layout.json | glovebox layout split - ./components/
    """
    # Use IO helper methods directly
    from glovebox.cli.helpers.output_formatter import create_output_formatter

    # Deprecated functions removed - using IOCommand instead
    from glovebox.cli.helpers.theme import get_themed_console

    console = get_themed_console()
    output_formatter = create_output_formatter()

    try:
        # Load JSON input using IOCommand
        from glovebox.cli.core.command_base import IOCommand

        command = IOCommand(output_formatter)
        input_result = command.load_input(
            source=input,
            supports_stdin=True,
            required=True,
            allowed_extensions=[".json"],
        )
        raw_data = input_result.data
        import json

        if isinstance(raw_data, str):
            layout_data = json.loads(raw_data)
        else:
            layout_data = raw_data

        # Get keyboard profile from context
        from glovebox.cli.helpers.profile import get_keyboard_profile_from_context

        keyboard_profile = get_keyboard_profile_from_context(ctx)

        # Auto-detect profile if needed
        if keyboard_profile is None and not no_auto:
            keyboard_field = layout_data.get("keyboard")
            if keyboard_field:
                from glovebox.config import create_keyboard_profile

                keyboard_profile = create_keyboard_profile(keyboard_field)

        if keyboard_profile is None:
            console.print_error(
                "No keyboard profile available. Use --profile or enable auto-detection."
            )
            raise typer.Exit(1)

        # Convert to LayoutData model
        from glovebox.layout.models import LayoutData

        layout_model = LayoutData.model_validate(layout_data)

        # Split layout
        layout_service = create_full_layout_service()
        result = layout_service.split_components(
            profile=keyboard_profile,
            layout_data=layout_model,
            output_dir=Path(output_dir),
            force=force,
        )

        if result.success:
            result_data = {
                "success": True,
                "output_directory": str(output_dir),
                "components_created": result.messages
                if hasattr(result, "messages")
                else [],
            }

            if format == "json":
                output_formatter.print_formatted(result_data, "json")
            else:
                console.print_success("Layout split into components")
                console.print_info(f"  Output directory: {output_dir}")
                console.print_info(
                    "  Components: metadata.json, layers/, behaviors, devicetree"
                )
        else:
            raise ValueError(f"Split failed: {'; '.join(result.errors)}")

    except Exception as e:
        # Handle service error
        exc_info = logging.getLogger(__name__).isEnabledFor(logging.DEBUG)
        logging.getLogger(__name__).error(
            "Failed to split layout: %s", e, exc_info=exc_info
        )
        console.print_error(f"Failed to split layout: {e}")
        raise typer.Exit(1) from e


@handle_errors
@with_profile(default_profile="glove80/v25.05", required=True, firmware_optional=True)
@with_metrics("merge")
def merge(
    ctx: typer.Context,
    input_dir: Annotated[
        Path,
        typer.Argument(help="Directory with metadata.json and layers/ subdirectory"),
    ],
    output: Annotated[Path, typer.Argument(help="Output layout JSON file path")],
    profile: ParameterFactory.create_profile_parameter() = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f", help="Overwrite existing files without prompting"
        ),
    ] = False,
    format: Annotated[
        str,
        typer.Option("--format", help="Output format: text, json"),
    ] = "text",
) -> None:
    """Merge component files into a single layout JSON file.

    Combines component files (created by split) back into a complete layout:
    - Reads metadata.json for layout metadata
    - Combines all files in layers/ directory
    - Includes custom behaviors and device tree if present

    Examples:
        glovebox layout merge ./components/ merged-layout.json
        glovebox layout merge ./split/ layout.json --force
        glovebox layout merge ./components/ - > output.json
    """
    # Use IO helper methods directly
    from glovebox.cli.helpers.output_formatter import create_output_formatter

    # Deprecated functions removed - using IOCommand instead
    from glovebox.cli.helpers.theme import get_themed_console

    console = get_themed_console()
    output_formatter = create_output_formatter()

    try:
        # Get keyboard profile from context
        from glovebox.cli.helpers.profile import get_keyboard_profile_from_context

        keyboard_profile = get_keyboard_profile_from_context(ctx)

        if keyboard_profile is None:
            console.print_error("Profile is required for layout merge operation")
            raise typer.Exit(1)

        # Merge components
        layout_service = create_full_layout_service()
        result = layout_service.compile_from_directory(
            profile=keyboard_profile,
            components_dir=Path(input_dir),
            output_file_prefix=Path(output).stem if output else "merged-layout",
            session_metrics=ctx.obj.session_metrics if ctx.obj else None,
            force=force,
        )

        if result.success:
            # Get the merged layout data
            output_files = result.get_output_files()
            if "json" in output_files:
                # Read the merged JSON file
                merged_json_path = output_files["json"]
                with merged_json_path.open() as f:
                    import json

                    merged_data = json.load(f)

                # Write to specified output using IOCommand
                from glovebox.cli.core.command_base import IOCommand

                command = IOCommand(output_formatter)
                formatted_data = json.dumps(merged_data, indent=2)
                command.write_output(
                    data=formatted_data,
                    destination=output,
                    format="text",  # Already formatted as JSON string
                    supports_stdout=True,
                    force_overwrite=force,
                    create_dirs=True,
                )

                result_data = {
                    "success": True,
                    "source_directory": str(input_dir),
                    "output_file": str(output),
                    "components_merged": result.messages
                    if hasattr(result, "messages")
                    else [],
                }

                if format == "json":
                    output_formatter.print_formatted(result_data, "json")
                else:
                    console.print_success("Components merged into layout")
                    console.print_info(f"  Source directory: {input_dir}")
                    console.print_info(f"  Output file: {output}")
            else:
                raise ValueError("Failed to generate JSON output from merge operation")
        else:
            raise ValueError(f"Merge failed: {'; '.join(result.errors)}")

    except Exception as e:
        # Handle service error
        exc_info = logging.getLogger(__name__).isEnabledFor(logging.DEBUG)
        logging.getLogger(__name__).error(
            "Failed to merge layout: %s", e, exc_info=exc_info
        )
        console.print_error(f"Failed to merge layout: {e}")
        raise typer.Exit(1) from e
