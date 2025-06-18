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
from typing import Any

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
        current_dir_yml = Path.cwd() / ".glovebox.yml"
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
        # Debug tracing for configuration loading process
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Starting configuration loading process")
            logger.debug(
                "Config search paths: %s", [str(p) for p in self._config_paths]
            )

            # Log environment variables that will affect configuration
            env_vars = {k: v for k, v in os.environ.items() if k.startswith(ENV_PREFIX)}
            if env_vars:
                logger.debug("Found %d Glovebox environment variables", len(env_vars))
                for k, v in env_vars.items():
                    logger.debug("  %s=%s", k, v)
            else:
                logger.debug("No Glovebox environment variables found")

        # Load configuration from YAML files and merge with environment variables
        config_data, found_path = self._adapter.search_config_files(self._config_paths)

        if found_path:
            logger.debug("Loaded user configuration from %s", found_path)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Config file contents: %s", config_data)

            self._main_config_path = found_path

            # Create UserConfigData with file data and automatic env var handling
            self._config = UserConfigData(**config_data)

            # Track sources for file-based values (including nested keys)
            self._track_file_sources(config_data, found_path.name)

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Configuration successfully loaded and validated")
        else:
            logger.info(
                "No user configuration files found. Using defaults with environment variables."
            )
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "Creating UserConfigData with defaults and environment variables only"
                )

            # Create UserConfigData with just environment variables
            self._config = UserConfigData()
            # Set main config path to the default XDG location
            if self._config_paths:
                self._main_config_path = self._config_paths[-1]  # Last path is XDG yml

        # Track environment variable sources
        self._track_env_var_sources()

        # Final debug output showing the resolved configuration
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Final configuration values:")
            logger.debug(
                "  profile: %s (source: %s)",
                self._config.profile,
                self.get_source("profile"),
            )
            logger.debug(
                "  log_level: %s (source: %s)",
                self._config.log_level,
                self.get_source("log_level"),
            )
            logger.debug(
                "  keyboard_paths: %s (source: %s)",
                self._config.keyboard_paths,
                self.get_source("keyboard_paths"),
            )
            logger.debug(
                "  firmware.flash.timeout: %s (source: %s)",
                self._config.firmware.flash.timeout,
                self.get_source("firmware.flash.timeout"),
            )
            logger.debug(
                "  firmware.flash.count: %s (source: %s)",
                self._config.firmware.flash.count,
                self.get_source("firmware.flash.count"),
            )
            logger.debug(
                "  firmware.flash.track_flashed: %s (source: %s)",
                self._config.firmware.flash.track_flashed,
                self.get_source("firmware.flash.track_flashed"),
            )
            logger.debug(
                "  firmware.flash.skip_existing: %s (source: %s)",
                self._config.firmware.flash.skip_existing,
                self.get_source("firmware.flash.skip_existing"),
            )
            logger.debug(
                "  firmware.flash.wait: %s (source: %s)",
                self._config.firmware.flash.wait,
                self.get_source("firmware.flash.wait"),
            )
            logger.debug(
                "  firmware.flash.poll_interval: %s (source: %s)",
                self._config.firmware.flash.poll_interval,
                self.get_source("firmware.flash.poll_interval"),
            )
            logger.debug(
                "  firmware.flash.show_progress: %s (source: %s)",
                self._config.firmware.flash.show_progress,
                self.get_source("firmware.flash.show_progress"),
            )
            logger.debug("Configuration loading completed successfully")

    def _track_file_sources(
        self, data: dict[str, Any], filename: str, prefix: str = ""
    ) -> None:
        """
        Recursively track sources for file-based configuration values.

        Args:
            data: Configuration data dictionary
            filename: Name of the config file
            prefix: Current key prefix for nested tracking
        """
        for key, value in data.items():
            current_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                # Recursively track nested dictionaries
                self._track_file_sources(value, filename, current_key)
            else:
                # Track this key as coming from file
                self._config_sources[current_key] = f"file:{filename}"

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
        return [path.expanduser() for path in self._config.keyboard_paths]

    def add_keyboard_path(self, path: str | Path) -> None:
        """
        Add a path to the keyboard paths if it's not already present.

        Args:
            path: The path to add
        """
        path_obj = Path(path).expanduser()
        current_paths = self.get_keyboard_paths()

        if path_obj not in current_paths:
            # Add to the list
            self._config.keyboard_paths.append(Path(path))
            self._config_sources["keyboard_paths"] = "runtime"

    def remove_keyboard_path(self, path: str | Path) -> None:
        """
        Remove a path from the keyboard paths if it exists.

        Args:
            path: The path to remove
        """
        path_obj = Path(path)
        # Remove from list if present
        try:
            self._config.keyboard_paths.remove(path_obj)
            self._config_sources["keyboard_paths"] = "runtime"
        except ValueError:
            # Path not in list, do nothing
            pass

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
        # Handle both top-level and nested keys
        if "." in key:
            # Handle nested keys like "firmware.flash.timeout"
            self._set_nested_key(key, value)
        elif key in UserConfigData.model_fields:
            # Handle top-level keys
            try:
                setattr(self._config, key, value)
                self._config_sources[key] = "runtime"
            except Exception as e:
                logger.warning("Invalid value for %s: %s", key, e)
                raise ValueError(f"Invalid value for {key}: {e}") from e
        else:
            logger.warning("Ignoring unknown configuration key: %s", key)
            raise ValueError(f"Unknown configuration key: {key}")

    def _set_nested_key(self, key: str, value: Any) -> None:
        """Set a nested configuration key using dot notation."""
        keys = key.split(".")
        current = self._config

        # Navigate to the parent object
        for k in keys[:-1]:
            if hasattr(current, k):
                current = getattr(current, k)
            else:
                logger.warning("Invalid configuration path: %s", key)
                raise ValueError(f"Invalid configuration path: {key}")

        # Set the final value
        final_key = keys[-1]
        if hasattr(current, final_key):
            try:
                setattr(current, final_key, value)
                self._config_sources[key] = "runtime"
            except Exception as e:
                logger.warning("Invalid value for %s: %s", key, e)
                raise ValueError(f"Invalid value for {key}: {e}") from e
        else:
            logger.warning("Invalid configuration key: %s", key)
            raise ValueError(f"Invalid configuration key: {key}")

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
