"""Core test fixtures for the glovebox project."""

import json
import os
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from typer.testing import CliRunner

from glovebox.config.models import (
    BuildConfig,
    BuildOptions,
    FirmwareConfig,
    FlashConfig,
    FormattingConfig,
    KConfigOption,
    KeyboardConfig,
    KeymapSection,
)
from glovebox.config.profile import KeyboardProfile
from glovebox.models import SystemBehavior
from glovebox.models.build import FirmwareOutputFiles
from glovebox.models.results import BuildResult, FlashResult, KeymapResult
from glovebox.protocols import FileAdapterProtocol, TemplateAdapterProtocol


# ---- Base Fixtures ----


@pytest.fixture
def cli_runner() -> CliRunner:
    """Return a Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_file_adapter() -> Mock:
    """Create a mock file adapter for testing."""
    adapter = Mock(spec=FileAdapterProtocol)
    return adapter


@pytest.fixture
def mock_template_adapter() -> Mock:
    """Create a mock template adapter for testing."""
    adapter = Mock(spec=TemplateAdapterProtocol)
    return adapter


# ---- Configuration Fixtures ----


@pytest.fixture
def mock_keyboard_config_dict() -> dict[str, Any]:
    """Create a mock keyboard configuration dictionary for testing."""
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
            "formatting": {"default_key_width": 8, "key_gap": "  ", "base_indent": ""},
        },
    }


@pytest.fixture
def mock_firmware_config_dict() -> dict[str, Any]:
    """Create a mock firmware configuration dictionary for testing."""
    return {
        "description": "Default test firmware",
        "version": "v1.0.0",
        "build_options": {"repository": "test/zmk", "branch": "main"},
    }


@pytest.fixture
def mock_keyboard_config() -> Mock:
    """Create a mocked KeyboardConfig instance to avoid initialization issues."""
    mock_config = Mock(spec=KeyboardConfig)

    # Set attributes that tests will access
    mock_config.keyboard = "test_keyboard"
    mock_config.description = "Mock keyboard for testing"
    mock_config.vendor = "Test Vendor"
    mock_config.key_count = 80

    # Create mock flash config
    mock_config.flash = Mock(spec=FlashConfig)
    mock_config.flash.method = "mass_storage"
    mock_config.flash.query = "vendor=Test and removable=true"
    mock_config.flash.usb_vid = "0x1234"
    mock_config.flash.usb_pid = "0x5678"

    # Create mock build config
    mock_config.build = Mock(spec=BuildConfig)
    mock_config.build.method = "docker"
    mock_config.build.docker_image = "test-zmk-build"
    mock_config.build.repository = "test/zmk"
    mock_config.build.branch = "main"

    # Create mock firmwares
    mock_config.firmwares = {
        "default": Mock(spec=FirmwareConfig),
        "bluetooth": Mock(spec=FirmwareConfig),
        "v25.05": Mock(spec=FirmwareConfig),
    }

    # Set up firmware attributes
    for name, firmware in mock_config.firmwares.items():
        firmware.version = (
            "v1.0.0"
            if name == "default"
            else ("v2.0.0" if name == "bluetooth" else "v25.05")
        )
        firmware.description = f"{name.capitalize()} test firmware"

        # Create mock build options
        firmware.build_options = Mock(spec=BuildOptions)
        firmware.build_options.repository = "test/zmk"
        firmware.build_options.branch = name if name != "default" else "main"

    # Create mock keymap config
    mock_config.keymap = Mock(spec=KeymapSection)
    mock_config.keymap.includes = ["<dt-bindings/zmk/keys.h>"]
    mock_config.keymap.system_behaviors = []
    mock_config.keymap.kconfig_options = {}
    mock_config.keymap.keymap_dtsi = "#include <behaviors.dtsi>"
    mock_config.keymap.system_behaviors_dts = "test behaviors"
    mock_config.keymap.key_position_header = "test header"

    # Create mock formatting
    mock_config.keymap.formatting = Mock(spec=FormattingConfig)
    mock_config.keymap.formatting.default_key_width = 8
    mock_config.keymap.formatting.key_gap = "  "
    mock_config.keymap.formatting.base_indent = ""

    return mock_config


@pytest.fixture
def mock_firmware_config() -> Mock:
    """Create a mocked FirmwareConfig instance."""
    mock_config = Mock(spec=FirmwareConfig)
    mock_config.version = "v1.0.0"
    mock_config.description = "Default test firmware"

    # Create mock build options
    mock_config.build_options = Mock(spec=BuildOptions)
    mock_config.build_options.repository = "test/zmk"
    mock_config.build_options.branch = "main"

    # Kconfig is None by default
    mock_config.kconfig = None

    return mock_config


@pytest.fixture
def mock_keyboard_profile() -> Mock:
    """Create a mocked KeyboardProfile."""
    mock_profile = Mock(spec=KeyboardProfile)
    mock_profile.keyboard_name = "test_keyboard"
    mock_profile.firmware_version = "default"

    # Set up properties that use the above mocks
    mock_profile.keyboard_config = Mock(spec=KeyboardConfig)
    mock_profile.firmware_config = Mock(spec=FirmwareConfig)

    return mock_profile


@pytest.fixture
def mock_load_keyboard_config(mock_keyboard_config) -> Generator[Mock, None, None]:
    """Mock the load_keyboard_config function."""
    with patch("glovebox.config.keyboard_config.load_keyboard_config") as mock_load:
        mock_load.return_value = mock_keyboard_config
        yield mock_load


@pytest.fixture
def mock_get_available_keyboards() -> Generator[Mock, None, None]:
    """Mock the get_available_keyboards function."""
    with patch("glovebox.config.keyboard_config.get_available_keyboards") as mock_get:
        mock_get.return_value = ["test_keyboard", "glove80", "corne"]
        yield mock_get


@pytest.fixture
def mock_get_firmware_config(mock_firmware_config) -> Generator[Mock, None, None]:
    """Mock the get_firmware_config function."""
    with patch("glovebox.config.keyboard_config.get_firmware_config") as mock_get:
        mock_get.return_value = mock_firmware_config
        yield mock_get


@pytest.fixture
def mock_get_available_firmwares() -> Generator[Mock, None, None]:
    """Mock the get_available_firmwares function."""
    with patch("glovebox.config.keyboard_config.get_available_firmwares") as mock_get:
        mock_get.return_value = ["default", "bluetooth", "v25.05"]
        yield mock_get


@pytest.fixture
def mock_create_keyboard_profile(mock_keyboard_profile) -> Generator[Mock, None, None]:
    """Mock the create_keyboard_profile function."""
    with patch(
        "glovebox.config.keyboard_config.create_keyboard_profile"
    ) as mock_create:
        mock_create.return_value = mock_keyboard_profile
        yield mock_create


@pytest.fixture
def mock_keymap_service() -> Mock:
    """Mock KeymapService with common behaviors."""
    mock = Mock()

    # Mock successful compile result
    result = KeymapResult(success=True)
    result.keymap_path = Path("/tmp/output/keymap.keymap")
    result.conf_path = Path("/tmp/output/keymap.conf")
    mock.compile.return_value = result

    # Mock successful split result
    split_result = KeymapResult(success=True)
    mock.split_keymap.return_value = split_result

    # Mock successful merge result
    merge_result = KeymapResult(success=True)
    mock.merge_layers.return_value = merge_result

    # Mock show result
    mock.show.return_value = ["Layer 1", "Layer 2"]

    # Mock validation result
    mock.validate.return_value = True

    return mock


@pytest.fixture
def mock_build_service() -> Mock:
    """Mock BuildService with common behaviors."""
    mock = Mock()

    # Create a mock FirmwareOutputFiles for the result

    output_files = FirmwareOutputFiles(
        main_uf2=Path("/tmp/output/glove80.uf2"), output_dir=Path("/tmp/output")
    )

    # Mock successful compile result
    result = BuildResult(
        success=True,
        messages=["Firmware built successfully", "Output: /tmp/output/glove80.uf2"],
        output_files=output_files,
    )
    mock.compile.return_value = result

    # Also set the compile_from_files method to return the same result
    mock.compile_from_files.return_value = result

    return mock


@pytest.fixture
def mock_flash_service() -> Mock:
    """Mock FlashService with common behaviors."""
    mock = Mock()

    # Mock successful flash result
    result = FlashResult(
        success=True,
        devices_flashed=2,
        devices_failed=0,
        device_details=[
            {"name": "Device 1", "status": "success"},
            {"name": "Device 2", "status": "success"},
        ],
    )
    mock.flash.return_value = result

    return mock


# ---- Sample Data Fixtures ----


@pytest.fixture
def sample_keymap_json() -> dict[str, Any]:
    """Sample keymap JSON data for testing.

    This is the consolidated fixture used by all tests.
    """
    return {
        "keyboard": "test_keyboard",
        "firmware_api_version": "1",
        "locale": "en-US",
        "uuid": "test-uuid",
        "date": "2025-01-01T00:00:00",
        "creator": "test",
        "title": "Test Keymap",
        "notes": "Test keymap for unit tests",
        "tags": ["test", "unit"],
        "layers": [[{"value": "&kp", "params": [{"value": "Q"}]} for _ in range(80)]],
        "layer_names": ["DEFAULT"],
        "custom_defined_behaviors": "",
        "custom_devicetree": "",
        "config_parameters": [
            {
                "paramName": "CONFIG_ZMK_KEYBOARD_NAME",
                "value": "Test Keyboard",
                "description": "Keyboard name",
            }
        ],
        "macros": [],
        "combos": [],
        "holdTaps": [],
        "inputListeners": [],
    }


@pytest.fixture
def sample_keymap_json_file(tmp_path: Path) -> Path:
    """Create a sample keymap JSON file."""
    keymap_data = {
        "version": 1,
        "notes": "Test keymap",
        "keyboard": "glove80",
        "title": "Test Keymap",
        "layer_names": ["QWERTY"],
        "layers": [
            {
                "name": "QWERTY",
                "layout": [
                    {"key": "Q"},
                    {"key": "W"},
                    {"key": "E"},
                    {"key": "R"},
                    {"key": "T"},
                    {"key": "Y"},
                    {"key": "U"},
                    {"key": "I"},
                    {"key": "O"},
                    {"key": "P"},
                ],
            }
        ],
    }

    keymap_file = tmp_path / "test_keymap.json"
    keymap_file.write_text(json.dumps(keymap_data))

    return keymap_file


@pytest.fixture
def sample_keymap_dtsi(tmp_path: Path) -> Path:
    """Create a sample keymap dtsi file."""
    content = """
    / {
        keymap {
            compatible = "zmk,keymap";
            qwerty_layer {
                bindings = <
                    &kp Q &kp W &kp E &kp R &kp T
                    &kp Y &kp U &kp I &kp O &kp P
                >;
            };
        };
    };
    """

    keymap_file = tmp_path / "test_keymap.keymap"
    keymap_file.write_text(content)

    return keymap_file


@pytest.fixture
def sample_config_file(tmp_path: Path) -> Path:
    """Create a sample config file."""
    content = """
    CONFIG_ZMK_KEYBOARD_NAME="Test Keyboard"
    CONFIG_BT_CTLR_TX_PWR_PLUS_8=y
    """

    config_file = tmp_path / "test_config.conf"
    config_file.write_text(content)

    return config_file


@pytest.fixture
def sample_firmware_file(tmp_path: Path) -> Path:
    """Create a sample firmware file."""
    content = "FIRMWARE_BINARY_DATA"

    firmware_file = tmp_path / "test_firmware.uf2"
    firmware_file.write_text(content)

    return firmware_file
