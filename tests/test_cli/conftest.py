"""Test fixtures for CLI tests."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from glovebox.cli import app
from glovebox.config.keyboard_config import KeyboardConfig
from glovebox.models.results import BuildResult, FlashResult, KeymapResult


@pytest.fixture
def cli_runner():
    """Return a Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_keymap_service():
    """Mock KeymapService."""
    mock = Mock()

    # Mock successful compile result
    result = KeymapResult(success=True)
    result.keymap_path = Path("/tmp/output/keymap.keymap")
    result.conf_path = Path("/tmp/output/keymap.conf")
    mock.compile.return_value = result

    # Mock successful split result
    split_result = KeymapResult(success=True)
    mock.split.return_value = split_result

    # Mock successful merge result
    merge_result = KeymapResult(success=True)
    mock.merge.return_value = merge_result

    # Mock show result
    mock.show.return_value = ["Layer 1", "Layer 2"]

    # Mock validation result
    mock.validate.return_value = True

    return mock


@pytest.fixture
def mock_build_service():
    """Mock BuildService."""
    mock = Mock()

    # Mock successful compile result
    result = BuildResult(
        success=True,
        messages=["Firmware built successfully", "Output: /tmp/output/glove80.uf2"],
    )
    result.firmware_path = Path("/tmp/output/glove80.uf2")
    mock.compile.return_value = result

    return mock


@pytest.fixture
def mock_flash_service():
    """Mock FlashService."""
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


@pytest.fixture
def mock_keyboard_config():
    """Mock KeyboardConfig."""
    # Since KeyboardConfig is a TypeAlias (dict[str, Any]), we'll create a dictionary with the expected keys
    mock = {
        "keyboard": "test_keyboard",
        "keyboard_type": "glove80",
        "version": "v25.05",
        "description": "Test Keyboard Configuration",
        "templates": {
            "keymap": "/tmp/templates/keymap.j2",
            "kconfig": "/tmp/templates/kconfig.j2",
        },
        "build": {
            "container": "zmk-docker",
            "builder": "zmk-builder",
            "keyboard": "glove80",
        },
        "firmwares": {
            "default": {
                "branch": "main",
                "container": "zmk-docker",
                "builder": "zmk-builder",
            }
        },
    }
    return mock


@pytest.fixture
def sample_keymap_json(tmp_path):
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
def sample_keymap_dtsi(tmp_path):
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
def sample_config_file(tmp_path):
    """Create a sample config file."""
    content = """
    CONFIG_ZMK_KEYBOARD_NAME="Test Keyboard"
    CONFIG_BT_CTLR_TX_PWR_PLUS_8=y
    """

    config_file = tmp_path / "test_config.conf"
    config_file.write_text(content)

    return config_file


@pytest.fixture
def sample_firmware_file(tmp_path):
    """Create a sample firmware file."""
    content = "FIRMWARE_BINARY_DATA"

    firmware_file = tmp_path / "test_firmware.uf2"
    firmware_file.write_text(content)

    return firmware_file
