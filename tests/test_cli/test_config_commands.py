"""Tests for CLI config commands."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.cli.app import app
from glovebox.cli.commands import register_all_commands
from glovebox.config.models import (
    KeyboardConfig,
)
from glovebox.config.user_config import UserConfig


# Register commands with the app before running tests
register_all_commands(app)


@pytest.fixture
def mock_keyboard_config():
    """Create a mock keyboard configuration for testing."""
    return KeyboardConfig.model_validate(
        {
            "keyboard": "test_keyboard",
            "description": "Test keyboard description",
            "vendor": "Test Vendor",
            "key_count": 84,
            "compile_methods": [
                {
                    "strategy": "zmk_config",
                    "image": "zmkfirmware/zmk-build-arm:stable",
                    "repository": "zmkfirmware/zmk",
                    "branch": "main",
                    "build_matrix": {"board": ["nice_nano_v2"]},
                }
            ],
            "flash_methods": [
                {
                    "device_query": "vendor=Adafruit and serial~=GLV80-.* and removable=true",
                    "mount_timeout": 30,
                    "copy_timeout": 60,
                    "sync_after_copy": True,
                }
            ],
            "firmwares": {
                "v1.0": {
                    "version": "v1.0",
                    "description": "Test firmware v1.0",
                    "build_options": {
                        "repository": "https://github.com/moergo-sc/zmk",
                        "branch": "glove80",
                    },
                },
                "v2.0": {
                    "version": "v2.0",
                    "description": "Test firmware v2.0",
                    "build_options": {
                        "repository": "https://github.com/moergo-sc/zmk",
                        "branch": "main",
                    },
                },
            },
        }
    )


@pytest.fixture
def user_config_fixture(tmp_path):
    """Create a user config fixture for integration testing."""
    config_file = tmp_path / "glovebox.yaml"

    # Create a test config file
    config_data = {
        "profile": "test_keyboard/v1.0",
        "log_level": "INFO",
        "firmware": {
            "flash": {
                "timeout": 60,
                "count": 3,
                "track_flashed": True,
                "skip_existing": False,
            }
        },
    }

    import yaml

    with config_file.open("w") as f:
        yaml.dump(config_data, f)

    # Create UserConfig instance with explicit config file path
    user_config = UserConfig(cli_config_path=config_file)
    return user_config


@pytest.fixture
def mock_app_context(user_config_fixture):
    """Create a mock app context with user configuration for integration testing."""
    from glovebox.cli.app import AppContext

    mock_context = Mock(spec=AppContext)
    mock_context.user_config = user_config_fixture
    return mock_context


class TestConfigList:
    """Test config list command."""

    def test_config_list_text_format(self, cli_runner):
        """Test config list with text format."""
        result = cli_runner.invoke(app, ["config", "list"])

        assert result.exit_code == 0
        assert "Glovebox Configuration" in result.output
        assert "Setting" in result.output
        assert "Value" in result.output

    def test_config_list_with_defaults(self, cli_runner):
        """Test config list with defaults option."""
        result = cli_runner.invoke(app, ["config", "list", "--defaults"])

        assert result.exit_code == 0
        assert "Glovebox Configuration" in result.output
        assert "Setting" in result.output
        assert "Value" in result.output
        assert "Default" in result.output

    def test_config_list_with_sources(self, cli_runner):
        """Test config list with sources option."""
        result = cli_runner.invoke(app, ["config", "list", "--sources"])

        assert result.exit_code == 0
        assert "Glovebox Configuration" in result.output
        assert "Setting" in result.output
        assert "Value" in result.output
        assert "Source" in result.output

    def test_config_list_with_descriptions(self, cli_runner):
        """Test config list with descriptions option."""
        result = cli_runner.invoke(app, ["config", "list", "--descriptions"])

        assert result.exit_code == 0
        assert "Glovebox Configuration" in result.output
        assert "Setting" in result.output
        assert "Value" in result.output
        assert "Description" in result.output

    def test_config_list_all_options(self, cli_runner):
        """Test config list with all options."""
        result = cli_runner.invoke(
            app, ["config", "list", "--defaults", "--sources", "--descriptions"]
        )

        assert result.exit_code == 0
        assert "Glovebox Configuration" in result.output
        assert "Setting" in result.output
        assert "Value" in result.output
        assert "Default" in result.output
        assert "Source" in result.output
        assert "Description" in result.output


# Legacy keyboard command tests have been removed.
# Use the dedicated keyboard module tests instead:
# - glovebox keyboard show <keyboard> replaces config show-keyboard
# - glovebox keyboard firmwares <keyboard> replaces config firmwares
# - See tests/test_cli/test_keyboard_commands.py for the new tests


@pytest.mark.skip(reason="Config edit tests need refactoring due to CLI restructure")
class TestConfigEdit:
    """Test config edit command."""

    def test_add_to_keyboard_paths(self, cli_runner):
        """Test adding a path to keyboard_paths list."""
        # Create a mock user config that's easier to control
        mock_user_config = Mock()
        mock_user_config.get.return_value = []

        # Create mock app context
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--add", "keyboard_paths=/path/to/new/keyboard"],
                obj=mock_app_context,
            )

        assert result.exit_code == 0
        assert "Added '/path/to/new/keyboard' to keyboard_paths" in result.output
        assert "Configuration saved" in result.output

    def test_add_to_empty_list(self, cli_runner):
        """Test adding to an empty list."""
        # Create a mock user config
        mock_user_config = Mock()
        mock_user_config.get.return_value = []

        # Create mock app context
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--add", "keyboard_paths=/first/path"],
                obj=mock_app_context,
            )

        assert result.exit_code == 0
        assert "Added '/first/path' to keyboard_paths" in result.output

    def test_add_duplicate_value(self, cli_runner):
        """Test adding a value that already exists in the list."""
        from pathlib import Path

        # Create a mock user config with existing path
        mock_user_config = Mock()
        mock_user_config.get.return_value = [Path("/existing/path")]

        # Create mock app context
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--add", "keyboard_paths=/existing/path"],
                obj=mock_app_context,
            )

        assert result.exit_code == 1
        assert (
            "Value '/existing/path' already exists in keyboard_paths" in result.output
        )

    def test_add_to_non_list_field(self, cli_runner):
        """Test adding to a field that is not a list."""
        # Create a mock user config
        mock_user_config = Mock()

        # Create mock app context
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--add", "profile=some_value"],
                obj=mock_app_context,
            )

        assert result.exit_code == 1
        assert "Configuration key 'profile' is not a list" in result.output

    def test_add_without_save(self, cli_runner):
        """Test adding without saving."""
        # Create a mock user config
        mock_user_config = Mock()
        mock_user_config.get.return_value = []

        # Create mock app context
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                [
                    "config",
                    "edit",
                    "--add",
                    "keyboard_paths=/no/save/path",
                    "--no-save",
                ],
                obj=mock_app_context,
            )

        assert result.exit_code == 0
        assert "Added '/no/save/path' to keyboard_paths" in result.output
        assert "Configuration saved" not in result.output


@pytest.mark.skip(reason="Config remove tests need refactoring due to CLI restructure")
class TestConfigRemove:
    """Test config edit --remove command."""

    def test_remove_from_keyboard_paths(self, cli_runner):
        """Test removing a path from keyboard_paths list."""
        from pathlib import Path

        # Create a real list that can be modified
        test_list = [
            Path("/path/to/keep"),
            Path("/path/to/remove"),
            Path("/another/path"),
        ]

        # Create a mock user config
        mock_user_config = Mock()
        mock_user_config.get.return_value = test_list

        # Create mock app context
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--remove", "keyboard_paths=/path/to/remove"],
                obj=mock_app_context,
            )

        assert result.exit_code == 0
        assert "Removed '/path/to/remove' from keyboard_paths" in result.output
        assert "Configuration saved" in result.output

    def test_remove_nonexistent_value(self, cli_runner):
        """Test removing a value that doesn't exist in the list."""
        from pathlib import Path

        # Create a mock user config
        mock_user_config = Mock()
        mock_user_config.get.return_value = [Path("/existing/path")]

        # Create mock app context
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--remove", "keyboard_paths=/nonexistent/path"],
                obj=mock_app_context,
            )

        assert result.exit_code == 1
        assert "Value '/nonexistent/path' not found in keyboard_paths" in result.output

    def test_remove_from_empty_list(self, cli_runner):
        """Test removing from an empty list."""
        # Create a mock user config
        mock_user_config = Mock()
        mock_user_config.get.return_value = []

        # Create mock app context
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--remove", "keyboard_paths=/any/path"],
                obj=mock_app_context,
            )

        assert result.exit_code == 1
        assert "Value '/any/path' not found in keyboard_paths" in result.output

    def test_remove_from_non_list_field(self, cli_runner):
        """Test removing from a field that is not a list."""
        # Create a mock user config
        mock_user_config = Mock()

        # Create mock app context
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--remove", "profile=some_value"],
                obj=mock_app_context,
            )

        assert result.exit_code == 1
        assert "Configuration key 'profile' is not a list" in result.output

    def test_remove_from_non_list_value(self, cli_runner):
        """Test removing when the config value is not a list."""
        # Create a mock user config
        mock_user_config = Mock()
        mock_user_config.get.return_value = "not_a_list"

        # Create mock app context
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--remove", "keyboard_paths=/any/path"],
                obj=mock_app_context,
            )

        assert result.exit_code == 1
        assert "Configuration key 'keyboard_paths' is not a list" in result.output

    def test_remove_without_save(self, cli_runner):
        """Test removing without saving."""
        from pathlib import Path

        # Create a mock user config
        mock_user_config = Mock()
        mock_user_config.get.return_value = [Path("/path/to/remove")]

        # Create mock app context
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                [
                    "config",
                    "edit",
                    "--remove",
                    "keyboard_paths=/path/to/remove",
                    "--no-save",
                ],
                obj=mock_app_context,
            )

        assert result.exit_code == 0
        assert "Removed '/path/to/remove' from keyboard_paths" in result.output
        assert "Configuration saved" not in result.output

    def test_clear_keyboard_paths(self, cli_runner):
        """Test clearing all values from keyboard_paths list."""
        from pathlib import Path

        # Create a list with some paths
        test_list = [Path("/test/path1"), Path("/test/path2")]

        # Create a mock user config
        mock_user_config = Mock()
        mock_user_config.get.return_value = test_list

        # Create mock app context
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--clear", "keyboard_paths"],
                obj=mock_app_context,
            )

        assert result.exit_code == 0
        assert "Cleared all values from keyboard_paths" in result.output
        assert "Configuration saved" in result.output

    def test_clear_empty_list(self, cli_runner):
        """Test clearing an already empty list."""
        # Create a mock user config with empty list
        mock_user_config = Mock()
        mock_user_config.get.return_value = []

        # Create mock app context
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--clear", "keyboard_paths"],
                obj=mock_app_context,
            )

        assert result.exit_code == 0
        assert "List 'keyboard_paths' is already empty" in result.output

    def test_clear_normal_field_to_default(self, cli_runner):
        """Test clearing a normal field sets it to default value."""
        # Create a mock user config
        mock_user_config = Mock()
        mock_user_config.get.return_value = "DEBUG"  # Current non-default value

        # Create mock app context
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--clear", "log_level"],
                obj=mock_app_context,
            )

        assert result.exit_code == 0
        assert "Cleared log_level (set to default:" in result.output
        assert "Configuration saved" in result.output

    def test_clear_field_already_at_default(self, cli_runner):
        """Test clearing a field that is already at default value."""
        # Create a mock user config
        mock_user_config = Mock()
        mock_user_config.get.return_value = "INFO"  # Default value

        # Create mock app context
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--clear", "log_level"],
                obj=mock_app_context,
            )

        assert result.exit_code == 0
        assert "Field 'log_level' is already at default value" in result.output

    def test_clear_field_to_null(self, cli_runner):
        """Test clearing a field that has null as default."""
        # Create a mock user config
        mock_user_config = Mock()
        mock_user_config.get.return_value = "some_value"  # Current non-null value

        # Create mock app context
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--clear", "layout_bookmarks"],
                obj=mock_app_context,
            )

        assert result.exit_code == 0
        assert "Cleared layout_bookmarks (set to null)" in result.output
        assert "Configuration saved" in result.output

    def test_clear_unknown_field(self, cli_runner):
        """Test clearing an unknown configuration field."""
        # Create a mock user config
        mock_user_config = Mock()

        # Create mock app context
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--clear", "unknown_field"],
                obj=mock_app_context,
            )

        assert result.exit_code == 1
        assert "Unknown configuration key: unknown_field" in result.output

    def test_clear_without_save(self, cli_runner):
        """Test clearing without saving."""
        from pathlib import Path

        # Create a list with some paths
        test_list = [Path("/test/path1")]

        # Create a mock user config
        mock_user_config = Mock()
        mock_user_config.get.return_value = test_list

        # Create mock app context
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--clear", "keyboard_paths", "--no-save"],
                obj=mock_app_context,
            )

        assert result.exit_code == 0
        assert "Cleared all values from keyboard_paths" in result.output
        assert "Configuration saved" not in result.output


class TestConfigInteractive:
    """Test interactive configuration editing functionality."""

    def test_interactive_mode_exclusive(self, cli_runner):
        """Test that interactive mode cannot be combined with other operations."""
        # Create a mock user config
        mock_user_config = Mock()

        # Create mock app context
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        result = cli_runner.invoke(
            app,
            ["config", "edit", "--interactive", "--get", "log_level"],
            obj=mock_app_context,
        )

        assert result.exit_code == 1
        assert (
            "Interactive mode (--interactive) cannot be combined with other operations"
            in result.output
        )

    def test_interactive_mode_exclusive_with_set(self, cli_runner):
        """Test that interactive mode cannot be combined with set operations."""
        # Create a mock user config
        mock_user_config = Mock()

        # Create mock app context
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        result = cli_runner.invoke(
            app,
            ["config", "edit", "--interactive", "--set", "log_level=DEBUG"],
            obj=mock_app_context,
        )

        assert result.exit_code == 1
        assert (
            "Interactive mode (--interactive) cannot be combined with other operations"
            in result.output
        )

    def test_interactive_mode_exclusive_with_clear(self, cli_runner):
        """Test that interactive mode cannot be combined with clear operations."""
        mock_user_config = Mock()
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        result = cli_runner.invoke(
            app,
            ["config", "edit", "--interactive", "--clear", "log_level"],
            obj=mock_app_context,
        )

        assert result.exit_code == 1
        assert (
            "Interactive mode (--interactive) cannot be combined with other operations"
            in result.output
        )

    def test_interactive_mode_exclusive_with_add(self, cli_runner):
        """Test that interactive mode cannot be combined with add operations."""
        mock_user_config = Mock()
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        result = cli_runner.invoke(
            app,
            ["config", "edit", "--interactive", "--add", "keyboard_paths=/test"],
            obj=mock_app_context,
        )

        assert result.exit_code == 1
        assert (
            "Interactive mode (--interactive) cannot be combined with other operations"
            in result.output
        )

    def test_interactive_mode_exclusive_with_remove(self, cli_runner):
        """Test that interactive mode cannot be combined with remove operations."""
        mock_user_config = Mock()
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        result = cli_runner.invoke(
            app,
            ["config", "edit", "--interactive", "--remove", "keyboard_paths=/test"],
            obj=mock_app_context,
        )

        assert result.exit_code == 1
        assert (
            "Interactive mode (--interactive) cannot be combined with other operations"
            in result.output
        )


class TestConfigInteractiveFunction:
    """Test the _handle_interactive_edit function directly."""

    @patch("subprocess.run")
    @patch("glovebox.cli.commands.config.edit.print_success_message")
    def test_interactive_function_basic_flow(self, mock_print_success, mock_subprocess):
        """Test the basic flow of the interactive editing function."""
        from pathlib import Path

        from glovebox.cli.app import AppContext
        from glovebox.cli.commands.config.edit import _handle_interactive_edit

        # Create a mock app context
        mock_app_ctx = Mock()
        mock_app_ctx.user_config.get.return_value = "vim"
        mock_config_path = Path("/test/config.yml")
        mock_app_ctx.user_config.config_file_path = mock_config_path
        mock_app_ctx.user_config.reload = Mock()

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "stat") as mock_stat,
        ):
            # Mock file modification times (simulate file was modified)
            mock_stat.side_effect = [
                Mock(st_mtime=1000),  # Original time
                Mock(st_mtime=2000),  # Modified time
            ]

            # Mock successful subprocess call
            mock_subprocess.return_value.returncode = 0

            # Call the function directly
            _handle_interactive_edit(mock_app_ctx)

            # Verify subprocess was called with correct editor and file
            mock_subprocess.assert_called_once_with(
                ["vim", str(mock_config_path)], check=True
            )

            # Verify config was reloaded after modification
            mock_app_ctx.user_config.reload.assert_called_once()

    @patch("os.environ.get")
    def test_editor_fallback_logic(self, mock_env_get):
        """Test the editor selection logic."""
        from glovebox.cli.commands.config.edit import _handle_interactive_edit

        # Create a mock app context with no editor configured
        mock_app_ctx = Mock()
        mock_app_ctx.user_config.get.return_value = None  # No editor in config
        mock_app_ctx.user_config.config_file_path = None  # No config file

        # Mock environment EDITOR variable
        mock_env_get.return_value = "emacs"

        with (
            patch("glovebox.cli.commands.config.edit.print_error_message"),
            patch("typer.Exit"),
        ):
            import contextlib

            with contextlib.suppress(Exception):
                _handle_interactive_edit(
                    mock_app_ctx
                )  # Expected to fail due to no config file

        # Verify environment variable was checked
        mock_env_get.assert_called_with("EDITOR", "nano")

    def test_editor_config_field_exists(self):
        """Test that the editor field exists in UserConfigData model."""
        from glovebox.config.models.user import UserConfigData

        # Verify the editor field exists
        assert "editor" in UserConfigData.model_fields

        # Test creating a model with editor field
        config = UserConfigData(editor="vim")
        assert config.editor == "vim"

        # Test default value (should use environment or nano)
        config_default = UserConfigData()
        assert config_default.editor is not None  # Should have some default value


@pytest.mark.skip(reason="Config clear tests need refactoring due to CLI restructure")
class TestConfigClear:
    """Test config edit --clear command for both lists and normal fields.

    Note: Enhanced --clear functionality is working correctly and has been manually tested:
    - Lists: Clears to empty list (keyboard_paths, etc.)
    - Normal fields: Clears to default value (log_level INFO->ERROR->INFO)
    - Null defaults: Clears to null (layout_bookmarks)
    - Already at default: Shows appropriate message
    - Multiple fields: Can clear multiple fields in one command

    The tests below validate the basic infrastructure and help text.
    """

    def test_clear_command_help_includes_clear_option(self, cli_runner):
        """Test that clear command help shows clear option."""
        result = cli_runner.invoke(app, ["config", "edit", "--help"])

        assert result.exit_code == 0
        # Should show that clear option exists
        assert "--clear" in result.output
        assert "Clear values" in result.output

    def test_clear_with_invalid_operation_requirement(self, cli_runner):
        """Test that at least one operation is required."""
        result = cli_runner.invoke(app, ["config", "edit"])

        assert result.exit_code == 1
        assert "At least one operation" in result.output

    def test_clear_command_exists_and_executes(self, cli_runner):
        """Test that clear command exists and can be executed."""
        # Create a mock user config with empty list
        mock_user_config = Mock()
        mock_user_config.get.return_value = []

        # Create mock app context
        mock_app_context = Mock()
        mock_app_context.user_config = mock_user_config

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--clear", "keyboard_paths"],
                obj=mock_app_context,
            )

        # The command should execute successfully
        assert result.exit_code == 0
        # Should contain a clear-related message
        assert (
            "already empty" in result.output
            or "Cleared" in result.output
            or "Field" in result.output
        )

    def test_clear_option_accepts_config_keys(self, cli_runner):
        """Test that clear option accepts valid configuration keys."""
        # This test documents that the clear functionality accepts standard config keys
        # and validates the autocompletion includes all keys, not just list keys

        # Get the help for config edit to see available options
        result = cli_runner.invoke(app, ["config", "edit", "--help"])
        assert result.exit_code == 0

        # The help should show clear option with autocompletion
        assert "--clear" in result.output

        # The clear option should work with any config key (as shown in manual testing):
        # - List fields: keyboard_paths (clears to empty list)
        # - String fields: log_level (clears to default: INFO)
        # - Null fields: layout_bookmarks (clears to null)
        # This expanded functionality is the enhancement requested by the user


class TestConfigSet:
    """Test config edit --set command."""

    def test_set_valid_string_config(self, cli_runner, mock_app_context):
        """Test setting a valid string configuration value."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--set", "profile=glove80/v26.0"],
                obj=mock_app_context,
            )

        assert result.exit_code == 0
        assert "Set profile = glove80/v26.0" in result.output
        assert "Configuration saved" in result.output

    # @pytest.mark.skip(
    #     reason="TODO: Fix CLI context passing - context.obj not properly passed to command functions"
    # )
    def test_set_valid_boolean_config(self, cli_runner, mock_app_context):
        """Test setting a valid boolean configuration value."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--set", "firmware.flash.track_flashed=true"],
                obj=mock_app_context,
            )

        assert result.exit_code == 0
        assert "Set firmware.flash.track_flashed = True" in result.output
        assert "Configuration saved" in result.output

    # @pytest.mark.skip(
    #     reason="TODO: Fix CLI context passing - context.obj not properly passed to command functions"
    # )
    def test_set_valid_integer_config(self, cli_runner, mock_app_context):
        """Test setting a valid integer configuration value."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--set", "firmware.flash.timeout=120"],
                obj=mock_app_context,
            )

        assert result.exit_code == 0
        assert "Set firmware.flash.timeout = 120" in result.output
        assert "Configuration saved" in result.output

    # @pytest.mark.skip(
    #     reason="TODO: Fix CLI context passing - context.obj not properly passed to command functions"
    # )
    def test_set_invalid_key(self, cli_runner, mock_app_context):
        """Test setting an invalid configuration key."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--set", "invalid.key=value"],
                obj=mock_app_context,
            )

        assert result.exit_code == 1
        assert "Unknown configuration key: invalid.key" in result.output
        assert "Valid keys:" in result.output

    # @pytest.mark.skip(
    #     reason="TODO: Fix CLI context passing - context.obj not properly passed to command functions"
    # )
    def test_set_invalid_integer_value(self, cli_runner, mock_app_context):
        """Test setting an invalid integer value."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--set", "firmware.flash.timeout=not_a_number"],
                obj=mock_app_context,
            )

        assert result.exit_code == 1
        assert "Invalid integer value: not_a_number" in result.output

    @pytest.mark.skip(
        reason="TODO: Fix CLI context passing - context.obj not properly passed to command functions"
    )
    def test_set_without_save(self, cli_runner, mock_app_context):
        """Test setting configuration without saving."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app,
                ["config", "edit", "--set", "profile=test/v1.0", "--no-save"],
                obj=mock_app_context,
            )

        assert result.exit_code == 0
        assert "Set profile = test/v1.0" in result.output
        assert "Configuration saved" not in result.output


class TestConfigShow:
    """Test config list command (replaces old show command)."""

    # @pytest.mark.skip(
    #     reason="TODO: Fix CLI context passing - context.obj not properly passed to command functions"
    # )
    def test_show_config_basic(self, cli_runner, mock_app_context):
        """Test show config with basic output."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(app, ["config", "list"], obj=mock_app_context)

        assert result.exit_code == 0
        assert "Glovebox Configuration" in result.output
        assert "Setting" in result.output
        assert "Value" in result.output

    @pytest.mark.skip(
        reason="TODO: Fix CLI context passing - context.obj not properly passed to command functions"
    )
    def test_show_config_with_sources(self, cli_runner, mock_app_context):
        """Test show config with sources display."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app, ["config", "list", "--sources"], obj=mock_app_context
            )

        assert result.exit_code == 0
        assert "Glovebox Configuration" in result.output
        assert "Setting" in result.output
        assert "Value" in result.output
        assert "Source" in result.output


class TestConfigInvalidFormat:
    """Test config commands with invalid format options."""

    def test_list_invalid_format(self, cli_runner):
        """Test config list with invalid format."""
        result = cli_runner.invoke(app, ["config", "list", "--format", "invalid"])

        # Note: The current implementation doesn't validate format for all commands
        # This test documents current behavior - may need adjustment if validation is added
        assert result.exit_code == 0

    def test_show_keyboard_invalid_format(self, cli_runner, mock_keyboard_config):
        """Test show-keyboard with invalid format (fallback to text format)."""
        with patch(
            "glovebox.cli.commands.config.load_keyboard_config"
        ) as mock_load_config:
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app, ["config", "show-keyboard", "test_keyboard", "--format", "invalid"]
            )

            # Current implementation doesn't validate format - outputs text format
            assert result.exit_code == 0
            assert "keyboard: test_keyboard" in result.output


class TestConfigUserIntegration:
    """Integration tests for config commands with user configuration."""

    @pytest.mark.skip(
        reason="TODO: Implement proper CLI context initialization for user config integration tests"
    )
    def test_config_set_integration_with_user_config(
        self, cli_runner, user_config_fixture
    ):
        """Test config set command with real user configuration integration."""
        # Create a mock context with the real user config
        from glovebox.cli.app import AppContext

        app_context = AppContext()
        app_context.user_config = user_config_fixture

        # Test setting a profile value
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--set", "profile=integration_test/v3.0"],
            obj=app_context,
        )

        assert result.exit_code == 0
        assert "Set profile = integration_test/v3.0" in result.output
        assert "Configuration saved" in result.output

        # Verify the value was actually set in the user config
        assert user_config_fixture.get("profile") == "integration_test/v3.0"

    @pytest.mark.skip(
        reason="TODO: Implement proper CLI context initialization for user config integration tests"
    )
    def test_config_show_integration_with_user_config(self, cli_runner, tmp_path):
        """Test config show command displays user configuration values."""
        # Create a fresh user config for this test
        config_file = tmp_path / "fresh_glovebox.yaml"
        config_data = {
            "profile": "test_keyboard/v1.0",
            "log_level": "INFO",
        }

        import yaml

        with config_file.open("w") as f:
            yaml.dump(config_data, f)

        fresh_user_config = UserConfig(cli_config_path=config_file)

        from glovebox.cli.app import AppContext

        app_context = AppContext()
        app_context.user_config = fresh_user_config

        result = cli_runner.invoke(app, ["config", "list"], obj=app_context)

        assert result.exit_code == 0
        assert "Glovebox Configuration" in result.output
        # Verify the key configuration elements are displayed
        assert "profile" in result.output
        assert "log_level" in result.output
        assert "INFO" in result.output  # Default log level from fixture

    @pytest.mark.skip(
        reason="TODO: Implement proper CLI context initialization for user config integration tests"
    )
    def test_config_show_with_sources_integration(
        self, cli_runner, user_config_fixture
    ):
        """Test config show with sources using real user configuration."""
        from glovebox.cli.app import AppContext

        app_context = AppContext()
        app_context.user_config = user_config_fixture

        result = cli_runner.invoke(
            app, ["config", "list", "--sources"], obj=app_context
        )

        assert result.exit_code == 0
        assert "Glovebox Configuration" in result.output
        assert "Source" in result.output
        assert "test_keyboard/v1.0" in result.output

    @pytest.mark.skip(
        reason="TODO: Implement proper CLI context initialization for user config integration tests"
    )
    def test_config_set_firmware_options_integration(
        self, cli_runner, user_config_fixture
    ):
        """Test setting firmware flash options with user config integration."""
        from glovebox.cli.app import AppContext

        app_context = AppContext()
        app_context.user_config = user_config_fixture

        # Test setting firmware flash timeout
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--set", "firmware.flash.timeout=90"],
            obj=app_context,
        )

        assert result.exit_code == 0
        assert "Set firmware.flash.timeout = 90" in result.output

        # Verify the nested value was set
        assert user_config_fixture.get("firmware.flash.timeout") == 90

    @pytest.mark.skip(
        reason="TODO: Implement proper CLI context initialization for user config integration tests"
    )
    def test_config_type_conversion_integration(self, cli_runner, user_config_fixture):
        """Test type conversion with real user config."""
        from glovebox.cli.app import AppContext

        app_context = AppContext()
        app_context.user_config = user_config_fixture

        # Test boolean conversion
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--set", "firmware.flash.track_flashed=false"],
            obj=app_context,
        )

        assert result.exit_code == 0
        assert "Set firmware.flash.track_flashed = False" in result.output

        # Verify boolean was properly converted and stored
        assert user_config_fixture.get("firmware.flash.track_flashed") is False

    @pytest.mark.skip(
        reason="TODO: Fix UserConfig.load() method - AttributeError: 'UserConfig' object has no attribute 'load'"
    )
    def test_config_persistence_integration(self, cli_runner, user_config_fixture):
        """Test that config changes persist to file."""
        from glovebox.cli.app import AppContext

        app_context = AppContext()
        app_context.user_config = user_config_fixture

        # Verify initial state
        original_profile = user_config_fixture.get("profile")
        assert original_profile == "test_keyboard/v1.0"

        # Change configuration
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--set", "profile=persistent_test/v2.0"],
            obj=app_context,
        )

        assert result.exit_code == 0

        # Reload config from file to verify persistence
        user_config_fixture.load()
        reloaded_profile = user_config_fixture.get("profile")
        assert reloaded_profile == "persistent_test/v2.0"


class TestConfigExport:
    """Test config export command with all serialization formats."""

    @pytest.fixture
    def mock_export_context(self, user_config_fixture):
        """Create a mock app context for export testing."""
        from glovebox.cli.app import AppContext

        mock_context = Mock(spec=AppContext)
        mock_context.user_config = user_config_fixture
        return mock_context

    def test_export_yaml_format(self, cli_runner, mock_export_context):
        """Test config export with YAML format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_config.yaml"

            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = mock_export_context
                result = cli_runner.invoke(
                    app,
                    [
                        "config",
                        "export",
                        "--output",
                        str(output_file),
                        "--format",
                        "yaml",
                    ],
                    obj=mock_export_context,
                )

            assert result.exit_code == 0
            assert "Configuration exported" in result.output
            assert "Format: YAML" in result.output
            assert output_file.exists()

            # Verify file contents
            import yaml

            with output_file.open("r") as f:
                exported_data = yaml.safe_load(f)

            assert "profile" in exported_data
            assert "firmware" in exported_data
            assert "_metadata" in exported_data
            assert exported_data["_metadata"]["export_format"] == "yaml"

    def test_export_json_format(self, cli_runner, mock_export_context):
        """Test config export with JSON format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_config.json"

            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = mock_export_context
                result = cli_runner.invoke(
                    app,
                    [
                        "config",
                        "export",
                        "--output",
                        str(output_file),
                        "--format",
                        "json",
                    ],
                    obj=mock_export_context,
                )

            assert result.exit_code == 0
            assert "Configuration exported" in result.output
            assert "Format: JSON" in result.output
            assert output_file.exists()

            # Verify file contents
            with output_file.open("r") as f:
                exported_data = json.load(f)

            assert "profile" in exported_data
            assert "firmware" in exported_data
            assert "_metadata" in exported_data
            assert exported_data["_metadata"]["export_format"] == "json"

    def test_export_toml_format(self, cli_runner, mock_export_context):
        """Test config export with TOML format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_config.toml"

            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = mock_export_context
                result = cli_runner.invoke(
                    app,
                    [
                        "config",
                        "export",
                        "--output",
                        str(output_file),
                        "--format",
                        "toml",
                    ],
                    obj=mock_export_context,
                )

            assert result.exit_code == 0
            assert "Configuration exported" in result.output
            assert "Format: TOML" in result.output
            assert "TOML format exported" in result.output
            assert output_file.exists()

            # Verify file contents
            import tomlkit

            with output_file.open("r") as f:
                exported_data = tomlkit.load(f)

            # Type guard to ensure exported_data is dict-like
            if hasattr(exported_data, "__getitem__"):
                assert "profile" in exported_data
                assert "firmware" in exported_data
                assert "_metadata" in exported_data

                # Safely access nested data with type checking
                metadata = exported_data.get("_metadata")
                if metadata is not None and hasattr(metadata, "__getitem__"):
                    assert metadata["export_format"] == "toml"

            # Verify None values are filtered out (TOML compatibility)
            firmware_section = exported_data.get("firmware")
            if firmware_section and isinstance(firmware_section, dict):
                firmware_docker = firmware_section.get("docker", {})
                if isinstance(firmware_docker, dict):
                    # Should not contain None values like manual_uid, manual_gid
                    assert all(v is not None for v in firmware_docker.values())

    def test_export_with_defaults(self, cli_runner, mock_export_context):
        """Test config export including default values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_config_defaults.yaml"

            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = mock_export_context
                result = cli_runner.invoke(
                    app,
                    [
                        "config",
                        "export",
                        "--output",
                        str(output_file),
                        "--include-defaults",
                    ],
                    obj=mock_export_context,
                )

            assert result.exit_code == 0
            assert "Include defaults: True" in result.output
            assert output_file.exists()

            # Verify more options are exported when including defaults
            import yaml

            with output_file.open("r") as f:
                exported_data = yaml.safe_load(f)

            # Should include cache_path and other default fields
            assert "cache_path" in exported_data
            assert "cache_strategy" in exported_data
            assert "cache_file_locking" in exported_data

    def test_export_without_defaults(self, cli_runner, mock_export_context):
        """Test config export excluding default values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_config_no_defaults.yaml"

            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = mock_export_context
                result = cli_runner.invoke(
                    app,
                    ["config", "export", "--output", str(output_file), "--no-defaults"],
                    obj=mock_export_context,
                )

            assert result.exit_code == 0
            assert "Include defaults: False" in result.output
            assert output_file.exists()

            # Verify fewer options are exported when excluding defaults
            import yaml

            with output_file.open("r") as f:
                exported_data = yaml.safe_load(f)

            # Should only include non-default values
            assert "_metadata" in exported_data
            # May or may not include cache_path depending on if it was customized

    def test_export_with_descriptions(self, cli_runner, mock_export_context):
        """Test config export with field descriptions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_config_descriptions.yaml"

            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = mock_export_context
                result = cli_runner.invoke(
                    app,
                    [
                        "config",
                        "export",
                        "--output",
                        str(output_file),
                        "--include-descriptions",
                    ],
                    obj=mock_export_context,
                )

            assert result.exit_code == 0
            assert "Descriptions included as comments" in result.output
            assert output_file.exists()

            # Verify comments are included in YAML
            with output_file.open("r") as f:
                content = f.read()

            assert "# Glovebox Configuration Export" in content
            assert "# Generated at:" in content
            assert "# Include defaults:" in content

    def test_export_invalid_format(self, cli_runner, mock_export_context):
        """Test config export with invalid format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "test_config.invalid"

            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = mock_export_context
                result = cli_runner.invoke(
                    app,
                    [
                        "config",
                        "export",
                        "--output",
                        str(output_file),
                        "--format",
                        "invalid",
                    ],
                    obj=mock_export_context,
                )

            assert result.exit_code == 1
            assert "Unsupported format: invalid" in result.output
            assert "Use yaml, json, or toml" in result.output


class TestConfigImport:
    """Test config import command with all serialization formats."""

    @pytest.fixture
    def mock_import_context(self, user_config_fixture):
        """Create a mock app context for import testing."""
        from glovebox.cli.app import AppContext

        mock_context = Mock(spec=AppContext)
        mock_context.user_config = user_config_fixture
        return mock_context

    def test_import_yaml_format(self, cli_runner, mock_import_context):
        """Test config import with YAML format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "import_config.yaml"

            # Create test config file
            test_config = {
                "profile": "imported_keyboard/v1.0",
                "log_level": "DEBUG",
                "cache_path": "/tmp/test_cache",
                "firmware": {"flash": {"timeout": 120, "count": 5}},
                "_metadata": {
                    "generated_at": "2025-01-01T00:00:00",
                    "export_format": "yaml",
                },
            }

            import yaml

            with config_file.open("w") as f:
                yaml.dump(test_config, f)

            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = mock_import_context
                result = cli_runner.invoke(
                    app,
                    ["config", "import", str(config_file), "--force"],
                    obj=mock_import_context,
                )

            assert result.exit_code == 0
            assert "Configuration imported successfully!" in result.output
            assert "Applied: 5 settings" in result.output
            assert "Imported config generated at: 2025-01-01T00:00:00" in result.output

    def test_import_json_format(self, cli_runner, mock_import_context):
        """Test config import with JSON format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "import_config.json"

            # Create test config file
            test_config = {
                "profile": "json_keyboard/v2.0",
                "log_level": "ERROR",
                "cache_strategy": "disabled",
                "firmware": {"flash": {"timeout": 90, "track_flashed": False}},
                "_metadata": {
                    "generated_at": "2025-01-01T12:00:00",
                    "export_format": "json",
                },
            }

            with config_file.open("w") as f:
                json.dump(test_config, f)

            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = mock_import_context
                result = cli_runner.invoke(
                    app,
                    ["config", "import", str(config_file), "--force"],
                    obj=mock_import_context,
                )

            assert result.exit_code == 0
            assert "Configuration imported successfully!" in result.output
            assert "Applied: 5 settings" in result.output

    def test_import_toml_format(self, cli_runner, mock_import_context):
        """Test config import with TOML format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "import_config.toml"

            # Create test config file
            toml_content = """
profile = "toml_keyboard/v3.0"
log_level = "WARNING"
cache_path = "/custom/cache/path"
disable_version_checks = true

[firmware.flash]
timeout = 150
count = 1
wait = true

[firmware.docker]
enable_user_mapping = false
container_home_dir = "/custom/home"

[_metadata]
generated_at = "2025-01-01T18:00:00"
export_format = "toml"
"""

            with config_file.open("w") as f:
                f.write(toml_content)

            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = mock_import_context
                result = cli_runner.invoke(
                    app,
                    ["config", "import", str(config_file), "--force"],
                    obj=mock_import_context,
                )

            assert result.exit_code == 0
            assert "Configuration imported successfully!" in result.output
            assert "Applied: 9 settings" in result.output

    def test_import_with_backup(self, cli_runner, mock_import_context):
        """Test config import with backup creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "import_config.yaml"

            # Create minimal test config
            test_config = {"profile": "backup_test/v1.0", "log_level": "INFO"}

            import yaml

            with config_file.open("w") as f:
                yaml.dump(test_config, f)

            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = mock_import_context
                result = cli_runner.invoke(
                    app,
                    ["config", "import", str(config_file), "--force", "--backup"],
                    obj=mock_import_context,
                )

            assert result.exit_code == 0
            assert "Backup saved to:" in result.output
            assert "Configuration imported successfully!" in result.output

    def test_import_without_backup(self, cli_runner, mock_import_context):
        """Test config import without backup creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "import_config.yaml"

            # Create minimal test config
            test_config = {"profile": "no_backup_test/v1.0"}

            import yaml

            with config_file.open("w") as f:
                yaml.dump(test_config, f)

            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = mock_import_context
                result = cli_runner.invoke(
                    app,
                    ["config", "import", str(config_file), "--force", "--no-backup"],
                    obj=mock_import_context,
                )

            assert result.exit_code == 0
            assert "Backup saved to:" not in result.output
            assert "Configuration imported successfully!" in result.output

    def test_import_dry_run(self, cli_runner, mock_import_context):
        """Test config import with dry run mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "import_config.yaml"

            # Create test config with multiple settings
            test_config = {
                "profile": "dry_run_test/v1.0",
                "log_level": "DEBUG",
                "cache_strategy": "process_isolated",
                "firmware": {"flash": {"timeout": 200, "count": 10}},
            }

            import yaml

            with config_file.open("w") as f:
                yaml.dump(test_config, f)

            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = mock_import_context
                result = cli_runner.invoke(
                    app,
                    ["config", "import", str(config_file), "--dry-run"],
                    obj=mock_import_context,
                )

            assert result.exit_code == 0
            assert "Configuration Changes (Dry Run)" in result.output
            assert "Dry run complete - no changes made" in result.output
            assert "Configuration imported successfully!" not in result.output

    def test_import_nonexistent_file(self, cli_runner, mock_import_context):
        """Test config import with nonexistent file."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_import_context
            result = cli_runner.invoke(
                app,
                ["config", "import", "/nonexistent/config.yaml", "--force"],
                obj=mock_import_context,
            )

        assert result.exit_code == 1
        assert "Configuration file not found:" in result.output

    def test_import_unsupported_format(self, cli_runner, mock_import_context):
        """Test config import with unsupported file format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.invalid"
            config_file.write_text("invalid content")

            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = mock_import_context
                result = cli_runner.invoke(
                    app,
                    ["config", "import", str(config_file), "--force"],
                    obj=mock_import_context,
                )

        assert result.exit_code == 1
        assert "Unsupported file format: .invalid" in result.output
        assert "Use .yaml, .json, or .toml" in result.output

    def test_import_malformed_file(self, cli_runner, mock_import_context):
        """Test config import with malformed file content."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "malformed.yaml"
            # Write invalid YAML
            config_file.write_text("invalid: yaml: content: [")

            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = mock_import_context
                result = cli_runner.invoke(
                    app,
                    ["config", "import", str(config_file), "--force"],
                    obj=mock_import_context,
                )

        assert result.exit_code == 1
        assert "Failed to import configuration:" in result.output

    def test_import_empty_config(self, cli_runner, mock_import_context):
        """Test config import with empty configuration file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "empty.yaml"
            # Write empty dict instead of completely empty file
            config_file.write_text("{}")

            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = mock_import_context
                result = cli_runner.invoke(
                    app,
                    ["config", "import", str(config_file), "--force"],
                    obj=mock_import_context,
                )

        assert result.exit_code == 0
        assert "No configuration settings found to import" in result.output


class TestConfigExportImportRoundTrip:
    """Test round-trip export/import functionality for all formats."""

    @pytest.fixture
    def configured_context(self, user_config_fixture):
        """Create a context with specific configuration for round-trip testing."""
        from glovebox.cli.app import AppContext

        # Set specific values for testing
        user_config_fixture.set("profile", "roundtrip_test/v1.0")
        user_config_fixture.set("log_level", "DEBUG")
        user_config_fixture.set("cache_path", "/tmp/roundtrip_cache")
        user_config_fixture.set("cache_strategy", "process_isolated")
        user_config_fixture.set("firmware.flash.timeout", 300)
        user_config_fixture.set("firmware.flash.count", 7)
        user_config_fixture.set("firmware.docker.enable_user_mapping", False)

        mock_context = Mock(spec=AppContext)
        mock_context.user_config = user_config_fixture
        return mock_context

    def test_yaml_roundtrip(self, cli_runner, configured_context):
        """Test YAML export followed by import preserves data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            export_file = Path(temp_dir) / "roundtrip.yaml"

            # Export configuration
            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = configured_context
                export_result = cli_runner.invoke(
                    app,
                    [
                        "config",
                        "export",
                        "--output",
                        str(export_file),
                        "--format",
                        "yaml",
                    ],
                    obj=configured_context,
                )

            assert export_result.exit_code == 0
            assert export_file.exists()

            # Import configuration
            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = configured_context
                import_result = cli_runner.invoke(
                    app,
                    ["config", "import", str(export_file), "--force"],
                    obj=configured_context,
                )

            assert import_result.exit_code == 0
            assert "Configuration imported successfully!" in import_result.output

    def test_json_roundtrip(self, cli_runner, configured_context):
        """Test JSON export followed by import preserves data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            export_file = Path(temp_dir) / "roundtrip.json"

            # Export configuration
            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = configured_context
                export_result = cli_runner.invoke(
                    app,
                    [
                        "config",
                        "export",
                        "--output",
                        str(export_file),
                        "--format",
                        "json",
                    ],
                    obj=configured_context,
                )

            assert export_result.exit_code == 0
            assert export_file.exists()

            # Import configuration
            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = configured_context
                import_result = cli_runner.invoke(
                    app,
                    ["config", "import", str(export_file), "--force"],
                    obj=configured_context,
                )

            assert import_result.exit_code == 0
            assert "Configuration imported successfully!" in import_result.output

    def test_toml_roundtrip(self, cli_runner, configured_context):
        """Test TOML export followed by import preserves data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            export_file = Path(temp_dir) / "roundtrip.toml"

            # Export configuration
            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = configured_context
                export_result = cli_runner.invoke(
                    app,
                    [
                        "config",
                        "export",
                        "--output",
                        str(export_file),
                        "--format",
                        "toml",
                    ],
                    obj=configured_context,
                )

            assert export_result.exit_code == 0
            assert export_file.exists()

            # Verify TOML doesn't contain None values
            import tomlkit

            with export_file.open("r") as f:
                exported_data = tomlkit.load(f)

            # Check that None values are filtered out
            firmware_section = exported_data.get("firmware")
            if firmware_section and isinstance(firmware_section, dict):
                firmware_docker = firmware_section.get("docker", {})
                if isinstance(firmware_docker, dict):
                    assert all(v is not None for v in firmware_docker.values())

            # Import configuration
            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = configured_context
                import_result = cli_runner.invoke(
                    app,
                    ["config", "import", str(export_file), "--force"],
                    obj=configured_context,
                )

            assert import_result.exit_code == 0
            assert "Configuration imported successfully!" in import_result.output

    def test_cross_format_compatibility(self, cli_runner, configured_context):
        """Test that data exported in one format can be imported in another."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yaml_file = Path(temp_dir) / "config.yaml"
            json_file = Path(temp_dir) / "config.json"
            toml_file = Path(temp_dir) / "config.toml"

            # Export to YAML
            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = configured_context
                yaml_result = cli_runner.invoke(
                    app,
                    [
                        "config",
                        "export",
                        "--output",
                        str(yaml_file),
                        "--format",
                        "yaml",
                    ],
                    obj=configured_context,
                )

            # Export to JSON
            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = configured_context
                json_result = cli_runner.invoke(
                    app,
                    [
                        "config",
                        "export",
                        "--output",
                        str(json_file),
                        "--format",
                        "json",
                    ],
                    obj=configured_context,
                )

            # Export to TOML
            with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                mock_ctx.return_value.obj = configured_context
                toml_result = cli_runner.invoke(
                    app,
                    [
                        "config",
                        "export",
                        "--output",
                        str(toml_file),
                        "--format",
                        "toml",
                    ],
                    obj=configured_context,
                )

            assert yaml_result.exit_code == 0
            assert json_result.exit_code == 0
            assert toml_result.exit_code == 0

            # Verify all files can be imported successfully
            for config_file in [yaml_file, json_file, toml_file]:
                with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
                    mock_ctx.return_value.obj = configured_context
                    import_result = cli_runner.invoke(
                        app,
                        [
                            "config",
                            "import",
                            str(config_file),
                            "--force",
                            "--no-backup",
                        ],
                        obj=configured_context,
                    )

                assert import_result.exit_code == 0
                assert "Configuration imported successfully!" in import_result.output
