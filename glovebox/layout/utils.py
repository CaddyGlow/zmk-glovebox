"""Utility functions for layout operations."""

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.layout.zmk_generator import ZmkFileContentGenerator

from glovebox.core.errors import LayoutError
from glovebox.layout.models import LayoutData
from glovebox.models.build import OutputPaths
from glovebox.protocols import FileAdapterProtocol


logger = logging.getLogger(__name__)
T = TypeVar("T")


def prepare_output_paths(output_file_prefix: str | Path) -> OutputPaths:
    """Prepare standardized output file paths.

    Given an output file prefix (which can be a path and base name),
    generates an OutputPaths object with standardized paths.

    Args:
        output_file_prefix: Base path and name for output files (str or Path)

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
    output_dir = output_prefix_path.parent
    base_name = output_prefix_path.name

    return OutputPaths(
        keymap=output_dir / f"{base_name}.keymap",
        conf=output_dir / f"{base_name}.conf",
        json=output_dir / f"{base_name}.json",
    )


def process_json_file(
    file_path: Path,
    operation_name: str,
    process_func: Callable[[LayoutData], T],
    file_adapter: FileAdapterProtocol,
) -> T:
    """Process a JSON keymap file with standard error handling and validation.

    Args:
        file_path: Path to the JSON file to process
        operation_name: Name of the operation for logging/error messages
        process_func: Function to call with validated LayoutData
        file_adapter: File adapter for reading files

    Returns:
        Result from process_func

    Raises:
        LayoutError: If file processing fails
    """
    logger.info("%s from %s...", operation_name, file_path)

    try:
        # Check if the file exists
        if not file_path.exists():
            raise LayoutError(f"Input file not found: {file_path}")

        # Load JSON data
        json_data = load_json_file(file_path, file_adapter)

        # Validate as LayoutData
        keymap_data = validate_keymap_data(json_data)

        # Process using the validated data
        return process_func(keymap_data)

    except Exception as e:
        logger.error("%s failed: %s", operation_name, e)
        raise LayoutError(f"{operation_name} failed: {e}") from e


def load_json_file(
    file_path: Path, file_adapter: FileAdapterProtocol
) -> dict[str, Any]:
    """Load and parse JSON from a file using the file adapter.

    Args:
        file_path: Path to the JSON file
        file_adapter: File adapter for reading files

    Returns:
        Parsed JSON as dictionary

    Raises:
        LayoutError: If file loading or parsing fails
    """
    try:
        result = file_adapter.read_json(file_path)
        if not isinstance(result, dict):
            raise LayoutError(
                f"Expected JSON object in file {file_path}, got {type(result)}"
            )
        return result
    except json.JSONDecodeError as e:
        raise LayoutError(f"Invalid JSON in file {file_path}: {e}") from e
    except Exception as e:
        raise LayoutError(f"Error reading file {file_path}: {e}") from e


def validate_keymap_data(json_data: dict[str, Any]) -> LayoutData:
    """Validate JSON data as LayoutData.

    Args:
        json_data: Raw JSON data to validate

    Returns:
        Validated LayoutData instance

    Raises:
        LayoutError: If validation fails
    """
    try:
        return LayoutData.model_validate(json_data)
    except Exception as e:
        raise LayoutError(f"Invalid keymap data: {e}") from e


def generate_config_file(
    file_adapter: FileAdapterProtocol,
    dtsi_generator: "ZmkFileContentGenerator",
    profile: "KeyboardProfile",
    keymap_data: LayoutData,
    output_path: Path,
) -> dict[str, str]:
    """Generate configuration file and return settings.

    Args:
        file_adapter: File adapter for writing files
        dtsi_generator: Generator for creating configuration content
        profile: Keyboard profile with configuration
        keymap_data: Layout data for configuration generation
        output_path: Path to write the configuration file

    Returns:
        Dictionary of kconfig settings
    """
    logger.info("Generating Kconfig .conf file...")

    # Use the ZmkFileContentGenerator to generate the config
    conf_content, kconfig_settings = dtsi_generator.generate_kconfig_conf(
        keymap_data, profile
    )

    # Write the config file
    file_adapter.write_text(output_path, conf_content)
    logger.info("Successfully generated config and saved to %s", output_path)
    return kconfig_settings


def generate_keymap_file(
    file_adapter: FileAdapterProtocol,
    template_adapter: Any,
    context_builder: Any,
    keymap_data: LayoutData,
    profile: "KeyboardProfile",
    output_path: Path,
) -> None:
    """Generate keymap file.

    Args:
        file_adapter: File adapter for writing files
        template_adapter: Template adapter for rendering
        context_builder: Builder for template context
        keymap_data: Layout data for keymap generation
        profile: Keyboard profile with configuration
        output_path: Path to write the keymap file

    Raises:
        LayoutError: If keymap generation fails
    """
    logger.info(
        "Building .keymap file for %s/%s",
        profile.keyboard_name,
        profile.firmware_version,
    )

    # Build template context using the context builder
    context = context_builder.build_context(keymap_data, profile)

    # Get template content from keymap configuration
    template_content = profile.keyboard_config.keymap.keymap_dtsi

    # Render template
    if template_content:
        keymap_content = template_adapter.render_string(template_content, context)
    else:
        raise LayoutError("No keymap_dtsi template available in keyboard configuration")

    file_adapter.write_text(output_path, keymap_content)
    logger.info("Successfully built keymap and saved to %s", output_path)


def convert_keymap_section_from_dict(keymap_dict: dict[str, Any]) -> Any:
    """Convert keymap section dictionary to KeymapSection object.

    This function handles the conversion of system behaviors and other keymap
    components from dictionary format to proper dataclass instances.

    Args:
        keymap_dict: Dictionary containing keymap section data

    Returns:
        KeymapSection object with converted data
    """
    from glovebox.layout.models import (
        BehaviorCommand,
        BehaviorParameter,
        SystemBehavior,
    )
    from glovebox.models.config import FormattingConfig, KConfigOption, KeymapSection

    # Convert system behaviors
    system_behaviors = []
    for behavior_data in keymap_dict.get("system_behaviors", []):
        # Convert commands
        commands = None
        if "commands" in behavior_data:
            commands = []
            for cmd_data in behavior_data["commands"]:
                # Convert additional params
                additional_params = None
                if "additionalParams" in cmd_data:
                    additional_params = []
                    for param_data in cmd_data["additionalParams"]:
                        additional_params.append(BehaviorParameter(**param_data))

                commands.append(
                    BehaviorCommand(
                        code=cmd_data.get("code", ""),
                        name=cmd_data.get("name"),
                        description=cmd_data.get("description"),
                        flatten=cmd_data.get("flatten", False),
                        additional_params=additional_params,
                    )
                )

        # Convert params
        params = []
        for param_data in behavior_data.get("params", []):
            if isinstance(param_data, dict):
                params.append(BehaviorParameter(**param_data))
            else:
                params.append(param_data)

        system_behaviors.append(
            SystemBehavior(
                code=behavior_data.get("code", ""),
                name=behavior_data.get("name", ""),
                description=behavior_data.get("description", ""),
                expected_params=behavior_data.get("expected_params", 0),
                origin=behavior_data.get("origin", ""),
                params=params,
                url=behavior_data.get("url"),
                is_macro_control_behavior=behavior_data.get(
                    "isMacroControlBehavior", False
                ),
                includes=behavior_data.get("includes"),
                commands=commands,
            )
        )

    # Convert kconfig options
    kconfig_options = {}
    for option_name, option_data in keymap_dict.get("kconfig_options", {}).items():
        kconfig_options[option_name] = KConfigOption(**option_data)

    # Convert formatting config
    formatting_data = keymap_dict.get("formatting", {})
    if isinstance(formatting_data, dict):
        formatting = FormattingConfig(
            default_key_width=formatting_data.get("default_key_width", 8),
            key_gap=formatting_data.get("key_gap", "  "),
            base_indent=formatting_data.get("base_indent", ""),
            rows=formatting_data.get("rows", []),
        )
    else:
        formatting = FormattingConfig(default_key_width=8, key_gap="  ")

    # Create and return keymap section
    return KeymapSection(
        includes=keymap_dict.get("includes", []),
        formatting=formatting,
        system_behaviors=system_behaviors,
        kconfig_options=kconfig_options,
        keymap_dtsi=keymap_dict.get("keymap_dtsi"),
        system_behaviors_dts=keymap_dict.get("system_behaviors_dts"),
        key_position_header=keymap_dict.get("key_position_header"),
    )
