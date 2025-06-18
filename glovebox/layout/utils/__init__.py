"""Layout utility modules."""

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from . import field_parser, json_operations, validation

if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.firmware.models import OutputPaths
    from glovebox.layout.models import LayoutData, LayoutResult

T = TypeVar("T")

# Load the parent utils.py module directly for backward compatibility
_utils_path = Path(__file__).parent.parent / "utils.py"
_spec = importlib.util.spec_from_file_location(
    "glovebox.layout.utils_orig", _utils_path
)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Could not load utils module from {_utils_path}")
_utils_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_utils_module)

# Type-annotated function assignments
build_template_context: Callable[..., dict[str, Any]] = (
    _utils_module.build_template_context
)
convert_keymap_section_from_dict: Callable[..., Any] = (
    _utils_module.convert_keymap_section_from_dict
)
generate_config_file: Callable[..., dict[str, str]] = _utils_module.generate_config_file
generate_kconfig_conf: Callable[..., tuple[str, dict[str, str]]] = (
    _utils_module.generate_kconfig_conf
)
generate_keymap_file: Callable[..., None] = _utils_module.generate_keymap_file
load_json_file: Callable[..., dict[str, Any]] = _utils_module.load_json_file
prepare_output_paths: Callable[..., "OutputPaths"] = _utils_module.prepare_output_paths
process_json_file: Callable[..., T] = _utils_module.process_json_file
resolve_template_file_path: Callable[..., Path] = (
    _utils_module.resolve_template_file_path
)
validate_keymap_data: Callable[..., "LayoutData"] = _utils_module.validate_keymap_data

__all__ = [
    # New modular utilities
    "field_parser",
    "json_operations",
    "validation",
    # Backward compatibility exports
    "build_template_context",
    "convert_keymap_section_from_dict",
    "generate_config_file",
    "generate_kconfig_conf",
    "generate_keymap_file",
    "load_json_file",
    "prepare_output_paths",
    "process_json_file",
    "resolve_template_file_path",
    "validate_keymap_data",
]
