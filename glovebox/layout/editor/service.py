"""Layout editor service for field manipulation operations."""

from pathlib import Path
from typing import Any

from glovebox.layout.models import LayoutData
from glovebox.layout.utils.field_parser import (
    extract_field_value_from_model,
    parse_field_value,
    set_field_value_on_model,
    unset_field_value_on_model,
)
from glovebox.layout.utils.json_operations import (
    VariableResolutionContext,
    load_layout_file,
    save_layout_file,
)
from glovebox.layout.utils.validation import validate_output_path
from glovebox.layout.utils.variable_resolver import VariableResolver
from glovebox.protocols import FileAdapterProtocol


class LayoutEditorService:
    """Service for editing layout field values."""

    def __init__(self, file_adapter: FileAdapterProtocol) -> None:
        """Initialize the editor service with required dependencies."""
        self.file_adapter = file_adapter

    def get_field_value(self, layout_file: Path, field_path: str) -> Any:
        """Get a specific field value from a layout file.

        Args:
            layout_file: Path to layout JSON file
            field_path: Field path with dot notation and array indexing

        Returns:
            Field value

        Raises:
            FileNotFoundError: If layout file doesn't exist
            KeyError: If field path is not found
            ValueError: If field path or array index is invalid
        """
        # Load WITHOUT variable resolution to preserve original variable references
        layout_data = load_layout_file(layout_file, self.file_adapter, skip_variable_resolution=True)
        return extract_field_value_from_model(layout_data, field_path)

    def set_field_value(
        self,
        layout_file: Path,
        field_path: str,
        value: str,
        value_type: str = "auto",
        output: Path | None = None,
        force: bool = False,
    ) -> Path:
        """Set a specific field value in a layout file.

        Args:
            layout_file: Path to layout JSON file
            field_path: Field path with dot notation and array indexing
            value: String value to parse and set
            value_type: Value type ('auto', 'string', 'number', 'boolean', 'json')
            output: Output file path (defaults to input file)
            force: Whether to overwrite existing files

        Returns:
            Path to the output file

        Raises:
            FileNotFoundError: If layout file doesn't exist
            KeyError: If field path is not found
            ValueError: If field path, value, or output path is invalid
        """
        # Wrap entire operation in variable resolution context to preserve variables
        with VariableResolutionContext(skip=True):
            # Load WITHOUT variable resolution to preserve original variable references
            layout_data = load_layout_file(layout_file, self.file_adapter, skip_variable_resolution=True)

            # Parse and convert the value based on type
            parsed_value = parse_field_value(value, value_type)

            # Set the field value directly on the Pydantic model for validation
            set_field_value_on_model(layout_data, field_path, parsed_value)

            # Determine output path
            output_path = output if output is not None else layout_file

            # Validate output path
            validate_output_path(output_path, layout_file, force)

            # Save the modified layout
            save_layout_file(layout_data, output_path, self.file_adapter)

            return output_path

    def unset_field_value(
        self,
        layout_file: Path,
        field_path: str,
        output: Path | None = None,
        force: bool = False,
    ) -> Path:
        """Remove a specific field value from a layout file.

        Args:
            layout_file: Path to layout JSON file
            field_path: Field path with dot notation and array indexing
            output: Output file path (defaults to input file)
            force: Whether to overwrite existing files

        Returns:
            Path to the output file

        Raises:
            FileNotFoundError: If layout file doesn't exist
            KeyError: If field path is not found
            ValueError: If field path or output path is invalid
        """
        # Wrap entire operation in variable resolution context to preserve variables
        with VariableResolutionContext(skip=True):
            # Load WITHOUT variable resolution to preserve original variable references
            layout_data = load_layout_file(layout_file, self.file_adapter, skip_variable_resolution=True)

            # Remove the field value directly on the Pydantic model
            unset_field_value_on_model(layout_data, field_path)

            # Determine output path
            output_path = output if output is not None else layout_file

            # Validate output path
            validate_output_path(output_path, layout_file, force)

            # Save the modified layout
            save_layout_file(layout_data, output_path, self.file_adapter)

            return output_path


def create_layout_editor_service(
    file_adapter: FileAdapterProtocol,
) -> LayoutEditorService:
    """Create a LayoutEditorService instance with explicit dependencies.

    Args:
        file_adapter: Required FileAdapter for file operations

    Returns:
        LayoutEditorService instance
    """
    return LayoutEditorService(file_adapter)
