"""
Keyboard configuration loading module.

This module provides functions for loading and accessing keyboard configurations
from YAML files, using Pydantic models for improved safety and validation.
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.config.user_config import UserConfig

from glovebox.config.models import FirmwareConfig, KeyboardConfig
from glovebox.core.errors import ConfigError
from glovebox.core.structlog_logger import get_struct_logger


logger = get_struct_logger(__name__)


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
    #  TODO: FIX TO USED XDG
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

    logger.debug(
        "Searching for keyboard '%s' in %d paths: %s",
        keyboard_name,
        len(search_paths),
        " | ".join(str(p) for p in search_paths),
    )

    # Look for the configuration file in all search paths
    for path in search_paths:
        # Try .yaml extension first
        yaml_file = path / f"{keyboard_name}.yaml"
        if yaml_file.exists():
            logger.debug("Found keyboard config: %s", yaml_file)
            return yaml_file

        # Then try .yml extension
        yml_file = path / f"{keyboard_name}.yml"
        if yml_file.exists():
            logger.debug("Found keyboard config: %s", yml_file)
            return yml_file

    logger.warning("Keyboard configuration not found: %s", keyboard_name)
    logger.debug(
        "Searched %d directories, no config found for '%s'",
        len(search_paths),
        keyboard_name,
    )
    return None


def load_keyboard_config(
    keyboard_name: str, user_config: Optional["UserConfig"] = None
) -> KeyboardConfig:
    """Load a keyboard configuration by name with include support.

    This is the unified keyboard configuration loading function that always
    uses include-aware loading for consistency.

    Args:
        keyboard_name: Name of the keyboard to load
        user_config: Optional user configuration instance

    Returns:
        Typed KeyboardConfig object with includes resolved

    Raises:
        ConfigError: If the keyboard configuration cannot be found or loaded
    """
    # Delegate to the include-aware implementation
    return load_keyboard_config_with_includes(keyboard_name, user_config)


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

    This is the unified keyboard profile creation function that always
    uses include-aware configuration loading for consistency.

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
    # Delegate to the include-aware implementation
    return create_keyboard_profile_with_includes(
        keyboard_name, firmware_version, user_config
    )


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


def load_keyboard_config_with_includes(
    keyboard_name: str, user_config: Optional["UserConfig"] = None
) -> KeyboardConfig:
    """Load a keyboard configuration with include directive support.

    NOTE: This function is now the implementation behind the unified
    load_keyboard_config() function. Direct use is maintained for
    backwards compatibility but load_keyboard_config() is preferred.

    Args:
        keyboard_name: Name of the keyboard to load
        user_config: Optional user configuration instance

    Returns:
        Typed KeyboardConfig object with includes resolved

    Raises:
        ConfigError: If the keyboard configuration cannot be found or loaded
    """
    from glovebox.config.include_loader import create_include_loader

    # Initialize search paths
    search_paths = initialize_search_paths(user_config)

    # Create include loader
    loader = create_include_loader(search_paths)

    # Load configuration with include support
    return loader.load_keyboard_config(keyboard_name)


def create_keyboard_profile_with_includes(
    keyboard_name: str,
    firmware_version: str | None = None,
    user_config: Optional["UserConfig"] = None,
) -> "KeyboardProfile":
    """Create a KeyboardProfile with include directive support.

    NOTE: This function is now the implementation behind the unified
    create_keyboard_profile() function. Direct use is maintained for
    backwards compatibility but create_keyboard_profile() is preferred.

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

    from glovebox.config.profile import KeyboardProfile

    # Load keyboard configuration with include support
    keyboard_config = load_keyboard_config_with_includes(keyboard_name, user_config)

    # trying to get the latest firmware, the first in the list
    if not firmware_version and len(keyboard_config.firmwares):
        firmware_version = list(keyboard_config.firmwares.keys())[0]

    return KeyboardProfile(
        keyboard_config=keyboard_config,
        firmware_version=firmware_version,
    )
