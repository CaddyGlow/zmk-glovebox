"""Configuration generator for creating ZMK config files."""

import logging
from typing import Any

from glovebox.config.models import KConfigOption
from glovebox.config.profile import KeyboardProfile
from glovebox.models.keymap import KeymapData


logger = logging.getLogger(__name__)


class ConfigGenerator:
    """Generator for ZMK configuration files."""

    def __init__(self) -> None:
        """Initialize the config generator."""
        logger.debug("ConfigGenerator initialized")

    def generate_kconfig(
        self,
        keymap_data_dict: dict[str, Any],
        kconfig_map: dict[str, dict[str, str]],
    ) -> tuple[str, dict[str, str]]:
        """Generate Kconfig content and settings.

        Args:
            keymap_data_dict: Keymap data containing config parameters
            kconfig_map: Mapping from JSON params to Kconfig options

        Returns:
            Tuple of (kconfig_content, kconfig_settings)
        """
        logger.info("Generating Kconfig content")

        kconfig_settings = {}
        config_lines = []

        # Add header
        config_lines.append("# Generated ZMK configuration")
        config_lines.append("")

        # Get config parameters
        config_params = keymap_data_dict.get("config_parameters", [])
        kconfig_data = keymap_data_dict.get("kconfig", {})
        keyboard_name = keymap_data_dict.get("keyboard", "unknown")

        # Process explicit kconfig settings first
        for key, value in kconfig_data.items():
            if key.startswith("CONFIG_"):
                config_key = key
            else:
                config_key = f"CONFIG_{key}"

            kconfig_settings[config_key] = str(value)

            if str(value).lower() in ["true", "y", "yes", "1"]:
                config_lines.append(f"{config_key}=y")
            elif str(value).lower() in ["false", "n", "no", "0"]:
                config_lines.append(f"# {config_key} is not set")
            else:
                config_lines.append(f'{config_key}="{value}"')

        # Process config parameters using kconfig map
        for param in config_params:
            if isinstance(param, dict):
                # Handle dict-style parameters from JSON
                param_name = param.get("paramName")
                param_value = param.get("value")
            else:
                # Handle ConfigParameter objects
                param_name = getattr(param, "param_name", None)
                param_value = getattr(param, "value", None)

            if not param_name or param_value is None:
                logger.warning(f"Invalid config parameter: {param}")
                continue

            # Look up in kconfig map
            kconfig_info = kconfig_map.get(param_name, {})
            if not kconfig_info:
                logger.warning(f"No kconfig mapping found for parameter: {param_name}")
                continue

            config_key = kconfig_info.get("config_key", f"CONFIG_{param_name.upper()}")
            param_type = kconfig_info.get("type", "string")

            # Skip if already processed
            if config_key in kconfig_settings:
                continue

            kconfig_settings[config_key] = str(param_value)

            # Format based on type
            if param_type == "bool":
                if str(param_value).lower() in ["true", "y", "yes", "1"]:
                    config_lines.append(f"{config_key}=y")
                else:
                    config_lines.append(f"# {config_key} is not set")
            elif param_type == "int":
                config_lines.append(f"{config_key}={param_value}")
            else:  # string
                config_lines.append(f'{config_key}="{param_value}"')

        # Add common ZMK settings
        default_configs = {
            "CONFIG_ZMK_KEYBOARD_NAME": keyboard_name,
        }

        for config_key, default_value in default_configs.items():
            if config_key not in kconfig_settings:
                kconfig_settings[config_key] = str(default_value)
                if config_key.endswith("_NAME"):
                    config_lines.append(f'{config_key}="{default_value}"')
                else:
                    config_lines.append(f"{config_key}={default_value}")

        config_content = "\n".join(config_lines)

        logger.info(f"Generated Kconfig with {len(kconfig_settings)} settings")
        return config_content, kconfig_settings


def create_config_generator() -> ConfigGenerator:
    """
    Create a ConfigGenerator instance.

    Returns:
        ConfigGenerator instance
    """
    return ConfigGenerator()
