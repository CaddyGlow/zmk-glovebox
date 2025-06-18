"""Layout field editing CLI commands."""

from pathlib import Path
from typing import Annotated

import typer

from glovebox.cli.commands.layout.base import LayoutOutputCommand
from glovebox.cli.decorators import handle_errors
from glovebox.cli.helpers.parameters import OutputFormatOption
from glovebox.layout.editor import create_layout_editor_service


@handle_errors
def get_field(
    layout_file: Annotated[Path, typer.Argument(help="Path to layout JSON file")],
    field_path: Annotated[
        str,
        typer.Argument(
            help="Field path (e.g., 'title', 'layer_names[0]', 'custom_defined_behaviors')"
        ),
    ],
    output_format: Annotated[
        str,
        typer.Option(
            "--output-format", help="Output format: text (default), json, or raw"
        ),
    ] = "text",
) -> None:
    """Get a specific field value from a layout JSON file.

    Supports dot notation and array indexing for nested field access.
    Use bracket notation for array indices and special characters.

    Examples:
        # Get basic fields
        glovebox layout get-field layout.json title
        glovebox layout get-field layout.json version
        glovebox layout get-field layout.json keyboard

        # Get array elements
        glovebox layout get-field layout.json layer_names[0]
        glovebox layout get-field layout.json layer_names[-1]  # Last element

        # Get nested fields
        glovebox layout get-field layout.json config_parameters[0].paramName

        # Get large text fields
        glovebox layout get-field layout.json custom_defined_behaviors --output-format raw
        glovebox layout get-field layout.json custom_devicetree --output-format raw

        # JSON output for automation
        glovebox layout get-field layout.json layer_names --output-format json
    """
    command = LayoutOutputCommand()
    command.validate_layout_file(layout_file)

    try:
        editor_service = create_layout_editor_service()
        value = editor_service.get_field_value(layout_file, field_path)

        # Format output based on requested format
        if output_format.lower() == "json":
            command.format_output(value, "json")
        elif output_format.lower() == "raw":
            # Raw output with no formatting
            print(str(value))
        else:
            # Text format with basic formatting
            if isinstance(value, dict | list):
                command.format_output(value, "json")
            else:
                print(str(value))

    except Exception as e:
        command.handle_service_error(e, f"get field '{field_path}'")


@handle_errors
def set_field(
    layout_file: Annotated[Path, typer.Argument(help="Path to layout JSON file")],
    field_path: Annotated[
        str,
        typer.Argument(
            help="Field path (e.g., 'title', 'layer_names[0]', 'custom_defined_behaviors')"
        ),
    ],
    value: Annotated[str, typer.Argument(help="New value for the field")],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output", "-o", help="Output file (default: overwrite original)"
        ),
    ] = None,
    value_type: Annotated[
        str,
        typer.Option(
            "--type", help="Value type: auto (default), string, number, boolean, json"
        ),
    ] = "auto",
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files")
    ] = False,
) -> None:
    """Set a specific field value in a layout JSON file.

    Supports dot notation and array indexing for nested field access.
    Values are automatically parsed based on type or can be explicitly typed.

    Examples:
        # Set basic string fields
        glovebox layout set-field layout.json title "My Custom Layout"
        glovebox layout set-field layout.json creator "username"

        # Set with explicit types
        glovebox layout set-field layout.json version "2.0.0" --type string

        # Set array elements
        glovebox layout set-field layout.json layer_names[0] "Base" --type string

        # Set large text fields from files
        glovebox layout set-field layout.json custom_defined_behaviors "$(cat behaviors.dtsi)" --type string

        # Set configuration values
        glovebox layout set-field layout.json config_parameters[0].value "true" --type string

        # Set with JSON values
        glovebox layout set-field layout.json tags '["custom", "modified"]' --type json

        # Output to different file
        glovebox layout set-field layout.json title "New Title" --output modified_layout.json
    """
    command = LayoutOutputCommand()
    command.validate_layout_file(layout_file)

    try:
        editor_service = create_layout_editor_service()
        output_path = editor_service.set_field_value(
            layout_file=layout_file,
            field_path=field_path,
            value=value,
            value_type=value_type,
            output=output,
            force=force,
        )

        # Show success with details
        details = {
            "file": output_path,
            "field": field_path,
            "value": str(value)[:100] + ("..." if len(str(value)) > 100 else ""),
        }
        command.print_operation_success("Field updated successfully", details)

    except Exception as e:
        command.handle_service_error(e, f"set field '{field_path}'")
