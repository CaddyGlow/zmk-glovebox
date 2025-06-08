"""Tests for ConfigFileAdapter."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from glovebox.adapters.config_file_adapter import (
    ConfigFileAdapter,
    create_config_file_adapter,
)
from glovebox.config.models import UserConfigData
from glovebox.core.errors import ConfigError
from glovebox.protocols.config_file_adapter_protocol import ConfigFileAdapterProtocol


def test_config_file_adapter_create():
    """Test creating ConfigFileAdapter."""
    adapter = create_config_file_adapter()
    assert isinstance(adapter, ConfigFileAdapter)
    assert isinstance(adapter, ConfigFileAdapterProtocol)


def test_config_file_adapter_load():
    """Test loading configuration file."""
    # Create a temporary config file
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w+", delete=False) as f:
        yaml.dump({"default_keyboard": "test_keyboard"}, f)
        temp_path = Path(f.name)

    try:
        # Load the config
        adapter = create_config_file_adapter()
        config = adapter.load_config(temp_path)

        # Verify the content
        assert isinstance(config, dict)
        assert config.get("default_keyboard") == "test_keyboard"

    finally:
        # Clean up
        temp_path.unlink(missing_ok=True)


def test_config_file_adapter_empty_file():
    """Test loading an empty configuration file."""
    # Create a temporary empty config file
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w+", delete=False) as f:
        temp_path = Path(f.name)

    try:
        # Load the config
        adapter = create_config_file_adapter()
        config = adapter.load_config(temp_path)

        # Verify it returns an empty dict
        assert isinstance(config, dict)
        assert not config  # empty dict

    finally:
        # Clean up
        temp_path.unlink(missing_ok=True)


def test_config_file_adapter_invalid_file():
    """Test loading an invalid configuration file."""
    # Create a temporary invalid config file
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w+", delete=False) as f:
        f.write("invalid: yaml: file")
        temp_path = Path(f.name)

    try:
        # Load the config should raise ConfigError
        adapter = create_config_file_adapter()
        with pytest.raises(ConfigError):
            adapter.load_config(temp_path)

    finally:
        # Clean up
        temp_path.unlink(missing_ok=True)


def test_config_file_adapter_save():
    """Test saving configuration file."""
    # Create a temporary path
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        temp_path = Path(f.name)
    temp_path.unlink(missing_ok=True)  # Remove so we can test creating the file

    try:
        # Save config
        adapter = create_config_file_adapter()
        config_data = {"default_keyboard": "test_keyboard"}
        adapter.save_config(temp_path, config_data)

        # Verify the file was created
        assert temp_path.exists()

        # Verify content
        with temp_path.open() as f:
            loaded_data = yaml.safe_load(f)
            assert loaded_data.get("default_keyboard") == "test_keyboard"

    finally:
        # Clean up
        temp_path.unlink(missing_ok=True)


def test_config_file_adapter_model():
    """Test loading and saving Pydantic model."""
    # Create a temporary config file
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w+", delete=False) as f:
        yaml.dump({"default_keyboard": "test_keyboard", "log_level": "DEBUG"}, f)
        temp_path = Path(f.name)

    try:
        # Load the model
        adapter = create_config_file_adapter()
        model = adapter.load_model(temp_path, UserConfigData)

        # Verify the model
        assert isinstance(model, UserConfigData)
        assert model.default_keyboard == "test_keyboard"
        assert model.log_level == "DEBUG"

        # Modify and save the model
        model.default_firmware = "test_firmware"
        adapter.save_model(temp_path, model)

        # Reload and verify changes
        new_model = adapter.load_model(temp_path, UserConfigData)
        assert new_model.default_firmware == "test_firmware"

    finally:
        # Clean up
        temp_path.unlink(missing_ok=True)


def test_config_file_adapter_search():
    """Test searching for configuration files."""
    # Create a few temporary config files
    paths = []
    try:
        # Create first config file
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w+", delete=False) as f:
            yaml.dump({"default_keyboard": "first_config"}, f)
            paths.append(Path(f.name))

        # Create second config file
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w+", delete=False) as f:
            yaml.dump({"default_keyboard": "second_config"}, f)
            paths.append(Path(f.name))

        # Search for configs
        adapter = create_config_file_adapter()
        config, found_path = adapter.search_config_files(paths)

        # Should find the first config
        assert isinstance(config, dict)
        assert config.get("default_keyboard") == "first_config"
        assert found_path == paths[0]

        # Search with reversed order
        config, found_path = adapter.search_config_files(list(reversed(paths)))

        # Should find the second config
        assert config.get("default_keyboard") == "second_config"
        assert found_path == paths[1]

        # Search with nonexistent paths
        config, found_path = adapter.search_config_files(
            [Path("/tmp/nonexistent.yaml")]
        )

        # Should return empty dict and None
        assert config == {}
        assert found_path is None

    finally:
        # Clean up
        for path in paths:
            path.unlink(missing_ok=True)
