"""
Keyboard configuration loading module.

This module provides functions for loading and accessing keyboard configurations
from YAML files, using typed dataclasses for improved safety and usability.
"""

import os
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import yaml


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

from glovebox.config.models import FirmwareConfig, KeyboardConfig
from glovebox.config.schema import validate_keyboard_config
from glovebox.core.errors import ConfigError
from glovebox.core.logging import get_logger


logger = get_logger(__name__)


# Module-level cache of loaded configurations
_keyboard_configs: dict[str, dict] = {}
_keyboard_configs_typed: dict[str, KeyboardConfig] = {}


def _initialize_search_paths() -> list[Path]:
    """Initialize the paths where keyboard configurations are searched for.

    Returns:
        List of paths to search for keyboard configurations
    """
    # Built-in configurations in the package
    package_path = Path(__file__).parent.parent.parent
    builtin_paths = [
        package_path / "keyboards",
    ]

    # User configurations in ~/.config/glovebox/keyboards
    user_config_dir = Path.home() / ".config" / "glovebox" / "keyboards"

    # Environment variable for additional configuration paths
    env_paths = os.environ.get("GLOVEBOX_KEYBOARD_PATH", "")
    extra_paths = [Path(p) for p in env_paths.split(":") if p]

    # Combine all paths
    all_paths = builtin_paths + [user_config_dir] + extra_paths

    # Filter out non-existent paths
    search_paths = [p for p in all_paths if p.exists() and p.is_dir()]
    logger.debug("Keyboard configuration search paths: %s", search_paths)

    return search_paths


def _find_keyboard_config_file(keyboard_name: str) -> Path | None:
    """Find the configuration file for a keyboard.

    Args:
        keyboard_name: Name of the keyboard to find

    Returns:
        Path to the configuration file, or None if not found
    """
    search_paths = _initialize_search_paths()

    # Look for the configuration file in all search paths
    for path in search_paths:
        # Try .yaml extension first
        yaml_file = path / f"{keyboard_name}.yaml"
        if yaml_file.exists():
            return yaml_file

        # Then try .yml extension
        yml_file = path / f"{keyboard_name}.yml"
        if yml_file.exists():
            return yml_file

    logger.warning("Keyboard configuration not found: %s", keyboard_name)
    return None


def load_keyboard_config_raw(keyboard_name: str) -> dict:
    """Load a keyboard configuration by name as a raw dictionary.

    Args:
        keyboard_name: Name of the keyboard to load

    Returns:
        Dictionary containing the keyboard configuration

    Raises:
        ConfigError: If the keyboard configuration cannot be found or loaded
    """
    # Return cached configuration if available
    if keyboard_name in _keyboard_configs:
        return _keyboard_configs[keyboard_name]

    # Find the configuration file
    config_file = _find_keyboard_config_file(keyboard_name)
    if not config_file:
        raise ConfigError(f"Keyboard configuration not found: {keyboard_name}")

    # Load the configuration
    try:
        with config_file.open() as f:
            config = yaml.safe_load(f)

        # Validate the configuration
        if not isinstance(config, dict):
            raise ConfigError(f"Invalid keyboard configuration format: {keyboard_name}")

        if config.get("keyboard") != keyboard_name:
            logger.warning(
                "Keyboard name mismatch: %s != %s",
                config.get("keyboard"),
                keyboard_name,
            )
            # Fix the name to match what was requested
            config["keyboard"] = keyboard_name

        # Validate against schema
        validate_keyboard_config(config)

        # Cache the configuration
        _keyboard_configs[keyboard_name] = config
        logger.info("Loaded keyboard configuration: %s", keyboard_name)

        return config

    except yaml.YAMLError as e:
        raise ConfigError(f"Error parsing keyboard configuration: {e}") from e
    except OSError as e:
        raise ConfigError(f"Error reading keyboard configuration: {e}") from e


def load_keyboard_config_typed(keyboard_name: str) -> KeyboardConfig:
    """Load a keyboard configuration by name as a typed object.

    Args:
        keyboard_name: Name of the keyboard to load

    Returns:
        Typed KeyboardConfig object

    Raises:
        ConfigError: If the keyboard configuration cannot be found or loaded
    """
    # Return cached typed configuration if available
    if keyboard_name in _keyboard_configs_typed:
        return _keyboard_configs_typed[keyboard_name]

    # Load raw config and convert to typed object
    raw_config = load_keyboard_config_raw(keyboard_name)
    try:
        typed_config = KeyboardConfig(**raw_config)

        # Cache the typed configuration
        _keyboard_configs_typed[keyboard_name] = typed_config

        return typed_config
    except Exception as e:
        raise ConfigError(
            f"Error converting keyboard configuration to typed object: {e}"
        ) from e


def get_firmware_config_typed(keyboard_name: str, firmware_name: str) -> FirmwareConfig:
    """Get a firmware configuration for a keyboard as a typed object.

    Args:
        keyboard_name: Name of the keyboard
        firmware_name: Name of the firmware

    Returns:
        Typed FirmwareConfig object

    Raises:
        ConfigError: If the keyboard or firmware configuration cannot be found
    """
    keyboard_config = load_keyboard_config_typed(keyboard_name)

    # Check if the firmware exists
    if firmware_name not in keyboard_config.firmwares:
        raise ConfigError(
            f"Firmware '{firmware_name}' not found for keyboard '{keyboard_name}'"
        )

    # Return the firmware configuration
    return keyboard_config.firmwares[firmware_name]


def get_available_keyboards() -> list[str]:
    """Get a list of available keyboard configurations.

    Returns:
        List of keyboard names that have configuration files
    """
    available_keyboards = set()
    search_paths = _initialize_search_paths()

    # Search all paths for keyboard configuration files
    for path in search_paths:
        yaml_files = list(path.glob("*.yaml")) + list(path.glob("*.yml"))
        for file_path in yaml_files:
            # Use the filename without extension as the keyboard name
            keyboard_name = file_path.stem
            available_keyboards.add(keyboard_name)

    return sorted(available_keyboards)


def get_available_firmwares(keyboard_name: str) -> list[str]:
    """Get a list of available firmware configurations for a keyboard.

    Args:
        keyboard_name: Name of the keyboard

    Returns:
        List of firmware names available for the keyboard

    Raises:
        ConfigError: If the keyboard configuration cannot be found
    """
    keyboard_config = load_keyboard_config_typed(keyboard_name)

    # Return the firmware names
    return sorted(keyboard_config.firmwares.keys())


def get_default_firmware(keyboard_name: str) -> str:
    """Get the default firmware version for a keyboard.

    This returns the first available firmware version for the keyboard,
    which is typically the latest version.

    Args:
        keyboard_name: Name of the keyboard

    Returns:
        Default firmware version name

    Raises:
        ConfigError: If the keyboard configuration cannot be found
        ValueError: If no firmware versions are available
    """
    firmware_versions = get_available_firmwares(keyboard_name)
    if not firmware_versions:
        raise ValueError(
            f"No firmware versions available for keyboard: {keyboard_name}"
        )
    return firmware_versions[0]


def create_keyboard_profile(
    keyboard_name: str, firmware_version: str
) -> "KeyboardProfile":  # Forward reference
    """Create a KeyboardProfile for the given keyboard and firmware.

    Args:
        keyboard_name: Name of the keyboard
        firmware_version: Version of firmware to use

    Returns:
        KeyboardProfile configured for the keyboard and firmware

    Raises:
        ConfigError: If the keyboard or firmware configuration cannot be found
    """
    from glovebox.config.profile import KeyboardProfile

    keyboard_config = load_keyboard_config_typed(keyboard_name)
    return KeyboardProfile(keyboard_config, firmware_version)


def create_profile_from_keyboard_name(
    keyboard_name: str,
) -> Optional["KeyboardProfile"]:  # Forward reference
    """Create a KeyboardProfile from a keyboard name using the default firmware.

    Args:
        keyboard_name: Name of the keyboard

    Returns:
        KeyboardProfile for the keyboard with default firmware, or None if not found
    """
    from glovebox.core.logging import get_logger

    logger = get_logger(__name__)

    try:
        # Get available firmware versions
        firmware_versions = get_available_firmwares(keyboard_name)

        if not firmware_versions:
            logger.warning(f"No firmware versions found for keyboard: {keyboard_name}")
            return None

        # Use the first available firmware version
        firmware_version = firmware_versions[0]

        # Create the profile
        return create_keyboard_profile(keyboard_name, firmware_version)

    except Exception as e:
        logger.warning(f"Failed to create profile for {keyboard_name}: {e}")
        return None


def clear_cache() -> None:
    """Clear the keyboard configuration cache."""
    _keyboard_configs.clear()
    _keyboard_configs_typed.clear()
    logger.debug("Cleared keyboard configuration cache")


# Compatibility functions for backward compatibility with existing tests


def load_keyboard_config(keyboard_name: str) -> dict:
    """
    Load a keyboard configuration by name.

    This is a compatibility function for backward compatibility with existing tests.
    New code should use load_keyboard_config_raw or load_keyboard_config_typed.

    Args:
        keyboard_name: Name of the keyboard to load

    Returns:
        Dictionary containing the keyboard configuration
    """
    warnings.warn(
        "load_keyboard_config is deprecated. Use load_keyboard_config_raw instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return load_keyboard_config_raw(keyboard_name)


def get_firmware_config(keyboard_name: str, firmware_name: str) -> dict:
    """
    Get a firmware configuration for a keyboard.

    This is a compatibility function for backward compatibility with existing tests.
    New code should use get_firmware_config_typed.

    Args:
        keyboard_name: Name of the keyboard
        firmware_name: Name of the firmware

    Returns:
        Firmware configuration dictionary
    """
    warnings.warn(
        "get_firmware_config is deprecated. Use get_firmware_config_typed instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    firmware_config = get_firmware_config_typed(keyboard_name, firmware_name)
    # Convert back to dictionary for backward compatibility
    return {
        "description": firmware_config.description,
        "version": firmware_config.version,
        "branch": firmware_config.build_options.branch
        if firmware_config.build_options
        else "main",
    }


# Mock class for compatibility with tests that use KeyboardConfigService
class KeyboardConfigService:
    """
    Compatibility class for tests that use KeyboardConfigService.

    This class provides the same interface as the old KeyboardConfigService class
    but delegates to the new module-level functions.
    """

    def load_keyboard_config(self, keyboard_name: str) -> dict:
        """Load a keyboard configuration by name."""
        return load_keyboard_config(keyboard_name)

    def get_firmware_config(self, keyboard_name: str, firmware_name: str) -> dict:
        """Get a firmware configuration for a keyboard."""
        return get_firmware_config(keyboard_name, firmware_name)

    def get_available_keyboards(self) -> list[str]:
        """Get a list of available keyboard configurations."""
        return get_available_keyboards()

    def get_available_firmwares(self, keyboard_name: str) -> list[str]:
        """Get a list of available firmware configurations for a keyboard."""
        return get_available_firmwares(keyboard_name)
