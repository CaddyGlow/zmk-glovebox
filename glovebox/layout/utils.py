"""Utility functions for layout operations."""

import json
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar


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
    output_dir = output_prefix_path.parent
    base_name = output_prefix_path.name

    # Use configurable file extensions if profile is provided, otherwise use defaults
    if profile:
        extensions = profile.keyboard_config.zmk.file_extensions
        keymap_ext = extensions.keymap
        conf_ext = extensions.conf
        json_ext = extensions.metadata
    else:
        # Default extensions for backward compatibility
        keymap_ext = ".keymap"
        conf_ext = ".conf"
        json_ext = ".json"

    return OutputPaths(
        keymap=output_dir / f"{base_name}{keymap_ext}",
        conf=output_dir / f"{base_name}{conf_ext}",
        json=output_dir / f"{base_name}{json_ext}",
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
    profile: "KeyboardProfile",
    keymap_data: LayoutData,
    output_path: Path,
) -> dict[str, str]:
    """Generate configuration file and return settings.

    Args:
        file_adapter: File adapter for writing files
        profile: Keyboard profile with configuration
        keymap_data: Layout data for configuration generation
        output_path: Path to write the configuration file

    Returns:
        Dictionary of kconfig settings
    """
    logger.info("Generating Kconfig .conf file...")

    # Generate the config using the function
    conf_content, kconfig_settings = generate_kconfig_conf(keymap_data, profile)

    # Write the config file
    file_adapter.write_text(output_path, conf_content)
    logger.info("Successfully generated config and saved to %s", output_path)
    return kconfig_settings


def build_template_context(
    keymap_data: LayoutData,
    profile: "KeyboardProfile",
    dtsi_generator: "ZmkFileContentGenerator",
) -> dict[str, Any]:
    """Build template context with generated DTSI content.

    Args:
        keymap_data: Keymap data model
        profile: Keyboard profile with configuration
        dtsi_generator: DTSI generator for creating template content

    Returns:
        Dictionary with template context
    """
    # Extract data for generation with fallback to empty lists
    layer_names = keymap_data.layer_names
    layers_data = keymap_data.layers
    hold_taps_data = keymap_data.hold_taps
    combos_data = keymap_data.combos
    macros_data = keymap_data.macros
    input_listeners_data = getattr(keymap_data, "input_listeners", [])

    # Get resolved includes from the profile
    resolved_includes = []
    if (
        hasattr(profile.keyboard_config.keymap, "includes")
        and profile.keyboard_config.keymap.includes is not None
    ):
        resolved_includes = profile.keyboard_config.keymap.includes

    # Generate DTSI components
    layer_defines = dtsi_generator.generate_layer_defines(profile, layer_names)
    keymap_node = dtsi_generator.generate_keymap_node(profile, layer_names, layers_data)
    behaviors_dtsi = dtsi_generator.generate_behaviors_dtsi(profile, hold_taps_data)
    combos_dtsi = dtsi_generator.generate_combos_dtsi(profile, combos_data, layer_names)
    macros_dtsi = dtsi_generator.generate_macros_dtsi(profile, macros_data)
    input_listeners_dtsi = dtsi_generator.generate_input_listeners_node(
        profile, input_listeners_data
    )

    # Get template elements from the keyboard profile
    key_position_header = (
        profile.keyboard_config.keymap.key_position_header
        if hasattr(profile.keyboard_config.keymap, "key_position_header")
        else ""
    )
    system_behaviors_dts = (
        profile.keyboard_config.keymap.system_behaviors_dts
        if hasattr(profile.keyboard_config.keymap, "system_behaviors_dts")
        else ""
    )

    # Profile identifiers
    profile_name = f"{profile.keyboard_name}/{profile.firmware_version}"
    firmware_version = profile.firmware_version

    # Build and return the template context with defaults for missing values
    context = {
        "keyboard": keymap_data.keyboard,
        "layer_names": layer_names,
        "layers": layers_data,
        "layer_defines": layer_defines,
        "keymap_node": keymap_node,
        "user_behaviors_dtsi": behaviors_dtsi,
        "combos_dtsi": combos_dtsi,
        "input_listeners_dtsi": input_listeners_dtsi,
        "user_macros_dtsi": macros_dtsi,
        "resolved_includes": "\n".join(resolved_includes),
        "key_position_header": key_position_header,
        "system_behaviors_dts": system_behaviors_dts,
        "custom_defined_behaviors": keymap_data.custom_defined_behaviors or "",
        "custom_devicetree": keymap_data.custom_devicetree or "",
        "profile_name": profile_name,
        "firmware_version": firmware_version,
        "generation_timestamp": datetime.now().isoformat(),
    }

    return context


def generate_kconfig_conf(
    keymap_data: LayoutData,
    profile: "KeyboardProfile",
) -> tuple[str, dict[str, str]]:
    """Generate kconfig content and settings from keymap data.

    Args:
        keymap_data: Keymap data with configuration parameters
        profile: Keyboard profile with kconfig options

    Returns:
        Tuple of (kconfig_content, kconfig_settings)
    """
    logger.info("Generating kconfig configuration")

    kconfig_options = profile.kconfig_options
    user_options: dict[str, str] = {}

    lines = []

    # Extract user config_parameters (kconfig) options from LayoutData
    for opt in keymap_data.config_parameters:
        line = ""
        if opt.param_name in kconfig_options:
            # get the real option name
            name = kconfig_options[opt.param_name].name
            if opt.value == kconfig_options[opt.param_name].default:
                # TODO: rewrite this comment
                # check if the user is setting same value as default
                # in that case, we set it but in comment
                # that allows the user to switch more easily firmware
                # without changing the kconfig
                line = "# "
        else:
            name = opt.param_name
            kconfig_prefix = profile.keyboard_config.zmk.patterns.kconfig_prefix
            if not name.startswith(kconfig_prefix):
                name = kconfig_prefix + name

        line += f"{name}={opt.value}"
        lines.append(line)

    # Generate formatted kconfig content
    lines.append("# Generated ZMK configuration")
    lines.append("")

    kconfig_content = "\n".join(lines)
    return kconfig_content, user_options


def generate_keymap_file(
    file_adapter: FileAdapterProtocol,
    template_adapter: Any,
    dtsi_generator: "ZmkFileContentGenerator",
    keymap_data: LayoutData,
    profile: "KeyboardProfile",
    output_path: Path,
) -> None:
    """Generate keymap file.

    Args:
        file_adapter: File adapter for writing files
        template_adapter: Template adapter for rendering
        dtsi_generator: DTSI generator for creating template content
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

    # Build template context using the function
    context = build_template_context(keymap_data, profile, dtsi_generator)

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
    from glovebox.config.models import FormattingConfig, KConfigOption, KeymapSection
    from glovebox.layout.models import (
        BehaviorCommand,
        BehaviorParameter,
        SystemBehavior,
    )

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
            key_gap=formatting_data.get("key_gap", "  "),
            base_indent=formatting_data.get("base_indent", ""),
            rows=formatting_data.get("rows", []),
        )
    else:
        formatting = FormattingConfig(key_gap="  ")

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
