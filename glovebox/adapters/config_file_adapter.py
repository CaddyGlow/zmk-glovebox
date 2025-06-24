"""Adapter for configuration file operations."""

import logging
from pathlib import Path
from typing import Any, Generic, TypeVar

import yaml
from pydantic import BaseModel

from glovebox.config.models import UserConfigData
from glovebox.core.errors import ConfigError
from glovebox.core.logging import get_logger
from glovebox.protocols.config_file_adapter_protocol import ConfigFileAdapterProtocol


logger = get_logger(__name__)

# Generic type for model
T = TypeVar("T", bound=BaseModel)


class ConfigFileAdapter(Generic[T]):
    """Adapter for loading and saving configuration files.

    This adapter handles file I/O operations for configuration files,
    supporting YAML format.
    """

    def load_config(self, file_path: Path) -> dict[str, Any]:
        """
        Load configuration from a YAML file.

        Args:
            file_path: Path to the configuration file

        Returns:
            Dictionary containing the configuration data

        Raises:
            ConfigError: If file cannot be read or parsed
        """
        try:
            with file_path.open("r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)

            # Ensure we have a valid dictionary
            if config_data is None:
                logger.warning("Empty YAML file: %s", file_path)
                return {}

            if not isinstance(config_data, dict):
                logger.warning(
                    "Invalid YAML format in %s - expected a dictionary", file_path
                )
                return {}

            return config_data

        except yaml.YAMLError as e:
            logger.warning("Error parsing YAML config file %s: %s", file_path, e)
            raise ConfigError(f"Error parsing config file {file_path}: {e}") from e
        except OSError as e:
            logger.warning("Error reading config file %s: %s", file_path, e)
            raise ConfigError(f"Error reading config file {file_path}: {e}") from e

    def save_config(self, file_path: Path, config_data: dict[str, Any]) -> None:
        """
        Save configuration to a YAML file.

        Args:
            file_path: Path to save the configuration file
            config_data: Dictionary containing configuration data

        Raises:
            ConfigError: If file cannot be written
        """
        try:
            # Create parent directories if they don't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with file_path.open("w", encoding="utf-8") as f:
                yaml.dump(config_data, f, default_flow_style=False, sort_keys=True)

            logger.debug("Saved configuration to %s", file_path)

        except OSError as e:
            msg = f"Error writing config file {file_path}: {e}"
            logger.error(msg)
            raise ConfigError(msg) from e

    def search_config_files(
        self, search_paths: list[Path]
    ) -> tuple[dict[str, Any], Path | None]:
        """
        Search for configuration files in multiple locations.

        Args:
            search_paths: List of paths to search for configuration files

        Returns:
            Tuple of (config_data, file_path) where file_path is the path of the first
            valid config file found, or None if no valid files were found
        """
        logger.debug(
            "Searching for config files in %d locations: %s", 
            len(search_paths), 
            " | ".join(str(p) for p in search_paths)
        )

        for i, config_path in enumerate(search_paths, 1):
            if not config_path.exists():
                continue

            try:
                config_data = self.load_config(config_path)
                if config_data:  # Only return if we got actual data
                    logger.debug(
                        "Found config file [%d/%d]: %s (%d keys)",
                        i, len(search_paths), config_path, len(config_data)
                    )
                    return config_data, config_path

            except ConfigError as e:
                # Already logged in load_config
                logger.debug("Config file [%d/%d] failed to load: %s", i, len(search_paths), e)
                continue

        # No valid config files found
        logger.debug("No valid configuration files found in any search paths")
        return {}, None

    def load_model(self, file_path: Path, model_class: type[T]) -> T:
        """
        Load configuration and convert to a Pydantic model.

        Args:
            file_path: Path to the configuration file
            model_class: Pydantic model class to convert to

        Returns:
            Instance of the model class

        Raises:
            ConfigError: If file cannot be read or parsed, or if data doesn't match model
        """
        try:
            config_data = self.load_config(file_path)
            return model_class.model_validate(config_data)

        except Exception as e:
            msg = f"Error converting config data to model: {e}"
            logger.error(msg)
            raise ConfigError(msg) from e

    def save_model(self, file_path: Path, model: T) -> None:
        """
        Save a Pydantic model to a configuration file.

        Args:
            file_path: Path to save the configuration file
            model: Pydantic model instance

        Raises:
            ConfigError: If file cannot be written
        """
        try:
            # Convert model to dict with Path objects serialized as strings
            config_data = model.model_dump(mode="json")
            self.save_config(file_path, config_data)

        except Exception as e:
            msg = f"Error saving model to config file: {e}"
            logger.error(msg)
            raise ConfigError(msg) from e


def create_config_file_adapter() -> ConfigFileAdapterProtocol[UserConfigData]:
    """Create a ConfigFileAdapter instance for UserConfigData."""
    return ConfigFileAdapter[UserConfigData]()
