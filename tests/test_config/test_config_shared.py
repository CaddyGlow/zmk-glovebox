"""Shared fixtures and utilities for keyboard configuration testing."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import yaml

from glovebox.config.keyboard_config import (
    create_keyboard_profile,
    get_available_keyboards,
    load_keyboard_config_raw,
    load_keyboard_config_typed,
)
from glovebox.config.models import FirmwareConfig, KeyboardConfig
from glovebox.config.profile import KeyboardProfile
from glovebox.models.results import BuildResult, FlashResult, KeymapResult


@pytest.fixture
def keyboard_config_dir(tmp_path):
    """Create a temporary directory with test keyboard configurations."""
    # Create keyboards directory
    keyboards_dir = tmp_path / "keyboards"
    keyboards_dir.mkdir()

    # Create test keyboard configuration
    test_keyboard_config = {
        "keyboard": "test_keyboard",
        "description": "Test keyboard for integration testing",
        "vendor": "Test Vendor",
        "version": "v1.0.0",
        "flash": {
            "method": "mass_storage",
            "query": "vendor=Test and removable=true",
            "usb_vid": 0x1234,
            "usb_pid": 0x5678,
        },
        "build": {
            "method": "docker",
            "docker_image": "test-zmk-build",
            "repository": "test/zmk",
            "branch": "main",
        },
        "firmwares": {
            "default": {
                "description": "Default test firmware",
                "version": "v1.0.0",
                "branch": "main",
            },
            "bluetooth": {
                "description": "Bluetooth-focused test firmware",
                "version": "bluetooth",
                "branch": "bluetooth",
                "kconfig": {
                    "CONFIG_ZMK_BLE": "y",
                    "CONFIG_ZMK_USB": "n",
                },
            },
        },
        "templates": {
            "keymap": """
            #include <behaviors.dtsi>
            #include <dt-bindings/zmk/keys.h>
            {{ resolved_includes }}

            / {
                keymap {
                    compatible = "zmk,keymap";
                    {{ keymap_node }}
                };
            };
            """,
            "key_position_header": """
            // Key positions
            #define KEY_0 0
            #define KEY_1 1
            // ... more keys
            """,
        },
    }

    # Create glove80 configuration
    glove80_config = {
        "keyboard": "glove80",
        "description": "MoErgo Glove80 split ergonomic keyboard",
        "vendor": "MoErgo",
        "version": "v25.05",
        "flash": {
            "method": "mass_storage",
            "query": "vendor=Adafruit and serial~=GLV80-.* and removable=true",
            "usb_vid": 0x1209,
            "usb_pid": 0x0080,
        },
        "build": {
            "method": "docker",
            "docker_image": "moergo-zmk-build",
            "repository": "moergo-sc/zmk",
            "branch": "v25.05",
        },
        "firmwares": {
            "v25.05": {
                "description": "Stable MoErgo firmware v25.05",
                "version": "v25.05",
                "branch": "v25.05",
            },
            "v25.04-beta.1": {
                "description": "Beta MoErgo firmware v25.04-beta.1",
                "version": "v25.04-beta.1",
                "branch": "v25.04-beta.1",
            },
        },
        "templates": {
            "keymap": "// Glove80 keymap template",
        },
    }

    # Write config files
    (keyboards_dir / "test_keyboard.yaml").write_text(yaml.dump(test_keyboard_config))
    (keyboards_dir / "glove80.yaml").write_text(yaml.dump(glove80_config))

    # Return the parent directory
    return tmp_path


@pytest.fixture
def keyboard_search_path(keyboard_config_dir):
    """Return the keyboard search path for testing."""
    return str(keyboard_config_dir / "keyboards")


@pytest.fixture
def mock_integrated_keyboard_config():
    """Create a mock keyboard configuration for integration testing."""
    return {
        "keyboard": "test_keyboard",
        "description": "Test keyboard for integration testing",
        "vendor": "Test Vendor",
        "version": "v1.0.0",
        "flash": {
            "method": "mass_storage",
            "query": "vendor=Test and removable=true",
            "usb_vid": 0x1234,
            "usb_pid": 0x5678,
        },
        "build": {
            "method": "docker",
            "docker_image": "test-zmk-build",
            "repository": "test/zmk",
            "branch": "main",
        },
        "firmwares": {
            "default": {
                "description": "Default test firmware",
                "version": "v1.0.0",
                "branch": "main",
            },
            "bluetooth": {
                "description": "Bluetooth-focused test firmware",
                "version": "bluetooth",
                "branch": "bluetooth",
                "kconfig": {
                    "CONFIG_ZMK_BLE": "y",
                    "CONFIG_ZMK_USB": "n",
                },
            },
        },
        "templates": {
            "keymap_template": "#include <behaviors.dtsi>",
            "key_position_header": "// Key positions",
        },
    }


# Integrated mocks for service testing
@pytest.fixture
def integrated_mock_load_keyboard_config_raw(mock_integrated_keyboard_config):
    """Mock the load_keyboard_config_raw function for integration testing."""
    with patch("glovebox.config.keyboard_config.load_keyboard_config_raw") as mock_load:
        mock_load.return_value = mock_integrated_keyboard_config
        yield mock_load


@pytest.fixture
def integrated_mock_load_keyboard_config_typed(mock_integrated_keyboard_config):
    """Mock the load_keyboard_config_typed function for integration testing."""
    with patch(
        "glovebox.config.keyboard_config.load_keyboard_config_typed"
    ) as mock_load:
        # Convert dict to KeyboardConfig object
        from glovebox.config.models import KeyboardConfig

        mock_load.return_value = KeyboardConfig(**mock_integrated_keyboard_config)
        yield mock_load


@pytest.fixture
def integrated_mock_create_keyboard_profile(mock_integrated_keyboard_config):
    """Mock the create_keyboard_profile function for integration testing."""
    with patch(
        "glovebox.config.keyboard_config.create_keyboard_profile"
    ) as mock_create:
        # Create a mock profile
        from glovebox.config.models import FirmwareConfig, KeyboardConfig
        from glovebox.config.profile import KeyboardProfile

        keyboard_config = KeyboardConfig(**mock_integrated_keyboard_config)
        firmware_name = "default"
        firmware_config = FirmwareConfig(
            **mock_integrated_keyboard_config["firmwares"][firmware_name]
        )

        profile = KeyboardProfile(keyboard_config, firmware_name)
        profile.firmware_config = firmware_config

        mock_create.return_value = profile
        yield mock_create


@pytest.fixture
def integrated_mock_get_available_keyboards():
    """Mock the get_available_keyboards function for integration testing."""
    with patch("glovebox.config.keyboard_config.get_available_keyboards") as mock_get:
        mock_get.return_value = ["test_keyboard", "glove80"]
        yield mock_get


@pytest.fixture
def integrated_sample_keymap():
    """Sample keymap data for integration testing."""
    return {
        "keyboard": "test_keyboard",
        "firmware_api_version": "1",
        "locale": "en-US",
        "uuid": "test-uuid",
        "date": "2025-01-01T00:00:00",
        "creator": "test",
        "title": "Test Keymap",
        "notes": "Integration test keymap",
        "tags": ["test", "integration"],
        "layers": [[{"value": "&kp", "params": [{"value": "Q"}]} for _ in range(80)]],
        "layer_names": ["DEFAULT"],
        "custom_defined_behaviors": "",
        "custom_devicetree": "",
        "config_parameters": [],
        "macros": [],
        "combos": [],
        "holdTaps": [],
        "inputListeners": [],
    }


# Real integration test
@pytest.mark.integration
def test_real_keyboard_config_integration(keyboard_config_dir):
    """Test real integration with keyboard config files."""
    # Set environment variable to point to our test directory
    with patch.dict(os.environ, {"GLOVEBOX_KEYBOARD_PATH": str(keyboard_config_dir)}):
        # Test that our test keyboards are found
        keyboards = get_available_keyboards()
        # Check for at least glove80 since it should always be present
        assert "glove80" in keyboards

        # Test loading the glove80 keyboard configuration
        config_raw = load_keyboard_config_raw("glove80")
        assert config_raw["keyboard"] == "glove80"
        assert "description" in config_raw

        # Test loading glove80 as typed object
        config_typed = load_keyboard_config_typed("glove80")
        assert isinstance(config_typed, KeyboardConfig)
        assert config_typed.keyboard == "glove80"
        assert hasattr(config_typed, "description")

        # Test creating a profile
        profile = create_keyboard_profile("glove80", "v25.05")
        assert isinstance(profile, KeyboardProfile)
        assert profile.keyboard_name == "glove80"
        assert profile.firmware_version == "v25.05"

        # Test getting firmwares
        glove_config = load_keyboard_config_typed("glove80")
        firmwares = glove_config.firmwares
        assert "v25.05" in firmwares
        assert "v25.04-beta.1" in firmwares
