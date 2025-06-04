import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from glovebox.adapters.file_adapter import FileAdapter


@pytest.fixture
def mock_file_adapter():
    """Create a mock file adapter for testing."""
    adapter = Mock(spec=FileAdapter)
    return adapter


@pytest.fixture
def mock_keyboard_config():
    """Create a mock keyboard configuration for testing."""
    return {
        "keyboard": "test_keyboard",
        "description": "Mock keyboard for testing",
        "vendor": "Test Vendor",
        "key_count": 80,
        "flash": {
            "method": "mass_storage",
            "query": "vendor=Test and removable=true",
            "usb_vid": "0x1234",
            "usb_pid": "0x5678",
        },
        "build": {
            "method": "docker",
            "docker_image": "test-zmk-build",
            "repository": "test/zmk",
            "branch": "main",
        },
        "visual_layout": {"rows": [[0, 1, 2, 3, 4]]},
        "formatting": {"default_key_width": 8, "key_gap": "  ", "base_indent": ""},
        "firmwares": {
            "default": {
                "description": "Default test firmware",
                "version": "v1.0.0",
                "build_options": {"repository": "test/zmk", "branch": "main"},
            },
            "bluetooth": {
                "description": "Bluetooth-focused test firmware",
                "version": "v2.0.0",
                "build_options": {"repository": "test/zmk", "branch": "bluetooth"},
            },
            "v25.05": {
                "description": "Bluetooth-focused test firmware",
                "version": "v25.05",
                "build_options": {"repository": "test/zmk", "branch": "v25.05"},
                "kconfig": {
                    "CONFIG_ZMK_BLE": {
                        "name": "CONFIG_ZMK_BLE",
                        "type": "bool",
                        "default": True,
                        "description": "Enable BLE",
                    },
                    "CONFIG_ZMK_USB": {
                        "name": "CONFIG_ZMK_USB",
                        "type": "bool",
                        "default": False,
                        "description": "Disable USB",
                    },
                },
            },
        },
        "keymap": {
            "includes": ["<dt-bindings/zmk/keys.h>"],
            "system_behaviors": [],
            "kconfig_options": {},
            "keymap_dtsi": "#include <behaviors.dtsi>",
            "system_behaviors_dts": "test behaviors",
            "key_position_header": "test header",
        },
    }


@pytest.fixture
def mock_firmware_config():
    """Create a mock firmware configuration for testing."""
    return {
        "description": "Default test firmware",
        "version": "v1.0.0",
        "branch": "main",
    }


@pytest.fixture
def mock_load_keyboard_config(mock_keyboard_config):
    """Mock the load_keyboard_config function."""
    with patch("glovebox.config.keyboard_config.load_keyboard_config") as mock_load:
        mock_load.return_value = mock_keyboard_config
        yield mock_load


@pytest.fixture
def mock_get_available_keyboards():
    """Mock the get_available_keyboards function."""
    with patch("glovebox.config.keyboard_config.get_available_keyboards") as mock_get:
        mock_get.return_value = ["test_keyboard", "glove80", "corne"]
        yield mock_get


@pytest.fixture
def mock_get_firmware_config(mock_firmware_config):
    """Mock the get_firmware_config function."""
    with patch("glovebox.config.keyboard_config.get_firmware_config") as mock_get:
        mock_get.return_value = mock_firmware_config
        yield mock_get


@pytest.fixture
def mock_get_available_firmwares():
    """Mock the get_available_firmwares function."""
    with patch("glovebox.config.keyboard_config.get_available_firmwares") as mock_get:
        mock_get.return_value = ["default", "bluetooth", "v25.05"]
        yield mock_get


@pytest.fixture
def mock_keyboard_config_service(mock_keyboard_config, mock_firmware_config):
    """Mock the KeyboardConfigService class."""
    with patch("glovebox.config.keyboard_config.KeyboardConfigService") as mock_cls:
        mock_service = MagicMock()
        mock_service.load_keyboard_config.return_value = mock_keyboard_config
        mock_service.get_available_keyboards.return_value = [
            "test_keyboard",
            "glove80",
            "corne",
        ]
        mock_service.get_firmware_config.return_value = mock_firmware_config
        mock_service.get_available_firmwares.return_value = [
            "default",
            "bluetooth",
            "v25.05",
        ]

        mock_cls.return_value = mock_service
        yield mock_service
