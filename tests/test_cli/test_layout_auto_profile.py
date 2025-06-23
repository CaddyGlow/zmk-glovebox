"""Tests for layout command auto-profile detection functionality."""

import json
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
        "keyboard": "corne",
        "title": "Test Corne Layout",
        "layers": [
            ["&kp TAB", "&kp Q", "&kp W", "&kp E", "&kp R", "&kp T"],
            ["&kp ESC", "&kp A", "&kp S", "&kp D", "&kp F", "&kp G"],
        ],
        "layer_names": ["Base", "Lower"],
    }
    json_file = tmp_path / "test_layout.json"
    json_file.write_text(json.dumps(test_json))
    return json_file


def test_layout_compile_auto_profile_detection(
    cli_runner, sample_json_layout, tmp_path
):
    """Test layout compile command with auto-profile detection from JSON."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    with (
        patch(
            "glovebox.cli.commands.layout.core.resolve_profile_with_auto_detection"
        ) as mock_resolve_profile,
        patch(
            "glovebox.cli.commands.layout.core.create_profile_from_option"
        ) as mock_create_profile,
        patch(
            "glovebox.cli.commands.layout.core.create_layout_service"
        ) as mock_create_service,
        patch(
            "glovebox.cli.commands.layout.core.get_user_config_from_context"
        ) as mock_get_user_config,
    ):
        # Mock auto-profile detection
        mock_resolve_profile.return_value = "corne"

        # Mock profile creation
        mock_profile = Mock()
        mock_profile.keyboard_name = "corne"
        mock_profile.firmware_version = None
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

        # Run command without profile flag (should auto-detect)
        cmd_result = cli_runner.invoke(
            app,
            ["layout", "compile", str(output_dir / "test"), str(sample_json_layout)],
            catch_exceptions=False,
        )

        # Verify profile resolution was called
        assert mock_resolve_profile.called
        args = mock_resolve_profile.call_args[0]
        # args should be (profile, json_file, no_auto, user_config)
        assert args[0] is None  # No explicit profile provided
        assert args[1] == sample_json_layout  # JSON file path
        assert args[2] is False  # no_auto should be False

        # Verify layout service was called
        assert mock_layout_service.generate_from_file.called

        assert cmd_result.exit_code == 0


def test_layout_compile_no_auto_flag_disables_detection(
    cli_runner, sample_json_layout, tmp_path
):
    """Test that --no-auto flag disables auto-profile detection."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    with (
        patch(
            "glovebox.cli.commands.layout.core.resolve_profile_with_auto_detection"
        ) as mock_resolve_profile,
        patch(
            "glovebox.cli.commands.layout.core.create_profile_from_option"
        ) as mock_create_profile,
        patch(
            "glovebox.cli.commands.layout.core.create_layout_service"
        ) as mock_create_service,
        patch(
            "glovebox.cli.commands.layout.core.get_user_config_from_context"
        ) as mock_get_user_config,
    ):
        # Mock profile resolution (should not detect since no_auto=True)
        mock_resolve_profile.return_value = None

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

        # Run command with --no-auto flag
        cmd_result = cli_runner.invoke(
            app,
            [
                "layout",
                "compile",
                str(output_dir / "test"),
                str(sample_json_layout),
                "--no-auto",
                "--profile",
                "glove80/v25.05",
            ],
            catch_exceptions=False,
        )

        # Verify profile resolution was called with no_auto=True
        assert mock_resolve_profile.called
        args, kwargs = mock_resolve_profile.call_args
        assert args[2] is True  # no_auto parameter

        assert cmd_result.exit_code == 0


def test_layout_validate_auto_profile_detection(cli_runner, sample_json_layout):
    """Test layout validate command with auto-profile detection."""
    with (
        patch(
            "glovebox.cli.commands.layout.core.resolve_profile_with_auto_detection"
        ) as mock_resolve_profile,
        patch(
            "glovebox.cli.commands.layout.core.create_profile_from_option"
        ) as mock_create_profile,
        patch(
            "glovebox.cli.commands.layout.core.create_layout_service"
        ) as mock_create_service,
        patch(
            "glovebox.cli.commands.layout.core.get_user_config_from_context"
        ) as mock_get_user_config,
    ):
        # Mock profile resolution
        mock_resolve_profile.return_value = "corne"

        # Mock profile creation
        mock_profile = Mock()
        mock_profile.keyboard_name = "corne"
        mock_create_profile.return_value = mock_profile

        # Mock layout service
        mock_layout_service = Mock()
        mock_layout_service.validate_from_file.return_value = True
        mock_create_service.return_value = mock_layout_service

        # Mock user config
        mock_get_user_config.return_value = None

        # Run validate command
        cmd_result = cli_runner.invoke(
            app,
            ["layout", "validate", str(sample_json_layout)],
            catch_exceptions=False,
        )

        # Verify auto-profile detection was used
        assert mock_resolve_profile.called

        # Verify layout service was called
        assert mock_layout_service.validate_from_file.called

        assert cmd_result.exit_code == 0


def test_layout_show_auto_profile_detection(cli_runner, sample_json_layout):
    """Test layout show command with auto-profile detection."""
    with (
        patch(
            "glovebox.cli.commands.layout.core.resolve_profile_with_auto_detection"
        ) as mock_resolve_profile,
        patch(
            "glovebox.cli.commands.layout.core.create_profile_from_option"
        ) as mock_create_profile,
        patch(
            "glovebox.cli.commands.layout.core.create_layout_service"
        ) as mock_create_service,
        patch(
            "glovebox.cli.commands.layout.core.get_user_config_from_context"
        ) as mock_get_user_config,
    ):
        # Mock profile resolution
        mock_resolve_profile.return_value = "corne"

        # Mock profile creation
        mock_profile = Mock()
        mock_profile.keyboard_name = "corne"
        mock_create_profile.return_value = mock_profile

        # Mock layout service
        mock_layout_service = Mock()
        mock_layout_service.show_from_file.return_value = "Layout display output"
        mock_create_service.return_value = mock_layout_service

        # Mock user config
        mock_get_user_config.return_value = None

        # Run show command
        cmd_result = cli_runner.invoke(
            app,
            ["layout", "show", str(sample_json_layout)],
            catch_exceptions=False,
        )

        # Verify auto-profile detection was used
        assert mock_resolve_profile.called

        # Verify layout service was called
        assert mock_layout_service.show_from_file.called

        assert cmd_result.exit_code == 0


def test_layout_split_auto_profile_detection(cli_runner, sample_json_layout, tmp_path):
    """Test layout split command with auto-profile detection."""
    output_dir = tmp_path / "components"
    output_dir.mkdir()

    with (
        patch(
            "glovebox.cli.commands.layout.file_operations.resolve_profile_with_auto_detection"
        ) as mock_resolve_profile,
        patch(
            "glovebox.cli.commands.layout.file_operations.create_profile_from_option"
        ) as mock_create_profile,
        patch(
            "glovebox.cli.commands.layout.file_operations.create_layout_service"
        ) as mock_create_service,
        patch(
            "glovebox.cli.commands.layout.file_operations.get_user_config_from_context"
        ) as mock_get_user_config,
    ):
        # Mock profile resolution
        mock_resolve_profile.return_value = "corne"

        # Mock profile creation
        mock_profile = Mock()
        mock_profile.keyboard_name = "corne"
        mock_create_profile.return_value = mock_profile

        # Mock layout service
        mock_layout_service = Mock()
        from glovebox.layout.models import LayoutResult

        mock_result = LayoutResult(success=True)
        mock_layout_service.decompose_components_from_file.return_value = mock_result
        mock_create_service.return_value = mock_layout_service

        # Mock user config
        mock_get_user_config.return_value = None

        # Run split command with auto-profile detection
        cmd_result = cli_runner.invoke(
            app,
            ["layout", "split", str(output_dir), str(sample_json_layout)],
            catch_exceptions=False,
        )

        # Verify auto-profile detection was used
        assert mock_resolve_profile.called

        # Verify layout service was called
        assert mock_layout_service.decompose_components_from_file.called

        assert cmd_result.exit_code == 0


def test_layout_commands_cli_profile_overrides_auto_detection(
    cli_runner, sample_json_layout, tmp_path
):
    """Test that CLI profile flag overrides auto-detection across all layout commands."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    with (
        patch(
            "glovebox.cli.commands.layout.core.resolve_profile_with_auto_detection"
        ) as mock_resolve_profile,
        patch(
            "glovebox.cli.commands.layout.core.create_profile_from_option"
        ) as mock_create_profile,
        patch(
            "glovebox.cli.commands.layout.core.create_layout_service"
        ) as mock_create_service,
        patch(
            "glovebox.cli.commands.layout.core.get_user_config_from_context"
        ) as mock_get_user_config,
    ):
        # Mock profile resolution to return explicit profile
        mock_resolve_profile.return_value = "glove80/v25.05"

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
        mock_layout_service.validate_from_file.return_value = True
        mock_layout_service.show_from_file.return_value = "Layout display"
        mock_layout_service.decompose_components_from_file.return_value = mock_result
        mock_create_service.return_value = mock_layout_service

        # Mock user config
        mock_get_user_config.return_value = None

        # Test compile command with explicit profile
        cmd_result = cli_runner.invoke(
            app,
            [
                "layout",
                "compile",
                str(output_dir / "test"),
                str(sample_json_layout),
                "--profile",
                "glove80/v25.05",
            ],
            catch_exceptions=False,
        )

        # Verify profile resolution was called with explicit profile
        assert mock_resolve_profile.called
        args, kwargs = mock_resolve_profile.call_args
        assert args[0] == "glove80/v25.05"  # explicit profile parameter

        assert cmd_result.exit_code == 0
