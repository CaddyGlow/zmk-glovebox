"""
Configuration loading with include directive support.

This module provides enhanced configuration loading capabilities that support
include directives, recursive loading, and configuration composition.
"""

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from glovebox.config.models import KeyboardConfig
from glovebox.core.errors import ConfigError
from glovebox.core.logging import get_logger


logger = get_logger(__name__)


class IncludeConfigLoader:
    """Configuration loader with include directive support."""

    def __init__(self, search_paths: list[Path]):
        """Initialize the loader with search paths.

        Args:
            search_paths: List of paths to search for configuration files
        """
        self.search_paths = search_paths
        self._loading_stack: list[Path] = []  # For cycle detection
        self._loaded_files: dict[Path, dict[str, Any]] = {}  # File cache

    def load_keyboard_config(
        self, keyboard_name: str, base_path: Path | None = None
    ) -> KeyboardConfig:
        """Load a keyboard configuration with include support.

        Args:
            keyboard_name: Name of the keyboard to load
            base_path: Base path for relative include resolution

        Returns:
            Typed KeyboardConfig object

        Raises:
            ConfigError: If the configuration cannot be found or loaded
        """
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Loading keyboard configuration with includes: %s", keyboard_name
            )

        # Find the configuration file
        config_file = self._find_config_file(keyboard_name)
        if not config_file:
            raise ConfigError(f"Keyboard configuration not found: {keyboard_name}")

        # Load the raw configuration with includes resolved
        raw_config = self._load_config_with_includes(config_file, base_path)

        # Fix keyboard name mismatch if needed
        if raw_config.get("keyboard") != keyboard_name:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "Keyboard name mismatch: file has '%s', expected '%s' - fixing",
                    raw_config.get("keyboard"),
                    keyboard_name,
                )
            raw_config["keyboard"] = keyboard_name

        # Convert to typed object using Pydantic validation
        try:
            typed_config = KeyboardConfig.model_validate(raw_config)
            logger.info(
                "Loaded keyboard configuration with includes: %s", keyboard_name
            )
            return typed_config
        except ValidationError as e:
            raise ConfigError(f"Invalid keyboard configuration format: {e}") from e

    def _find_config_file(self, keyboard_name: str) -> Path | None:
        """Find a configuration file by name.

        Supports both single-file configurations and directory-based configurations:
        1. {keyboard_name}.yaml
        2. {keyboard_name}.yml
        3. {keyboard_name}/keyboard.yaml
        4. {keyboard_name}/keyboard.yml
        5. {keyboard_name}/{keyboard_name}.yaml
        6. {keyboard_name}/{keyboard_name}.yml

        Args:
            keyboard_name: Name of the keyboard configuration

        Returns:
            Path to the configuration file, or None if not found
        """
        for search_path in self.search_paths:
            # Try single-file configurations first
            # Try .yaml extension
            yaml_file = search_path / f"{keyboard_name}.yaml"
            if yaml_file.exists():
                return yaml_file

            # Then try .yml extension
            yml_file = search_path / f"{keyboard_name}.yml"
            if yml_file.exists():
                return yml_file

            # Try directory-based configurations
            config_dir = search_path / keyboard_name
            if config_dir.exists() and config_dir.is_dir():
                # Try keyboard.yaml in directory
                dir_yaml = config_dir / "keyboard.yaml"
                if dir_yaml.exists():
                    return dir_yaml

                # Try keyboard.yml in directory
                dir_yml = config_dir / "keyboard.yml"
                if dir_yml.exists():
                    return dir_yml

                # Try {keyboard_name}.yaml in directory
                named_yaml = config_dir / f"{keyboard_name}.yaml"
                if named_yaml.exists():
                    return named_yaml

                # Try {keyboard_name}.yml in directory
                named_yml = config_dir / f"{keyboard_name}.yml"
                if named_yml.exists():
                    return named_yml

        return None

    def _load_config_with_includes(
        self, config_file: Path, base_path: Path | None = None
    ) -> dict[str, Any]:
        """Load a configuration file with include directives resolved.

        Args:
            config_file: Path to the configuration file
            base_path: Base path for relative include resolution

        Returns:
            Configuration dictionary with includes resolved

        Raises:
            ConfigError: If there are cycles or loading errors
        """
        # Use absolute path for consistent cache keys and cycle detection
        config_file = config_file.resolve()

        # Check for circular includes
        if config_file in self._loading_stack:
            cycle_path = " -> ".join(
                str(p)
                for p in self._loading_stack[self._loading_stack.index(config_file) :]
            )
            raise ConfigError(
                f"Circular include detected: {cycle_path} -> {config_file}"
            )

        # Return cached config if available
        if config_file in self._loaded_files:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Using cached config: %s", config_file)
            return self._loaded_files[config_file]

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Loading config file: %s", config_file)

        # Add to loading stack for cycle detection
        self._loading_stack.append(config_file)

        try:
            # Load the raw YAML
            with config_file.open() as f:
                raw_config_data = yaml.safe_load(f)

            if not isinstance(raw_config_data, dict):
                raise ConfigError(
                    f"Configuration file must contain a dictionary: {config_file}"
                )

            raw_config: dict[str, Any] = raw_config_data

            # Process includes if present
            if "include" in raw_config:
                raw_config = self._process_includes(raw_config, config_file, base_path)

            # Cache the processed configuration
            self._loaded_files[config_file] = raw_config

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Successfully loaded and cached config: %s", config_file)

            return raw_config

        except yaml.YAMLError as e:
            raise ConfigError(
                f"Error parsing configuration file {config_file}: {e}"
            ) from e
        except OSError as e:
            raise ConfigError(
                f"Error reading configuration file {config_file}: {e}"
            ) from e
        finally:
            # Remove from loading stack
            if config_file in self._loading_stack:
                self._loading_stack.remove(config_file)

    def _process_includes(
        self,
        config: dict[str, Any],
        config_file: Path,
        base_path: Path | None = None,
    ) -> dict[str, Any]:
        """Process include directives in a configuration.

        Args:
            config: Configuration dictionary
            config_file: Path to the current configuration file
            base_path: Base path for relative include resolution

        Returns:
            Configuration with includes resolved and merged
        """
        includes = config.pop("include", [])
        if not includes:
            return config

        if not isinstance(includes, list):
            includes = [includes]

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Processing %d include(s) for %s", len(includes), config_file)

        # Use config file's directory as base path if not provided
        if base_path is None:
            base_path = config_file.parent

        # Load and merge included configurations
        merged_config: dict[str, Any] = {}

        for include_path in includes:
            resolved_path = self._resolve_include_path(
                include_path, base_path, config_file
            )
            included_config = self._load_config_with_includes(resolved_path, base_path)

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Merging include: %s", resolved_path)

            merged_config = self._merge_configurations(merged_config, included_config)

        # Merge the current config on top of included configs
        final_config = self._merge_configurations(merged_config, config)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Completed include processing for %s", config_file)

        return final_config

    def _resolve_include_path(
        self, include_path: str, base_path: Path, config_file: Path
    ) -> Path:
        """Resolve an include path to an absolute path.

        Args:
            include_path: The include path from the configuration
            base_path: Base path for relative resolution
            config_file: Current configuration file path

        Returns:
            Resolved absolute path to the include file

        Raises:
            ConfigError: If the include file cannot be found
        """
        # Convert to Path object
        include_path_obj = Path(include_path)

        # If absolute path, use as-is
        if include_path_obj.is_absolute():
            if include_path_obj.exists():
                return include_path_obj.resolve()
            raise ConfigError(f"Include file not found: {include_path}")

        # Try relative to base path
        base_relative = base_path / include_path_obj
        if base_relative.exists():
            return base_relative.resolve()

        # Try relative to config file directory
        config_relative = config_file.parent / include_path_obj
        if config_relative.exists():
            return config_relative.resolve()

        # Try adding extensions if no extension provided
        if not include_path_obj.suffix:
            for ext in [".yaml", ".yml"]:
                # Try with base path
                base_with_ext = base_path / f"{include_path}{ext}"
                if base_with_ext.exists():
                    return base_with_ext.resolve()

                # Try with config file directory
                config_with_ext = config_file.parent / f"{include_path}{ext}"
                if config_with_ext.exists():
                    return config_with_ext.resolve()

        # Search in configured search paths
        for search_path in self.search_paths:
            search_file = search_path / include_path_obj
            if search_file.exists():
                return search_file.resolve()

            # Try with extensions
            if not include_path_obj.suffix:
                for ext in [".yaml", ".yml"]:
                    search_with_ext = search_path / f"{include_path}{ext}"
                    if search_with_ext.exists():
                        return search_with_ext.resolve()

        raise ConfigError(
            f"Include file not found: {include_path} (searched relative to {base_path}, {config_file.parent}, and {self.search_paths})"
        )

    def _merge_configurations(
        self, base: dict[str, Any], override: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge two configuration dictionaries.

        Args:
            base: Base configuration dictionary
            override: Override configuration dictionary

        Returns:
            Merged configuration dictionary
        """
        if not base:
            return override.copy()
        if not override:
            return base.copy()

        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                # Recursively merge nested dictionaries
                result[key] = self._merge_configurations(result[key], value)
            elif (
                key in result
                and isinstance(result[key], list)
                and isinstance(value, list)
            ):
                # Extend lists (override adds to base)
                result[key] = result[key] + value
            else:
                # Direct override for other types
                result[key] = value

        return result

    def clear_cache(self) -> None:
        """Clear the loaded file cache."""
        self._loaded_files.clear()
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Cleared include loader cache")


def create_include_loader(search_paths: list[Path]) -> IncludeConfigLoader:
    """Create an include configuration loader.

    Args:
        search_paths: List of paths to search for configuration files

    Returns:
        IncludeConfigLoader instance
    """
    return IncludeConfigLoader(search_paths)
