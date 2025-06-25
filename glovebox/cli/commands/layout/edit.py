"""Unified layout editing CLI command with batch operations and JSON path support."""

import json
import logging
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from glovebox.adapters import create_file_adapter
from glovebox.cli.commands.layout.base import LayoutOutputCommand
from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers import print_error_message
from glovebox.cli.helpers.auto_profile import resolve_json_file_path
from glovebox.cli.helpers.parameters import OutputFormatOption
from glovebox.layout.editor import create_layout_editor_service
from glovebox.layout.layer import create_layout_layer_service
from glovebox.layout.template_service import create_jinja2_template_service
from glovebox.layout.utils.json_operations import load_layout_file
from glovebox.layout.utils.variable_resolver import VariableResolver


console = Console()
logger = logging.getLogger(__name__)


@handle_errors
def edit(
    layout_file: Annotated[
        Path | None,
        typer.Argument(
            help="Path to layout JSON file. Uses GLOVEBOX_JSON_FILE environment variable if not provided."
        ),
    ] = None,
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
    unset: Annotated[
        list[str] | None,
        typer.Option(
            "--unset",
            help="Remove field or dictionary key (e.g., 'variables.myVar')",
        ),
    ] = None,
    merge: Annotated[
        list[str] | None,
        typer.Option(
            "--merge",
            help="Merge values into field using key=--from syntax or key=value for objects",
        ),
    ] = None,
    append: Annotated[
        list[str] | None,
        typer.Option(
            "--append",
            help="Append values to array field using key=--from syntax or key=value",
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
    list_usage: Annotated[
        bool, typer.Option("--list-usage", help="Show where each variable is used")
    ] = False,
    dump_context: Annotated[
        bool,
        typer.Option(
            "--dump-context", help="Dump template context values for all stages"
        ),
    ] = False,
    context_stages: Annotated[
        list[str] | None,
        typer.Option(
            "--context-stages",
            help="Specify which context stages to dump (basic, behaviors, layers, custom). Default: all stages",
        ),
    ] = None,
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
    confirm: Annotated[
        bool,
        typer.Option(
            "--confirm",
            help="Show merge preview and ask for confirmation before overwriting existing fields",
        ),
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
        --unset variables.oldVar             # Remove dictionary key or field
        --merge variables=--from other.json$.variables  # Merge variables from another file
        --append tags="gaming"               # Append single value to array
        --append tags=--from other.json$.tags  # Append array values from another file

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
        --list-usage                         # Show where each variable is used
        --dump-context                       # Dump all template context values
        --dump-context --context-stages basic behaviors  # Dump specific stages only

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

        # Set complex nested fields with array indexing and variables
        glovebox layout edit layout.json --set 'hold_taps[0].tapping_term_ms="${tapMs}"'

        # Create new variable entries (dict keys are created automatically)
        glovebox layout edit layout.json --set variables.myVar=value --set variables.timing=150

        # Remove variables or dictionary keys
        glovebox layout edit layout.json --unset variables.oldVar --unset variables.unused

        # Append to lists (extends list if index is beyond current length)
        glovebox layout edit layout.json --set 'tags[5]="new-tag"'

        # Remove from lists (by index)
        glovebox layout edit layout.json --unset 'tags[2]'

        # Layer management
        glovebox layout edit layout.json --add-layer "Gaming" --position 3
        glovebox layout edit layout.json --remove-layer "15"  # Remove by index
        glovebox layout edit layout.json --remove-layer "Mouse*"  # Remove by pattern

        # Import from other layouts
        glovebox layout edit layout.json --add-layer "Symbol" --from other.json:Symbol

        # Merge and append operations
        glovebox layout edit layout.json --merge variables=--from vars.json$.variables
        glovebox layout edit layout.json --append tags=--from other.json$.tags
        glovebox layout edit layout.json --merge variables=--from vars.json$.variables --confirm

        # Batch operations
        glovebox layout edit layout.json \\
          --set title="Updated Layout" \\
          --merge variables=--from vars.json$.variables \\
          --add-layer "Gaming" --from gaming.json:Base \\
          --remove-layer "Unused"

        # List operations only (no save)
        glovebox layout edit layout.json --list-layers --no-save

        # Template context debugging
        glovebox layout edit layout.json --dump-context --no-save
        glovebox layout edit layout.json --dump-context --context-stages behaviors layers --format json
    """
    # Resolve JSON file path (supports environment variable)
    resolved_json_file = resolve_json_file_path(layout_file)

    if resolved_json_file is None:
        print_error_message(
            "JSON file is required. Provide as argument or set GLOVEBOX_JSON_FILE environment variable."
        )
        raise typer.Exit(1)

    command = LayoutOutputCommand()
    command.validate_layout_file(resolved_json_file)

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
                value = editor_service.get_field_value(resolved_json_file, field_path)
                results[f"get:{field_path}"] = value

        # Process list-layers operation (read-only)
        if list_layers:
            layer_result = layer_service.list_layers(resolved_json_file)
            results["layers"] = layer_result

        # Process list-usage operation (read-only)
        if list_usage:
            usage_result = _get_variable_usage(resolved_json_file, file_adapter)
            results["variable_usage"] = usage_result

        # Process dump-context operation (read-only)
        if dump_context:
            context_result = _get_template_context(
                resolved_json_file, file_adapter, context_stages
            )
            results["template_context"] = context_result

        # If only read operations, output results and return
        if (get or list_layers or list_usage or dump_context) and not any(
            [set, unset, merge, append, add_layer, remove_layer, move_layer, copy_layer]
        ):
            _output_results(command, results, output_format)
            return

        # Process write operations (if save is enabled)
        if not save:
            from glovebox.cli.helpers import print_success_message

            print_success_message("Read-only mode: no changes saved")
            _output_results(command, results, output_format)
            return

        current_file = resolved_json_file
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
                    # Format: --set field=--from source.json$.path
                    import_source = value_spec[7:]  # Remove "--from "
                    resolved_value = _resolve_import_source(import_source, field_path)
                    # Convert complex objects to JSON strings for the editor service
                    if isinstance(resolved_value, dict | list):
                        value = json.dumps(resolved_value)
                    else:
                        value = resolved_value
                elif value_spec == "--from" and from_source:
                    # Format: --set field=--from --from source.json$.path
                    resolved_value = _resolve_import_source(from_source, field_path)
                    # Convert complex objects to JSON strings for the editor service
                    if isinstance(resolved_value, dict | list):
                        value = json.dumps(resolved_value)
                    else:
                        value = resolved_value
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

        # Process unset operations
        if unset:
            for field_path in unset:
                output_path = editor_service.unset_field_value(
                    layout_file=current_file,
                    field_path=field_path,
                    output=output if not changes_made else None,
                    force=force,
                )
                current_file = output_path
                changes_made = True
                operations.append({"type": "unset", "field": field_path})

        # Process merge operations
        if merge:
            for merge_operation in merge:
                if "=" not in merge_operation:
                    raise ValueError(
                        f"Invalid merge syntax: {merge_operation}. Use key=value or key=--from format."
                    )

                field_path, value_spec = merge_operation.split("=", 1)

                # Handle --from imports for merge
                if value_spec.startswith("--from "):
                    import_source = value_spec[7:]  # Remove "--from "
                    merge_value = _resolve_import_source(import_source, field_path)
                elif value_spec == "--from" and from_source:
                    merge_value = _resolve_import_source(from_source, field_path)
                else:
                    # Try to parse as JSON for object merging
                    try:
                        merge_value = json.loads(value_spec)
                    except json.JSONDecodeError:
                        merge_value = value_spec

                logger.debug("Set value %r", merge_value)
                logger.debug("Set value %r", value_spec)
                output_path = _merge_field_value(
                    current_file,
                    field_path,
                    merge_value,
                    output if not changes_made else None,
                    force,
                    confirm,
                )
                current_file = output_path
                changes_made = True
                operations.append(
                    {
                        "type": "merge",
                        "field": field_path,
                        "value": str(merge_value)[:50],
                    }
                )

        # Process append operations
        if append:
            for append_operation in append:
                if "=" not in append_operation:
                    raise ValueError(
                        f"Invalid append syntax: {append_operation}. Use key=value or key=--from format."
                    )

                field_path, value_spec = append_operation.split("=", 1)

                # Handle --from imports for append
                if value_spec.startswith("--from "):
                    import_source = value_spec[7:]  # Remove "--from "
                    append_value = _resolve_import_source(import_source, field_path)
                elif value_spec == "--from" and from_source:
                    append_value = _resolve_import_source(from_source, field_path)
                else:
                    # Try to parse as JSON for array appending
                    try:
                        append_value = json.loads(value_spec)
                    except json.JSONDecodeError:
                        append_value = value_spec

                # Check for import errors
                if isinstance(append_value, str) and append_value.startswith(
                    "IMPORT_ERROR:"
                ):
                    raise ValueError(append_value)

                output_path = _append_field_value(
                    current_file,
                    field_path,
                    append_value,
                    output if not changes_made else None,
                    force,
                )
                current_file = output_path
                changes_made = True
                operations.append(
                    {
                        "type": "append",
                        "field": field_path,
                        "value": str(append_value)[:50],
                    }
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

        all_warnings = []
        if remove_layer:
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
            and not any([set, merge, append, add_layer, move_layer, copy_layer])
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
                    elif op["type"] == "unset":
                        print_list_item(f"Removed {op['field']}")
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
                    elif op["type"] == "merge":
                        print_list_item(f"Merged into {op['field']}: {op['value']}")
                    elif op["type"] == "append":
                        print_list_item(f"Appended to {op['field']}: {op['value']}")

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
            elif key == "variable_usage":
                if "error" in value:
                    print_list_item(f"Error getting variable usage: {value['error']}")
                elif "message" in value:
                    print_list_item(value["message"])
                else:
                    # Display the usage table
                    if value:
                        table = Table(title="Variable Usage")
                        table.add_column("Variable", style="cyan")
                        table.add_column("Used In", style="green")
                        table.add_column("Count", style="blue")

                        for var_name, paths in value.items():
                            usage_str = (
                                "\n".join(paths)
                                if len(paths) <= 5
                                else "\n".join(paths[:5])
                                + f"\n... and {len(paths) - 5} more"
                            )
                            table.add_row(var_name, usage_str, str(len(paths)))

                        console.print(table)
                    else:
                        print_list_item("No variable usage found")
            elif key == "template_context":
                if "error" in value:
                    print_list_item(f"Error getting template context: {value['error']}")
                else:
                    _display_template_context(value, output_format)


def _resolve_import_source(import_source: str, target_field: str) -> Any:
    """Resolve import source to actual value."""
    try:
        file_adapter = create_file_adapter()

        # Parse the import source
        if "$." in import_source:
            # JSON path syntax: file.json$.path.to.field
            file_part, json_path = import_source.split("$.", 1)
            source_file = Path(file_part)
        elif ":" in import_source:
            # Shortcut syntax: file.json:layer or file.json:behaviors
            file_part, shortcut = import_source.split(":", 1)
            source_file = Path(file_part)
            # Convert shortcut to JSON path
            if shortcut == "behaviors":
                json_path = "custom_defined_behaviors"
            elif shortcut == "meta":
                json_path = "title,creator,notes"  # Multiple metadata fields
            else:
                # Assume it's a layer name - find it in layer_names
                json_path = f"layers[{shortcut}]"  # Will be resolved below
        else:
            # Direct file import
            source_file = Path(import_source)
            json_path = None

        # Load the source file
        if not source_file.exists():
            raise FileNotFoundError(f"Import source file not found: {source_file}")

        source_data = file_adapter.read_json(source_file)

        # If no specific path, return entire file
        if not json_path:
            return source_data

        # Resolve JSON path
        return _resolve_json_path(source_data, json_path, source_file)

    except Exception as e:
        # CLAUDE.md pattern: debug-aware stack traces
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error(
            "Failed to resolve import '%s': %s", import_source, e, exc_info=exc_info
        )
        # Return error information for better debugging
        return f"IMPORT_ERROR: Failed to resolve import '{import_source}': {e}"


def _resolve_json_path(data: dict[str, Any], json_path: str, source_file: Path) -> Any:
    """Resolve a JSON path in the given data."""
    # Handle special layer name resolution
    if (
        json_path.startswith("layers[")
        and json_path.endswith("]")
        and not json_path[7:-1].isdigit()
    ):
        # Layer name lookup: layers[LayerName] -> layers[index]
        layer_name = json_path[7:-1]  # Extract layer name
        layer_names = data.get("layer_names", [])
        try:
            layer_index = layer_names.index(layer_name)
            json_path = f"layers[{layer_index}]"
        except ValueError as e:
            raise ValueError(
                f"Layer '{layer_name}' not found in {source_file}. Available layers: {layer_names}"
            ) from e

    # Split path and traverse
    current = data
    path_parts = []
    i = 0

    while i < len(json_path):
        if json_path[i] == "[":
            # Array index
            end_bracket = json_path.find("]", i)
            if end_bracket == -1:
                raise ValueError(f"Invalid JSON path: unmatched '[' in '{json_path}'")

            index_str = json_path[i + 1 : end_bracket]
            try:
                index = int(index_str)
                if not isinstance(current, list):
                    raise TypeError(
                        f"Cannot index non-list at path: {'.'.join(path_parts)}"
                    )
                if index >= len(current):
                    raise IndexError(
                        f"Index {index} out of range for array of length {len(current)}"
                    )
                current = current[index]
                path_parts.append(f"[{index}]")
                i = end_bracket + 1
            except ValueError as e:
                raise ValueError(
                    f"Invalid array index '{index_str}' in JSON path"
                ) from e
        elif json_path[i] == ".":
            i += 1  # Skip dot
        else:
            # Object key
            start = i
            while i < len(json_path) and json_path[i] not in ".[]":
                i += 1

            key = json_path[start:i]
            if not key:
                continue

            if not isinstance(current, dict):
                raise TypeError(
                    f"Cannot access key '{key}' on non-object at path: {'.'.join(path_parts)}"
                )

            if key not in current:
                raise KeyError(
                    f"Key '{key}' not found at path: {'.'.join(path_parts)}. Available keys: {list(current.keys())}"
                )

            current = current[key]
            path_parts.append(key)

    return current


def _merge_field_value(
    layout_file: Path,
    field_path: str,
    merge_value: Any,
    output: Path | None,
    force: bool,
    confirm: bool = False,
) -> Path:
    """Merge a value into a field (for dictionaries/objects)."""
    from glovebox.adapters import create_file_adapter
    from glovebox.layout.utils.field_parser import (
        extract_field_value_from_model,
        set_field_value_on_model,
    )
    from glovebox.layout.utils.json_operations import (
        VariableResolutionContext,
        load_layout_file,
        save_layout_file,
    )

    # Wrap entire operation in variable resolution context to preserve variables
    with VariableResolutionContext(skip=True):
        file_adapter = create_file_adapter()

        # Load the layout WITHOUT variable resolution to preserve variable references
        layout_data = load_layout_file(
            layout_file, file_adapter, skip_variable_resolution=True
        )

        # Get current field value
        try:
            current_value = extract_field_value_from_model(layout_data, field_path)
        except Exception:
            current_value = {}  # Default to empty dict if field doesn't exist

        # Merge logic
        if isinstance(current_value, dict) and isinstance(merge_value, dict):
            # Deep merge dictionaries
            merged_value = _deep_merge_dicts(current_value, merge_value)

            # Show confirmation if requested
            if confirm and not _confirm_merge_operation(
                current_value, merge_value, merged_value, field_path
            ):
                raise typer.Abort("Merge operation cancelled by user")

        elif isinstance(merge_value, dict):
            # Replace with new dict if current is not a dict
            merged_value = merge_value

            # Show confirmation for complete replacement
            if confirm:
                console.print(
                    f"\n[yellow]⚠️  Complete replacement of field '{field_path}'[/yellow]"
                )
                console.print(
                    f"[red]Current value ({type(current_value).__name__}):[/red] {current_value}"
                )
                console.print(f"[green]New value (dict):[/green] {merge_value}")

                if not typer.confirm(
                    "This will completely replace the current value. Continue?"
                ):
                    raise typer.Abort("Merge operation cancelled by user")
        else:
            raise TypeError(
                f"Cannot merge non-dictionary value into field '{field_path}'. Current type: {type(current_value)}, merge type: {type(merge_value)}"
            )

        # Set the merged value
        set_field_value_on_model(layout_data, field_path, merged_value)

        # Determine output path
        output_path = output or layout_file

        # Save the modified layout
        save_layout_file(layout_data, output_path, file_adapter)

        return output_path


def _append_field_value(
    layout_file: Path,
    field_path: str,
    append_value: Any,
    output: Path | None,
    force: bool,
) -> Path:
    """Append a value to an array field."""
    from glovebox.adapters import create_file_adapter
    from glovebox.layout.utils.field_parser import (
        extract_field_value_from_model,
        set_field_value_on_model,
    )
    from glovebox.layout.utils.json_operations import (
        VariableResolutionContext,
        load_layout_file,
        save_layout_file,
    )

    # Wrap entire operation in variable resolution context to preserve variables
    with VariableResolutionContext(skip=True):
        file_adapter = create_file_adapter()

        # Load the layout WITHOUT variable resolution to preserve variable references
        layout_data = load_layout_file(
            layout_file, file_adapter, skip_variable_resolution=True
        )

        # Get current field value
        try:
            current_value = extract_field_value_from_model(layout_data, field_path)
        except Exception:
            current_value = []  # Default to empty list if field doesn't exist

        # Append logic
        if isinstance(current_value, list):
            if isinstance(append_value, list):
                # Special handling for layers field - append entire layer as single element
                if field_path == "layers":
                    # For layers, append the entire array as a single layer
                    new_value = current_value + [append_value]
                else:
                    # For other fields, extend with multiple values
                    new_value = current_value + append_value
            else:
                # Append single value
                new_value = current_value + [append_value]
        else:
            raise TypeError(
                f"Cannot append to non-array field '{field_path}'. Current type: {type(current_value)}"
            )

        logger.debug("Appending value to field '%s': %s", field_path, new_value)
        logger.debug("layout_data: %s", layout_data)
        # Set the new value
        set_field_value_on_model(layout_data, field_path, new_value)

        # Determine output path
        output_path = output or layout_file

        # Save the modified layout
        save_layout_file(layout_data, output_path, file_adapter)

        return output_path


def _deep_merge_dicts(dict1: dict[str, Any], dict2: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries."""
    result = dict1.copy()

    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge_dicts(result[key], value)
        else:
            result[key] = value

    return result


def _confirm_merge_operation(
    current_value: dict[str, Any],
    merge_value: dict[str, Any],
    merged_value: dict[str, Any],
    field_path: str,
) -> bool:
    """Show merge preview and ask for user confirmation."""
    # Analyze what will be overwritten and what will be added
    overwritten_keys = []
    new_keys = []

    for key, value in merge_value.items():
        if key in current_value:
            if current_value[key] != value:
                overwritten_keys.append(key)
        else:
            new_keys.append(key)

    console.print(f"\n[cyan]📋 Merge Preview for field '{field_path}'[/cyan]")

    if new_keys:
        console.print(f"\n[green]✅ New keys to be added ({len(new_keys)}):[/green]")
        for key in new_keys:
            console.print(f"  + {key}: {merge_value[key]}")

    if overwritten_keys:
        console.print(
            f"\n[yellow]⚠️  Existing keys to be overwritten ({len(overwritten_keys)}):[/yellow]"
        )
        for key in overwritten_keys:
            console.print(f"  [red]- {key}: {current_value[key]}[/red]")
            console.print(f"  [green]+ {key}: {merge_value[key]}[/green]")

    if not overwritten_keys and not new_keys:
        console.print("[dim]No changes detected in merge operation.[/dim]")
        return True

    # Show summary
    total_keys_after = len(merged_value)
    console.print("\n[cyan]Summary:[/cyan]")
    console.print(f"  Current keys: {len(current_value)}")
    console.print(f"  New keys: {len(new_keys)}")
    console.print(f"  Overwritten keys: {len(overwritten_keys)}")
    console.print(f"  Total keys after merge: {total_keys_after}")

    if overwritten_keys:
        return typer.confirm(
            "\nProceed with merge? This will overwrite existing values."
        )
    else:
        return typer.confirm("\nProceed with merge?")


def _parse_import_source(source: str) -> tuple[str | None, str | None]:
    """Parse import source into file and layer/path components."""
    if ":" in source:
        file_part, layer_part = source.split(":", 1)
        return file_part, layer_part
    return source, None


def _get_variable_usage(layout_file: Path, file_adapter: Any) -> dict[str, Any]:
    """Get variable usage information from a layout file."""
    try:
        # For variable usage analysis, we need to read the raw JSON
        # to see the actual variable references before resolution
        json_data = file_adapter.read_json(layout_file)
        variables_dict = json_data.get("variables", {})

        if not variables_dict:
            return {"message": "No variables found in layout"}

        resolver = VariableResolver(variables_dict)
        usage = resolver.get_variable_usage(json_data)
        return usage
    except Exception as e:
        # CLAUDE.md pattern: debug-aware stack traces
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("Failed to get variable usage: %s", e, exc_info=exc_info)
        return {"error": str(e)}


def _get_template_context(
    layout_file: Path, file_adapter: Any, context_stages: list[str] | None
) -> dict[str, Any]:
    """Get template context information from a layout file."""
    try:
        # Load layout data without variable resolution to get original templates
        layout_data = load_layout_file(
            layout_file, file_adapter, skip_variable_resolution=True
        )

        # Create template service
        template_service = create_jinja2_template_service()

        # Define available stages
        available_stages = ["basic", "behaviors", "layers", "custom"]

        # Use specified stages or all stages
        stages_to_dump = context_stages if context_stages else available_stages

        # Validate requested stages
        invalid_stages = [
            stage for stage in stages_to_dump if stage not in available_stages
        ]
        if invalid_stages:
            return {
                "error": f"Invalid context stages: {', '.join(invalid_stages)}. Available: {', '.join(available_stages)}"
            }

        # Create context for each requested stage
        contexts = {}
        for stage in stages_to_dump:
            try:
                context = template_service.create_template_context(layout_data, stage)
                # Convert any complex objects to JSON-serializable format
                contexts[stage] = _make_json_serializable(context)
            except Exception as stage_error:
                # CLAUDE.md pattern: debug-aware stack traces
                exc_info = logger.isEnabledFor(logging.DEBUG)
                logger.warning(
                    "Failed to create context for stage '%s': %s",
                    stage,
                    stage_error,
                    exc_info=exc_info,
                )
                contexts[stage] = {"error": str(stage_error)}

        return {
            "stages": contexts,
            "layout_title": layout_data.title,
            "keyboard": layout_data.keyboard,
            "available_stages": available_stages,
            "dumped_stages": stages_to_dump,
        }

    except Exception as e:
        # CLAUDE.md pattern: debug-aware stack traces
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("Failed to get template context: %s", e, exc_info=exc_info)
        return {"error": str(e)}


def _make_json_serializable(obj: Any) -> Any:
    """Convert object to JSON-serializable format."""
    if callable(obj):
        return f"<function: {obj.__name__}>"
    elif isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_make_json_serializable(item) for item in obj]
    elif hasattr(obj, "__dict__"):
        return f"<object: {type(obj).__name__}>"
    else:
        return obj


def _display_template_context(context_data: dict[str, Any], output_format: str) -> None:
    """Display template context data in the specified format."""
    from glovebox.cli.helpers import print_list_item, print_success_message

    if output_format.lower() == "json":
        console.print(json.dumps(context_data, indent=2))
        return

    # Text format display
    print_success_message(
        f"Template Context for '{context_data.get('layout_title', 'Unknown Layout')}'"
    )
    print_list_item(f"Keyboard: {context_data.get('keyboard', 'Unknown')}")
    print_list_item(
        f"Dumped stages: {', '.join(context_data.get('dumped_stages', []))}"
    )

    stages = context_data.get("stages", {})

    for stage_name in context_data.get("dumped_stages", []):
        stage_context = stages.get(stage_name, {})

        if "error" in stage_context:
            print_list_item(
                f"❌ {stage_name.title()} Stage: Error - {stage_context['error']}"
            )
            continue

        print_list_item(f"📋 {stage_name.title()} Stage Context:")

        # Display key context items
        if "variables" in stage_context and stage_context["variables"]:
            console.print("  [cyan]Variables:[/cyan]")
            for var_name, var_value in stage_context["variables"].items():
                console.print(f"    {var_name}: {var_value}")

        if "keyboard" in stage_context:
            console.print(f"  [cyan]Keyboard:[/cyan] {stage_context['keyboard']}")

        if "title" in stage_context:
            console.print(f"  [cyan]Title:[/cyan] {stage_context['title']}")

        # Optional metadata fields
        if "creator" in stage_context and stage_context["creator"]:
            console.print(f"  [cyan]Creator:[/cyan] {stage_context['creator']}")

        if "uuid" in stage_context and stage_context["uuid"]:
            console.print(f"  [cyan]UUID:[/cyan] {stage_context['uuid']}")

        if "version" in stage_context and stage_context["version"]:
            console.print(f"  [cyan]Version:[/cyan] {stage_context['version']}")

        if "date" in stage_context and stage_context["date"]:
            console.print(f"  [cyan]Date:[/cyan] {stage_context['date']}")

        if "tags" in stage_context and stage_context["tags"]:
            console.print(
                f"  [cyan]Tags:[/cyan] {', '.join(map(str, stage_context['tags']))}"
            )

        # Config parameters - handle as dict of paramName/value pairs
        if "config_parameters" in stage_context and stage_context["config_parameters"]:
            console.print("  [cyan]Config Parameters:[/cyan]")
            config_params = stage_context["config_parameters"]
            if isinstance(config_params, list):
                # Handle list format [{"paramName": "key", "value": "val"}, ...]
                for param in config_params:
                    if (
                        isinstance(param, dict)
                        and "paramName" in param
                        and "value" in param
                    ):
                        console.print(f"    {param['paramName']}: {param['value']}")
                    else:
                        console.print(f"    {param}")
            elif isinstance(config_params, dict):
                # Handle direct dict format {"key": "value", ...}
                for param_name, param_value in config_params.items():
                    console.print(f"    {param_name}: {param_value}")

        if "layer_names" in stage_context and stage_context["layer_names"]:
            console.print(
                f"  [cyan]Layers:[/cyan] {', '.join(stage_context['layer_names'])}"
            )

        if (
            "layer_name_to_index" in stage_context
            and stage_context["layer_name_to_index"]
        ):
            console.print("  [cyan]Layer Indices:[/cyan]")
            for layer_name, index in stage_context["layer_name_to_index"].items():
                console.print(f"    {layer_name}: {index}")

        # Stage-specific content
        if stage_name in ("behaviors", "layers", "custom"):
            behavior_types = ["holdTaps", "combos", "macros"]
            for behavior_type in behavior_types:
                if behavior_type in stage_context and stage_context[behavior_type]:
                    console.print(f"  [cyan]{behavior_type.title()}:[/cyan]")
                    for behavior in stage_context[behavior_type]:
                        if isinstance(behavior, dict) and "name" in behavior:
                            console.print(f"    - {behavior['name']}")
                        else:
                            console.print(f"    - {behavior}")

        if stage_name in ("layers", "custom") and "layers_by_name" in stage_context:
            layers_by_name = stage_context["layers_by_name"]
            if layers_by_name:
                console.print(
                    f"  [cyan]Layer Content Available:[/cyan] {', '.join(layers_by_name.keys())}"
                )

        # Show utility functions
        utility_functions = [
            key for key in stage_context if key.startswith("<function:")
        ]
        if utility_functions:
            console.print(
                f"  [cyan]Utility Functions:[/cyan] {', '.join(utility_functions)}"
            )

        console.print()  # Add spacing between stages


def _unset_field_value(
    editor_service: Any, layout_file: Path, field_path: str, force: bool
) -> Path:
    """Remove a field value from a layout file."""
    from glovebox.adapters import create_file_adapter
    from glovebox.layout.utils.field_parser import unset_field_value_on_model
    from glovebox.layout.utils.json_operations import load_layout_file, save_layout_file

    file_adapter = create_file_adapter()

    # Load the layout WITHOUT variable resolution to preserve variable references
    layout_data = load_layout_file(
        layout_file, file_adapter, skip_variable_resolution=True
    )

    # Remove the field value
    unset_field_value_on_model(layout_data, field_path)

    # Save the modified layout
    save_layout_file(layout_data, layout_file, file_adapter)

    return layout_file


def _display_variables_usage(
    json_data: dict[str, Any], resolver: VariableResolver, output_format: str
) -> None:
    """Display where each variable is used."""
    usage = resolver.get_variable_usage(json_data)

    if output_format == "json":
        console.print(json.dumps(usage, indent=2))
    else:
        if not usage:
            console.print("[yellow]No variable usage found[/yellow]")
            return

        table = Table(title="Variable Usage")
        table.add_column("Variable", style="cyan")
        table.add_column("Used In", style="green")
        table.add_column("Count", style="blue")

        for var_name, paths in usage.items():
            usage_str = (
                "\n".join(paths)
                if len(paths) <= 5
                else "\n".join(paths[:5]) + f"\n... and {len(paths) - 5} more"
            )
            table.add_row(var_name, usage_str, str(len(paths)))

        console.print(table)
