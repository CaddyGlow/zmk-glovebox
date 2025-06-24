"""Unified layout editing CLI command with batch operations and JSON path support."""

from pathlib import Path
from typing import Annotated, Any

import typer

from glovebox.adapters import create_file_adapter
from glovebox.cli.commands.layout.base import LayoutOutputCommand
from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers.parameters import OutputFormatOption
from glovebox.layout.editor import create_layout_editor_service
from glovebox.layout.layer import create_layout_layer_service


@handle_errors
def edit(
    layout_file: Annotated[Path, typer.Argument(help="Path to layout JSON file")],
    # Field operations
    get: Annotated[
        list[str] | None,
        typer.Option("--get", help="Get field value(s) using JSON path notation"),
    ] = None,
    set: Annotated[
        list[str] | None,
        typer.Option(
            "--set",
            help="Set field value using key=value or key=--from syntax",
        ),
    ] = None,
    # Layer operations
    add_layer: Annotated[
        list[str] | None,
        typer.Option(
            "--add-layer", help="Add new layer(s) with optional --from import"
        ),
    ] = None,
    remove_layer: Annotated[
        list[str] | None,
        typer.Option(
            "--remove-layer", help="Remove layer(s) by name, index, or regex pattern"
        ),
    ] = None,
    move_layer: Annotated[
        list[str] | None,
        typer.Option(
            "--move-layer",
            help="Move layer using 'LayerName:position' syntax",
        ),
    ] = None,
    copy_layer: Annotated[
        list[str] | None,
        typer.Option(
            "--copy-layer",
            help="Copy layer using 'SourceLayer:NewName' syntax",
        ),
    ] = None,
    list_layers: Annotated[
        bool, typer.Option("--list-layers", help="List all layers in the layout")
    ] = False,
    # Import/position options
    from_source: Annotated[
        str | None,
        typer.Option(
            "--from",
            help="Import source: file.json, file.json:layer, file.json$.path",
        ),
    ] = None,
    position: Annotated[
        int | None,
        typer.Option("--position", help="Position for add-layer operations"),
    ] = None,
    # Output options
    output: Annotated[
        Path | None,
        typer.Option(
            "--output", "-o", help="Output file (default: overwrite original)"
        ),
    ] = None,
    output_format: OutputFormatOption = "text",
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
    save: Annotated[
        bool, typer.Option("--save/--no-save", help="Save changes to file")
    ] = True,
) -> None:
    """Unified layout editing command with batch operations support.

    This command replaces get-field, set-field, add-layer, remove-layer,
    move-layer, and list-layers with a single, powerful interface that
    supports batch operations and JSON path imports.

    Field Operations:
        --get title                           # Get field value
        --get "layers[0]" --get "title"      # Get multiple fields
        --set title="New Title"              # Set field value
        --set "custom_defined_behaviors=--from other.json:behaviors"  # Import from file

    Layer Operations:
        --add-layer "NewLayer"               # Add empty layer
        --add-layer "Gaming" --position 2    # Add at specific position
        --add-layer "Symbol" --from other.json:Symbol  # Import layer
        --remove-layer "UnusedLayer"         # Remove layer by name
        --remove-layer "15"                  # Remove layer by index (0-based)
        --remove-layer "Mouse.*"             # Remove layers matching regex
        --remove-layer "Mouse*"              # Remove layers with wildcard pattern
        --move-layer "Symbol:0"              # Move Symbol to position 0
        --copy-layer "Base:Gaming"           # Copy Base layer as Gaming
        --list-layers                        # List all layers

    JSON Path Support:
        --from "file.json$.layers[0]"        # Import using JSON path
        --from "file.json:Symbol"            # Shortcut for layer by name
        --from "file.json:behaviors"         # Shortcut for custom_defined_behaviors
        --from "file.json:meta"              # Shortcut for metadata fields

    Batch Operations:
        glovebox layout edit layout.json \\
          --set title="My Layout" \\
          --add-layer "Gaming" \\
          --remove-layer "Unused" \\
          --move-layer "Symbol:0"

    Examples:
        # Get field values
        glovebox layout edit layout.json --get title --get version

        # Set multiple fields
        glovebox layout edit layout.json --set title="New" --set version="2.0"

        # Layer management
        glovebox layout edit layout.json --add-layer "Gaming" --position 3
        glovebox layout edit layout.json --remove-layer "15"  # Remove by index
        glovebox layout edit layout.json --remove-layer "Mouse*"  # Remove by pattern

        # Import from other layouts
        glovebox layout edit layout.json --add-layer "Symbol" --from other.json:Symbol

        # Batch operations
        glovebox layout edit layout.json \\
          --set title="Updated Layout" \\
          --add-layer "Gaming" --from gaming.json:Base \\
          --remove-layer "Unused"

        # List operations only (no save)
        glovebox layout edit layout.json --list-layers --no-save
    """
    command = LayoutOutputCommand()
    command.validate_layout_file(layout_file)

    try:
        file_adapter = create_file_adapter()
        editor_service = create_layout_editor_service(file_adapter)
        layer_service = create_layout_layer_service(file_adapter)

        # Collect all operations
        operations: list[dict[str, Any]] = []
        results: dict[str, Any] = {}

        # Process get operations first (read-only)
        if get:
            for field_path in get:
                value = editor_service.get_field_value(layout_file, field_path)
                results[f"get:{field_path}"] = value

        # Process list-layers operation (read-only)
        if list_layers:
            layer_result = layer_service.list_layers(layout_file)
            results["layers"] = layer_result

        # If only read operations, output results and return
        if (get or list_layers) and not any(
            [set, add_layer, remove_layer, move_layer, copy_layer]
        ):
            _output_results(command, results, output_format)
            return

        # Process write operations (if save is enabled)
        if not save:
            from glovebox.cli.helpers import print_success_message

            print_success_message("Read-only mode: no changes saved")
            _output_results(command, results, output_format)
            return

        current_file = layout_file
        changes_made = False

        # Process set operations
        if set:
            for set_operation in set:
                if "=" not in set_operation:
                    raise ValueError(
                        f"Invalid set syntax: {set_operation}. Use key=value format."
                    )

                field_path, value_spec = set_operation.split("=", 1)

                # Handle --from imports
                if value_spec.startswith("--from "):
                    import_source = value_spec[7:]  # Remove "--from "
                    value = _resolve_import_source(import_source, field_path)
                else:
                    value = value_spec

                output_path = editor_service.set_field_value(
                    layout_file=current_file,
                    field_path=field_path,
                    value=value,
                    value_type="auto",
                    output=output if not changes_made else None,
                    force=force,
                )
                current_file = output_path
                changes_made = True
                operations.append(
                    {"type": "set", "field": field_path, "value": str(value)[:50]}
                )

        # Process layer operations
        if add_layer:
            for layer_spec in add_layer:
                layer_name = layer_spec
                import_from = None
                import_layer = None

                # Parse --from if specified globally
                if from_source:
                    import_from, import_layer = _parse_import_source(from_source)

                result = layer_service.add_layer(
                    layout_file=current_file,
                    layer_name=layer_name,
                    position=position,
                    import_from=Path(import_from) if import_from else None,
                    import_layer=import_layer,
                    output=output if not changes_made else None,
                    force=force,
                )
                current_file = result["output_path"]
                changes_made = True
                operations.append(
                    {
                        "type": "add_layer",
                        "layer": layer_name,
                        "position": result["position"],
                    }
                )

        if remove_layer:
            all_warnings = []
            for layer_identifier in remove_layer:
                result = layer_service.remove_layer(
                    layout_file=current_file,
                    layer_identifier=layer_identifier,
                    output=output if not changes_made else None,
                    force=force,
                    warn_on_no_match=True,
                )

                # Collect warnings
                if result.get("warnings"):
                    all_warnings.extend(result["warnings"])

                # Only update current file if layers were actually removed
                if result["had_matches"]:
                    current_file = result["output_path"]
                    changes_made = True

                # Handle multiple removed layers
                for removed_layer in result["removed_layers"]:
                    operations.append(
                        {
                            "type": "remove_layer",
                            "layer": removed_layer["name"],
                            "position": removed_layer["position"],
                        }
                    )

            # Show warnings for non-matching identifiers
            if all_warnings:
                from glovebox.cli.helpers.output import print_warning_message

                for warning in all_warnings:
                    print_warning_message(warning)

        if move_layer:
            for move_spec in move_layer:
                if ":" not in move_spec:
                    raise ValueError(
                        f"Invalid move syntax: {move_spec}. Use 'LayerName:position' format."
                    )

                layer_name, position_str = move_spec.split(":", 1)
                new_position = int(position_str)

                result = layer_service.move_layer(
                    layout_file=current_file,
                    layer_name=layer_name,
                    new_position=new_position,
                    output=output if not changes_made else None,
                    force=force,
                )
                current_file = result["output_path"]
                changes_made = True
                operations.append(
                    {
                        "type": "move_layer",
                        "layer": layer_name,
                        "from": result["from_position"],
                        "to": result["to_position"],
                    }
                )

        if copy_layer:
            for copy_spec in copy_layer:
                if ":" not in copy_spec:
                    raise ValueError(
                        f"Invalid copy syntax: {copy_spec}. Use 'SourceLayer:NewName' format."
                    )

                source_layer, new_layer = copy_spec.split(":", 1)

                # Copy is implemented as add with copy_from
                result = layer_service.add_layer(
                    layout_file=current_file,
                    layer_name=new_layer,
                    copy_from=source_layer,
                    output=output if not changes_made else None,
                    force=force,
                )
                current_file = result["output_path"]
                changes_made = True
                operations.append(
                    {"type": "copy_layer", "source": source_layer, "new": new_layer}
                )

        # Handle case where no write operations succeeded but had warnings
        if (
            not changes_made
            and "all_warnings" in locals()
            and all_warnings
            and not any([set, add_layer, move_layer, copy_layer])
        ):
            from glovebox.cli.helpers.output import print_warning_message

            print_warning_message(
                "No layers were removed - all identifiers failed to match"
            )
            return

        # Output results
        if changes_made:
            from glovebox.cli.helpers import print_list_item, print_success_message

            operation_count = len(operations)
            warning_count = len(all_warnings) if "all_warnings" in locals() else 0

            if operation_count > 0:
                success_msg = (
                    f"Layout edited successfully ({operation_count} operations)"
                )
                if warning_count > 0:
                    success_msg += f" with {warning_count} warnings"
                print_success_message(success_msg)
                print_list_item(f"Output: {current_file}")

            if output_format.lower() == "json":
                result_data = {
                    "success": True,
                    "output_file": str(current_file),
                    "operations": operations,
                    "results": results,
                    "warnings": all_warnings if "all_warnings" in locals() else [],
                }
                command.format_output(result_data, "json")
            else:
                for op in operations:
                    if op["type"] == "set":
                        print_list_item(f"Set {op['field']}: {op['value']}")
                    elif op["type"] == "add_layer":
                        print_list_item(
                            f"Added layer '{op['layer']}' at position {op['position']}"
                        )
                    elif op["type"] == "remove_layer":
                        position_info = (
                            f" (position {op['position']})" if "position" in op else ""
                        )
                        print_list_item(f"Removed layer '{op['layer']}'{position_info}")
                    elif op["type"] == "move_layer":
                        print_list_item(
                            f"Moved layer '{op['layer']}' from {op['from']} to {op['to']}"
                        )
                    elif op["type"] == "copy_layer":
                        print_list_item(
                            f"Copied layer '{op['source']}' as '{op['new']}'"
                        )

        # Include any read results
        if results:
            _output_results(command, results, output_format)

    except Exception as e:
        command.handle_service_error(e, "edit layout")


def _output_results(
    command: LayoutOutputCommand, results: dict[str, Any], output_format: str
) -> None:
    """Output read operation results."""
    if not results:
        return

    if output_format.lower() == "json":
        command.format_output(results, "json")
    else:
        from glovebox.cli.helpers import print_list_item, print_success_message

        for key, value in results.items():
            if key.startswith("get:"):
                field_name = key[4:]  # Remove "get:" prefix
                if isinstance(value, dict | list):
                    print_success_message(f"{field_name}:")
                    command.format_output(value, "json")
                else:
                    print_list_item(f"{field_name}: {value}")
            elif key == "layers":
                layer_lines = [
                    f"{layer['position']:2d}: {layer['name']} ({layer['binding_count']} bindings)"
                    for layer in value["layers"]
                ]
                command.print_text_list(
                    layer_lines, f"Layout has {value['total_layers']} layers:"
                )


def _resolve_import_source(import_source: str, target_field: str) -> Any:
    """Resolve import source to actual value."""
    # This is a placeholder for the full JSON path implementation
    # For now, return the import specification for processing by the service layer
    return f"IMPORT:{import_source}"


def _parse_import_source(source: str) -> tuple[str | None, str | None]:
    """Parse import source into file and layer/path components."""
    if ":" in source:
        file_part, layer_part = source.split(":", 1)
        return file_part, layer_part
    return source, None
