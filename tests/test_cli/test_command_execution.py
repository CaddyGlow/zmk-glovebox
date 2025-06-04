"""Tests for CLI command execution."""

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import typer

from glovebox.cli import app
from glovebox.models.results import BuildResult, FlashResult, KeymapResult
from glovebox.services.build_service import create_build_service
from glovebox.services.flash_service import create_flash_service
from glovebox.services.keymap_service import create_keymap_service


@patch("glovebox.cli.create_keymap_service")
@patch("glovebox.cli.Path")
@patch("glovebox.config.keyboard_config.create_keyboard_profile")
def test_keymap_compile_command(
    mock_create_keyboard_profile,
    mock_path_cls,
    mock_create_service,
    cli_runner,
    mock_keymap_service,
    mock_keyboard_config,
    sample_keymap_json,
):
    """Test keymap compile command with KeyboardProfile."""
    # Setup path mock
    mock_path_instance = Mock()
    mock_path_instance.exists.return_value = True
    mock_path_instance.read_text.return_value = "{}"
    mock_path_cls.return_value = mock_path_instance

    # Setup keymap service mock
    mock_create_service.return_value = mock_keymap_service

    # Ensure the service returns a successful result
    from glovebox.models.results import KeymapResult

    success_result = KeymapResult(success=True)
    success_result.keymap_path = Path("/tmp/output/keymap.keymap")
    success_result.conf_path = Path("/tmp/output/keymap.conf")
    mock_keymap_service.compile.return_value = success_result

    # Create a mock KeyboardProfile
    mock_keyboard_profile = Mock()
    mock_keyboard_profile.keyboard_name = "glove80"
    mock_keyboard_profile.firmware_version = "v25.05"
    mock_create_keyboard_profile.return_value = mock_keyboard_profile

    # Run the command
    result = cli_runner.invoke(
        app,
        [
            "keymap",
            "compile",
            "output/test",
            "--profile",
            "glove80/v25.05",
            str(sample_keymap_json),
        ],
        catch_exceptions=False,
    )

    print(f"Test result output: {result.output}")
    print(f"Exit code: {result.exit_code}")
    print(f"Exception: {getattr(result, 'exception', None)}")

    assert result.exit_code == 0
    assert "Keymap compiled successfully" in result.output

    # Verify service was called with correct args
    mock_keymap_service.compile.assert_called_once()

    # Verify the KeyboardProfile was created correctly
    mock_create_keyboard_profile.assert_called_once_with("glove80", "v25.05")

    # Verify the service was called with the profile
    call_args = mock_keymap_service.compile.call_args
    assert call_args is not None
    args, kwargs = call_args
    assert kwargs.get("profile") == mock_keyboard_profile


@patch("glovebox.cli.create_keymap_service")
@patch("glovebox.cli.Path")
@patch("glovebox.config.keyboard_config.load_keyboard_config_raw")
def test_keymap_compile_failure(
    mock_load_config,
    mock_path_cls,
    mock_create_service,
    cli_runner,
    mock_keymap_service,
):
    """Test keymap compile command failure handling."""
    # Setup path mock
    mock_path_instance = Mock()
    mock_path_instance.exists.return_value = True
    mock_path_instance.read_text.return_value = "{}"
    mock_path_cls.return_value = mock_path_instance

    # Setup keymap service mock
    mock_create_service.return_value = mock_keymap_service

    # Configure mock to return failure result
    failed_result = KeymapResult(success=False)
    failed_result.errors.append("Invalid keymap structure")
    mock_keymap_service.compile.return_value = failed_result

    # Setup config mock
    mock_config = {
        "keyboard": "glove80",
        "description": "Test Keyboard Configuration",
        "vendor": "MoErgo",
        "key_count": 80,
        "flash": {
            "method": "mass_storage",
            "query": "vendor=Adafruit and serial~=GLV80-.* and removable=true",
            "usb_vid": "0x1209",
            "usb_pid": "0x0080",
        },
        "build": {
            "method": "docker",
            "docker_image": "moergo-zmk-build",
            "repository": "moergo-sc/zmk",
            "branch": "v25.05",
        },
        "visual_layout": {"rows": [[0, 1, 2, 3, 4]]},
        "formatting": {"default_key_width": 8, "key_gap": "  ", "base_indent": ""},
        "firmwares": {
            "v25.05": {
                "version": "v25.05",
                "description": "Default firmware",
                "build_options": {"repository": "moergo-sc/zmk", "branch": "v25.05"},
            }
        },
        "keymap": {
            "includes": ["<dt-bindings/zmk/keys.h>"],
            "system_behaviors": [],
            "kconfig_options": {},
            "keymap_dtsi": "test template",
            "system_behaviors_dts": "test behaviors",
            "key_position_header": "test header",
        },
    }
    mock_load_config.return_value = mock_config

    result = cli_runner.invoke(
        app,
        [
            "keymap",
            "compile",
            "output/test",
            "--profile",
            "glove80/v25.05",
            "test.json",
        ],
        catch_exceptions=False,
    )

    print(f"Failure test output: {result.output}")
    assert result.exit_code == 1
    assert "Keymap compilation failed" in result.output
    assert "Invalid keymap structure" in result.output


@patch("glovebox.cli.create_keymap_service")
@patch("glovebox.cli.Path")
def test_keymap_split_command(
    mock_path_cls,
    mock_create_service,
    cli_runner,
    mock_keymap_service,
    sample_keymap_json,
    tmp_path,
):
    """Test keymap split command."""
    # Setup path mocks
    mock_create_service.return_value = mock_keymap_service

    # Use actual paths for clarity
    output_dir = tmp_path / "split_output"
    output_dir.mkdir()

    # Setup successful result
    split_result = KeymapResult(success=True)
    mock_keymap_service.split.return_value = split_result

    result = cli_runner.invoke(
        app,
        ["keymap", "split", str(sample_keymap_json), str(output_dir)],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "Keymap split into layers" in result.output

    # Verify service was called
    mock_keymap_service.split.assert_called_once()


@patch("glovebox.cli.create_keymap_service")
@patch("glovebox.cli.Path")
def test_keymap_merge_command(
    mock_path_cls, mock_create_service, cli_runner, mock_keymap_service, tmp_path
):
    """Test keymap merge command."""
    # Setup mocks
    mock_create_service.return_value = mock_keymap_service

    # Setup successful result
    merge_result = KeymapResult(success=True)
    mock_keymap_service.merge.return_value = merge_result

    # Use actual paths for clarity
    input_dir = tmp_path / "merge_input"
    input_dir.mkdir()
    output_file = tmp_path / "merged.json"

    result = cli_runner.invoke(
        app,
        ["keymap", "merge", str(input_dir), "--output", str(output_file)],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "Keymap merged and saved" in result.output

    # Verify service was called
    mock_keymap_service.merge.assert_called_once()


@patch("glovebox.cli.create_keymap_service")
@patch("glovebox.cli.Path")
@patch("glovebox.cli.json.loads")
def test_keymap_show_command(
    mock_json_loads,
    mock_path_cls,
    mock_create_service,
    cli_runner,
    mock_keymap_service,
    sample_keymap_json,
):
    """Test keymap show command (using traditional show method)."""
    # Setup mocks
    mock_create_service.return_value = mock_keymap_service
    mock_path_instance = Mock()
    mock_path_instance.exists.return_value = True
    mock_path_instance.read_text.return_value = "{}"
    mock_path_cls.return_value = mock_path_instance

    # Return valid JSON
    mock_json_loads.return_value = {"valid": "data"}

    # Configure mock to return specific layout lines
    mock_keymap_service.show.return_value = [
        "Layer: QWERTY",
        "+-----+-----+-----+-----+-----+",
        "| Q   | W   | E   | R   | T   |",
        "| Y   | U   | I   | O   | P   |",
        "+-----+-----+-----+-----+-----+",
    ]

    result = cli_runner.invoke(
        app, ["keymap", "show", str(sample_keymap_json)], catch_exceptions=False
    )

    assert result.exit_code == 0
    assert "Layer: QWERTY" in result.output
    assert "| Q   | W   | E   | R   | T   |" in result.output

    # Verify service was called
    mock_keymap_service.show.assert_called_once()


@patch("glovebox.cli.create_display_service")
@patch("glovebox.cli.create_keymap_service")
@patch("glovebox.cli.Path")
@patch("glovebox.cli.json.loads")
@patch("glovebox.config.keyboard_config.create_keyboard_profile")
def test_keymap_show_command_with_profile(
    mock_create_keyboard_profile,
    mock_json_loads,
    mock_path_cls,
    mock_create_keymap,
    mock_create_display,
    cli_runner,
    mock_keymap_service,
    sample_keymap_json,
):
    """Test keymap show command with KeyboardProfile."""
    # Setup mocks
    mock_path_instance = Mock()
    mock_path_instance.exists.return_value = True
    mock_path_instance.read_text.return_value = "{}"
    mock_path_cls.return_value = mock_path_instance

    # Return valid JSON
    mock_json_loads.return_value = {"keyboard": "glove80", "valid": "data"}

    # Create a mock KeyboardProfile
    mock_keyboard_profile = Mock()
    mock_keyboard_profile.keyboard_name = "glove80"
    mock_keyboard_profile.firmware_version = "v25.05"
    mock_create_keyboard_profile.return_value = mock_keyboard_profile

    # Create a mock DisplayService and mock its display_keymap_with_layout method
    mock_display_service = Mock()
    mock_display_service.display_keymap_with_layout.return_value = (
        "Enhanced Layout Display with Profile\n"
        "Layer: QWERTY\n"
        "+-----+-----+-----+-----+-----+\n"
        "| Q   | W   | E   | R   | T   |\n"
        "| Y   | U   | I   | O   | P   |\n"
        "+-----+-----+-----+-----+-----+"
    )
    mock_create_display.return_value = mock_display_service

    # Run the command with profile option
    result = cli_runner.invoke(
        app,
        [
            "keymap",
            "show",
            str(sample_keymap_json),
            "--profile",
            "glove80/v25.05",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "Enhanced Layout Display with Profile" in result.output
    assert "Layer: QWERTY" in result.output

    # Verify the KeyboardProfile was created correctly
    mock_create_keyboard_profile.assert_called_once_with("glove80", "v25.05")

    # Verify the display service was called with the profile
    mock_display_service.display_keymap_with_layout.assert_called_once()
    call_args = mock_display_service.display_keymap_with_layout.call_args
    assert call_args is not None
    args, kwargs = call_args
    assert kwargs.get("profile") == mock_keyboard_profile


@patch("glovebox.cli.create_keymap_service")
@patch("glovebox.cli.Path")
@patch("glovebox.cli.json.loads")
def test_keymap_validate_command(
    mock_json_loads,
    mock_path_cls,
    mock_create_service,
    cli_runner,
    mock_keymap_service,
    sample_keymap_json,
):
    """Test keymap validate command."""
    # Setup mocks
    mock_create_service.return_value = mock_keymap_service
    mock_path_instance = Mock()
    mock_path_instance.exists.return_value = True
    mock_path_instance.read_text.return_value = "{}"
    mock_path_cls.return_value = mock_path_instance

    # Return valid JSON
    mock_json_loads.return_value = {"valid": "data"}

    # First test: validation passes
    mock_keymap_service.validate.return_value = True

    result = cli_runner.invoke(
        app, ["keymap", "validate", str(sample_keymap_json)], catch_exceptions=False
    )

    assert result.exit_code == 0
    assert "valid" in result.output

    # Second test: validation fails
    mock_keymap_service.validate.return_value = False

    result = cli_runner.invoke(
        app, ["keymap", "validate", str(sample_keymap_json)], catch_exceptions=False
    )

    assert result.exit_code == 1
    assert "invalid" in result.output


@patch("glovebox.cli.create_build_service")
@patch("glovebox.cli.Path")
@patch("glovebox.config.keyboard_config.create_keyboard_profile")
def test_firmware_compile_command_with_profile(
    mock_create_keyboard_profile,
    mock_path_cls,
    mock_create_service,
    cli_runner,
    mock_build_service,
    sample_keymap_dtsi,
    sample_config_file,
    tmp_path,
):
    """Test firmware compile command with KeyboardProfile."""
    # Setup mocks
    mock_create_service.return_value = mock_build_service
    mock_path_instance = Mock()
    mock_path_instance.exists.return_value = True
    mock_path_cls.return_value = mock_path_instance

    # Create a mock KeyboardProfile
    mock_keyboard_profile = Mock()
    mock_keyboard_profile.keyboard_name = "glove80"
    mock_keyboard_profile.firmware_version = "v25.05"
    mock_create_keyboard_profile.return_value = mock_keyboard_profile

    # Setup output directory
    output_dir = tmp_path / "build_output"

    # Run the command with profile
    result = cli_runner.invoke(
        app,
        [
            "firmware",
            "compile",
            str(sample_keymap_dtsi),
            str(sample_config_file),
            "--output-dir",
            str(output_dir),
            "--profile",
            "glove80/v25.05",
            "--branch",
            "main",
            "--verbose",
        ],
        catch_exceptions=False,
    )

    # Verify results
    assert result.exit_code == 0
    assert "Firmware compiled successfully" in result.output

    # Verify the KeyboardProfile was created correctly
    mock_create_keyboard_profile.assert_called_once_with("glove80", "v25.05")

    # Verify service was called with the profile
    mock_build_service.compile.assert_called_once()
    call_args = mock_build_service.compile.call_args
    assert call_args is not None
    args, kwargs = call_args

    # Check build_config
    build_config = args[0]
    assert build_config["keymap_path"] == str(sample_keymap_dtsi)
    assert build_config["kconfig_path"] == str(sample_config_file)
    assert build_config["output_dir"] == str(output_dir)
    assert build_config["branch"] == "main"
    assert build_config["verbose"] is True

    # Check profile was passed correctly
    assert kwargs.get("profile") == mock_keyboard_profile


@patch("glovebox.cli.create_build_service")
@patch("glovebox.cli.Path")
def test_firmware_compile_command(
    mock_path_cls,
    mock_create_service,
    cli_runner,
    mock_build_service,
    sample_keymap_dtsi,
    sample_config_file,
    tmp_path,
):
    """Test firmware compile command (traditional keyboard parameter)."""
    # Setup mocks
    mock_create_service.return_value = mock_build_service
    mock_path_instance = Mock()
    mock_path_instance.exists.return_value = True
    mock_path_cls.return_value = mock_path_instance

    # Setup output directory
    output_dir = tmp_path / "build_output"

    # Run the command with traditional parameters
    result = cli_runner.invoke(
        app,
        [
            "firmware",
            "compile",
            str(sample_keymap_dtsi),
            str(sample_config_file),
            "--output-dir",
            str(output_dir),
            "--keyboard",
            "glove80",
            "--firmware",
            "v25.05",
            "--branch",
            "main",
            "--verbose",
        ],
        catch_exceptions=False,
    )

    # Verify results
    assert result.exit_code == 0
    assert "Firmware compiled successfully" in result.output

    # Verify service was called with correct args
    mock_build_service.compile.assert_called_once()
    call_args = mock_build_service.compile.call_args
    assert call_args is not None
    args, kwargs = call_args

    # Check build_config
    build_config = args[0]
    assert build_config["keyboard"] == "glove80"
    assert build_config["keymap_path"] == str(sample_keymap_dtsi)
    assert build_config["kconfig_path"] == str(sample_config_file)
    assert build_config["output_dir"] == str(output_dir)
    assert build_config["branch"] == "main"
    assert build_config["verbose"] is True


@patch("glovebox.cli.create_flash_service")
@patch("glovebox.cli.Path")
def test_firmware_flash_command(
    mock_path_cls,
    mock_create_service,
    cli_runner,
    mock_flash_service,
    sample_firmware_file,
):
    """Test firmware flash command (traditional query parameter)."""
    # Setup mocks
    mock_create_service.return_value = mock_flash_service
    mock_path_instance = Mock()
    mock_path_instance.exists.return_value = True
    mock_path_cls.return_value = mock_path_instance

    # Run the command with query parameter
    result = cli_runner.invoke(
        app,
        [
            "firmware",
            "flash",
            str(sample_firmware_file),
            "--query",
            "vendor=Test",
            "--timeout",
            "30",
            "--count",
            "1",
        ],
        catch_exceptions=False,
    )

    # Verify results
    assert result.exit_code == 0
    assert "Successfully flashed" in result.output

    # Verify service was called with correct args
    mock_flash_service.flash.assert_called_once()
    call_args = mock_flash_service.flash.call_args
    assert call_args is not None
    args, kwargs = call_args
    assert kwargs.get("firmware_file") is not None
    assert kwargs.get("query") == "vendor=Test"
    assert kwargs.get("timeout") == 30
    assert kwargs.get("count") == 1
    assert kwargs.get("track_flashed") is True
    assert kwargs.get("profile") is None


@patch("glovebox.cli.create_flash_service")
@patch("glovebox.cli.Path")
@patch("glovebox.config.keyboard_config.create_keyboard_profile")
def test_firmware_flash_command_with_profile(
    mock_create_keyboard_profile,
    mock_path_cls,
    mock_create_service,
    cli_runner,
    mock_flash_service,
    sample_firmware_file,
):
    """Test firmware flash command with KeyboardProfile."""
    # Setup mocks
    mock_create_service.return_value = mock_flash_service
    mock_path_instance = Mock()
    mock_path_instance.exists.return_value = True
    mock_path_cls.return_value = mock_path_instance

    # Create a mock KeyboardProfile
    mock_keyboard_profile = Mock()
    mock_keyboard_profile.keyboard_name = "glove80"
    mock_keyboard_profile.firmware_version = "v25.05"
    mock_create_keyboard_profile.return_value = mock_keyboard_profile

    # Run the command with profile
    result = cli_runner.invoke(
        app,
        [
            "firmware",
            "flash",
            str(sample_firmware_file),
            "--profile",
            "glove80/v25.05",
            "--timeout",
            "30",
            "--count",
            "1",
        ],
        catch_exceptions=False,
    )

    # Verify results
    assert result.exit_code == 0
    assert "Successfully flashed" in result.output

    # Verify the KeyboardProfile was created correctly
    mock_create_keyboard_profile.assert_called_once_with("glove80", "v25.05")

    # Verify service was called with the profile
    mock_flash_service.flash.assert_called_once()
    call_args = mock_flash_service.flash.call_args
    assert call_args is not None
    args, kwargs = call_args
    assert kwargs.get("firmware_file") is not None
    assert kwargs.get("profile") == mock_keyboard_profile
    assert kwargs.get("timeout") == 30
    assert kwargs.get("count") == 1
    assert kwargs.get("track_flashed") is True


@patch("glovebox.config.keyboard_config.get_available_keyboards")
def test_config_list_command(mock_get_available, cli_runner):
    """Test config list command."""
    # Use the actual keyboard name that's available in the test environment
    mock_get_available.return_value = ["glove80"]

    result = cli_runner.invoke(app, ["config", "list"])

    assert result.exit_code == 0
    assert "Available keyboard configurations" in result.output
    assert "glove80" in result.output


@patch("glovebox.config.keyboard_config.load_keyboard_config_raw")
@pytest.mark.skip(reason="Test takes too long or runs real commands in background")
def test_config_show_command(mock_load_config, cli_runner):
    """Test config show command."""
    mock_config = {
        "keyboard": "glove80_v25.05",
        "keyboard_type": "glove80",
        "version": "v25.05",
        "description": "MoErgo Glove80 ZMK firmware v25.05",
        "templates": {
            "keymap": "templates/keymap.j2",
            "kconfig": "templates/kconfig.j2",
        },
        "build": {"container": "zmk-docker", "builder": "zmk-builder"},
    }

    mock_load_config.return_value = mock_config

    result = cli_runner.invoke(app, ["config", "show", "glove80_v25.05"])

    assert result.exit_code == 0
    assert "Keyboard: glove80_v25.05" in result.output
    assert "MoErgo Glove80 ZMK firmware v25.05" in result.output
    assert "templates/keymap.j2" in result.output


def test_status_command(cli_runner):
    """Test status command."""
    with patch("subprocess.run") as mock_run:
        # Mock subprocess for docker version check
        mock_process = Mock()
        mock_process.stdout = "Docker version 24.0.5"
        mock_run.return_value = mock_process

        with patch(
            "glovebox.config.keyboard_config.get_available_keyboards"
        ) as mock_get_available:
            # Use the actual keyboard name that's available in the test environment
            mock_get_available.return_value = ["glove80"]

            result = cli_runner.invoke(app, ["status"])

            assert result.exit_code == 0
            assert "Glovebox v" in result.output
            assert "System Dependencies" in result.output
            assert "Docker" in result.output
            assert "Available Keyboards" in result.output
            assert "Environment" in result.output
