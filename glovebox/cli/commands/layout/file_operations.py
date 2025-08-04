"""Layout file manipulation CLI commands (split, merge, export, import)."""

import json
import logging
from pathlib import Path
from typing import Annotated, Any

import typer

from glovebox.cli.commands.layout.dependencies import create_full_layout_service
from glovebox.cli.decorators import handle_errors, with_metrics, with_profile
from glovebox.cli.helpers.parameter_factory import ParameterFactory


@handle_errors
@with_profile(required=True, firmware_optional=True, support_auto_detection=True)
@with_metrics("split")
def split(
    ctx: typer.Context,
    input: Annotated[
        str,
        typer.Argument(
            help="JSON layout file, @library-ref, '-' for stdin, or env:GLOVEBOX_JSON_FILE"
        ),
    ],
    output_dir: Annotated[Path, typer.Argument(help="Directory to save split files")],
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Keyboard profile in format 'keyboard' or 'keyboard/firmware'",
        ),
    ] = None,
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
        # Load JSON input using direct input handling
        if input == "-":
            # Read from stdin
            import sys

            raw_data = sys.stdin.read()
            layout_data = json.loads(raw_data)
        else:
            # Read from file
            input_path = Path(input)
            if not input_path.exists():
                console.print_error(f"Input file does not exist: {input_path}")
                raise typer.Exit(1)

            with input_path.open() as f:
                layout_data = json.load(f)

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

        # Split layout using component service
        layout_service = create_full_layout_service()
        # Access the component service from the layout service
        component_service = layout_service._component_service
        result = component_service.split_components(
            layout=layout_model,
            output_dir=Path(output_dir),
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
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Keyboard profile in format 'keyboard' or 'keyboard/firmware'",
        ),
    ] = None,
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

        # Merge components using component service
        layout_service = create_full_layout_service()
        component_service = layout_service._component_service

        # Read metadata first
        metadata_file = Path(input_dir) / "metadata.json"
        if not metadata_file.exists():
            console.print_error(f"metadata.json not found in {input_dir}")
            raise typer.Exit(1)

        with metadata_file.open() as f:
            metadata_data = json.load(f)

        from glovebox.layout.models import LayoutData

        metadata_layout = LayoutData.model_validate(metadata_data)

        # Merge components
        layers_dir = Path(input_dir) / "layers"
        merged_layout = component_service.merge_components(
            metadata_layout=metadata_layout,
            layers_dir=layers_dir,
        )

        # Write output
        output_data = merged_layout.model_dump(mode="json", by_alias=True)

        if str(output) == "-":
            # Write to stdout
            print(json.dumps(output_data, indent=2))
        else:
            # Write to file
            output_path = Path(output)

            # Check for existing file
            if output_path.exists() and not force:
                console.print_warning(f"Output file already exists: {output_path}")
                if not typer.confirm("Overwrite existing file?"):
                    raise typer.Abort()

            # Create parent directories if needed
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with output_path.open("w") as f:
                json.dump(output_data, f, indent=2)

        result_data = {
            "success": True,
            "source_directory": str(input_dir),
            "output_file": str(output),
            "layers_merged": len(merged_layout.layers),
        }

        if format == "json":
            output_formatter.print_formatted(result_data, "json")
        else:
            console.print_success("Components merged into layout")
            console.print_info(f"  Source directory: {input_dir}")
            console.print_info(f"  Output file: {output}")
            console.print_info(f"  Layers merged: {len(merged_layout.layers)}")

    except Exception as e:
        # Handle service error
        exc_info = logging.getLogger(__name__).isEnabledFor(logging.DEBUG)
        logging.getLogger(__name__).error(
            "Failed to merge layout: %s", e, exc_info=exc_info
        )
        console.print_error(f"Failed to merge layout: {e}")
        raise typer.Exit(1) from e
