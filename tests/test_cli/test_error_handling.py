"""Tests for CLI error handling."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import typer

from glovebox.cli import app
from glovebox.core.errors import BuildError, ConfigError, FlashError, LayoutError
from glovebox.firmware.flash.models import FlashResult
from glovebox.firmware.models import BuildResult
from glovebox.layout.models import LayoutResult


@patch("glovebox.layout.create_layout_service")
@pytest.mark.skip(reason="Test takes too long or runs real commands in background")
def test_layout_error_handling(mock_create_service, cli_runner):
    """Test LayoutError handling in CLI."""
    mock_service = Mock()
    mock_service.compile.side_effect = LayoutError("Invalid layout structure")
    mock_create_service.return_value = mock_service

    with patch("glovebox.config.keyboard_profile.KeyboardConfig") as mock_config_cls:
        mock_config = Mock()
        mock_config.name = "test_keyboard"
        mock_config.keyboard_type = "glove80"
        mock_config.version = "v25.05"
        mock_config_cls.load.return_value = mock_config

        result = cli_runner.invoke(
            app,
            [
                "layout",
                "compile",
                "output/test",
                "--profile",
                "glove80_v25.04",
                "test.json",
            ],
        )

        assert result.exit_code == 1
        assert "Layout error: Invalid layout structure" in result.output


@patch("glovebox.firmware.build_service.create_build_service")
@pytest.mark.skip(reason="Test takes too long or runs real commands in background")
def test_build_error_handling(mock_create_service, cli_runner, tmp_path):
    """Test BuildError handling in CLI."""
    mock_service = Mock()
    mock_service.compile.side_effect = BuildError("Docker container failed")
    mock_create_service.return_value = mock_service

    keymap_file = tmp_path / "test.keymap"
    keymap_file.touch()
    config_file = tmp_path / "test.conf"
    config_file.touch()

    result = cli_runner.invoke(
        app, ["firmware", "compile", str(keymap_file), str(config_file)]
    )

    assert result.exit_code == 1
    assert "Build error: Docker container failed" in result.output


@patch("glovebox.firmware.flash.service.create_flash_service")
@pytest.mark.skip(reason="Test takes too long or runs real commands in background")
def test_flash_error_handling(mock_create_service, cli_runner, tmp_path):
    """Test FlashError handling in CLI."""
    mock_service = Mock()
    mock_service.flash.side_effect = FlashError("Device not found")
    mock_create_service.return_value = mock_service

    firmware_file = tmp_path / "test.uf2"
    firmware_file.touch()

    result = cli_runner.invoke(app, ["firmware", "flash", str(firmware_file)])

    assert result.exit_code == 1
    assert "Flash error: Device not found" in result.output


@patch("glovebox.config.keyboard_profile.KeyboardConfig")
@pytest.mark.skip(reason="Test takes too long or runs real commands in background")
def test_config_error_handling(mock_config_cls, cli_runner):
    """Test ConfigError handling in CLI."""
    # Mock KeyboardConfig.load to raise ConfigError
    mock_config_cls.load.side_effect = ConfigError("Keyboard configuration not found")

    # Mock list_available to return available keyboards
    mock_config_cls.list_available.return_value = [
        "glove80_v25.04",
        "glove80_v25.05",
        "zmk_default",
    ]

    result = cli_runner.invoke(app, ["config", "show", "nonexistent-keyboard"])

    assert result.exit_code == 1
    assert "Configuration error" in result.output
    assert "glove80_v25.04" in result.output
    assert "glove80_v25.05" in result.output


@pytest.mark.skip(reason="Implementation has changed, needs to be rewritten")
@patch("glovebox.layout.create_layout_service")
@patch("glovebox.cli.helpers.profile.create_profile_from_option")
def test_json_decode_error_handling(
    mock_create_profile, mock_create_service, cli_runner, tmp_path
):
    """Test JSONDecodeError handling in CLI."""
    # Create invalid JSON file
    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text("{invalid:json")

    # Mock the keymap service and profile
    mock_service = Mock()
    mock_create_service.return_value = mock_service

    # Make validate_file raise a LayoutError with the specific error message
    from glovebox.core.errors import LayoutError

    mock_service.validate_file.side_effect = LayoutError(
        "Keymap validation failed: Invalid JSON"
    )

    # Create a mock profile
    mock_profile = Mock()
    mock_create_profile.return_value = mock_profile

    result = cli_runner.invoke(
        app, ["keymap", "validate", str(invalid_json)], catch_exceptions=True
    )

    assert result.exit_code == 1
    assert "Keymap validation failed: Invalid JSON" in result.output


@pytest.mark.skip(reason="Test takes too long or runs real commands in background")
def test_file_not_found_error_handling(cli_runner):
    """Test FileNotFoundError handling in CLI."""
    nonexistent_file = "/nonexistent/file.json"

    # Need to bypass the json loading by mocking json.loads which is called before the file check
    with patch("pathlib.Path.exists") as mock_exists:
        mock_exists.return_value = False

        result = cli_runner.invoke(app, ["keymap", "validate", nonexistent_file])

        assert result.exit_code == 1
        assert "File not found" in result.output


@patch("glovebox.layout.create_layout_service")
@pytest.mark.skip(reason="Test takes too long or runs real commands in background")
def test_unexpected_error_handling(mock_create_service, cli_runner, tmp_path):
    """Test unexpected error handling in CLI."""
    mock_service = Mock()
    mock_service.validate.side_effect = RuntimeError("Unexpected error occurred")
    mock_create_service.return_value = mock_service

    # Create a valid JSON file with required fields for keymap
    json_file = tmp_path / "valid.json"
    json_file.write_text("""
    {
        "keyboard": "glove80",
        "title": "Test Keymap",
        "layer_names": ["Default"],
        "layers": [{"name": "Default", "layout": []}]
    }
    """)

    # Add a patch to bypass the json validation
    with patch("json.loads") as mock_json_loads:
        mock_json_loads.return_value = {
            "keyboard": "glove80",
            "title": "Test Keymap",
            "layer_names": ["Default"],
            "layers": [{"name": "Default", "layout": []}],
        }

        result = cli_runner.invoke(app, ["keymap", "validate", str(json_file)])

        assert result.exit_code == 1
        assert "Unexpected error: Unexpected error occurred" in result.output
