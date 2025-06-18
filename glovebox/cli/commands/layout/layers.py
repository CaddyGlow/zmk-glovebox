"""Layout layer management CLI commands."""

from pathlib import Path
from typing import Annotated

import typer

from glovebox.cli.commands.layout.base import LayoutOutputCommand
from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers.parameters import OutputFormatOption
from glovebox.layout.layer import create_layout_layer_service


@handle_errors
def add_layer(
    layout_file: Annotated[Path, typer.Argument(help="Path to layout JSON file")],
    layer_name: Annotated[str, typer.Argument(help="Name of the new layer")],
    position: Annotated[
        int | None,
        typer.Option(
            "--position",
            "-p",
            help="Position to insert (0-based index, default: append)",
        ),
    ] = None,
    copy_from: Annotated[
        str | None,
        typer.Option("--copy-from", help="Copy bindings from existing layer name"),
    ] = None,
    import_from: Annotated[
        Path | None,
        typer.Option(
            "--import-from",
            help="Import layer from external JSON file (layer.json or full layout.json)",
        ),
    ] = None,
    import_layer: Annotated[
        str | None,
        typer.Option(
            "--import-layer",
            help="Specific layer name to import (when importing from full layout)",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output", "-o", help="Output file (default: overwrite original)"
        ),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
) -> None:
    """Add a new layer to the layout.

    Creates a new layer with empty bindings, copies from an existing layer,
    or imports from an external JSON file. The layer can be inserted at a
    specific position or appended to the end.

    Examples:
        # Add empty layer at the end
        glovebox layout add-layer layout.json "MyNewLayer"

        # Insert layer at specific position
        glovebox layout add-layer layout.json "MyNewLayer" --position 5

        # Copy layer from existing layer
        glovebox layout add-layer layout.json "CopiedLayer" --copy-from "Symbol"

        # Import layer from single layer JSON file
        glovebox layout add-layer layout.json "ImportedLayer" --import-from exported_layer.json

        # Import specific layer from full layout JSON
        glovebox layout add-layer layout.json "ImportedSymbol" --import-from other_layout.json --import-layer "Symbol"

        # Import and insert at specific position
        glovebox layout add-layer layout.json "ImportedLayer" --import-from layer.json --position 2

        # Output to different file
        glovebox layout add-layer layout.json "NewLayer" --output modified_layout.json
    """
    command = LayoutOutputCommand()
    command.validate_layout_file(layout_file)

    try:
        layer_service = create_layout_layer_service()
        result = layer_service.add_layer(
            layout_file=layout_file,
            layer_name=layer_name,
            position=position,
            copy_from=copy_from,
            import_from=import_from,
            import_layer=import_layer,
            output=output,
            force=force,
        )

        # Show success with details
        command.print_operation_success(
            "Layer added successfully",
            {
                "file": result["output_path"],
                "layer": result["layer_name"],
                "position": result["position"],
                "copy_from": result.get("copy_from"),
                "import_from": result.get("import_from"),
                "import_layer": result.get("import_layer"),
                "total_layers": result["total_layers"],
            },
        )

    except Exception as e:
        command.handle_service_error(e, f"add layer '{layer_name}'")


@handle_errors
def remove_layer(
    layout_file: Annotated[Path, typer.Argument(help="Path to layout JSON file")],
    layer_name: Annotated[str, typer.Argument(help="Name of the layer to remove")],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output", "-o", help="Output file (default: overwrite original)"
        ),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
) -> None:
    """Remove a layer from the layout.

    Removes both the layer name and its corresponding binding data.

    Examples:
        # Remove a layer
        glovebox layout remove-layer layout.json "UnusedLayer"

        # Remove layer and save to different file
        glovebox layout remove-layer layout.json "UnusedLayer" --output modified_layout.json
    """
    command = LayoutOutputCommand()
    command.validate_layout_file(layout_file)

    try:
        layer_service = create_layout_layer_service()
        result = layer_service.remove_layer(
            layout_file=layout_file,
            layer_name=layer_name,
            output=output,
            force=force,
        )

        # Show success with details
        command.print_operation_success(
            "Layer removed successfully",
            {
                "file": result["output_path"],
                "removed_layer": result["layer_name"],
                "position_was": result["position"],
                "remaining_layers": result["remaining_layers"],
            },
        )

    except Exception as e:
        command.handle_service_error(e, f"remove layer '{layer_name}'")


@handle_errors
def move_layer(
    layout_file: Annotated[Path, typer.Argument(help="Path to layout JSON file")],
    layer_name: Annotated[str, typer.Argument(help="Name of the layer to move")],
    new_position: Annotated[int, typer.Argument(help="New position (0-based index)")],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output", "-o", help="Output file (default: overwrite original)"
        ),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
) -> None:
    """Move a layer to a new position in the layout.

    Reorders layers by moving the specified layer to a new position.
    All other layers shift accordingly.

    Examples:
        # Move layer to beginning
        glovebox layout move-layer layout.json "Symbol" 0

        # Move layer to end
        glovebox layout move-layer layout.json "Symbol" -1

        # Move layer to specific position
        glovebox layout move-layer layout.json "Symbol" 5

        # Move layer and save to different file
        glovebox layout move-layer layout.json "Symbol" 2 --output reordered_layout.json
    """
    command = LayoutOutputCommand()
    command.validate_layout_file(layout_file)

    try:
        layer_service = create_layout_layer_service()
        result = layer_service.move_layer(
            layout_file=layout_file,
            layer_name=layer_name,
            new_position=new_position,
            output=output,
            force=force,
        )

        if not result["moved"]:
            command.print_operation_success(
                f"Layer '{layer_name}' is already at position {new_position}", {}
            )
            return

        # Show success with details
        command.print_operation_success(
            "Layer moved successfully",
            {
                "file": result["output_path"],
                "layer": result["layer_name"],
                "from_position": result["from_position"],
                "to_position": result["to_position"],
            },
        )

    except Exception as e:
        command.handle_service_error(e, f"move layer '{layer_name}'")


@handle_errors
def list_layers(
    layout_file: Annotated[Path, typer.Argument(help="Path to layout JSON file")],
    output_format: OutputFormatOption = "text",
) -> None:
    """List all layers in the layout with their positions.

    Shows layer names, positions, and binding counts for each layer.

    Examples:
        # List layers in text format
        glovebox layout list-layers layout.json

        # List layers in JSON format for automation
        glovebox layout list-layers layout.json --output-format json

        # List layers in table format
        glovebox layout list-layers layout.json --output-format table
    """
    command = LayoutOutputCommand()
    command.validate_layout_file(layout_file)

    try:
        layer_service = create_layout_layer_service()
        result = layer_service.list_layers(layout_file)

        if output_format.lower() == "json":
            command.format_output(result, "json")
        elif output_format.lower() == "table":
            command.format_output(result["layers"], "table")
        else:
            # Text format
            layer_lines = [
                f"{layer['position']:2d}: {layer['name']} ({layer['binding_count']} bindings)"
                for layer in result["layers"]
            ]
            command.print_text_list(
                layer_lines, f"Layout has {result['total_layers']} layers:"
            )

    except Exception as e:
        command.handle_service_error(e, "list layers")


@handle_errors
def export_layer(
    layout_file: Annotated[Path, typer.Argument(help="Path to layout JSON file")],
    layer_name: Annotated[str, typer.Argument(help="Name of the layer to export")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Output JSON file")],
    format_type: Annotated[
        str,
        typer.Option(
            "--format",
            help="Export format: bindings (array of bindings), layer (layer object), or full (minimal layout)",
        ),
    ] = "bindings",
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
) -> None:
    """Export a layer to an external JSON file.

    Exports layer data in various formats that can be imported by add-layer.
    This enables sharing and reusing individual layers across layouts.

    Export Formats:
        bindings - Array of binding objects (compact format)
        layer    - Layer object with name and bindings
        full     - Minimal layout with just this layer (for compatibility)

    Examples:
        # Export layer as bindings array (most compact)
        glovebox layout export-layer layout.json "Symbol" --output symbol_layer.json

        # Export as layer object
        glovebox layout export-layer layout.json "Symbol" --output symbol_layer.json --format layer

        # Export as minimal full layout
        glovebox layout export-layer layout.json "Symbol" --output symbol_layout.json --format full

        # Force overwrite existing file
        glovebox layout export-layer layout.json "Symbol" --output symbol.json --force
    """
    command = LayoutOutputCommand()
    command.validate_layout_file(layout_file)

    try:
        layer_service = create_layout_layer_service()
        result = layer_service.export_layer(
            layout_file=layout_file,
            layer_name=layer_name,
            output=output,
            format_type=format_type,
            force=force,
        )

        # Show success with details
        command.print_operation_success(
            "Layer exported successfully",
            {
                "source": result["source_file"],
                "layer": result["layer_name"],
                "output": result["output_file"],
                "format": result["format"],
                "bindings": result["binding_count"],
            },
        )

    except Exception as e:
        command.handle_service_error(e, f"export layer '{layer_name}'")
