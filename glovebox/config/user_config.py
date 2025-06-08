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
    # Default profile
    "profile": "glove80/v25.05",
    # Logging
    "log_level": "INFO",
    # Flash behavior (deprecated - use firmware.flash.skip_existing)
    "flash_skip_existing": False,
    # Firmware configuration
    "firmware": {
        "flash": {
            "timeout": 60,
            "count": 2,
            "track_flashed": True,
            "skip_existing": False,
        }
    },
}


class UserConfig:
    """
    Manages user-specific configuration for Glovebox using Pydantic Settings.

    The configuration is loaded from multiple sources with the following precedence:
    1. Environment variables (highest precedence) - handled by Pydantic Settings
    2. Config files (.env, YAML) - handled by custom logic + Pydantic Settings
    3. Default values (lowest precedence) - defined in model
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

        # Track config sources
        self._config_sources: dict[str, str] = {}

        # Main config path for saving
        self._main_config_path: Path | None = None

        # Generate config paths to search
        self._config_paths = self._generate_config_paths(cli_config_path)

        # Load configuration from files and environment variables
        self._load_config()

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
        Load configuration from config files and environment variables using Pydantic Settings.
        """
        # Load configuration from YAML files and merge with environment variables
        config_data, found_path = self._adapter.search_config_files(self._config_paths)

        if found_path:
            logger.debug("Loaded user configuration from %s", found_path)
            self._main_config_path = found_path

            # Create UserConfigData with file data and automatic env var handling
            self._config = UserConfigData(**config_data)

            # Track sources for file-based values
            for key in config_data:
                self._config_sources[key] = f"file:{found_path.name}"
        else:
            logger.info(
                "No user configuration files found. Using defaults with environment variables."
            )
            # Create UserConfigData with just environment variables
            self._config = UserConfigData()
            # Set main config path to the default XDG location
            if self._config_paths:
                self._main_config_path = self._config_paths[-1]  # Last path is XDG yml

        # Track environment variable sources
        self._track_env_var_sources()

    def _track_env_var_sources(self) -> None:
        """Track which configuration values came from environment variables."""
        for env_name, _env_value in os.environ.items():
            if not env_name.startswith(ENV_PREFIX):
                continue

            # Convert env var name to config key format
            config_key = env_name[len(ENV_PREFIX) :].lower()

            # Handle nested firmware configuration
            if config_key.startswith("firmware__flash__"):
                nested_key = config_key.replace("firmware__flash__", "")
                self._config_sources[f"firmware.flash.{nested_key}"] = "environment"
            elif config_key in UserConfigData.model_fields:
                self._config_sources[config_key] = "environment"

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
        Get a list of user-defined keyboard configuration paths.

        Returns:
            List of Path objects for user keyboard configurations
        """
        if not self._config.keyboard_paths.strip():
            return []
        return [
            Path(path.strip()).expanduser()
            for path in self._config.keyboard_paths.split(",")
            if path.strip()
        ]

    def add_keyboard_path(self, path: str | Path) -> None:
        """
        Add a path to the keyboard paths if it's not already present.

        Args:
            path: The path to add
        """
        path_str = str(path)
        current_paths = self.get_keyboard_paths()
        path_obj = Path(path).expanduser()

        if path_obj not in current_paths:
            # Add to the comma-separated string
            if self._config.keyboard_paths.strip():
                self._config.keyboard_paths = (
                    f"{self._config.keyboard_paths},{path_str}"
                )
            else:
                self._config.keyboard_paths = path_str
            self._config_sources["keyboard_paths"] = "runtime"

    def remove_keyboard_path(self, path: str | Path) -> None:
        """
        Remove a path from the keyboard paths if it exists.

        Args:
            path: The path to remove
        """
        path_obj = Path(path).expanduser()
        current_paths = self.get_keyboard_paths()

        if path_obj in current_paths:
            # Remove from list and rebuild comma-separated string
            remaining_paths = [p for p in current_paths if p != path_obj]
            self._config.keyboard_paths = ",".join(str(p) for p in remaining_paths)
            self._config_sources["keyboard_paths"] = "runtime"

    def reset_to_defaults(self) -> None:
        """Reset the configuration to default values."""
        self._config = UserConfigData()
        self._config_sources = {}

    # Direct access to configuration is available via self._config
    # No need for property wrappers with Pydantic Settings

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
