"""Tests for CLI command execution."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


pytestmark = [pytest.mark.docker, pytest.mark.integration]

from glovebox.cli import app
from glovebox.cli.commands import register_all_commands
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
            "glovebox.cli.commands.layout.dependencies.create_full_layout_service"
        ) as mock_create_full_service,
        patch(
            "glovebox.cli.commands.layout.dependencies.create_layout_service"
        ) as mock_create_service,
        patch("glovebox.cli.commands.layout.core.Path") as mock_path_cls,
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

        # Set up service mocks (both old and new patterns)
        mock_create_service.return_value = mock_layout_service
        mock_create_full_service.return_value = mock_layout_service

        # Set up model validation mock
        mock_layout_data = Mock()
        mock_model_validate.return_value = mock_layout_data

        # Set up profile mock
        mock_create_profile.return_value = mock_keyboard_profile

        yield {
            "mock_create_service": mock_create_service,
            "mock_create_full_service": mock_create_full_service,
            "mock_path_cls": mock_path_cls,
            "mock_create_profile": mock_create_profile,
            "mock_model_validate": mock_model_validate,
            "mock_path_instance": mock_path_instance,
            "mock_layout_data": mock_layout_data,
            "mock_layout_service": mock_layout_service,
        }


# Common setup for firmware command tests
@pytest.fixture
def setup_firmware_command_test(mock_keyboard_profile):
    """Set up common mocks for firmware command tests."""
    with (
        patch("glovebox.compilation.create_compilation_service") as mock_create_service,
        patch(
            "glovebox.cli.commands.firmware.helpers.execute_compilation_service"
        ) as mock_execute_compilation,
        patch(
            "glovebox.cli.commands.firmware.helpers.execute_compilation_from_json"
        ) as mock_execute_json_compilation,
        patch("glovebox.cli.commands.firmware.compile.Path") as mock_path_cls,
        patch(
            "glovebox.cli.helpers.profile.create_profile_from_context"
        ) as mock_create_profile,
        patch(
            "glovebox.cli.commands.firmware.helpers.get_build_output_dir"
        ) as mock_get_build_dir,
        patch(
            "glovebox.cli.commands.firmware.helpers.resolve_compilation_type"
        ) as mock_resolve_compilation,
        patch(
            "glovebox.cli.commands.firmware.helpers.setup_progress_display"
        ) as mock_setup_progress,
        patch(
            "glovebox.cli.commands.firmware.helpers.get_cache_services_with_fallback"
        ) as mock_get_cache_services,
        patch(
            "glovebox.cli.commands.firmware.helpers.format_compilation_output"
        ) as mock_format_output,
        patch(
            "glovebox.cli.commands.firmware.helpers.process_compilation_output"
        ) as mock_process_output,
    ):
        # Set up path mock
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path_cls.return_value = mock_path_instance

        # Set up compilation service mock
        mock_compilation_service = Mock()

        # Create proper FirmwareOutputFiles for BuildResult
        from glovebox.firmware.models import FirmwareOutputFiles

        output_files = FirmwareOutputFiles(
            uf2_files=[Path("/tmp/output/glove80.uf2")], output_dir=Path("/tmp/output")
        )

        build_result = BuildResult(
            success=True,
            messages=["Firmware built successfully"],
            output_files=output_files,
        )

        mock_compilation_service.compile.return_value = build_result
        mock_create_service.return_value = mock_compilation_service

        # Mock the helper functions that CompileFirmwareCommand actually calls
        mock_execute_compilation.return_value = build_result
        mock_execute_json_compilation.return_value = build_result
        mock_get_build_dir.return_value = (Path("/tmp/output"), False)
        mock_resolve_compilation.return_value = ("zmk_config", Mock())
        mock_setup_progress.return_value = (None, None, None)
        mock_get_cache_services.return_value = (Mock(), Mock(), Mock())

        # Mock the output formatting to actually print the expected message
        def mock_format_output_func(result, output_format, output_dir):
            if result.success:
                print("Firmware compiled successfully")

        mock_format_output.side_effect = mock_format_output_func

        # Set up profile mock - ensure keyboard_config has compile_methods
        mock_keyboard_profile.keyboard_config.compile_methods = [
            Mock(type="moergo", image="test-zmk-build")
        ]

        # Set up firmware_config with build_options
        mock_build_options = Mock()
        mock_build_options.repository = "test-repo"
        mock_build_options.branch = "test-branch"

        mock_firmware_config = Mock()
        mock_firmware_config.build_options = mock_build_options

        mock_keyboard_profile.firmware_config = mock_firmware_config
        mock_create_profile.return_value = mock_keyboard_profile

        yield {
            "mock_create_service": mock_create_service,
            "mock_execute_compilation": mock_execute_compilation,
            "mock_execute_json_compilation": mock_execute_json_compilation,
            "mock_path_cls": mock_path_cls,
            "mock_create_profile": mock_create_profile,
            "mock_path_instance": mock_path_instance,
            "mock_format_output": mock_format_output,
            "mock_process_output": mock_process_output,
        }


# Test cases for keymap commands
@pytest.mark.parametrize(
    "command,args,success,output_contains",
    [
        (
            "layout compile",
            ["input.json", "--output", "output/test", "--profile", "glove80/v25.05"],
            True,
            "Layout compiled successfully",
        ),
        (
            "layout validate",
            ["input.json", "--profile", "glove80/v25.05"],
            True,
            "valid",
        ),
        pytest.param(
            "layout split",
            ["input.json", "split_output"],
            True,
            "Layout split into components",
            marks=pytest.mark.skip(
                reason="Complex mocking required - covered by other tests"
            ),
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
        elif arg == "split_output":
            split_dir = tmp_path / "split_output"
            split_dir.mkdir(exist_ok=True)
            real_args.append(str(split_dir))
        else:
            real_args.append(arg)

    # Configure service mocks based on command
    if "compile" in command:
        # Mock the layout service's compile method for new command pattern
        mock_result = Mock()
        mock_result.success = success
        mock_result.keymap_content = "// Test keymap content" if success else None
        mock_result.config_content = "# Test config content" if success else None
        mock_result.errors = [] if success else ["Invalid keymap structure"]

        setup_layout_command_test[
            "mock_layout_service"
        ].compile.return_value = mock_result

        # Mock Path objects to avoid file existence issues
        mock_keymap_path = Mock()
        mock_keymap_path.exists.return_value = False  # Avoid overwrite prompts
        mock_config_path = Mock()
        mock_config_path.exists.return_value = False

        setup_layout_command_test["mock_path_cls"].return_value.with_suffix.side_effect = [
            mock_keymap_path, mock_config_path
        ]
    elif "split" in command:
        mock_result = Mock()
        mock_result.success = success
        setup_layout_command_test[
            "mock_layout_service"
        ].decompose_components_from_file.return_value = mock_result
    elif "validate" in command:
        # Mock layout service validate method and layer reference validation
        setup_layout_command_test[
            "mock_layout_service"
        ].validate.return_value = success

        # Mock the LayoutData model's validate_layer_references method
        mock_layout_data = setup_layout_command_test["mock_layout_data"]
        mock_layout_data.validate_layer_references.return_value = []

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
    ].return_value.compile.return_value = build_result

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
            [
                "nonexistent.json",
                "--output",
                "output/test",
                "--profile",
                "glove80/v25.05",
            ],
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
            patch("glovebox.cli.commands.layout.core.Path") as mock_path_cls,
            patch("glovebox.cli.commands.firmware.compile.Path") as mock_path_cls2,
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
        ("config show", [], "Glovebox Configuration"),
    ],
)
def test_config_commands(
    command, args, output_contains, isolated_cli_environment, cli_runner
):
    """Test config commands."""
    # Run the command
    result = cli_runner.invoke(
        app,
        command.split() + args,
        catch_exceptions=True,
    )

    # Verify results
    if result.exit_code != 0:
        print(f"Command failed with exit code {result.exit_code}")
        print(f"Command output: {result.output}")
        print(f"Exception: {result.exception}")
    assert result.exit_code == 0
    assert output_contains in result.output


# Test status command
def test_status_command(cli_runner):
    """Test status command."""
    with patch("glovebox.cli.commands.status.collect_all_diagnostics") as mock_collect:
        # Mock comprehensive diagnostics data
        mock_diagnostics = {
            "version": "1.0.0",
            "system": {
                "environment": {
                    "platform": "Linux 6.12.28",
                    "python_version": "3.12.7",
                    "working_directory": "/test",
                },
                "file_system": {},
                "disk_space": {"available_gb": 10.0},
            },
            "docker": {
                "availability": "available",
                "version_info": {"client": "24.0.5", "server": "24.0.5"},
                "daemon_status": "running",
                "images": {},
                "capabilities": {},
            },
            "usb_flash": {
                "usb_detection": {"status": "available", "platform_adapter": "linux"},
                "detected_devices": [],
                "os_capabilities": {"mount_tool": "udisksctl"},
            },
            "configuration": {
                "user_config": {
                    "validation_status": "valid",
                    "found_config": "config.yml",
                    "environment_vars": {},
                },
                "keyboard_discovery": {
                    "found_keyboards": 1,
                    "keyboard_status": [
                        {"name": "glove80", "status": "valid", "has_firmwares": False}
                    ],
                },
            },
            "layout": {
                "processing": {"json_parsing": "available"},
                "zmk_generation": {"keymap_generation": "available"},
            },
        }
        mock_collect.return_value = mock_diagnostics

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
        assert "System Environment" in result.output
        assert "Docker" in result.output
        assert "Configuration" in result.output
        assert "Environment" in result.output
