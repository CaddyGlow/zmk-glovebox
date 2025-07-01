"""Tests for UserConfig wrapper class.

This module tests the UserConfig class which wraps UserConfigData
and handles file loading, source tracking, and configuration management.
"""

import os
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from glovebox.config.user_config import UserConfig, create_user_config


class TestUserConfigInitialization:
    """Tests for UserConfig initialization and setup."""

    def test_default_initialization(self, clean_environment, mock_config_adapter: Mock):
        """Test UserConfig initialization with defaults."""
        # Mock no config file found
        mock_config_adapter.search_config_files.return_value = ({}, None)

        config = UserConfig(config_adapter=mock_config_adapter)

        # Should use default values from base config
        assert config._config.profile == "glove80/v25.05"
        assert config._config.cache_strategy == "shared"
        assert config._config.firmware.flash.timeout == 30

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
        # Mock base config loading
        mock_adapter.load_config.return_value = {
            "profile": "glove80/v25.05",
            "cache_strategy": "shared",
            "firmware": {"flash": {"timeout": 30}},
        }
        mock_adapter.search_config_files.return_value = (
            sample_config_dict,
            config_path,
        )

        config = UserConfig(config_adapter=mock_adapter)

        # Should use values from config file
        assert config._config.profile == "test_keyboard/v1.0"
        assert config._config.firmware.flash.timeout == 120

    def test_config_path_generation(self, clean_environment, mock_config_adapter: Mock):
        """Test configuration path generation."""
        mock_config_adapter.search_config_files.return_value = ({}, None)

        config = UserConfig(config_adapter=mock_config_adapter)

        # Should have generated config paths
        call_args = mock_config_adapter.search_config_files.call_args[0][0]
        config_paths = call_args

        # Should include current directory paths
        assert any("glovebox.yaml" in str(path) for path in config_paths)
        assert any("glovebox.yml" in str(path) for path in config_paths)

        # Should include XDG config paths
        assert any(".config/glovebox" in str(path) for path in config_paths)

    def test_cli_config_path_priority(
        self, clean_environment, temp_config_dir: Path, mock_config_adapter: Mock
    ):
        """Test that CLI-provided config path has priority."""
        cli_config_path = temp_config_dir / "cli_config.yml"

        mock_config_adapter.search_config_files.return_value = ({}, None)

        config = UserConfig(
            cli_config_path=cli_config_path, config_adapter=mock_config_adapter
        )

        # Should include CLI path first in search
        call_args = mock_config_adapter.search_config_files.call_args[0][0]
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
        # Note: log_level is now nested, skip this check
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

        # Non-environment values should show as base_config
        assert config.get_source("cache_strategy") == "base_config"


class TestUserConfigBaseConfig:
    """Tests for base configuration loading and merging functionality."""

    def test_base_config_loading(self, clean_environment):
        """Test that base config is loaded correctly."""
        mock_adapter = Mock()
        mock_adapter.search_config_files.return_value = ({}, None)
        # Mock the base config loading
        mock_adapter.load_config.return_value = {
            "profile": "base_keyboard/v1.0",
            "cache_strategy": "shared",
            "icon_mode": "emoji",
        }

        config = UserConfig(config_adapter=mock_adapter)

        # Should have loaded base config values
        assert config._config.profile == "base_keyboard/v1.0"
        assert config._config.cache_strategy == "shared"
        assert config._config.icon_mode.value == "emoji"

    def test_user_config_merges_over_base(self, clean_environment):
        """Test that user config values override base config values."""
        mock_adapter = Mock()

        # Mock base config
        mock_adapter.load_config.return_value = {
            "profile": "base_keyboard/v1.0",
            "cache_strategy": "shared",
            "icon_mode": "emoji",
            "firmware": {"flash": {"timeout": 30, "verify": True}},
        }

        # Mock user config that overrides some values
        user_config = {
            "profile": "user_keyboard/v2.0",
            "icon_mode": "text",
            "firmware": {
                "flash": {
                    "timeout": 60
                    # Note: verify doesn't exist in current model
                }
            },
        }
        mock_adapter.search_config_files.return_value = (
            user_config,
            Path("/tmp/user.yml"),
        )

        config = UserConfig(config_adapter=mock_adapter)

        # User values should override base values
        assert config._config.profile == "user_keyboard/v2.0"
        assert config._config.icon_mode.value == "text"
        assert config._config.firmware.flash.timeout == 60

        # Base values should be preserved where not overridden
        assert config._config.cache_strategy == "shared"  # From base
        # Remove check for non-existent verify attribute

    def test_base_config_source_tracking(self, clean_environment):
        """Test that base config sources are tracked correctly."""
        mock_adapter = Mock()

        # Mock base config
        mock_adapter.load_config.return_value = {
            "cache_strategy": "shared",
            "icon_mode": "emoji",
        }

        # Mock empty user config
        mock_adapter.search_config_files.return_value = ({}, None)

        config = UserConfig(config_adapter=mock_adapter)

        # Base config values should be tracked
        assert config.get_source("cache_strategy") == "base_config"
        assert config.get_source("icon_mode") == "base_config"

    def test_nested_config_merging(self, clean_environment):
        """Test that nested configuration merging works correctly."""
        mock_adapter = Mock()

        # Mock base config with nested structure
        mock_adapter.load_config.return_value = {
            "cache_ttls": {
                "workspace_base": 3600,
                "workspace_branch": 3600,
                # Note: layout_diff doesn't exist in current model
            },
            "firmware": {
                "flash": {"timeout": 30}
            },  # Removed verify/auto_detect as they don't exist
        }

        # Mock user config that partially overrides nested values
        user_config = {
            "cache_ttls": {
                "workspace_base": 7200,  # Override this using correct field name
                # Keep workspace_branch from base
            },
            "firmware": {
                "flash": {
                    "timeout": 120,  # Override this
                    # Note: verify and auto_detect don't exist in current model
                }
            },
        }
        mock_adapter.search_config_files.return_value = (
            user_config,
            Path("/tmp/user.yml"),
        )

        config = UserConfig(config_adapter=mock_adapter)

        # User overrides should take effect
        assert config._config.cache_ttls.workspace_base == 7200
        assert config._config.firmware.flash.timeout == 120

        # Base values should be preserved where not overridden
        assert config._config.cache_ttls.workspace_branch == 3600
        # Note: layout_diff and verify/auto_detect don't exist in current model

    def test_base_config_file_not_found(self, clean_environment):
        """Test behavior when base config file is not found."""
        mock_adapter = Mock()
        mock_adapter.search_config_files.return_value = ({}, None)
        # Mock base config file not existing
        mock_adapter.load_config.side_effect = FileNotFoundError(
            "Base config not found"
        )

        config = UserConfig(config_adapter=mock_adapter)

        # Should still work with Pydantic model defaults
        assert config._config.profile == "glove80/v25.05"  # Pydantic default
        assert config._config.cache_strategy == "shared"  # Pydantic default


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
        config._config.logging_config.handlers[0].level = "ERROR"

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

        # Note: log_level is now nested, so we skip this test or adjust for the nested structure
        # config.set("log_level", "ERROR")
        # assert config._config.log_level == "ERROR"
        # assert config.get_source("log_level") == "runtime"

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
        # Note: log_level check removed as it's nested now

        # Reset to defaults
        config.reset_to_defaults()

        # Should have default values
        assert config._config.profile == "glove80/v25.05"
        assert (
            config._config.logging_config.handlers[0].level == "WARNING"
        )  # Default from create_default_logging_config
        assert config._config_sources == {}

    def test_get_log_level_int(self, clean_environment):
        """Test get_log_level_int() method."""
        mock_adapter = Mock()
        mock_adapter.search_config_files.return_value = ({}, None)

        config = UserConfig(config_adapter=mock_adapter)

        # Test different log levels
        import logging

        config._config.logging_config.handlers[0].level = "DEBUG"
        assert config.get_log_level_int() == logging.DEBUG

        config._config.logging_config.handlers[0].level = "INFO"
        assert config.get_log_level_int() == logging.INFO

        config._config.logging_config.handlers[0].level = "WARNING"
        assert config.get_log_level_int() == logging.WARNING

        config._config.logging_config.handlers[0].level = "ERROR"
        assert config.get_log_level_int() == logging.ERROR

        config._config.logging_config.handlers[0].level = "CRITICAL"
        assert config.get_log_level_int() == logging.CRITICAL

        # Invalid level should default to INFO
        config._config.logging_config.handlers[0].level = "INVALID"
        assert config.get_log_level_int() == logging.INFO

    def test_keyboard_path_methods(self, clean_environment):
        """Test keyboard path helper methods."""
        mock_adapter = Mock()
        mock_adapter.search_config_files.return_value = ({}, None)

        config = UserConfig(config_adapter=mock_adapter)

        # Test get_keyboard_paths
        config._config.profiles_paths = [Path("~/test"), Path("/absolute/path")]
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
        assert Path("/new/path") in config._config.profiles_paths
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
        config._config.profiles_paths = [Path("/path/one"), Path("/path/two")]

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

    def test_factory_function(self, isolated_config):
        """Test create_user_config factory function."""
        # Use the isolated config to get the CLI config path for proper isolation
        config = create_user_config(cli_config_path=isolated_config.config_file_path)

        assert isinstance(config, UserConfig)
        # Should use values from the isolated environment
        assert config._config.profile == "test_keyboard/v1.0"  # From isolated config
        assert (
            config._config.logging_config.handlers[0].level == "WARNING"
        )  # Default from create_default_logging_config

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
        # Note: log_level check removed as it's nested now
        assert (
            config._config.firmware.flash.timeout
            == sample_config_dict["firmware"]["flash"]["timeout"]
        )
