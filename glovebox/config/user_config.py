"""
User configuration management for Glovebox.

This module handles user-specific configuration settings, including:
- Config file location and loading/saving
- Default configuration values
- Path expansion and validation
- Environment variable expansion
"""

import json
import os
from pathlib import Path
from typing import Any, cast

from glovebox.core.errors import ConfigError
from glovebox.core.logging import get_logger


logger = get_logger(__name__)

# Default configuration values
DEFAULT_CONFIG = {
    # Paths for user-defined keyboards and layouts
    "keyboard_paths": [],
    "layout_paths": [],
    # Default preferences
    "default_keyboard": "glove80",
    "default_firmware": "v25.05",
    "default_build_method": "docker",
    # Feature flags
    "enable_experimental": False,
    "verbose_logging": False,
}

# Type definitions for better type hinting
ConfigValue = str | int | bool | list[Any] | dict[str, Any] | None
ConfigDict = dict[str, ConfigValue]


class UserConfig:
    """
    Manages user-specific configuration for Glovebox.

    The configuration is stored in JSON format at ~/.config/glovebox/config.json
    and includes user preferences, paths to custom configurations, and feature flags.
    """

    def __init__(self, config_path: str | Path | None = None):
        """
        Initialize the user configuration handler.

        Args:
            config_path: Optional path to the configuration file.
                         If not provided, defaults to ~/.config/glovebox/config.json
        """
        self._config: ConfigDict = dict(DEFAULT_CONFIG)  # Start with default config

        if config_path:
            self._config_path = Path(config_path).expanduser().resolve()
        else:
            # Default config location
            self._config_path = Path.home() / ".config" / "glovebox" / "config.json"

        self._load_config()

    def _load_config(self) -> None:
        """
        Load configuration from the config file if it exists.
        If the file doesn't exist, the default configuration will be used.
        """
        if not self._config_path.exists():
            logger.info(
                "No config file found at %s. Using default configuration.",
                self._config_path,
            )
            return

        try:
            with self._config_path.open("r", encoding="utf-8") as f:
                user_config = json.load(f)

            # Merge user config with defaults (preserving any extra keys from user config)
            for key, value in user_config.items():
                self._config[key] = value

            logger.debug("Loaded user configuration from %s", self._config_path)
        except json.JSONDecodeError as e:
            msg = f"Error parsing user config file {self._config_path}: {e}"
            logger.error(msg)
            raise ConfigError(msg) from e
        except OSError as e:
            msg = f"Error reading user config file {self._config_path}: {e}"
            logger.error(msg)
            raise ConfigError(msg) from e

    def save(self) -> None:
        """
        Save the current configuration to the config file.
        Creates parent directories if they don't exist.
        """
        try:
            # Create parent directories if they don't exist
            self._config_path.parent.mkdir(parents=True, exist_ok=True)

            with self._config_path.open("w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, sort_keys=True)

            logger.debug("Saved user configuration to %s", self._config_path)
        except OSError as e:
            msg = f"Error writing user config file {self._config_path}: {e}"
            logger.error(msg)
            raise ConfigError(msg) from e

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: The configuration key to retrieve
            default: Value to return if the key doesn't exist

        Returns:
            The configuration value, or the default if not found
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.

        Args:
            key: The configuration key to set
            value: The value to assign to the key
        """
        self._config[key] = value

    def get_path_list(self, key: str) -> list[Path]:
        """
        Get a list of paths from the configuration, with environment variables and
        user directory expansion.

        Args:
            key: The configuration key for the path list

        Returns:
            A list of Path objects with expanded paths
        """
        path_list = self.get(key, [])
        if not isinstance(path_list, list):
            logger.warning(
                "Configuration key '%s' is not a list. Using empty list.", key
            )
            return []

        expanded_paths = []
        for path_str in path_list:
            if not isinstance(path_str, str):
                logger.warning(
                    "Path '%s' in '%s' is not a string. Skipping.", path_str, key
                )
                continue

            # Expand environment variables and user directory
            expanded_path = os.path.expandvars(str(Path(path_str).expanduser()))
            expanded_paths.append(Path(expanded_path))

        return expanded_paths

    def add_path(self, key: str, path: str | Path) -> None:
        """
        Add a path to a configuration path list if it's not already present.

        Args:
            key: The configuration key for the path list
            path: The path to add
        """
        path_str = str(path)
        path_list = self.get(key, [])

        if not isinstance(path_list, list):
            logger.warning(
                "Configuration key '%s' is not a list. Creating new list.", key
            )
            path_list = []

        if path_str not in path_list:
            path_list.append(path_str)
            self.set(key, path_list)

    def remove_path(self, key: str, path: str | Path) -> None:
        """
        Remove a path from a configuration path list if it exists.

        Args:
            key: The configuration key for the path list
            path: The path to remove
        """
        path_str = str(path)
        path_list = self.get(key, [])

        if not isinstance(path_list, list):
            logger.warning(
                "Configuration key '%s' is not a list. No action taken.", key
            )
            return

        if path_str in path_list:
            path_list.remove(path_str)
            self.set(key, path_list)

    def get_keyboard_paths(self) -> list[Path]:
        """
        Get a list of user-defined keyboard configuration paths with expansion.

        Returns:
            List of expanded Path objects for user keyboard configurations
        """
        return self.get_path_list("keyboard_paths")

    def get_layout_paths(self) -> list[Path]:
        """
        Get a list of user-defined layout paths with expansion.

        Returns:
            List of expanded Path objects for user layouts
        """
        return self.get_path_list("layout_paths")

    def get_default_keyboard(self) -> str:
        """
        Get the default keyboard name.

        Returns:
            The configured default keyboard name
        """
        return cast(str, self.get("default_keyboard", "glove80"))

    def get_default_firmware(self) -> str:
        """
        Get the default firmware version.

        Returns:
            The configured default firmware version
        """
        return cast(str, self.get("default_firmware", "v25.05"))

    def get_default_build_method(self) -> str:
        """
        Get the default build method.

        Returns:
            The configured default build method
        """
        return cast(str, self.get("default_build_method", "docker"))

    def is_experimental_enabled(self) -> bool:
        """
        Check if experimental features are enabled.

        Returns:
            True if experimental features are enabled, False otherwise
        """
        return bool(self.get("enable_experimental", False))

    def reset_to_defaults(self) -> None:
        """Reset the configuration to default values."""
        self._config = dict(DEFAULT_CONFIG)


# Default instance for easy importing
default_user_config = UserConfig()
