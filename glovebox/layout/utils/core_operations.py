"""Core layout operations and file processing utilities."""

import json
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from glovebox.layout.behavior.analysis import get_required_includes_for_layout


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.layout.zmk_generator import ZmkFileContentGenerator

from glovebox.core.errors import LayoutError
from glovebox.firmware.models import OutputPaths
from glovebox.layout.models import LayoutData
from glovebox.protocols import FileAdapterProtocol


logger = logging.getLogger(__name__)
T = TypeVar("T")


def prepare_output_paths(
    output_file_prefix: str | Path, profile: "KeyboardProfile | None" = None
) -> OutputPaths:
    """Prepare standardized output file paths.

    Given an output file prefix (which can be a path and base name),
    generates an OutputPaths object with standardized paths.

    Args:
        output_file_prefix: Base path and name for output files (str or Path)
        profile: Optional keyboard profile for configurable file extensions

    Returns:
        OutputPaths with standardized paths for keymap, conf, and json files

    Examples:
        >>> prepare_output_paths("/tmp/my_keymap")
        OutputPaths(
            keymap=PosixPath('/tmp/my_keymap.keymap'),
            conf=PosixPath('/tmp/my_keymap.conf'),
            json=PosixPath('/tmp/my_keymap.json')
        )
    """
    output_prefix_path = Path(output_file_prefix).resolve()

    # Extract directory and base name
    output_dir = output_prefix_path.parent
    base_name = output_prefix_path.name

    # Generate paths with appropriate extensions
    keymap_path = output_dir / f"{base_name}.keymap"
    conf_path = output_dir / f"{base_name}.conf"
    json_path = output_dir / f"{base_name}.json"

    return OutputPaths(
        keymap=keymap_path,
        conf=conf_path,
        json=json_path,
    )


def process_json_file(
    file_path: Path,
    operation_name: str,
    operation_func: Callable[[LayoutData], T],
    file_adapter: FileAdapterProtocol,
    process_templates: bool = True,
) -> T:
    """Process a JSON keymap file with error handling and validation.

    Args:
        file_path: Path to the JSON file to process
        operation_name: Human-readable name of the operation for error messages
        operation_func: Function that takes LayoutData and returns result
        file_adapter: File adapter for reading operations
        process_templates: Whether to process Jinja2 templates (default: True)

    Returns:
        Result from the operation function

    Raises:
        LayoutError: If file loading, validation, or operation fails
    """
    try:
        logger.info("%s from %s...", operation_name, file_path)

        # Load with or without template processing based on parameter
        from .json_operations import load_layout_file

        layout_data = load_layout_file(
            file_path,
            file_adapter,
            skip_template_processing=(not process_templates),
        )

        # Perform the operation
        return operation_func(layout_data)

    except Exception as e:
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("%s failed: %s", operation_name, e, exc_info=exc_info)
        raise LayoutError(f"{operation_name} failed: {e}") from e


def resolve_template_file_path(keyboard_name: str, template_file: str) -> Path:
    """Resolve a template file path relative to keyboard configuration directories.

    Args:
        keyboard_name: Name of the keyboard configuration
        template_file: Relative path to the template file

    Returns:
        Resolved absolute path to the template file

    Raises:
        LayoutError: If the template file cannot be found
    """
    from glovebox.config.keyboard_profile import initialize_search_paths

    # Get the standard search paths for keyboard configurations
    search_paths = initialize_search_paths()
    template_path_obj = Path(template_file)

    # If absolute path, validate and use as-is
    if template_path_obj.is_absolute():
        if template_path_obj.exists():
            return template_path_obj.resolve()
        raise LayoutError(f"Template file not found: {template_file}")

    # Try to resolve relative to keyboard configuration directories
    for search_path in search_paths:
        # Try relative to keyboard directory (for modular configs)
        keyboard_dir = search_path / keyboard_name
        if keyboard_dir.exists() and keyboard_dir.is_dir():
            keyboard_relative = keyboard_dir / template_path_obj
            if keyboard_relative.exists():
                return keyboard_relative.resolve()

        # Try relative to search path root
        search_relative = search_path / template_path_obj
        if search_relative.exists():
            return search_relative.resolve()

    raise LayoutError(
        f"Template file not found: {template_file}. "
        f"Searched relative to keyboard '{keyboard_name}' directories in: "
        f"{[str(p) for p in search_paths]}"
    )
