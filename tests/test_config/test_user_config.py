"""Tests for UserConfig."""

import logging
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from glovebox.adapters.config_file_adapter import ConfigFileAdapter
from glovebox.config.models import UserConfigData
from glovebox.config.user_config import UserConfig, create_user_config
from glovebox.core.errors import ConfigError


def test_user_config_create():
    """Test creating UserConfig with factory function."""
    config = create_user_config()
    assert isinstance(config, UserConfig)


def test_user_config_with_adapter():
    """Test UserConfig with mock adapter."""
    # Create mock adapter
    mock_adapter = MagicMock(spec=ConfigFileAdapter[UserConfigData])
    # Need to mock search_config_files, not load_config
    mock_adapter.search_config_files.return_value = (
        {"default_keyboard": "test_keyboard"},
        Path("/mock/path"),
    )

    # Create UserConfig with mock adapter
    config = create_user_config(config_adapter=mock_adapter)

    # Verify config uses the mock adapter's data
    assert config.default_keyboard == "test_keyboard"

    # Verify adapter was called
    mock_adapter.search_config_files.assert_called()


def test_user_config_cli_path():
    """Test UserConfig with CLI path."""
    # Create a temporary config file
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w+", delete=False) as f:
        yaml.dump({"default_keyboard": "cli_keyboard"}, f)
        temp_path = Path(f.name)

    try:
        # Create UserConfig with CLI path
        config = create_user_config(cli_config_path=temp_path)

        # Verify config uses the CLI path's data
        assert config.default_keyboard == "cli_keyboard"

    finally:
        # Clean up
        temp_path.unlink(missing_ok=True)


def test_user_config_env_vars():
    """Test UserConfig with environment variables."""
    # Set environment variable
    os.environ["GLOVEBOX_DEFAULT_KEYBOARD"] = "env_keyboard"

    try:
        # Create UserConfig
        config = create_user_config()

        # Verify environment variable takes precedence
        assert config.default_keyboard == "env_keyboard"
        assert config.get_source("default_keyboard") == "environment"

    finally:
        # Clean up
        del os.environ["GLOVEBOX_DEFAULT_KEYBOARD"]


def test_user_config_property_access():
    """Test direct property access to configuration values."""
    # Use a mock adapter to ensure we get the default values
    mock_adapter = MagicMock(spec=ConfigFileAdapter[UserConfigData])
    mock_adapter.search_config_files.return_value = ({}, None)
    config = create_user_config(config_adapter=mock_adapter)

    # Test getters
    assert config.default_keyboard == "glove80"
    assert config.default_firmware == "v25.05"
    assert config.log_level == "INFO"
    assert isinstance(config.keyboard_paths, list)

    # Test setters
    config.default_keyboard = "test_keyboard"
    assert config.default_keyboard == "test_keyboard"
    assert config.get_source("default_keyboard") == "runtime"

    config.default_firmware = "test_firmware"
    assert config.default_firmware == "test_firmware"

    config.log_level = "DEBUG"
    assert config.log_level == "DEBUG"

    config.keyboard_paths = ["/path/to/test"]
    assert config.keyboard_paths == ["/path/to/test"]


def test_user_config_get_set():
    """Test UserConfig get and set methods."""
    config = create_user_config()

    # Set values
    config.set("default_keyboard", "new_keyboard")
    config.set("log_level", "DEBUG")

    # Get values
    assert config.get("default_keyboard") == "new_keyboard"
    assert config.get("log_level") == "DEBUG"
    assert config.get_source("default_keyboard") == "runtime"

    # Get invalid key
    assert config.get("invalid_key", "default") == "default"

    # Set invalid key should raise
    with pytest.raises(ValueError):
        config.set("invalid_key", "value")


def test_user_config_save():
    """Test saving UserConfig."""
    # Create a temporary path
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        temp_path = Path(f.name)
    temp_path.unlink(missing_ok=True)  # Remove so we can test creating the file

    try:
        # Create a mock adapter
        mock_adapter = MagicMock(spec=ConfigFileAdapter[UserConfigData])
        # Need to mock the search_config_files method
        mock_adapter.search_config_files.return_value = ({}, None)

        # Create UserConfig with our adapter
        config = create_user_config(config_adapter=mock_adapter)

        # Set the main config path manually
        config._main_config_path = temp_path

        # Set a value and save
        config.default_keyboard = "saved_keyboard"
        config.save()

        # Verify adapter's save_model was called
        mock_adapter.save_model.assert_called_once()

    finally:
        # Clean up
        temp_path.unlink(missing_ok=True)


def test_user_config_keyboard_paths():
    """Test UserConfig keyboard paths methods."""
    config = create_user_config()

    # Test add_keyboard_path
    config.add_keyboard_path("/path/to/test1")
    assert "/path/to/test1" in config.keyboard_paths

    # Test add_keyboard_path doesn't add duplicates
    config.add_keyboard_path("/path/to/test1")
    assert len([p for p in config.keyboard_paths if p == "/path/to/test1"]) == 1

    # Test add_keyboard_path with Path object
    config.add_keyboard_path(Path("/path/to/test2"))
    assert "/path/to/test2" in config.keyboard_paths

    # Test remove_keyboard_path
    config.remove_keyboard_path("/path/to/test1")
    assert "/path/to/test1" not in config.keyboard_paths

    # Test get_keyboard_paths
    paths = config.get_keyboard_paths()
    assert isinstance(paths, list)
    assert all(isinstance(p, Path) for p in paths)


def test_user_config_log_level_int():
    """Test UserConfig get_log_level_int method."""
    # Use a mock adapter to ensure we get the default values
    mock_adapter = MagicMock(spec=ConfigFileAdapter[UserConfigData])
    mock_adapter.search_config_files.return_value = ({}, None)
    config = create_user_config(config_adapter=mock_adapter)

    # Now test with a clean config that has the default values
    config.log_level = "INFO"  # Reset to known state
    assert config.get_log_level_int() == logging.INFO  # Should be 20

    # Test custom log level
    config.log_level = "DEBUG"
    assert config.get_log_level_int() == logging.DEBUG  # Should be 10

    config.log_level = "WARNING"
    assert config.get_log_level_int() == logging.WARNING  # Should be 30

    config.log_level = "ERROR"
    assert config.get_log_level_int() == logging.ERROR  # Should be 40

    # Test case insensitivity
    config.log_level = "debug"  # lowercase
    assert config.get_log_level_int() == logging.DEBUG  # Should be 10


def test_user_config_reset_to_defaults():
    """Test UserConfig reset_to_defaults method."""
    config = create_user_config()

    # Change some values
    config.default_keyboard = "test_keyboard"
    config.default_firmware = "test_firmware"
    config.log_level = "DEBUG"

    # Reset to defaults
    config.reset_to_defaults()

    # Verify values are reset
    assert config.default_keyboard == "glove80"
    assert config.default_firmware == "v25.05"
    assert config.log_level == "INFO"
    assert config.keyboard_paths == []
