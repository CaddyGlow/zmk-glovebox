"""
User configuration management for Glovebox.

This module handles user-specific configuration settings with multiple sources:
1. Environment variables (highest precedence)
2. Command-line provided config file
3. Config file in current directory
4. User's XDG config directory
5. Default values (lowest precedence)
"""

import logging
import os
from pathlib import Path
from typing import Any, cast

from glovebox.adapters.config_file_adapter import (
    ConfigFileAdapter,
    create_config_file_adapter,
)
from glovebox.config.models import UserConfigData
from glovebox.core.errors import ConfigError
from glovebox.core.logging import get_logger


logger = get_logger(__name__)

# Environment variable prefixes
ENV_PREFIX = "GLOVEBOX_"

# Default configuration values for backward compatibility with CLI commands
DEFAULT_CONFIG = {
    # Paths for user-defined keyboards and layouts
    "keyboard_paths": [],
    # Default preferences
    "default_keyboard": "glove80",
    "default_firmware": "v25.05",
    # Logging
    "log_level": "INFO",
}


class UserConfig:
    """
    Manages user-specific configuration for Glovebox.

    The configuration is loaded from multiple sources with the following precedence:
    1. Environment variables (highest precedence)
    2. Command-line provided config file
    3. Config file in current directory
    4. User's XDG config directory (~/.config/glovebox/config.yaml)
    5. Default values (lowest precedence)
    """

    def __init__(
        self,
        cli_config_path: str | Path | None = None,
        config_adapter: ConfigFileAdapter[UserConfigData] | None = None,
    ):
        """
        Initialize the user configuration handler.

        Args:
            cli_config_path: Optional config file path provided via CLI
            config_adapter: Optional adapter for file operations
        """
        # Initialize adapter
        self._adapter = config_adapter or create_config_file_adapter()

        # Initialize config data with defaults
        self._config = UserConfigData()

        # Track config sources
        self._config_sources: dict[str, str] = {}

        # Main config path for saving
        self._main_config_path: Path | None = None

        # Generate config paths to search
        self._config_paths = self._generate_config_paths(cli_config_path)

        # Load configuration from files
        self._load_config()

        # Apply environment variables
        self._apply_env_vars()

    def _generate_config_paths(self, cli_config_path: str | Path | None) -> list[Path]:
        """Generate a list of config paths to search in order of precedence."""
        config_paths = []

        # 1. CLI provided config path (if specified)
        if cli_config_path:
            cli_path = Path(cli_config_path).expanduser().resolve()
            config_paths.append(cli_path)

        # 2. Current directory config files
        current_dir_yaml = Path.cwd() / "glovebox.yaml"
        current_dir_yml = Path.cwd() / "glovebox.yml"
        config_paths.extend([current_dir_yaml, current_dir_yml])

        # 3. XDG config directory
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config_home:
            xdg_yaml = Path(xdg_config_home) / "glovebox" / "config.yaml"
            xdg_yml = Path(xdg_config_home) / "glovebox" / "config.yml"
            config_paths.extend([xdg_yaml, xdg_yml])
        else:
            # Default XDG location
            xdg_yaml = Path.home() / ".config" / "glovebox" / "config.yaml"
            xdg_yml = Path.home() / ".config" / "glovebox" / "config.yml"
            config_paths.extend([xdg_yaml, xdg_yml])

        return config_paths

    def _load_config(self) -> None:
        """
        Load configuration from config files in order of precedence.
        """
        # Use adapter to search for a valid config file
        config_data, found_path = self._adapter.search_config_files(self._config_paths)

        if found_path:
            # Update config and track sources
            self._update_config_from_dict(config_data, f"file:{found_path.name}")

            logger.debug("Loaded user configuration from %s", found_path)
            self._main_config_path = found_path
        else:
            logger.info(
                "No user configuration files found. Using default configuration."
            )
            # Set main config path to the default XDG location if no configs were found
            if self._config_paths:
                self._main_config_path = self._config_paths[-1]  # Last path is XDG yml

    def _update_config_from_dict(self, data: dict[str, Any], source: str) -> None:
        """Update configuration from a dictionary and track sources."""
        # Only update fields that exist in our model
        for field_name in UserConfigData.model_fields:
            if field_name in data:
                try:
                    # Update the field with validation
                    setattr(self._config, field_name, data[field_name])
                    self._config_sources[field_name] = source
                except Exception as e:
                    logger.warning("Invalid value for %s: %s", field_name, e)

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
            config_key = "_".join(config_key.split("_"))

            # Check if this is a valid config field
            if config_key in UserConfigData.model_fields:
                try:
                    # Update the field with validation
                    setattr(self._config, config_key, env_value)
                    self._config_sources[config_key] = "environment"
                    logger.debug(
                        "Applied environment variable %s = %s", env_name, env_value
                    )
                except Exception as e:
                    logger.warning("Invalid value for %s: %s", config_key, e)

    def save(self) -> None:
        """
        Save the current configuration to the main config file.
        Creates parent directories if they don't exist.
        """
        if not self._main_config_path:
            logger.warning("No config path set, can't save configuration.")
            return

        try:
            # Use adapter to save config
            self._adapter.save_model(self._main_config_path, self._config)
            logger.debug("Saved user configuration to %s", self._main_config_path)
        except ConfigError as e:
            # Already logged in adapter
            raise

    def get_source(self, key: str) -> str:
        """
        Get the source of a configuration value.

        Args:
            key: The configuration key

        Returns:
            The source of the configuration value (environment, file:name, runtime, default)
        """
        return self._config_sources.get(key, "default")

    def get_keyboard_paths(self) -> list[Path]:
        """
        Get a list of user-defined keyboard configuration paths with expansion.

        Returns:
            List of expanded Path objects for user keyboard configurations
        """
        return self._config.get_expanded_keyboard_paths()

    def add_keyboard_path(self, path: str | Path) -> None:
        """
        Add a path to the keyboard paths if it's not already present.

        Args:
            path: The path to add
        """
        path_str = str(path)
        if path_str not in self._config.keyboard_paths:
            # Create a new list to ensure it's properly updated
            paths = list(self._config.keyboard_paths)
            paths.append(path_str)
            self._config.keyboard_paths = paths
            self._config_sources["keyboard_paths"] = "runtime"

    def remove_keyboard_path(self, path: str | Path) -> None:
        """
        Remove a path from the keyboard paths if it exists.

        Args:
            path: The path to remove
        """
        path_str = str(path)
        if path_str in self._config.keyboard_paths:
            # Create a new list to ensure it's properly updated
            paths = list(self._config.keyboard_paths)
            paths.remove(path_str)
            self._config.keyboard_paths = paths
            self._config_sources["keyboard_paths"] = "runtime"

    def reset_to_defaults(self) -> None:
        """Reset the configuration to default values."""
        self._config = UserConfigData()
        self._config_sources = {}

    # Direct property access to configuration values
    @property
    def default_keyboard(self) -> str:
        """Get the default keyboard name."""
        return self._config.default_keyboard

    @default_keyboard.setter
    def default_keyboard(self, value: str) -> None:
        """Set the default keyboard name."""
        self._config.default_keyboard = value
        self._config_sources["default_keyboard"] = "runtime"

    @property
    def default_firmware(self) -> str:
        """Get the default firmware version."""
        return self._config.default_firmware

    @default_firmware.setter
    def default_firmware(self, value: str) -> None:
        """Set the default firmware version."""
        self._config.default_firmware = value
        self._config_sources["default_firmware"] = "runtime"

    @property
    def log_level(self) -> str:
        """Get the log level."""
        return self._config.log_level

    @log_level.setter
    def log_level(self, value: str) -> None:
        """Set the log level."""
        self._config.log_level = value
        self._config_sources["log_level"] = "runtime"

    @property
    def keyboard_paths(self) -> list[str]:
        """Get the keyboard paths."""
        return self._config.keyboard_paths

    @keyboard_paths.setter
    def keyboard_paths(self, value: list[str]) -> None:
        """Set the keyboard paths."""
        self._config.keyboard_paths = value
        self._config_sources["keyboard_paths"] = "runtime"

    # Helper methods to maintain compatibility with existing code
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: The configuration key to retrieve
            default: Value to return if the key doesn't exist

        Returns:
            The configuration value, or the default if not found
        """
        if hasattr(self._config, key):
            return getattr(self._config, key)
        return default

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.

        Args:
            key: The configuration key to set
            value: The value to assign to the key
        """
        # Only allow setting known config keys
        if key in UserConfigData.model_fields:
            try:
                setattr(self._config, key, value)
                self._config_sources[key] = "runtime"
            except Exception as e:
                logger.warning("Invalid value for %s: %s", key, e)
                raise ValueError(f"Invalid value for {key}: {e}") from e
        else:
            logger.warning("Ignoring unknown configuration key: %s", key)
            raise ValueError(f"Unknown configuration key: {key}")

    def get_log_level_int(self) -> int:
        """
        Get the log level as an integer value for use with logging module.

        Returns:
            The configured log level as an int (logging.INFO, etc.)
        """
        level_name = (
            self._config.log_level.upper()
        )  # Ensure uppercase for logging module
        try:
            # Define mapping for type safety
            level_map = {
                "DEBUG": logging.DEBUG,
                "INFO": logging.INFO,
                "WARNING": logging.WARNING,
                "ERROR": logging.ERROR,
                "CRITICAL": logging.CRITICAL,
            }
            return level_map.get(level_name, logging.INFO)
        except (AttributeError, ValueError):
            return logging.INFO


# Factory function to create UserConfig instance
def create_user_config(
    cli_config_path: str | Path | None = None,
    config_adapter: ConfigFileAdapter[UserConfigData] | None = None,
) -> UserConfig:
    """
    Create a UserConfig instance with optional dependency injection.

    Args:
        cli_config_path: Optional config file path provided via CLI
        config_adapter: Optional ConfigFileAdapter instance

    Returns:
        Configured UserConfig instance
    """
    return UserConfig(
        cli_config_path=cli_config_path,
        config_adapter=config_adapter,
    )
