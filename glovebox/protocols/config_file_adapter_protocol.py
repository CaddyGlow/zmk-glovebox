"""Protocol definition for configuration file operations."""

from pathlib import Path
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel


# Type variable for generic model type
T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class ConfigFileAdapterProtocol(Protocol, Generic[T]):
    """Protocol for configuration file operations."""

    def load_config(self, file_path: Path) -> dict[str, Any]:
        """Load configuration from a file.

        Args:
            file_path: Path to the configuration file

        Returns:
            Dictionary containing the configuration data

        Raises:
            ConfigError: If file cannot be read or parsed
        """
        ...

    def save_config(self, file_path: Path, config_data: dict[str, Any]) -> None:
        """Save configuration to a file.

        Args:
            file_path: Path to save the configuration file
            config_data: Dictionary containing configuration data

        Raises:
            ConfigError: If file cannot be written
        """
        ...

    def search_config_files(
        self, search_paths: list[Path]
    ) -> tuple[dict[str, Any], Path | None]:
        """Search for configuration files in multiple locations.

        Args:
            search_paths: List of paths to search for configuration files

        Returns:
            Tuple of (config_data, file_path) where file_path is the path of the first
            valid config file found, or None if no valid files were found
        """
        ...

    def load_model(self, file_path: Path, model_class: type[T]) -> T:
        """Load configuration and convert to a Pydantic model.

        Args:
            file_path: Path to the configuration file
            model_class: Pydantic model class to convert to

        Returns:
            Instance of the model class

        Raises:
            ConfigError: If file cannot be read or parsed, or if data doesn't match model
        """
        ...

    def save_model(self, file_path: Path, model: T) -> None:
        """Save a Pydantic model to a configuration file.

        Args:
            file_path: Path to save the configuration file
            model: Pydantic model instance

        Raises:
            ConfigError: If file cannot be written
        """
        ...
