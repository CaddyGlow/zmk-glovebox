"""Tests for CLI command execution."""

import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock, patch

import pytest
import typer

from glovebox.cli import app
from glovebox.cli.commands import register_all_commands
from glovebox.firmware.flash.models import FlashResult
from glovebox.firmware.models import BuildResult
from glovebox.layout.models import LayoutResult


# Register commands with the app before running tests
register_all_commands(app)


# Common setup for keymap command tests
@pytest.fixture
def setup_layout_command_test(mock_layout_service, mock_keyboard_profile):
    """Set up common mocks for layout command tests."""
    with (
        patch(
            "glovebox.cli.commands.layout.create_layout_service"
        ) as mock_create_service,
        patch("glovebox.cli.commands.layout.Path") as mock_path_cls,
        patch(
            "glovebox.cli.helpers.profile.create_profile_from_option"
        ) as mock_create_profile,
        patch(
            "glovebox.layout.models.LayoutData.model_validate"
        ) as mock_model_validate,
    ):
        # Set up path mock
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.read_text.return_value = "{}"  # Minimal JSON
        mock_path_cls.return_value = mock_path_instance

        # Set up service mock
        mock_create_service.return_value = mock_layout_service

        # Set up model validation mock
        mock_layout_data = Mock()
        mock_model_validate.return_value = mock_layout_data

        # Set up profile mock
        mock_create_profile.return_value = mock_keyboard_profile

        yield {
            "mock_create_service": mock_create_service,
            "mock_path_cls": mock_path_cls,
            "mock_create_profile": mock_create_profile,
            "mock_model_validate": mock_model_validate,
            "mock_path_instance": mock_path_instance,
            "mock_layout_data": mock_layout_data,
            "mock_layout_service": mock_layout_service,
        }


# Common setup for firmware command tests
@pytest.fixture
def setup_firmware_command_test(mock_build_service, mock_keyboard_profile):
    """Set up common mocks for firmware command tests."""
    with (
        patch(
            "glovebox.cli.commands.firmware.create_build_service"
        ) as mock_create_service,
        patch("glovebox.cli.commands.firmware.Path") as mock_path_cls,
        patch(
            "glovebox.cli.helpers.profile.create_profile_from_context"
        ) as mock_create_profile,
    ):
        # Set up path mock
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path_cls.return_value = mock_path_instance

        # Set up service mock
        mock_create_service.return_value = mock_build_service

        # Set up profile mock
        mock_create_profile.return_value = mock_keyboard_profile

        yield {
            "mock_create_service": mock_create_service,
            "mock_path_cls": mock_path_cls,
            "mock_create_profile": mock_create_profile,
            "mock_path_instance": mock_path_instance,
        }


# Test cases for keymap commands
@pytest.mark.parametrize(
    "command,args,success,output_contains",
    [
        (
            "layout compile",
            ["output/test", "--profile", "glove80/v25.05", "input.json"],
            True,
            "Layout generated successfully",
        ),
        (
            "layout validate",
            ["--profile", "glove80/v25.05", "input.json"],
            True,
            "valid",
        ),
        (
            "layout decompose",
            ["input.json", "decompose_output"],
            True,
            "Layout layers decomposed to",
        ),
    ],
)
def test_layout_commands(
    command,
    args,
    success,
    output_contains,
    setup_layout_command_test,
    cli_runner,
    sample_keymap_json,
    tmp_path,
):
    """Test layout commands with parameterized inputs."""
    # Create a temporary sample file
    input_file = tmp_path / "input.json"
    input_file.write_text(json.dumps(sample_keymap_json))

    # Replace placeholder paths with real paths
    real_args = []
    for arg in args:
        if arg == "input.json":
            real_args.append(str(input_file))
        elif arg.startswith("output/"):
            output_dir = tmp_path / "output"
            output_dir.mkdir(exist_ok=True)
            real_args.append(str(output_dir / arg.split("/")[1]))
        elif arg == "decompose_output":
            decompose_dir = tmp_path / "decompose_output"
            decompose_dir.mkdir(exist_ok=True)
            real_args.append(str(decompose_dir))
        else:
            real_args.append(arg)

    # Configure service mocks based on command
    if "compile" in command:
        layout_result = LayoutResult(success=success)
        layout_result.keymap_path = Path(tmp_path / "output/keymap.keymap")
        layout_result.conf_path = Path(tmp_path / "output/keymap.conf")
        if not success:
            layout_result.errors.append("Invalid keymap structure")
        setup_layout_command_test[
            "mock_layout_service"
        ].generate_from_file.return_value = layout_result
    elif "decompose" in command:
        layout_result = LayoutResult(success=success)
        setup_layout_command_test[
            "mock_layout_service"
        ].decompose_components_from_file.return_value = layout_result
    elif "validate" in command:
        setup_layout_command_test[
            "mock_layout_service"
        ].validate_from_file.return_value = success

    # Run the command
    result = cli_runner.invoke(
        app,
        command.split() + real_args,
        catch_exceptions=True,
    )

    # Verify results
    expected_exit_code = 0 if success else 1
    # Print useful debug info if the test fails
    if result.exit_code != expected_exit_code:
        print(f"Command failed with exit code {result.exit_code}")
        print(f"Command output: {result.output}")
        print(f"Exception: {result.exception}")
    assert result.exit_code == expected_exit_code
    assert output_contains in result.output


# Test cases for firmware commands
@pytest.mark.parametrize(
    "command,args,success,output_contains",
    [
        (
            "firmware compile",
            [
                "keymap.keymap",
                "config.conf",
                "--output-dir",
                "output",
                "--profile",
                "glove80/v25.05",
            ],
            True,
            "Firmware compiled successfully",
        ),
    ],
)
def test_firmware_compile_commands(
    command,
    args,
    success,
    output_contains,
    setup_firmware_command_test,
    cli_runner,
    tmp_path,
    sample_keymap_dtsi,
    sample_config_file,
):
    """Test firmware compile commands with parameterized inputs."""
    # Replace placeholder paths with real paths
    real_args = []
    for arg in args:
        if arg == "keymap.keymap":
            real_args.append(str(sample_keymap_dtsi))
        elif arg == "config.conf":
            real_args.append(str(sample_config_file))
        elif arg == "output":
            output_dir = tmp_path / "output"
            output_dir.mkdir(exist_ok=True)
            real_args.append(str(output_dir))
        else:
            real_args.append(arg)

    # Set up result
    build_result = BuildResult(success=success)
    build_result.add_message("Firmware compiled successfully")
    setup_firmware_command_test[
        "mock_create_service"
    ].return_value.compile_from_files.return_value = build_result

    # Run the command
    result = cli_runner.invoke(
        app,
        command.split() + real_args,
        catch_exceptions=True,
    )

    # Verify results
    expected_exit_code = 0 if success else 1
    # Print useful debug info if the test fails
    if result.exit_code != expected_exit_code:
        print(f"Command failed with exit code {result.exit_code}")
        print(f"Command output: {result.output}")
        print(f"Exception: {result.exception}")
    assert result.exit_code == expected_exit_code
    assert output_contains in result.output


# Test error cases
@pytest.mark.parametrize(
    "command,args",
    [
        (
            "layout compile",
            ["output/test", "--profile", "glove80/v25.05", "nonexistent.json"],
        ),
        (
            "firmware flash",
            ["nonexistent.uf2", "--profile", "glove80/v25.05"],
        ),
    ],
)
def test_command_errors(command, args, cli_runner, tmp_path):
    """Test error handling in CLI commands."""
    # Replace placeholder paths with real paths
    real_args = []
    for arg in args:
        if arg.startswith("output/"):
            output_dir = tmp_path / "output"
            output_dir.mkdir(exist_ok=True)
            real_args.append(str(output_dir / arg.split("/")[1]))
        elif arg == "nonexistent.json" or arg == "nonexistent.uf2":
            # Use a path that doesn't exist
            real_args.append(str(tmp_path / arg))
        else:
            real_args.append(arg)

    # Mock the configuration loading
    with patch(
        "glovebox.cli.helpers.profile.create_profile_from_option"
    ) as mock_create_profile:
        # Set up mock profile
        from glovebox.config.profile import KeyboardProfile

        mock_profile = Mock(spec=KeyboardProfile)
        mock_profile.keyboard_name = "glove80"
        mock_profile.firmware_version = "v25.05"
        mock_create_profile.return_value = mock_profile

        # Set up file path mock
        with (
            patch("glovebox.cli.commands.layout.Path") as mock_path_cls,
            patch("glovebox.cli.commands.firmware.Path") as mock_path_cls2,
        ):
            # Set path to not exist for error case
            mock_path_instance = Mock()
            mock_path_instance.exists.return_value = False
            mock_path_cls.return_value = mock_path_instance
            mock_path_cls2.return_value = mock_path_instance

            # Run the command - we're expecting errors here
            result = cli_runner.invoke(
                app,
                command.split() + real_args,
                catch_exceptions=True,
            )

            # Verify results
            # Print useful debug info if the test unexpectedly passes
            if result.exit_code == 0:
                print(
                    f"Command unexpectedly succeeded with exit code {result.exit_code}"
                )
                print(f"Command output: {result.output}")
            assert result.exit_code != 0


# Test config commands
@pytest.mark.parametrize(
    "command,args,output_contains",
    [
        ("config list", [], "Available keyboard configurations"),
    ],
)
def test_config_commands(command, args, output_contains, cli_runner):
    """Test config commands."""
    with patch(
        "glovebox.cli.commands.config.get_available_keyboards"
    ) as mock_get_available:
        # Mock available keyboards
        mock_get_available.return_value = ["glove80", "test_keyboard"]

        # Run the command
        result = cli_runner.invoke(
            app,
            command.split() + args,
            catch_exceptions=True,
        )

        # Verify results
        # Print useful debug info if the test fails
        if result.exit_code != 0:
            print(f"Command failed with exit code {result.exit_code}")
            print(f"Command output: {result.output}")
            print(f"Exception: {result.exception}")
        assert result.exit_code == 0
        assert output_contains in result.output
        assert "glove80" in result.output


# Test status command
def test_status_command(cli_runner):
    """Test status command."""
    with (
        patch("glovebox.cli.commands.status.subprocess.run") as mock_run,
        patch("glovebox.cli.commands.status.load_keyboard_config") as mock_load_config,
        patch(
            "glovebox.cli.commands.status.get_available_keyboards"
        ) as mock_get_available,
    ):
        # Mock subprocess for docker version check
        mock_process = Mock()
        mock_process.stdout = "Docker version 24.0.5"
        mock_run.return_value = mock_process

        # Mock config data
        mock_load_config.return_value = {"firmwares": {"v25.05": {}}}

        # Mock available keyboards
        mock_get_available.return_value = ["glove80"]

        # Run the command
        result = cli_runner.invoke(app, ["status"])

        # Verify results
        # Print useful debug info if the test fails
        if result.exit_code != 0:
            print(f"Command failed with exit code {result.exit_code}")
            print(f"Command output: {result.output}")
            print(f"Exception: {result.exception}")
        assert result.exit_code == 0
        assert "Glovebox v" in result.output
        assert "System Dependencies" in result.output
        assert "Docker" in result.output
        assert "Available Keyboards" in result.output
        assert "Environment" in result.output
