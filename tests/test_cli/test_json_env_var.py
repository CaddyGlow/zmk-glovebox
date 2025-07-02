"""Tests for GLOVEBOX_JSON_FILE environment variable support across CLI commands."""

import json
import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.cli import app
from glovebox.cli.commands import register_all_commands


# Register commands with the app before running tests
register_all_commands(app)


@pytest.fixture
def sample_json_layout(tmp_path):
    """Create a sample JSON layout file for testing."""
    test_json = {
        "keyboard": "glove80",
        "title": "Test Glove80 Layout",
        "layers": [
            ["&kp TAB", "&kp Q", "&kp W", "&kp E", "&kp R", "&kp T"],
            ["&kp ESC", "&kp A", "&kp S", "&kp D", "&kp F", "&kp G"],
        ],
        "layer_names": ["Base", "Lower"],
    }
    json_file = tmp_path / "test_layout.json"
    json_file.write_text(json.dumps(test_json))
    return json_file


@pytest.fixture
def clean_env():
    """Ensure GLOVEBOX_JSON_FILE is not set in environment."""
    original_value = os.environ.get("GLOVEBOX_JSON_FILE")
    if "GLOVEBOX_JSON_FILE" in os.environ:
        del os.environ["GLOVEBOX_JSON_FILE"]
    yield
    if original_value is not None:
        os.environ["GLOVEBOX_JSON_FILE"] = original_value


def test_layout_compile_with_json_env_var(
    cli_runner, sample_json_layout, tmp_path, clean_env
):
    """Test layout compile command using GLOVEBOX_JSON_FILE environment variable."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Set environment variable
    os.environ["GLOVEBOX_JSON_FILE"] = str(sample_json_layout)

    with (
        patch(
            "glovebox.cli.commands.layout.core.create_profile_from_option"
        ) as mock_create_profile,
        patch(
            "glovebox.cli.commands.layout.dependencies.create_layout_service"
        ) as mock_create_service,
        patch(
            "glovebox.cli.commands.layout.core.get_user_config_from_context"
        ) as mock_get_user_config,
    ):
        # Mock profile creation
        mock_profile = Mock()
        mock_profile.keyboard_name = "glove80"
        mock_profile.firmware_version = "v25.05"
        mock_create_profile.return_value = mock_profile

        # Mock layout service
        mock_layout_service = Mock()
        from glovebox.layout.models import LayoutResult

        mock_result = LayoutResult(success=True)
        mock_result.keymap_path = output_dir / "test.keymap"
        mock_result.conf_path = output_dir / "test.conf"
        mock_result.json_path = output_dir / "test.json"
        mock_layout_service.generate_from_file.return_value = mock_result
        mock_create_service.return_value = mock_layout_service

        # Mock user config
        mock_get_user_config.return_value = None

        # Run command without JSON file argument (should use env var)
        cmd_result = cli_runner.invoke(
            app,
            [
                "layout",
                "compile",
                str(output_dir / "test"),
                "--profile",
                "glove80/v25.05",
            ],
            catch_exceptions=False,
        )

        # Verify layout service was called with the file from env var
        assert mock_layout_service.generate_from_file.called
        call_args = mock_layout_service.generate_from_file.call_args
        assert call_args.kwargs["json_file_path"] == sample_json_layout

        assert cmd_result.exit_code == 0


def test_layout_validate_with_json_env_var(cli_runner, sample_json_layout, clean_env):
    """Test layout validate command using GLOVEBOX_JSON_FILE environment variable."""
    # Set environment variable
    os.environ["GLOVEBOX_JSON_FILE"] = str(sample_json_layout)

    with (
        patch(
            "glovebox.cli.commands.layout.core.create_profile_from_option"
        ) as mock_create_profile,
        patch(
            "glovebox.cli.commands.layout.dependencies.create_layout_service"
        ) as mock_create_service,
        patch(
            "glovebox.cli.commands.layout.core.get_user_config_from_context"
        ) as mock_get_user_config,
    ):
        # Mock profile creation
        mock_profile = Mock()
        mock_profile.keyboard_name = "glove80"
        mock_create_profile.return_value = mock_profile

        # Mock layout service
        mock_layout_service = Mock()
        mock_layout_service.validate_from_file.return_value = True
        mock_create_service.return_value = mock_layout_service

        # Mock user config
        mock_get_user_config.return_value = None

        # Run command without JSON file argument (should use env var)
        cmd_result = cli_runner.invoke(
            app,
            ["layout", "validate", "--profile", "glove80/v25.05"],
            catch_exceptions=False,
        )

        # Verify layout service was called with the file from env var
        assert mock_layout_service.validate_from_file.called
        call_args = mock_layout_service.validate_from_file.call_args
        assert call_args.kwargs["json_file_path"] == sample_json_layout

        assert cmd_result.exit_code == 0


def test_layout_show_with_json_env_var(cli_runner, sample_json_layout, clean_env):
    """Test layout show command using GLOVEBOX_JSON_FILE environment variable."""
    # Set environment variable
    os.environ["GLOVEBOX_JSON_FILE"] = str(sample_json_layout)

    with (
        patch(
            "glovebox.cli.commands.layout.core.create_profile_from_option"
        ) as mock_create_profile,
        patch(
            "glovebox.cli.commands.layout.dependencies.create_layout_service"
        ) as mock_create_service,
        patch(
            "glovebox.cli.commands.layout.core.get_user_config_from_context"
        ) as mock_get_user_config,
    ):
        # Mock profile creation
        mock_profile = Mock()
        mock_profile.keyboard_name = "glove80"
        mock_create_profile.return_value = mock_profile

        # Mock layout service
        mock_layout_service = Mock()
        mock_layout_service.show_from_file.return_value = "Layout display output"
        mock_create_service.return_value = mock_layout_service

        # Mock user config
        mock_get_user_config.return_value = None

        # Run command without JSON file argument (should use env var)
        cmd_result = cli_runner.invoke(
            app,
            ["layout", "show", "--profile", "glove80/v25.05"],
            catch_exceptions=False,
        )

        # Verify layout service was called with the file from env var
        assert mock_layout_service.show_from_file.called
        call_args = mock_layout_service.show_from_file.call_args
        assert call_args.kwargs["json_file_path"] == sample_json_layout

        assert cmd_result.exit_code == 0


def test_layout_split_with_json_env_var(
    cli_runner, sample_json_layout, tmp_path, clean_env
):
    """Test layout split command using GLOVEBOX_JSON_FILE environment variable."""
    output_dir = tmp_path / "components"
    output_dir.mkdir()

    # Set environment variable
    os.environ["GLOVEBOX_JSON_FILE"] = str(sample_json_layout)

    with (
        patch(
            "glovebox.cli.commands.layout.file_operations.create_profile_from_option"
        ) as mock_create_profile,
        patch(
            "glovebox.cli.commands.layout.dependencies.create_layout_service"
        ) as mock_create_service,
        patch(
            "glovebox.cli.commands.layout.file_operations.get_user_config_from_context"
        ) as mock_get_user_config,
    ):
        # Mock profile creation
        mock_profile = Mock()
        mock_profile.keyboard_name = "glove80"
        mock_create_profile.return_value = mock_profile

        # Mock layout service
        mock_layout_service = Mock()
        from glovebox.layout.models import LayoutResult

        mock_result = LayoutResult(success=True)
        mock_layout_service.decompose_components_from_file.return_value = mock_result
        mock_create_service.return_value = mock_layout_service

        # Mock user config
        mock_get_user_config.return_value = None

        # Run command without JSON file argument (should use env var)
        cmd_result = cli_runner.invoke(
            app,
            ["layout", "split", str(output_dir), "--profile", "glove80/v25.05"],
            catch_exceptions=False,
        )

        # Verify layout service was called with the file from env var
        assert mock_layout_service.decompose_components_from_file.called
        call_args = mock_layout_service.decompose_components_from_file.call_args
        assert call_args.kwargs["json_file_path"] == sample_json_layout

        assert cmd_result.exit_code == 0


def test_firmware_compile_with_json_env_var(cli_runner, sample_json_layout, clean_env):
    """Test firmware compile command using GLOVEBOX_JSON_FILE environment variable."""
    # Set environment variable
    os.environ["GLOVEBOX_JSON_FILE"] = str(sample_json_layout)

    with (
        patch(
            "glovebox.cli.helpers.profile.create_profile_from_option"
        ) as mock_create_profile,
        patch(
            "glovebox.cli.commands.firmware._execute_compilation_from_json"
        ) as mock_compile,
        patch(
            "glovebox.cli.helpers.profile.get_user_config_from_context"
        ) as mock_get_user_config,
    ):
        # Mock profile creation
        mock_profile = Mock()
        mock_profile.keyboard_name = "glove80"
        mock_profile.firmware_version = "v25.05"
        mock_profile.keyboard_config.compile_methods = [Mock(method_type="zmk_config")]
        mock_create_profile.return_value = mock_profile

        # Mock user config
        mock_get_user_config.return_value = None

        # Mock compilation result
        from glovebox.firmware.models import BuildResult

        mock_result = BuildResult(success=True)
        mock_result.messages = ["Compilation successful"]
        mock_compile.return_value = mock_result

        # Run command without JSON file argument (should use env var)
        cmd_result = cli_runner.invoke(
            app,
            ["firmware", "compile", "--profile", "glove80/v25.05"],
            catch_exceptions=False,
        )

        # Verify compilation was called with the file from env var
        assert mock_compile.called
        call_args = mock_compile.call_args
        assert call_args[0][1] == sample_json_layout  # json_file parameter

        assert cmd_result.exit_code == 0


def test_cli_argument_overrides_env_var(
    cli_runner, sample_json_layout, tmp_path, clean_env
):
    """Test that CLI argument takes precedence over GLOVEBOX_JSON_FILE environment variable."""
    # Create a different JSON file
    other_json = {
        "keyboard": "corne",
        "title": "Other Layout",
        "layers": [["&kp A"]],
        "layer_names": ["Base"],
    }
    other_json_file = tmp_path / "other_layout.json"
    other_json_file.write_text(json.dumps(other_json))

    # Set environment variable to one file
    os.environ["GLOVEBOX_JSON_FILE"] = str(sample_json_layout)

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    with (
        patch(
            "glovebox.cli.commands.layout.core.create_profile_from_option"
        ) as mock_create_profile,
        patch(
            "glovebox.cli.commands.layout.dependencies.create_layout_service"
        ) as mock_create_service,
        patch(
            "glovebox.cli.commands.layout.core.get_user_config_from_context"
        ) as mock_get_user_config,
    ):
        # Mock profile creation
        mock_profile = Mock()
        mock_profile.keyboard_name = "corne"
        mock_create_profile.return_value = mock_profile

        # Mock layout service
        mock_layout_service = Mock()
        from glovebox.layout.models import LayoutResult

        mock_result = LayoutResult(success=True)
        mock_result.keymap_path = output_dir / "test.keymap"
        mock_result.conf_path = output_dir / "test.conf"
        mock_result.json_path = output_dir / "test.json"
        mock_layout_service.generate_from_file.return_value = mock_result
        mock_create_service.return_value = mock_layout_service

        # Mock user config
        mock_get_user_config.return_value = None

        # Run command with explicit JSON file argument (should override env var)
        cmd_result = cli_runner.invoke(
            app,
            [
                "layout",
                "compile",
                str(output_dir / "test"),
                str(other_json_file),  # Explicit argument should override env var
                "--profile",
                "corne",
            ],
            catch_exceptions=False,
        )

        # Verify layout service was called with the explicit file, not the env var
        assert mock_layout_service.generate_from_file.called
        call_args = mock_layout_service.generate_from_file.call_args
        assert call_args.kwargs["json_file_path"] == other_json_file
        assert call_args.kwargs["json_file_path"] != sample_json_layout

        assert cmd_result.exit_code == 0


def test_error_when_no_json_file_provided(cli_runner, tmp_path, clean_env):
    """Test error when neither CLI argument nor environment variable is provided."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Ensure no environment variable is set
    if "GLOVEBOX_JSON_FILE" in os.environ:
        del os.environ["GLOVEBOX_JSON_FILE"]

    # Run command without JSON file argument and no env var
    cmd_result = cli_runner.invoke(
        app,
        ["layout", "compile", str(output_dir / "test"), "--profile", "glove80/v25.05"],
        catch_exceptions=False,
    )

    # Should fail with error message
    assert cmd_result.exit_code == 1
    assert "JSON file is required" in cmd_result.output
    assert "GLOVEBOX_JSON_FILE" in cmd_result.output


def test_error_when_env_var_points_to_nonexistent_file(cli_runner, tmp_path, clean_env):
    """Test error when GLOVEBOX_JSON_FILE points to a non-existent file."""
    nonexistent_file = tmp_path / "nonexistent.json"

    # Set environment variable to non-existent file
    os.environ["GLOVEBOX_JSON_FILE"] = str(nonexistent_file)

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Run command (should fail with file not found error)
    cmd_result = cli_runner.invoke(
        app,
        ["layout", "compile", str(output_dir / "test"), "--profile", "glove80/v25.05"],
        catch_exceptions=False,
    )

    # Should fail with file not found error
    assert cmd_result.exit_code == 1
    assert "not found" in cmd_result.output.lower()


def test_combined_env_var_and_auto_profile_detection(
    cli_runner, sample_json_layout, clean_env
):
    """Test that both GLOVEBOX_JSON_FILE and auto-profile detection work together."""
    # Set environment variable
    os.environ["GLOVEBOX_JSON_FILE"] = str(sample_json_layout)

    with (
        patch(
            "glovebox.cli.commands.layout.core.resolve_profile_with_auto_detection"
        ) as mock_resolve_profile,
        patch(
            "glovebox.cli.commands.layout.core.create_profile_from_option"
        ) as mock_create_profile,
        patch(
            "glovebox.cli.commands.layout.dependencies.create_layout_service"
        ) as mock_create_service,
        patch(
            "glovebox.cli.commands.layout.core.get_user_config_from_context"
        ) as mock_get_user_config,
    ):
        # Mock auto-profile detection (should detect "glove80" from sample JSON)
        mock_resolve_profile.return_value = "glove80"

        # Mock profile creation
        mock_profile = Mock()
        mock_profile.keyboard_name = "glove80"
        mock_create_profile.return_value = mock_profile

        # Mock layout service
        mock_layout_service = Mock()
        mock_layout_service.validate_from_file.return_value = True
        mock_create_service.return_value = mock_layout_service

        # Mock user config
        mock_get_user_config.return_value = None

        # Run command without JSON file or profile (should use env var + auto-detect)
        cmd_result = cli_runner.invoke(
            app,
            ["layout", "validate"],
            catch_exceptions=False,
        )

        # Verify both env var resolution and auto-profile detection were used
        assert mock_resolve_profile.called
        args = mock_resolve_profile.call_args[0]
        assert args[1] == sample_json_layout  # JSON file from env var
        assert args[2] is False  # no_auto should be False

        assert cmd_result.exit_code == 0
