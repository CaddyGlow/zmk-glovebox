"""Tests for UserConfig wrapper class.

This module tests the UserConfig class which wraps UserConfigData
and handles file loading, source tracking, and configuration management.
"""

import os
from pathlib import Path
from typing import Any
from unittest.mock import Mock, call

import pytest

from glovebox.config.user_config import UserConfig, create_user_config


class TestUserConfigInitialization:
    """Tests for UserConfig initialization and setup."""

    def test_default_initialization(self, clean_environment, mock_config_adapter: Mock):
        """Test UserConfig initialization with defaults."""
        # Mock no config file found
        mock_config_adapter.search_config_files.return_value = ({}, None)

        config = UserConfig(config_adapter=mock_config_adapter)

        # Should use default values
        assert config._config.profile == "glove80/v25.05"
        assert config._config.log_level == "INFO"
        assert config._config.firmware.flash.timeout == 60

        # Should have called search_config_files
        mock_config_adapter.search_config_files.assert_called_once()

    def test_initialization_with_config_file(
        self,
        clean_environment,
        sample_config_dict: dict[str, Any],
        temp_config_dir: Path,
    ):
        """Test UserConfig initialization with config file."""
        config_path = temp_config_dir / "test_config.yml"

        mock_adapter = Mock()
        mock_adapter.search_config_files.return_value = (
            sample_config_dict,
            config_path,
        )

        config = UserConfig(config_adapter=mock_adapter)

        # Should use values from config file
        assert config._config.profile == "test_keyboard/v1.0"
        assert config._config.log_level == "DEBUG"
        assert config._config.firmware.flash.timeout == 120
        assert config._config.firmware.flash.count == 5

    def test_config_path_generation(self, clean_environment):
        """Test configuration path generation."""
        mock_adapter = Mock()
        mock_adapter.search_config_files.return_value = ({}, None)

        config = UserConfig(config_adapter=mock_adapter)

        # Should have generated config paths
        call_args = mock_adapter.search_config_files.call_args[0][0]
        config_paths = call_args

        # Should include current directory paths
        assert any("glovebox.yaml" in str(path) for path in config_paths)
        assert any("glovebox.yml" in str(path) for path in config_paths)

        # Should include XDG config paths
        assert any(".config/glovebox" in str(path) for path in config_paths)

    def test_cli_config_path_priority(self, clean_environment, temp_config_dir: Path):
        """Test that CLI-provided config path has priority."""
        cli_config_path = temp_config_dir / "cli_config.yml"

        mock_adapter = Mock()
        mock_adapter.search_config_files.return_value = ({}, None)

        config = UserConfig(
            cli_config_path=cli_config_path, config_adapter=mock_adapter
        )

        # Should include CLI path first in search
        call_args = mock_adapter.search_config_files.call_args[0][0]
        config_paths = call_args
        assert config_paths[0] == cli_config_path.resolve()


class TestUserConfigSourceTracking:
    """Tests for configuration source tracking."""

    def test_file_source_tracking(
        self,
        clean_environment,
        sample_config_dict: dict[str, Any],
        temp_config_dir: Path,
    ):
        """Test tracking of file-based configuration sources."""
        config_path = temp_config_dir / "source_test.yml"

        mock_adapter = Mock()
        mock_adapter.search_config_files.return_value = (
            sample_config_dict,
            config_path,
        )

        config = UserConfig(config_adapter=mock_adapter)

        # Should track file sources
        assert config.get_source("profile") == "file:source_test.yml"
        assert config.get_source("log_level") == "file:source_test.yml"
        assert config.get_source("keyboard_paths") == "file:source_test.yml"

    def test_environment_source_tracking(
        self, clean_environment, temp_config_dir: Path
    ):
        """Test tracking of environment variable sources."""
        # Set environment variables
        os.environ["GLOVEBOX_PROFILE"] = "env/test"
        os.environ["GLOVEBOX_FIRMWARE__FLASH__TIMEOUT"] = "999"

        mock_adapter = Mock()
        mock_adapter.search_config_files.return_value = ({}, None)

        config = UserConfig(config_adapter=mock_adapter)

        # Should track environment sources
        assert config.get_source("profile") == "environment"
        assert config.get_source("firmware.flash.timeout") == "environment"

        # Non-environment values should show as default
        assert config.get_source("log_level") == "default"


class TestUserConfigFileOperations:
    """Tests for file loading and saving operations."""

    def test_save_configuration(self, clean_environment, temp_config_dir: Path):
        """Test saving configuration to file."""
        config_path = temp_config_dir / "save_test.yml"

        mock_adapter = Mock()
        mock_adapter.search_config_files.return_value = ({}, None)

        config = UserConfig(config_adapter=mock_adapter)
        config._main_config_path = config_path

        # Modify configuration
        config._config.profile = "modified/config"
        config._config.log_level = "ERROR"

        # Save configuration
        config.save()

        # Should have called adapter save method
        mock_adapter.save_model.assert_called_once_with(config_path, config._config)

    def test_save_without_config_path(self, clean_environment):
        """Test save behavior when no config path is set."""
        mock_adapter = Mock()
        mock_adapter.search_config_files.return_value = ({}, None)

        config = UserConfig(config_adapter=mock_adapter)
        config._main_config_path = None

        # Should not raise exception, just log warning
        config.save()

        # Should not call save_model
        mock_adapter.save_model.assert_not_called()

    def test_config_file_precedence(self, clean_environment, temp_config_dir: Path):
        """Test configuration file search precedence."""
        # Create multiple config files
        current_config = temp_config_dir / "glovebox.yml"
        xdg_config = temp_config_dir / ".config" / "glovebox" / "config.yml"

        mock_adapter = Mock()

        # Test that it searches in correct order
        config_paths = [current_config, xdg_config]
        mock_adapter.search_config_files.return_value = ({}, None)

        UserConfig(config_adapter=mock_adapter)

        # Should have called with paths in precedence order
        call_args = mock_adapter.search_config_files.call_args[0][0]

        # Current directory should come before XDG config
        current_indices = [
            i for i, path in enumerate(call_args) if "glovebox.yml" in str(path)
        ]
        xdg_indices = [
            i for i, path in enumerate(call_args) if ".config/glovebox" in str(path)
        ]

        assert min(current_indices) < min(xdg_indices)


class TestUserConfigHelperMethods:
    """Tests for UserConfig helper methods."""

    def test_get_method(
        self,
        clean_environment,
        sample_config_dict: dict[str, Any],
        temp_config_dir: Path,
    ):
        """Test get() method for configuration access."""
        config_path = temp_config_dir / "helper_test.yml"

        mock_adapter = Mock()
        mock_adapter.search_config_files.return_value = (
            sample_config_dict,
            config_path,
        )

        config = UserConfig(config_adapter=mock_adapter)

        # Should return actual values
        assert config.get("profile") == "test_keyboard/v1.0"
        assert config.get("log_level") == "DEBUG"

        # Should return default for missing keys
        assert config.get("nonexistent_key", "default_value") == "default_value"
        assert config.get("nonexistent_key") is None

    def test_set_method(self, clean_environment):
        """Test set() method for configuration modification."""
        mock_adapter = Mock()
        mock_adapter.search_config_files.return_value = ({}, None)

        config = UserConfig(config_adapter=mock_adapter)

        # Test setting valid keys
        config.set("profile", "new/profile")
        assert config._config.profile == "new/profile"
        assert config.get_source("profile") == "runtime"

        config.set("log_level", "ERROR")
        assert config._config.log_level == "ERROR"
        assert config.get_source("log_level") == "runtime"

    def test_set_invalid_key(self, clean_environment):
        """Test set() method with invalid key."""
        mock_adapter = Mock()
        mock_adapter.search_config_files.return_value = ({}, None)

        config = UserConfig(config_adapter=mock_adapter)

        # Should raise ValueError for unknown keys
        with pytest.raises(ValueError, match="Unknown configuration key"):
            config.set("invalid_key", "value")

    def test_reset_to_defaults(
        self,
        clean_environment,
        sample_config_dict: dict[str, Any],
        temp_config_dir: Path,
    ):
        """Test reset_to_defaults() method."""
        config_path = temp_config_dir / "reset_test.yml"

        mock_adapter = Mock()
        mock_adapter.search_config_files.return_value = (
            sample_config_dict,
            config_path,
        )

        config = UserConfig(config_adapter=mock_adapter)

        # Verify modified state
        assert config._config.profile == "test_keyboard/v1.0"
        assert config._config.log_level == "DEBUG"

        # Reset to defaults
        config.reset_to_defaults()

        # Should have default values
        assert config._config.profile == "glove80/v25.05"
        assert config._config.log_level == "INFO"
        assert config._config_sources == {}

    def test_get_log_level_int(self, clean_environment):
        """Test get_log_level_int() method."""
        mock_adapter = Mock()
        mock_adapter.search_config_files.return_value = ({}, None)

        config = UserConfig(config_adapter=mock_adapter)

        # Test different log levels
        import logging

        config._config.log_level = "DEBUG"
        assert config.get_log_level_int() == logging.DEBUG

        config._config.log_level = "INFO"
        assert config.get_log_level_int() == logging.INFO

        config._config.log_level = "WARNING"
        assert config.get_log_level_int() == logging.WARNING

        config._config.log_level = "ERROR"
        assert config.get_log_level_int() == logging.ERROR

        config._config.log_level = "CRITICAL"
        assert config.get_log_level_int() == logging.CRITICAL

        # Invalid level should default to INFO
        config._config.log_level = "INVALID"
        assert config.get_log_level_int() == logging.INFO

    def test_keyboard_path_methods(self, clean_environment):
        """Test keyboard path helper methods."""
        mock_adapter = Mock()
        mock_adapter.search_config_files.return_value = ({}, None)

        config = UserConfig(config_adapter=mock_adapter)

        # Test get_keyboard_paths
        config._config.keyboard_paths = [Path("~/test"), Path("/absolute/path")]
        paths = config.get_keyboard_paths()

        # Should return expanded Path objects
        assert all(isinstance(path, Path) for path in paths)
        assert len(paths) == 2

    def test_add_keyboard_path(self, clean_environment):
        """Test add_keyboard_path() method."""
        mock_adapter = Mock()
        mock_adapter.search_config_files.return_value = ({}, None)

        config = UserConfig(config_adapter=mock_adapter)

        # Add new path
        config.add_keyboard_path("/new/path")
        assert Path("/new/path") in config._config.keyboard_paths
        assert config.get_source("keyboard_paths") == "runtime"

        # Adding duplicate should not duplicate
        config.add_keyboard_path("/new/path")
        # Check that path appears only once in the get_keyboard_paths result
        paths = config.get_keyboard_paths()
        path_count = sum(1 for p in paths if str(p) == "/new/path")
        assert path_count == 1

    def test_remove_keyboard_path(self, clean_environment):
        """Test remove_keyboard_path() method."""
        mock_adapter = Mock()
        mock_adapter.search_config_files.return_value = ({}, None)

        config = UserConfig(config_adapter=mock_adapter)

        # Set initial paths
        config._config.keyboard_paths = [Path("/path/one"), Path("/path/two")]

        # Remove existing path
        config.remove_keyboard_path("/path/one")
        paths = config.get_keyboard_paths()
        assert Path("/path/one") not in paths
        assert Path("/path/two") in paths
        assert config.get_source("keyboard_paths") == "runtime"

        # Removing non-existent path should not error
        config.remove_keyboard_path("/nonexistent")
        paths = config.get_keyboard_paths()
        assert Path("/path/two") in paths


class TestUserConfigFactory:
    """Tests for the create_user_config factory function."""

    def test_factory_function(self, clean_environment):
        """Test create_user_config factory function."""
        config = create_user_config()

        assert isinstance(config, UserConfig)
        assert config._config.profile == "glove80/v26.0"
        assert config._config.log_level == "WARNING"

    def test_factory_with_cli_path(self, clean_environment, temp_config_dir: Path):
        """Test factory function with CLI config path."""
        cli_path = temp_config_dir / "cli.yml"

        config = create_user_config(cli_config_path=cli_path)

        assert isinstance(config, UserConfig)
        # Should have attempted to load from CLI path
        assert config._main_config_path is not None

    def test_factory_with_adapter(self, clean_environment):
        """Test factory function with custom adapter."""
        mock_adapter = Mock()
        mock_adapter.search_config_files.return_value = ({}, None)

        config = create_user_config(config_adapter=mock_adapter)

        assert isinstance(config, UserConfig)
        assert config._adapter == mock_adapter


class TestUserConfigIntegration:
    """Integration tests for UserConfig with real file operations."""

    def test_real_file_loading(
        self, clean_environment, config_file: Path, sample_config_dict: dict[str, Any]
    ):
        """Test loading from real config file."""
        # Use real file adapter (not mocked)
        config = create_user_config(cli_config_path=config_file)

        # Should load values from file
        assert config._config.profile == sample_config_dict["profile"]
        assert config._config.log_level == sample_config_dict["log_level"]
        assert (
            config._config.firmware.flash.timeout
            == sample_config_dict["firmware"]["flash"]["timeout"]
        )
