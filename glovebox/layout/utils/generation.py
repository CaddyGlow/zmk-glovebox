"""Layout generation utilities for configuration and keymap files."""

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.layout.behavior.analysis import get_required_includes_for_layout


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.layout.zmk_generator import ZmkFileContentGenerator

from glovebox.core.errors import LayoutError
from glovebox.layout.models import LayoutData
from glovebox.protocols import FileAdapterProtocol


logger = logging.getLogger(__name__)


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
    # Generate the config using the function
    conf_content, kconfig_settings = generate_kconfig_conf(keymap_data, profile)

    # Write the config file
    file_adapter.write_text(output_path, conf_content)
    
    if kconfig_settings:
        options_summary = " | ".join(f"{k}={v}" for k, v in kconfig_settings.items())
        logger.debug("Generated Kconfig with %d options: %s", len(kconfig_settings), options_summary)
    
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

    # Get resolved includes from the profile and format them as #include <>
    resolved_includes = []
    if (
        hasattr(profile.keyboard_config.keymap, "header_includes")
        and profile.keyboard_config.keymap.header_includes is not None
    ):
        # Format bare header names as #include <header_name>
        resolved_includes = [
            f"#include <{include}>"
            for include in profile.keyboard_config.keymap.header_includes
        ]

    additional_includes = get_required_includes_for_layout(profile, keymap_data)
    resolved_includes.extend(
        [f"#include <{include}>" for include in additional_includes]
    )

    # Generate DTSI components
    # IMPORTANT: Generate behaviors first so they are registered before keymap generation
    layer_defines = dtsi_generator.generate_layer_defines(profile, layer_names)
    behaviors_dtsi = dtsi_generator.generate_behaviors_dtsi(profile, hold_taps_data)
    combos_dtsi = dtsi_generator.generate_combos_dtsi(profile, combos_data, layer_names)
    macros_dtsi = dtsi_generator.generate_macros_dtsi(profile, macros_data)
    input_listeners_dtsi = dtsi_generator.generate_input_listeners_node(
        profile, input_listeners_data
    )
    # Generate keymap node AFTER behaviors are registered
    keymap_node = dtsi_generator.generate_keymap_node(profile, layer_names, layers_data)

    # Get template elements from the keyboard profile
    key_position_header = ""
    if hasattr(profile.keyboard_config.keymap, "key_position_header"):
        key_position_header = profile.keyboard_config.keymap.key_position_header or ""

    system_behaviors_dts = ""
    if hasattr(profile.keyboard_config.keymap, "system_behaviors_dts"):
        system_behaviors_dts = profile.keyboard_config.keymap.system_behaviors_dts or ""

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
    kconfig_options = profile.kconfig_options
    user_options: dict[str, str] = {}

    lines = []
    lines.append("# Generated ZMK configuration")
    lines.append("")

    # Extract user config_parameters (kconfig) options from LayoutData
    for opt in keymap_data.config_parameters:
        line = ""
        comment_prefix = ""

        if opt.param_name in kconfig_options:
            # Supported option - get the real option name
            name = kconfig_options[opt.param_name].name
            if opt.value == kconfig_options[opt.param_name].default:
                # User is setting same value as default
                # Comment it out to allow easier firmware switching
                comment_prefix = "# "
            
            # Track user options (only non-commented ones)
            if not comment_prefix:
                user_options[name] = opt.value

        else:
            # Unsupported option - add warning and comment out
            logger.warning(
                "Unsupported kconfig option '%s' found. This option is not registered "
                "in the keyboard or firmware configuration. Adding as commented line.",
                opt.param_name,
            )

            name = opt.param_name
            kconfig_prefix = profile.keyboard_config.zmk.patterns.kconfig_prefix
            if not name.startswith(kconfig_prefix):
                name = kconfig_prefix + name

            # Comment out unsupported options with explanation
            comment_prefix = "# "
            lines.append(
                f"# Warning: '{opt.param_name}' is not a supported kconfig option"
            )

        line = f"{comment_prefix}{name}={opt.value}"
        lines.append(line)
        lines.append("")  # Add blank line after each option for readability

    # Remove the last blank line if present
    if lines and lines[-1] == "":
        lines.pop()

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

    # Get template content from keymap configuration - support both inline and file templates
    keymap_section = profile.keyboard_config.keymap
    inline_template = keymap_section.keymap_dtsi
    template_file = keymap_section.keymap_dtsi_file

    # Render template based on source type
    if inline_template:
        logger.debug("Using inline keymap template")
        keymap_content = template_adapter.render_string(inline_template, context)
    elif template_file:
        # Resolve template file path
        from .core_operations import resolve_template_file_path

        template_path = resolve_template_file_path(profile.keyboard_name, template_file)
        keymap_content = template_adapter.render_template(template_path, context)
    else:
        raise LayoutError(
            "No keymap template available in keyboard configuration. "
            "Specify either keymap_dtsi (inline) or keymap_dtsi_file (template file)."
        )

    file_adapter.write_text(output_path, keymap_content)


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
        header_includes=keymap_dict.get(
            "header_includes", keymap_dict.get("includes", [])
        ),
        formatting=formatting,
        system_behaviors=system_behaviors,
        kconfig_options=kconfig_options,
        keymap_dtsi=keymap_dict.get("keymap_dtsi"),
        keymap_dtsi_file=keymap_dict.get("keymap_dtsi_file"),
        system_behaviors_dts=keymap_dict.get("system_behaviors_dts"),
        key_position_header=keymap_dict.get("key_position_header"),
    )
