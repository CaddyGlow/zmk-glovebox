"""
Keyboard configuration loading module.

This module provides functions for loading and accessing keyboard configurations
from YAML files, using Pydantic models for improved safety and validation.
"""

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import yaml
from pydantic import ValidationError


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.config.user_config import UserConfig

from glovebox.config.models import FirmwareConfig, KeyboardConfig
from glovebox.core.errors import ConfigError
from glovebox.core.logging import get_logger


logger = get_logger(__name__)


# Module-level cache of loaded configurations
_keyboard_configs: dict[str, KeyboardConfig] = {}


def initialize_search_paths(user_config: Optional["UserConfig"] = None) -> list[Path]:
    """Initialize the paths where keyboard configurations are searched for.

    Args:
        user_config: Optional user configuration instance. If provided, user-defined
                    keyboard paths from config will be included.

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

    # Get additional paths from user config if provided
    user_paths = []
    if user_config:
        user_paths = user_config.get_keyboard_paths()

    # Combine all paths
    all_paths = builtin_paths + [user_config_dir] + extra_paths + user_paths

    # Filter out non-existent paths
    search_paths = [p for p in all_paths if p.exists() and p.is_dir()]
    logger.debug("Keyboard configuration search paths: %s", search_paths)

    return search_paths


def _find_keyboard_config_file(
    keyboard_name: str, user_config: Optional["UserConfig"] = None
) -> Path | None:
    """Find the configuration file for a keyboard.

    Args:
        keyboard_name: Name of the keyboard to find
        user_config: Optional user configuration instance

    Returns:
        Path to the configuration file, or None if not found
    """
    search_paths = initialize_search_paths(user_config)

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Searching for keyboard '%s' configuration file", keyboard_name)
        logger.debug("Search paths: %s", [str(p) for p in search_paths])

    # Look for the configuration file in all search paths
    for i, path in enumerate(search_paths, 1):
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("  [%d/%d] Checking directory: %s", i, len(search_paths), path)

        # Try .yaml extension first
        yaml_file = path / f"{keyboard_name}.yaml"
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("    Checking: %s", yaml_file)
        if yaml_file.exists():
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("    ✓ Found keyboard config: %s", yaml_file)
            return yaml_file

        # Then try .yml extension
        yml_file = path / f"{keyboard_name}.yml"
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("    Checking: %s", yml_file)
        if yml_file.exists():
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("    ✓ Found keyboard config: %s", yml_file)
            return yml_file

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("    ❌ No config files found in this directory")

    logger.warning("Keyboard configuration not found: %s", keyboard_name)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "Searched %d directories, no config file found for '%s'",
            len(search_paths),
            keyboard_name,
        )
    return None


def load_keyboard_config(
    keyboard_name: str, user_config: Optional["UserConfig"] = None
) -> KeyboardConfig:
    """Load a keyboard configuration by name as a typed object.

    Args:
        keyboard_name: Name of the keyboard to load
        user_config: Optional user configuration instance

    Returns:
        Typed KeyboardConfig object

    Raises:
        ConfigError: If the keyboard configuration cannot be found or loaded
    """
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Loading keyboard configuration: %s", keyboard_name)

    # Return cached typed configuration if available
    if keyboard_name in _keyboard_configs:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("  ✓ Found cached configuration for '%s'", keyboard_name)
        return _keyboard_configs[keyboard_name]

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("  ↻ Configuration not cached, loading from file...")

    # Find the configuration file
    config_file = _find_keyboard_config_file(keyboard_name, user_config)
    if not config_file:
        raise ConfigError(f"Keyboard configuration not found: {keyboard_name}")

    # Load the configuration
    try:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("  📄 Reading config file: %s", config_file)

        with config_file.open() as f:
            raw_config = yaml.safe_load(f)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("  ✓ YAML parsing successful")
            logger.debug(
                "  📋 Raw config keys: %s",
                list(raw_config.keys())
                if isinstance(raw_config, dict)
                else "Not a dict",
            )

        # Basic validation
        if not isinstance(raw_config, dict):
            raise ConfigError(f"Invalid keyboard configuration format: {keyboard_name}")

        # Fix keyboard name mismatch if needed
        if raw_config.get("keyboard") != keyboard_name:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "  ⚠ Keyboard name mismatch: file has '%s', expected '%s' - fixing",
                    raw_config.get("keyboard"),
                    keyboard_name,
                )
            logger.warning(
                "Keyboard name mismatch: %s != %s",
                raw_config.get("keyboard"),
                keyboard_name,
            )
            raw_config["keyboard"] = keyboard_name

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("  🔍 Validating configuration with Pydantic...")

        # Convert to typed object using Pydantic validation
        typed_config = KeyboardConfig.model_validate(raw_config)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("  ✓ Pydantic validation successful")
            logger.debug("  💾 Caching configuration for future use")

        # Cache the typed configuration
        _keyboard_configs[keyboard_name] = typed_config
        logger.info("Loaded keyboard configuration: %s", keyboard_name)

        return typed_config
    except yaml.YAMLError as e:
        raise ConfigError(f"Error parsing keyboard configuration: {e}") from e
    except OSError as e:
        raise ConfigError(f"Error reading keyboard configuration: {e}") from e
    except ValidationError as e:
        raise ConfigError(f"Invalid keyboard configuration format: {e}") from e
    except Exception as e:
        raise ConfigError(f"Error loading keyboard configuration: {e}") from e


def get_firmware_config(
    keyboard_name: str, firmware_name: str, user_config: Optional["UserConfig"] = None
) -> FirmwareConfig:
    """Get a firmware configuration for a keyboard as a typed object.

    Args:
        keyboard_name: Name of the keyboard
        firmware_name: Name of the firmware
        user_config: Optional user configuration instance

    Returns:
        Typed FirmwareConfig object

    Raises:
        ConfigError: If the keyboard or firmware configuration cannot be found
    """
    keyboard_config = load_keyboard_config(keyboard_name, user_config)

    # Check if the firmware exists
    if firmware_name not in keyboard_config.firmwares:
        raise ConfigError(
            f"Firmware '{firmware_name}' not found for keyboard '{keyboard_name}'"
        )

    # Return the firmware configuration
    return keyboard_config.firmwares[firmware_name]


def get_available_keyboards(user_config: Optional["UserConfig"] = None) -> list[str]:
    """Get a list of available keyboard configurations.

    Args:
        user_config: Optional user configuration instance

    Returns:
        List of keyboard names that have configuration files
    """
    available_keyboards = set()
    search_paths = initialize_search_paths(user_config)

    # Search all paths for keyboard configuration files
    for path in search_paths:
        yaml_files = list(path.glob("*.yaml")) + list(path.glob("*.yml"))
        for file_path in yaml_files:
            # Use the filename without extension as the keyboard name
            keyboard_name = file_path.stem
            available_keyboards.add(keyboard_name)

    return sorted(available_keyboards)


def get_available_firmwares(
    keyboard_name: str, user_config: Optional["UserConfig"] = None
) -> list[str]:
    """Get a list of available firmware configurations for a keyboard.

    Args:
        keyboard_name: Name of the keyboard
        user_config: Optional user configuration instance

    Returns:
        List of firmware names available for the keyboard

    Raises:
        ConfigError: If the keyboard configuration cannot be found
    """
    keyboard_config = load_keyboard_config(keyboard_name, user_config)

    # Return the firmware names
    return sorted(keyboard_config.firmwares.keys())


def get_default_firmware(
    keyboard_name: str, user_config: Optional["UserConfig"] = None
) -> str:
    """Get the default firmware version for a keyboard.

    This returns the first available firmware version for the keyboard,
    which is typically the latest version.

    Args:
        keyboard_name: Name of the keyboard
        user_config: Optional user configuration instance

    Returns:
        Default firmware version name

    Raises:
        ConfigError: If the keyboard configuration cannot be found
        ValueError: If no firmware versions are available
    """
    firmware_versions = get_available_firmwares(keyboard_name, user_config)
    if not firmware_versions:
        raise ValueError(
            f"No firmware versions available for keyboard: {keyboard_name}"
        )
    return firmware_versions[0]


def create_keyboard_profile(
    keyboard_name: str,
    firmware_version: str | None = None,
    user_config: Optional["UserConfig"] = None,
) -> "KeyboardProfile":  # Forward reference
    """Create a KeyboardProfile for the given keyboard and optional firmware.

    Args:
        keyboard_name: Name of the keyboard
        firmware_version: Version of firmware to use (optional)
        user_config: Optional user configuration instance

    Returns:
        KeyboardProfile configured for the keyboard and firmware

    Raises:
        ConfigError: If the keyboard configuration cannot be found, or if firmware
                    version is specified but not found
    """
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "Creating keyboard profile: keyboard='%s', firmware='%s'",
            keyboard_name,
            firmware_version,
        )

    from glovebox.config.profile import KeyboardProfile

    keyboard_config = load_keyboard_config(keyboard_name, user_config)

    if logger.isEnabledFor(logging.DEBUG):
        if firmware_version:
            logger.debug(
                "  🔧 Creating profile with specific firmware: %s", firmware_version
            )
        else:
            logger.debug("  📦 Creating keyboard-only profile (no firmware specified)")

    profile = KeyboardProfile(keyboard_config, firmware_version)

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("  ✓ Profile created successfully")
        logger.debug("    - Keyboard: %s", profile.keyboard_name)
        logger.debug(
            "    - Firmware: %s", profile.firmware_version or "None (keyboard-only)"
        )
        logger.debug(
            "    - Has firmware config: %s", profile.firmware_config is not None
        )

    return profile


def create_profile_from_keyboard_name(
    keyboard_name: str,
    user_config: Optional["UserConfig"] = None,
) -> Optional["KeyboardProfile"]:  # Forward reference
    """Create a KeyboardProfile from a keyboard name using the default firmware.

    Args:
        keyboard_name: Name of the keyboard
        user_config: Optional user configuration instance

    Returns:
        KeyboardProfile for the keyboard with default firmware, or None if not found
    """
    from glovebox.core.logging import get_logger

    logger = get_logger(__name__)

    try:
        # Get available firmware versions
        firmware_versions = get_available_firmwares(keyboard_name, user_config)

        if not firmware_versions:
            logger.warning(f"No firmware versions found for keyboard: {keyboard_name}")
            return None

        # Use the first available firmware version
        firmware_version = firmware_versions[0]

        # Create the profile
        return create_keyboard_profile(keyboard_name, firmware_version, user_config)

    except Exception as e:
        logger.warning(f"Failed to create profile for {keyboard_name}: {e}")
        return None


def clear_cache() -> None:
    """Clear the keyboard configuration cache."""
    _keyboard_configs.clear()
    logger.debug("Cleared keyboard configuration cache")
