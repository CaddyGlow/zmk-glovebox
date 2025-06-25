"""JSON file operations for layout data."""

import json
from pathlib import Path
from typing import Any

from glovebox.layout.models import LayoutData
from glovebox.protocols import FileAdapterProtocol


# Module-level flag to control variable resolution
_skip_variable_resolution = False


class VariableResolutionContext:
    """Context manager for controlling variable resolution during operations."""

    def __init__(self, skip: bool = True) -> None:
        self.skip = skip
        self.old_value: bool | None = None

    def __enter__(self) -> "VariableResolutionContext":
        global _skip_variable_resolution
        self.old_value = _skip_variable_resolution
        _skip_variable_resolution = self.skip
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        global _skip_variable_resolution
        if self.old_value is not None:
            _skip_variable_resolution = self.old_value


def load_layout_file(
    file_path: Path,
    file_adapter: FileAdapterProtocol,
    skip_variable_resolution: bool = False,
    skip_template_processing: bool = False,
) -> LayoutData:
    """Load and validate a layout JSON file.

    Args:
        file_path: Path to the layout JSON file
        file_adapter: File adapter for file operations
        skip_variable_resolution: If True, skip variable resolution to preserve
                                  original variable references (for edit operations)
        skip_template_processing: If True, skip template processing to avoid
                                  serialization issues (for edit operations)

    Returns:
        Validated LayoutData instance

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file contains invalid JSON
        ValueError: If data doesn't match LayoutData schema
    """
    if not file_adapter.check_exists(file_path):
        raise FileNotFoundError(f"Layout file not found: {file_path}")

    global _skip_variable_resolution

    try:
        content = file_adapter.read_text(file_path)
        data = json.loads(content)

        # Convert integer timestamps to datetime objects for date fields
        if "date" in data and isinstance(data["date"], int):
            from datetime import datetime

            data["date"] = datetime.fromtimestamp(data["date"])

        # Set the module flag before validation
        old_skip_value = _skip_variable_resolution
        _skip_variable_resolution = skip_variable_resolution

        try:
            # Conditionally skip template processing to avoid serialization issues
            if skip_template_processing:
                with VariableResolutionContext(skip=True):
                    return LayoutData.model_validate(data)
            else:
                return LayoutData.model_validate(data)
        finally:
            # Restore the original flag value
            _skip_variable_resolution = old_skip_value

    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Invalid JSON in layout file {file_path}: {e.msg}", e.doc, e.pos
        ) from e
    except Exception as e:
        raise ValueError(f"Invalid layout data in {file_path}: {e}") from e


def should_skip_variable_resolution() -> bool:
    """Check if variable resolution should be skipped."""
    return _skip_variable_resolution


def save_layout_file(
    layout_data: LayoutData, file_path: Path, file_adapter: FileAdapterProtocol
) -> None:
    """Save layout data to JSON file with proper formatting.

    Args:
        layout_data: LayoutData instance to save
        file_path: Path where to save the file
        file_adapter: File adapter for file operations

    Raises:
        OSError: If file cannot be written
    """
    try:
        # Use Pydantic's serialization with aliases and sorted fields
        content = json.dumps(
            layout_data.model_dump(by_alias=True, exclude_unset=True, mode="json"),
            indent=2,
            ensure_ascii=False,
        )
        file_adapter.write_text(file_path, content)
    except OSError as e:
        raise OSError(f"Failed to save layout file {file_path}: {e}") from e


def load_json_data(
    file_path: Path, file_adapter: FileAdapterProtocol
) -> dict[str, Any]:
    """Load raw JSON data from file.

    Args:
        file_path: Path to JSON file
        file_adapter: File adapter for file operations

    Returns:
        Dictionary with JSON data

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file contains invalid JSON
    """
    if not file_adapter.check_exists(file_path):
        raise FileNotFoundError(f"JSON file not found: {file_path}")

    try:
        content = file_adapter.read_text(file_path)
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError(f"JSON file {file_path} does not contain a dictionary")
        return data
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Invalid JSON in file {file_path}: {e.msg}", e.doc, e.pos
        ) from e


def save_json_data(
    data: dict[str, Any] | list[Any], file_path: Path, file_adapter: FileAdapterProtocol
) -> None:
    """Save raw JSON data to file.

    Args:
        data: Data to save as JSON
        file_path: Path where to save the file
        file_adapter: File adapter for file operations

    Raises:
        OSError: If file cannot be written
    """
    try:
        content = json.dumps(data, indent=2, ensure_ascii=False)
        file_adapter.write_text(file_path, content)
    except OSError as e:
        raise OSError(f"Failed to save JSON file {file_path}: {e}") from e
