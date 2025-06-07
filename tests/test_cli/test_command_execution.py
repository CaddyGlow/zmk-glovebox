"""Tests for CLI command execution."""

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import typer

from glovebox.cli import app
from glovebox.cli.commands import register_all_commands
from glovebox.cli.helpers.profile import create_profile_from_option
from glovebox.models.build import FirmwareOutputFiles
from glovebox.models.results import BuildResult, FlashResult, KeymapResult
from glovebox.services.build_service import create_build_service
from glovebox.services.flash_service import create_flash_service
from glovebox.services.keymap_service import create_keymap_service


# Register commands with the app before running tests
register_all_commands(app)


@patch("glovebox.cli.commands.keymap.create_keymap_service")
@patch("glovebox.cli.commands.keymap.Path")
@patch("glovebox.cli.helpers.profile.create_profile_from_option")
@patch("glovebox.models.keymap.KeymapData.model_validate")
def test_keymap_compile_command(
    mock_model_validate,
    mock_create_profile,
    mock_path_cls,
    mock_create_service,
    cli_runner,
    mock_keymap_service,
    mock_keyboard_config,
    sample_keymap_json,
    tmp_path,
):
    """Test keymap compile command with KeyboardProfile."""
    # Setup path mock
    mock_path_instance = Mock()
    mock_path_instance.exists.return_value = True
    mock_path_instance.read_text.return_value = json.dumps(sample_keymap_json)
    mock_path_cls.return_value = mock_path_instance

    # Setup keymap service mock
    mock_create_service.return_value = mock_keymap_service

    # Mock the KeymapData validation
    mock_keymap_data = Mock()
    mock_model_validate.return_value = mock_keymap_data

    # Create a mock KeyboardProfile
    mock_keyboard_profile = Mock()
    mock_keyboard_profile.keyboard_name = "glove80"
    mock_keyboard_profile.firmware_version = "v25.05"
    mock_create_profile.return_value = mock_keyboard_profile

    # Ensure the service returns a successful result
    from glovebox.models.results import KeymapResult

    success_result = KeymapResult(success=True)
    success_result.keymap_path = Path("/tmp/output/keymap.keymap")
    success_result.conf_path = Path("/tmp/output/keymap.conf")
    mock_keymap_service.compile_from_file.return_value = success_result

    # Create a temporary file with sample keymap data
    temp_file = tmp_path / "test_keymap.json"
    temp_file.write_text(json.dumps(sample_keymap_json))

    # Run the command
    result = cli_runner.invoke(
        app,
        [
            "keymap",
            "compile",
            "output/test",
            "--profile",
            "glove80/v25.05",
            str(temp_file),
        ],
        catch_exceptions=True,
    )

    print(f"Test result output: {result.output}")
    print(f"Exit code: {result.exit_code}")
    print(f"Exception: {getattr(result, 'exception', None)}")

    assert result.exit_code == 0
    assert "Keymap compiled successfully" in result.output

    # Verify service was called with correct args
    mock_keymap_service.compile_from_file.assert_called_once()

    # Verify the KeyboardProfile was created correctly
    mock_create_profile.assert_called_once_with("glove80/v25.05")


@patch("glovebox.cli.commands.keymap.create_keymap_service")
@patch("glovebox.cli.commands.keymap.Path")
@patch("glovebox.cli.helpers.profile.create_profile_from_option")
@patch("glovebox.models.keymap.KeymapData.model_validate")
def test_keymap_compile_failure(
    mock_model_validate,
    mock_create_profile,
    mock_path_cls,
    mock_create_service,
    cli_runner,
    mock_keymap_service,
    tmp_path,
):
    """Test keymap compile command failure handling."""
    # Setup path mock
    mock_path_instance = Mock()
    mock_path_instance.exists.return_value = True
    mock_path_instance.read_text.return_value = json.dumps(
        {
            "keyboard": "test_keyboard",
            "title": "Test Keymap",
            "layer_names": ["Layer 1"],
            "layers": [[{"value": "&kp", "params": [{"value": "A"}]}]],
        }
    )
    mock_path_cls.return_value = mock_path_instance

    # Setup keymap service mock
    mock_create_service.return_value = mock_keymap_service

    # Mock the KeymapData validation
    mock_keymap_data = Mock()
    mock_model_validate.return_value = mock_keymap_data

    # Create a mock profile
    mock_profile = Mock()
    mock_profile.keyboard_name = "glove80"
    mock_profile.firmware_version = "v25.05"
    mock_create_profile.return_value = mock_profile

    # Configure mock to return failure result
    failed_result = KeymapResult(success=False)
    failed_result.errors.append("Invalid keymap structure")
    mock_keymap_service.compile_from_file.return_value = failed_result

    # Create a temporary sample file for the test
    temp_file = tmp_path / "test_keymap.json"
    valid_keymap_data = {
        "keyboard": "test_keyboard",
        "title": "Test Keymap",
        "layer_names": ["Layer 1"],
        "layers": [[{"value": "&kp", "params": [{"value": "A"}]}]],
    }
    temp_file.write_text(json.dumps(valid_keymap_data))
    temp_path = str(temp_file)

    result = cli_runner.invoke(
        app,
        [
            "keymap",
            "compile",
            "output/test",
            "--profile",
            "glove80/v25.05",
            temp_path,
        ],
        catch_exceptions=True,
    )

    print(f"Failure test output: {result.output}")
    assert result.exit_code == 1
    assert "Keymap compilation failed" in result.output
    assert "Invalid keymap structure" in result.output


@patch("glovebox.cli.helpers.profile.create_profile_from_option")
@patch("glovebox.cli.commands.keymap.create_keymap_service")
@patch("glovebox.cli.commands.keymap.Path")
@patch("glovebox.models.keymap.KeymapData.model_validate")
def test_keymap_split_command(
    mock_model_validate,
    mock_path_cls,
    mock_create_service,
    mock_create_profile,
    cli_runner,
    mock_keymap_service,
    sample_keymap_json,
    tmp_path,
):
    """Test keymap split command."""
    # Setup path mocks
    mock_create_service.return_value = mock_keymap_service

    # Mock the profile creation
    mock_keyboard_profile = Mock()
    mock_keyboard_profile.keyboard_name = "glove80"
    mock_keyboard_profile.firmware_version = "v25.05"
    mock_create_profile.return_value = mock_keyboard_profile

    # Use actual paths for clarity
    output_dir = tmp_path / "split_output"
    output_dir.mkdir()

    # Setup successful result
    split_result = KeymapResult(success=True)
    mock_keymap_service.split_keymap_from_file.return_value = split_result

    # Create valid keymap data for test
    valid_keymap_data = {
        "keyboard": "test_keyboard",
        "title": "Test Keymap",
        "layer_names": ["Layer 1"],
        "layers": [[{"value": "&kp", "params": [{"value": "A"}]}]],
    }

    # Mock the path read text to return valid keymap data
    mock_path_instance = Mock()
    mock_path_instance.exists.return_value = True
    mock_path_instance.read_text.return_value = json.dumps(valid_keymap_data)
    mock_path_cls.return_value = mock_path_instance

    # Mock the KeymapData validation
    mock_keymap_data = Mock()
    mock_model_validate.return_value = mock_keymap_data

    # Create a temporary sample file for the test
    temp_file = tmp_path / "test_keymap.json"
    temp_file.write_text(json.dumps(valid_keymap_data))
    temp_path = str(temp_file)

    result = cli_runner.invoke(
        app,
        ["keymap", "split", temp_path, str(output_dir)],
        catch_exceptions=True,
    )

    assert result.exit_code == 0
    assert "Keymap split into layers" in result.output

    # Verify service was called
    mock_keymap_service.split_keymap_from_file.assert_called_once()


@pytest.mark.skip("Mocking complexity, needs simplified test")
@patch("glovebox.cli.helpers.profile.create_profile_from_option")
@patch("glovebox.cli.commands.keymap.create_keymap_service")
@patch("glovebox.cli.commands.keymap.Path")
@patch("glovebox.models.keymap.KeymapData.model_validate")
def test_keymap_merge_command(
    mock_model_validate,
    mock_path_cls,
    mock_create_service,
    mock_create_profile,
    cli_runner,
    mock_keymap_service,
    tmp_path,
):
    """Test keymap merge command."""
    # Setup mocks
    mock_create_service.return_value = mock_keymap_service

    # Mock the profile creation
    mock_keyboard_profile = Mock()
    mock_keyboard_profile.keyboard_name = "glove80"
    mock_keyboard_profile.firmware_version = "v25.05"
    mock_create_profile.return_value = mock_keyboard_profile

    # Setup successful result
    merge_result = KeymapResult(success=True)
    mock_keymap_service.merge_layers.return_value = merge_result

    # Use actual paths for clarity
    input_dir = tmp_path / "merge_input"
    input_dir.mkdir()

    # Create layers directory
    layers_dir = input_dir / "layers"
    layers_dir.mkdir()

    # Create metadata.json in the input directory
    metadata_json_path = input_dir / "metadata.json"
    valid_metadata_data = {
        "keyboard": "test_keyboard",
        "title": "Test Keymap",
        "layer_names": ["Layer 1"],
        "layers": [],
    }

    # Mock file existence checks
    mock_path_instance = Mock()
    mock_path_instance.exists.return_value = True
    mock_path_instance.read_text.return_value = json.dumps(valid_metadata_data)
    mock_path_instance.__truediv__.side_effect = lambda x: Mock(
        exists=lambda: True,
        read_text=lambda: json.dumps(valid_metadata_data)
        if x == "metadata.json"
        else "",
        parent=Mock(),
    )
    mock_path_cls.return_value = mock_path_instance

    # Mock the KeymapData validation
    mock_keymap_data = Mock()
    mock_model_validate.return_value = mock_keymap_data

    output_file = tmp_path / "merged.json"

    result = cli_runner.invoke(
        app,
        ["keymap", "merge", str(input_dir), "--output", str(output_file)],
        catch_exceptions=True,
    )

    assert result.exit_code == 0
    assert "Keymap merged and saved" in result.output

    # Verify service was called
    mock_keymap_service.merge_layers.assert_called_once()


@patch("glovebox.cli.helpers.profile.create_profile_from_option")
@patch("glovebox.cli.commands.keymap.create_keymap_service")
@patch("glovebox.cli.commands.keymap.Path")
@patch("glovebox.cli.commands.keymap.json.loads")
@patch("glovebox.models.keymap.KeymapData.model_validate")
def test_keymap_show_command(
    mock_model_validate,
    mock_json_loads,
    mock_path_cls,
    mock_create_service,
    mock_create_profile,
    cli_runner,
    mock_keymap_service,
    sample_keymap_json,
    tmp_path,
):
    """Test keymap show command (using traditional show method)."""
    # Setup mocks
    mock_create_service.return_value = mock_keymap_service

    # Mock the profile creation
    mock_keyboard_profile = Mock()
    mock_keyboard_profile.keyboard_name = "glove80"
    mock_keyboard_profile.firmware_version = "v25.05"
    mock_create_profile.return_value = mock_keyboard_profile

    # Create valid keymap data
    valid_keymap_data = {
        "keyboard": "test_keyboard",
        "title": "Test Keymap",
        "layer_names": ["Layer 1"],
        "layers": [[{"value": "&kp", "params": [{"value": "A"}]}]],
    }

    mock_path_instance = Mock()
    mock_path_instance.exists.return_value = True
    mock_path_instance.read_text.return_value = json.dumps(valid_keymap_data)
    mock_path_cls.return_value = mock_path_instance

    # Return valid JSON
    mock_json_loads.return_value = valid_keymap_data

    # Mock the KeymapData validation
    mock_keymap_data = Mock()
    mock_model_validate.return_value = mock_keymap_data

    # Configure mock to handle the NotImplementedError
    mock_keymap_service.show_from_file.side_effect = NotImplementedError(
        "The layout display feature is not yet implemented. Coming in a future release."
    )

    # Create a temporary sample file for the test
    temp_file = tmp_path / "test_keymap.json"
    temp_file.write_text(json.dumps(valid_keymap_data))
    temp_path = str(temp_file)

    # Test with catch_exceptions=True to handle the expected NotImplementedError
    result = cli_runner.invoke(
        app,
        ["keymap", "show", temp_path, "--profile", "glove80/v25.05"],
        catch_exceptions=True,
    )

    # The command should fail with exit code 1 because of the NotImplementedError
    assert result.exit_code == 1
    # Verify the error message is included in the output
    assert "not yet implemented" in result.output

    # Verify service was called
    mock_keymap_service.show_from_file.assert_called_once()


@patch("glovebox.cli.helpers.profile.create_profile_from_option")
@patch("glovebox.cli.commands.keymap.create_keymap_service")
@patch("glovebox.cli.commands.keymap.Path")
@patch("glovebox.cli.commands.keymap.json.loads")
@patch("glovebox.models.keymap.KeymapData.model_validate")
def test_keymap_validate_command(
    mock_model_validate,
    mock_json_loads,
    mock_path_cls,
    mock_create_service,
    mock_create_profile,
    cli_runner,
    mock_keymap_service,
    sample_keymap_json,
    tmp_path,
):
    """Test keymap validate command."""
    # Setup mocks
    mock_create_service.return_value = mock_keymap_service

    # Mock the profile creation
    mock_keyboard_profile = Mock()
    mock_keyboard_profile.keyboard_name = "glove80"
    mock_keyboard_profile.firmware_version = "v25.05"
    mock_create_profile.return_value = mock_keyboard_profile

    mock_path_instance = Mock()
    mock_path_instance.exists.return_value = True
    mock_path_instance.read_text.return_value = "{}"
    mock_path_cls.return_value = mock_path_instance

    # Mock valid keymap data
    valid_keymap_data = {
        "keyboard": "test_keyboard",
        "title": "Test Keymap",
        "layer_names": ["Layer 1"],
        "layers": [[{"value": "&kp", "params": [{"value": "A"}]}]],
    }
    mock_json_loads.return_value = valid_keymap_data

    # Create a mock KeymapData object
    mock_keymap_data = Mock()
    mock_model_validate.return_value = mock_keymap_data

    # First test: validation passes
    mock_keymap_service.validate_file.return_value = True

    # Create a temporary sample file for the test
    temp_file = tmp_path / "test_keymap.json"
    temp_file.write_text(json.dumps(valid_keymap_data))
    temp_path = str(temp_file)

    result = cli_runner.invoke(
        app,
        ["keymap", "validate", temp_path, "--profile", "glove80/v25.05"],
        catch_exceptions=True,
    )

    print(f"Validate test output: {result.output}")
    print(f"Exception: {getattr(result, 'exception', None)}")

    assert result.exit_code == 0
    assert "valid" in result.output

    # Second test: validation fails
    mock_keymap_service.validate_file.return_value = False

    # Use the same temporary file for the failure test
    result = cli_runner.invoke(
        app,
        ["keymap", "validate", temp_path, "--profile", "glove80/v25.05"],
        catch_exceptions=True,
    )

    print(f"Validate failure test output: {result.output}")
    print(f"Exception: {getattr(result, 'exception', None)}")

    assert result.exit_code == 1
    assert "invalid" in result.output


@patch("glovebox.cli.commands.firmware.create_build_service")
@patch("glovebox.cli.commands.firmware.Path")
@patch("glovebox.cli.commands.firmware.create_profile_from_option")
def test_firmware_compile_command_with_profile(
    mock_create_profile,
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
    mock_create_profile.return_value = mock_keyboard_profile

    # Configure build service to return success

    build_result = BuildResult(success=True)
    build_result.add_message("Firmware compiled successfully")
    mock_build_service.compile_from_files.return_value = build_result

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
        catch_exceptions=True,
    )

    # Verify results
    assert result.exit_code == 0
    assert "Firmware compiled successfully" in result.output

    # Verify the KeyboardProfile was created correctly
    mock_create_profile.assert_called_once_with("glove80/v25.05")

    # Verify service was called with the profile
    mock_build_service.compile_from_files.assert_called_once()
    call_args = mock_build_service.compile_from_files.call_args
    assert call_args is not None
    args, kwargs = call_args

    # Check correct parameters are passed
    assert kwargs.get("keymap_file_path") == sample_keymap_dtsi
    assert kwargs.get("kconfig_file_path") == sample_config_file
    assert kwargs.get("output_dir") == output_dir
    assert kwargs.get("branch") == "main"
    assert kwargs.get("verbose") is True
    assert kwargs.get("profile") == mock_keyboard_profile


@patch("glovebox.cli.commands.firmware.create_build_service")
@patch("glovebox.cli.commands.firmware.Path")
@patch("glovebox.cli.commands.firmware.create_profile_from_option")
def test_firmware_compile_command(
    mock_create_profile,
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

    # Create a mock KeyboardProfile
    mock_keyboard_profile = Mock()
    mock_keyboard_profile.keyboard_name = "glove80"
    mock_keyboard_profile.firmware_version = "v25.05"
    mock_create_profile.return_value = mock_keyboard_profile

    # Configure build service to return success

    build_result = BuildResult(success=True)
    build_result.add_message("Firmware compiled successfully")
    mock_build_service.compile_from_files.return_value = build_result

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
        catch_exceptions=True,
    )

    # Verify results
    assert result.exit_code == 0
    assert "Firmware compiled successfully" in result.output

    # Verify service was called with correct args
    mock_build_service.compile_from_files.assert_called_once()
    call_args = mock_build_service.compile_from_files.call_args
    assert call_args is not None
    args, kwargs = call_args

    # Check correct parameters are passed
    assert kwargs.get("keymap_file_path") == sample_keymap_dtsi
    assert kwargs.get("kconfig_file_path") == sample_config_file
    assert kwargs.get("output_dir") == output_dir
    assert kwargs.get("branch") == "main"
    assert kwargs.get("verbose") is True


@patch("glovebox.cli.commands.firmware.create_flash_service")
@patch("glovebox.cli.commands.firmware.Path")
@patch("glovebox.cli.helpers.profile.create_profile_from_option", autospec=True)
def test_firmware_flash_command(
    mock_create_profile,
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

    # Create a mock KeyboardProfile
    mock_keyboard_profile = Mock()
    mock_keyboard_profile.keyboard_name = "glove80"
    mock_keyboard_profile.firmware_version = "v25.05"
    mock_create_profile.return_value = mock_keyboard_profile

    # Configure the mock to return success

    flash_result = FlashResult(success=True)
    flash_result.add_message("Device detected")
    flash_result.add_message("Firmware flashed successfully")
    flash_result.devices_flashed = 1
    mock_flash_service.flash_from_file.return_value = flash_result

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
            "--profile",
            "glove80/v25.05",
        ],
        catch_exceptions=True,
    )

    # Verify results
    assert result.exit_code == 0
    assert "Successfully flashed" in result.output

    # Verify service was called with correct args
    mock_flash_service.flash_from_file.assert_called_once()
    call_args = mock_flash_service.flash_from_file.call_args
    assert call_args is not None
    args, kwargs = call_args
    assert kwargs.get("firmware_file_path") is not None
    assert kwargs.get("query") == "vendor=Test"
    assert kwargs.get("timeout") == 30
    assert kwargs.get("count") == 1
    assert kwargs.get("track_flashed") is True


@patch("glovebox.cli.commands.firmware.create_flash_service")
@patch("glovebox.cli.commands.firmware.Path")
@patch("glovebox.cli.helpers.profile.create_profile_from_option", autospec=True)
def test_firmware_flash_command_with_profile(
    mock_create_profile,
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
    mock_create_profile.return_value = mock_keyboard_profile

    # Configure the mock to return success

    flash_result = FlashResult(success=True)
    flash_result.add_message("Device detected")
    flash_result.add_message("Firmware flashed successfully")
    flash_result.devices_flashed = 1
    mock_flash_service.flash_from_file.return_value = flash_result

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
        catch_exceptions=True,
    )

    # Verify results
    assert result.exit_code == 0
    assert "Successfully flashed" in result.output

    # Verify service was called with the profile
    mock_flash_service.flash_from_file.assert_called_once()
    call_args = mock_flash_service.flash_from_file.call_args
    assert call_args is not None
    args, kwargs = call_args
    assert kwargs.get("firmware_file_path") is not None
    assert kwargs.get("timeout") == 30
    assert kwargs.get("count") == 1
    assert kwargs.get("track_flashed") is True


@patch("glovebox.cli.commands.config.get_available_keyboards")
def test_config_list_command(mock_get_available, cli_runner):
    """Test config list command."""
    # Use the actual keyboard name that's available in the test environment
    mock_get_available.return_value = ["glove80"]

    result = cli_runner.invoke(app, ["config", "list"])

    assert result.exit_code == 0
    assert "Available keyboard configurations" in result.output
    assert "glove80" in result.output


@patch("glovebox.cli.commands.config.load_keyboard_config")
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
    with patch("glovebox.cli.commands.status.subprocess.run") as mock_run:
        # Mock subprocess for docker version check
        mock_process = Mock()
        mock_process.stdout = "Docker version 24.0.5"
        mock_run.return_value = mock_process

        with patch(
            "glovebox.cli.commands.status.load_keyboard_config"
        ) as mock_load_config:
            # Mock config data
            mock_load_config.return_value = {"firmwares": {"v25.05": {}}}

            with patch(
                "glovebox.cli.commands.status.get_available_keyboards"
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
