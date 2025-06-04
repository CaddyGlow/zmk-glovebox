"""Test fixtures for the new typed configuration system."""

from unittest.mock import MagicMock, patch

import pytest

from glovebox.config.models import FirmwareConfig, KeyboardConfig, SystemBehavior
from glovebox.config.profile import KeyboardProfile


@pytest.fixture
def mock_keyboard_config_typed(mock_keyboard_config):
    """Create a mock typed keyboard configuration for testing."""
    # Start with a copy of the raw config
    config_dict = mock_keyboard_config.copy()

    # Add required fields that might be missing
    if "key_count" not in config_dict:
        config_dict["key_count"] = 80

    if "visual_layout" not in config_dict:
        config_dict["visual_layout"] = {"rows": [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9]]}

    if "formatting" not in config_dict:
        config_dict["formatting"] = {
            "default_key_width": 8,
            "key_gap": "  ",
            "base_indent": "    ",
        }

    if "keymap" not in config_dict:
        config_dict["keymap"] = {
            "includes": ["#include <dt-bindings/zmk/keys.h>"],
            "system_behaviors": [
                {
                    "code": "&kp",
                    "name": "&kp",
                    "description": "Key press behavior",
                    "expected_params": 1,
                    "origin": "zmk",
                    "params": [],
                }
            ],
        }

    # Convert raw values to proper formats
    if "flash" in config_dict:
        flash = config_dict["flash"]
        if "usb_vid" in flash and isinstance(flash["usb_vid"], int):
            flash["usb_vid"] = f"0x{flash['usb_vid']:04x}"
        if "usb_pid" in flash and isinstance(flash["usb_pid"], int):
            flash["usb_pid"] = f"0x{flash['usb_pid']:04x}"

    # Create a typed KeyboardConfig instance
    return KeyboardConfig(**config_dict)


@pytest.fixture
def mock_firmware_config_typed(mock_firmware_config):
    """Create a mock typed firmware configuration for testing."""
    # Start with a copy of the raw config
    config_dict = mock_firmware_config.copy()

    # Add required fields that might be missing
    if "build_options" not in config_dict:
        config_dict["build_options"] = {"repository": "test/zmk", "branch": "main"}

    # Create a typed FirmwareConfig instance
    return FirmwareConfig(**config_dict)


@pytest.fixture
def mock_keyboard_profile(mock_keyboard_config_typed, mock_firmware_config_typed):
    """Create a mock KeyboardProfile for testing."""
    profile = KeyboardProfile(mock_keyboard_config_typed, "default")
    profile.firmware_config = mock_firmware_config_typed
    return profile


@pytest.fixture
def mock_load_keyboard_config_raw(mock_keyboard_config):
    """Mock the load_keyboard_config_raw function."""
    with patch("glovebox.config.keyboard_config.load_keyboard_config_raw") as mock_load:
        mock_load.return_value = mock_keyboard_config
        yield mock_load


@pytest.fixture
def mock_load_keyboard_config_typed(mock_keyboard_config_typed):
    """Mock the load_keyboard_config_typed function."""
    with patch(
        "glovebox.config.keyboard_config.load_keyboard_config_typed"
    ) as mock_load:
        mock_load.return_value = mock_keyboard_config_typed
        yield mock_load


@pytest.fixture
def mock_get_firmware_config_typed(mock_firmware_config_typed):
    """Mock the get_firmware_config_typed function."""
    with patch("glovebox.config.keyboard_config.get_firmware_config_typed") as mock_get:
        mock_get.return_value = mock_firmware_config_typed
        yield mock_get


@pytest.fixture
def mock_create_keyboard_profile(mock_keyboard_profile):
    """Mock the create_keyboard_profile function."""
    with patch(
        "glovebox.config.keyboard_config.create_keyboard_profile"
    ) as mock_create:
        mock_create.return_value = mock_keyboard_profile
        yield mock_create


# Also create mock fixtures for the legacy API for backward compatibility
@pytest.fixture
def mock_load_keyboard_config(mock_keyboard_config):
    """Mock the load_keyboard_config function (legacy)."""
    with patch("glovebox.config.keyboard_config.load_keyboard_config_raw") as mock_load:
        mock_load.return_value = mock_keyboard_config
        yield mock_load


@pytest.fixture
def mock_get_firmware_config(mock_firmware_config):
    """Mock the get_firmware_config function (legacy)."""
    with patch("glovebox.config.keyboard_config.get_firmware_config_typed") as mock_get:
        mock_get.return_value = mock_firmware_config
        yield mock_get
