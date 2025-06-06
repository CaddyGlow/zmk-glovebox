"""
User configuration management for Glovebox.

This module handles user-specific configuration settings with multiple sources:
1. Environment variables (highest precedence)
2. Command-line provided config file
3. Config file in current directory
4. User's XDG config directory
5. Default values (lowest precedence)
"""

import json
import logging
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
    # Default preferences
    "default_keyboard": "glove80",
    "default_firmware": "v25.05",
    # Logging
    "log_level": "INFO",
}

# Environment variable prefixes
ENV_PREFIX = "GLOVEBOX_"


class UserConfig:
    """
    Manages user-specific configuration for Glovebox.

    The configuration is loaded from multiple sources with the following precedence:
    1. Environment variables (highest precedence)
    2. Command-line provided config file
    3. Config file in current directory
    4. User's XDG config directory (~/.config/glovebox/config.json)
    5. Default values (lowest precedence)
    """

    def __init__(
        self, cli_config_path: str | Path | None = None, search_current_dir: bool = True
    ):
        """
        Initialize the user configuration handler.

        Args:
            cli_config_path: Optional config file path provided via CLI
            search_current_dir: Whether to search for config file in current directory
        """
        # Start with default config
        self._config: dict[str, Any] = dict(DEFAULT_CONFIG)
        self._config_sources: dict[
            str, str
        ] = {}  # Track where each config value came from

        # Configuration file paths to try in order of precedence
        self._config_paths: list[tuple[str, Path]] = []

        # 1. CLI provided config path (if specified)
        if cli_config_path:
            cli_path = Path(cli_config_path).expanduser().resolve()
            self._config_paths.append(("cli", cli_path))

        # 2. Current directory config file
        if search_current_dir:
            current_dir_config = Path.cwd() / "glovebox.json"
            self._config_paths.append(("current_dir", current_dir_config))

        # 3. XDG config directory
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config_home:
            xdg_path = Path(xdg_config_home) / "glovebox" / "config.json"
        else:
            # Default XDG location
            xdg_path = Path.home() / ".config" / "glovebox" / "config.json"
        self._config_paths.append(("xdg", xdg_path))

        # Main config path for saving (use the highest priority existing path, or XDG if none exist)
        self._main_config_path: Path | None = None

        # Load configuration from all sources
        self._load_config()

        # Apply environment variable overrides (highest precedence)
        self._apply_env_vars()

    def _load_config(self) -> None:
        """
        Load configuration from all config files in order of precedence.
        """
        found_config = False

        # Try each config path in order
        for source, config_path in self._config_paths:
            if not config_path.exists():
                logger.debug("Config file not found: %s", config_path)
                continue

            try:
                with config_path.open("r", encoding="utf-8") as f:
                    user_config = json.load(f)

                # Apply config values from this file
                for key in DEFAULT_CONFIG:
                    if key in user_config:
                        self._config[key] = user_config[key]
                        self._config_sources[key] = source

                logger.debug("Loaded user configuration from %s", config_path)
                found_config = True

                # Use the first found config as the main config path for saving
                if self._main_config_path is None:
                    self._main_config_path = config_path  # Path instance

            except json.JSONDecodeError as e:
                logger.warning("Error parsing config file %s: %s", config_path, e)
            except OSError as e:
                logger.warning("Error reading config file %s: %s", config_path, e)

        if not found_config:
            logger.info(
                "No user configuration files found. Using default configuration."
            )
            # Set main config path to XDG if no configs were found
            if self._config_paths:
                self._main_config_path = self._config_paths[-1][1]  # XDG path

    def _apply_env_vars(self) -> None:
        """
        Apply configuration from environment variables.
        Environment variables have the highest precedence.
        Format: GLOVEBOX_UPPERCASE_KEY_NAME
        """
        for env_name, env_value in os.environ.items():
            if not env_name.startswith(ENV_PREFIX):
                continue

            # Extract config key from env var name (GLOVEBOX_DEFAULT_KEYBOARD -> default_keyboard)
            config_key = env_name[len(ENV_PREFIX) :].lower()

            # Convert to standard snake_case format
            # Replace underscores with spaces first, then replace spaces with underscores
            config_key = "_".join(config_key.split("_"))

            # Only apply if it's a known config key
            if config_key in DEFAULT_CONFIG:
                # Convert environment variable value to appropriate type
                default_value = DEFAULT_CONFIG[config_key]

                if isinstance(default_value, bool):  # type: ignore
                    # Convert string to boolean for bool fields
                    # Using a temporary variable to avoid type confusion
                    bool_val = env_value.lower() in (  # type: ignore
                        "true",
                        "yes",
                        "1",
                        "y",
                    )
                    self._config[config_key] = bool_val
                elif isinstance(default_value, int):
                    try:
                        # Convert string to int for integer fields
                        int_val = int(env_value)
                        self._config[config_key] = int_val
                    except ValueError:
                        logger.warning(
                            "Invalid integer value for %s: %s", env_name, env_value
                        )
                elif isinstance(default_value, list):
                    # Convert comma-separated string to list for list fields
                    list_val = [item.strip() for item in env_value.split(",")]
                    self._config[config_key] = list_val
                else:
                    # String values for string fields
                    # Just assign directly to avoid type confusion
                    self._config[config_key] = env_value

                self._config_sources[config_key] = "environment"
                logger.debug(
                    "Applied environment variable %s = %s", env_name, env_value
                )

    def save(self) -> None:
        """
        Save the current configuration to the main config file.
        Creates parent directories if they don't exist.
        """
        if not self._main_config_path:
            logger.warning("No config path set, can't save configuration.")
            return

        try:
            # Create parent directories if they don't exist
            self._main_config_path.parent.mkdir(parents=True, exist_ok=True)

            with self._main_config_path.open("w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, sort_keys=True)

            logger.debug("Saved user configuration to %s", self._main_config_path)
        except OSError as e:
            msg = f"Error writing user config file {self._main_config_path}: {e}"
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
        # Only allow setting known config keys
        if key in DEFAULT_CONFIG:
            self._config[key] = value
            self._config_sources[key] = "runtime"
        else:
            logger.warning("Ignoring unknown configuration key: %s", key)

    def get_source(self, key: str) -> str:
        """
        Get the source of a configuration value.

        Args:
            key: The configuration key

        Returns:
            The source of the configuration value (environment, cli, current_dir, xdg, default)
        """
        # Always returns a string because default is provided
        source: str = self._config_sources.get(key, "default")
        return source

    def get_keyboard_paths(self) -> list[Path]:
        """
        Get a list of user-defined keyboard configuration paths with expansion.

        Returns:
            List of expanded Path objects for user keyboard configurations
        """
        path_list = self.get("keyboard_paths", [])
        if not isinstance(path_list, list):
            return []

        expanded_paths = []
        for path_str in path_list:
            if not isinstance(path_str, str):
                continue

            # Expand environment variables and user directory
            expanded_path = os.path.expandvars(str(Path(path_str).expanduser()))
            expanded_paths.append(Path(expanded_path))

        return expanded_paths

    def add_keyboard_path(self, path: str | Path) -> None:
        """
        Add a path to the keyboard paths if it's not already present.

        Args:
            path: The path to add
        """
        path_str = str(path)
        path_list = self.get("keyboard_paths", [])

        if not isinstance(path_list, list):
            path_list = []

        if path_str not in path_list:
            path_list.append(path_str)
            self.set("keyboard_paths", path_list)

    def remove_keyboard_path(self, path: str | Path) -> None:
        """
        Remove a path from the keyboard paths if it exists.

        Args:
            path: The path to remove
        """
        path_str = str(path)
        path_list = self.get("keyboard_paths", [])

        if not isinstance(path_list, list):
            return

        if path_str in path_list:
            path_list.remove(path_str)
            self.set("keyboard_paths", path_list)

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

    def get_log_level(self) -> int:
        """
        Get the log level.

        Returns:
            The configured log level as an int (logging.INFO, etc.)
        """
        level_name = self.get("log_level", "INFO")
        if isinstance(level_name, str):
            try:
                return int(getattr(logging, level_name.upper()))
            except AttributeError:
                return logging.INFO
        return logging.INFO

    def reset_to_defaults(self) -> None:
        """Reset the configuration to default values."""
        self._config = dict(DEFAULT_CONFIG)
        self._config_sources = {}


# Default instance for easy importing
default_user_config = UserConfig()
