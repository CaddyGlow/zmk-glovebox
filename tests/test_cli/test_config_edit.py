"""Tests for CLI config edit commands (set, add, remove, clear, interactive)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.cli.app import app
from glovebox.cli.commands import register_all_commands
from glovebox.config.user_config import UserConfig


# Register commands with the app before running tests
register_all_commands(app)


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
    """Create a mock app context with user config."""
    context = Mock()
    context.user_config = user_config_fixture
    context.use_emoji = False
    return context


class TestConfigEdit:
    """Test cases for config edit command with set operations."""

    def test_config_edit_set_simple(self, cli_runner, mock_app_context):
        """Test setting a simple configuration value."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(
                app, ["config", "edit", "--set", "log_level=DEBUG"]
            )

            assert result.exit_code == 0
            assert "Set log_level = DEBUG" in result.output

    def test_config_edit_set_multiple(self, cli_runner, mock_app_context):
        """Test setting multiple configuration values."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(
                app,
                [
                    "config",
                    "edit",
                    "--set",
                    "log_level=DEBUG",
                    "--set",
                    "profile=test/v2.0",
                ],
            )

            assert result.exit_code == 0
            assert "Set log_level = DEBUG" in result.output
            assert "Set profile = test/v2.0" in result.output

    def test_config_edit_get_single(self, cli_runner, mock_app_context):
        """Test getting a single configuration value."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(app, ["config", "edit", "--get", "log_level"])

            assert result.exit_code == 0
            assert "log_level:" in result.output

    def test_config_edit_get_multiple(self, cli_runner, mock_app_context):
        """Test getting multiple configuration values."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(
                app,
                [
                    "config",
                    "edit",
                    "--get",
                    "log_level",
                    "--get",
                    "profile",
                ],
            )

            assert result.exit_code == 0
            assert "log_level:" in result.output
            assert "profile:" in result.output

    def test_config_edit_invalid_key(self, cli_runner, mock_app_context):
        """Test setting an invalid configuration key."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(
                app, ["config", "edit", "--set", "invalid_key=value"]
            )

            assert result.exit_code == 0  # Command succeeds but shows error
            assert "Unknown configuration key" in result.output

    def test_config_edit_invalid_format(self, cli_runner, mock_app_context):
        """Test setting with invalid key=value format."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(
                app, ["config", "edit", "--set", "invalid_format"]
            )

            assert result.exit_code == 0  # Command succeeds but shows error
            assert "Invalid key=value format" in result.output


class TestConfigAdd:
    """Test cases for config edit command with add operations."""

    def test_config_edit_add_to_list(self, cli_runner, mock_app_context):
        """Test adding values to a list configuration."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(
                app, ["config", "edit", "--add", "keyboard_paths=/new/path"]
            )

            assert result.exit_code == 0
            assert "Added '/new/path' to keyboard_paths" in result.output

    def test_config_edit_add_duplicate(self, cli_runner, mock_app_context):
        """Test adding duplicate value to list."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            # First add
            cli_runner.invoke(
                app, ["config", "edit", "--add", "keyboard_paths=/test/path"]
            )

            # Try to add same value again
            result = cli_runner.invoke(
                app, ["config", "edit", "--add", "keyboard_paths=/test/path"]
            )

            assert result.exit_code == 0
            assert "already exists" in result.output

    def test_config_edit_add_to_non_list(self, cli_runner, mock_app_context):
        """Test adding to a non-list configuration."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(
                app, ["config", "edit", "--add", "log_level=DEBUG"]
            )

            assert result.exit_code == 0
            assert "is not a list" in result.output


class TestConfigRemove:
    """Test cases for config edit command with remove operations."""

    def test_config_edit_remove_from_list(self, cli_runner, mock_app_context):
        """Test removing values from a list configuration."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            # First add a value
            cli_runner.invoke(
                app, ["config", "edit", "--add", "keyboard_paths=/test/path"]
            )

            # Then remove it
            result = cli_runner.invoke(
                app, ["config", "edit", "--remove", "keyboard_paths=/test/path"]
            )

            assert result.exit_code == 0
            assert "Removed '/test/path' from keyboard_paths" in result.output

    def test_config_edit_remove_nonexistent(self, cli_runner, mock_app_context):
        """Test removing non-existent value from list."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(
                app, ["config", "edit", "--remove", "keyboard_paths=/nonexistent"]
            )

            assert result.exit_code == 0
            assert "not found" in result.output

    def test_config_edit_remove_from_non_list(self, cli_runner, mock_app_context):
        """Test removing from a non-list configuration."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(
                app, ["config", "edit", "--remove", "log_level=DEBUG"]
            )

            assert result.exit_code == 0
            assert "is not a list" in result.output


class TestConfigClear:
    """Test cases for config edit command with clear operations."""

    def test_config_edit_clear_list(self, cli_runner, mock_app_context):
        """Test clearing a list configuration."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            # First add some values
            cli_runner.invoke(
                app, ["config", "edit", "--add", "keyboard_paths=/test/path1"]
            )
            cli_runner.invoke(
                app, ["config", "edit", "--add", "keyboard_paths=/test/path2"]
            )

            # Then clear the list
            result = cli_runner.invoke(
                app, ["config", "edit", "--clear", "keyboard_paths"]
            )

            assert result.exit_code == 0
            assert "Cleared all values from keyboard_paths" in result.output

    def test_config_edit_clear_empty_list(self, cli_runner, mock_app_context):
        """Test clearing an already empty list."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(
                app, ["config", "edit", "--clear", "keyboard_paths"]
            )

            assert result.exit_code == 0
            assert "already empty" in result.output

    def test_config_edit_clear_field(self, cli_runner, mock_app_context):
        """Test clearing a non-list field to default."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(
                app, ["config", "edit", "--clear", "cache_strategy"]
            )

            assert result.exit_code == 0
            # Should succeed and show clearing message


class TestConfigInteractive:
    """Test cases for interactive config editing."""

    def test_config_edit_interactive_exclusive(self, cli_runner, mock_app_context):
        """Test that interactive mode is exclusive with other operations."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(
                app,
                [
                    "config",
                    "edit",
                    "--interactive",
                    "--set",
                    "log_level=DEBUG",
                ],
            )

            assert result.exit_code == 1
            assert "cannot be combined" in result.output

    @patch("subprocess.run")
    def test_config_edit_interactive_success(
        self, mock_subprocess, cli_runner, mock_app_context
    ):
        """Test successful interactive editing."""
        mock_subprocess.return_value = Mock()
        mock_subprocess.return_value.returncode = 0

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            # Mock file modification time check
            with patch("pathlib.Path.stat") as mock_stat:
                mock_stat.return_value.st_mtime = 1000  # Simulate file modification

                result = cli_runner.invoke(app, ["config", "edit", "--interactive"])

                assert result.exit_code == 0

    def test_config_edit_no_operations(self, cli_runner, mock_app_context):
        """Test config edit with no operations specified."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(app, ["config", "edit"])

            assert result.exit_code == 1
            assert "At least one operation" in result.output

    def test_config_edit_combined_operations(self, cli_runner, mock_app_context):
        """Test config edit with multiple operations combined."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(
                app,
                [
                    "config",
                    "edit",
                    "--get",
                    "log_level",
                    "--set",
                    "profile=test/v1.0",
                    "--add",
                    "keyboard_paths=/new/path",
                ],
            )

            assert result.exit_code == 0
            assert "log_level:" in result.output
            assert "Set profile = test/v1.0" in result.output
            assert "Added '/new/path' to keyboard_paths" in result.output


class TestConfigSet:
    """Test cases for specific set operations and type conversions."""

    def test_config_set_boolean_true(self, cli_runner, mock_app_context):
        """Test setting boolean value to true."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(
                app, ["config", "edit", "--set", "firmware.flash.track_flashed=true"]
            )

            assert result.exit_code == 0
            assert "Set firmware.flash.track_flashed = True" in result.output

    def test_config_set_boolean_false(self, cli_runner, mock_app_context):
        """Test setting boolean value to false."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(
                app, ["config", "edit", "--set", "firmware.flash.track_flashed=false"]
            )

            assert result.exit_code == 0
            assert "Set firmware.flash.track_flashed = False" in result.output

    def test_config_set_integer(self, cli_runner, mock_app_context):
        """Test setting integer value."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(
                app, ["config", "edit", "--set", "firmware.flash.timeout=120"]
            )

            assert result.exit_code == 0
            assert "Set firmware.flash.timeout = 120" in result.output

    def test_config_set_invalid_integer(self, cli_runner, mock_app_context):
        """Test setting invalid integer value."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(
                app, ["config", "edit", "--set", "firmware.flash.timeout=invalid"]
            )

            assert result.exit_code == 0
            assert "Invalid integer value" in result.output

    def test_config_set_with_no_save(self, cli_runner, mock_app_context):
        """Test setting values without saving."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(
                app,
                [
                    "config",
                    "edit",
                    "--set",
                    "log_level=DEBUG",
                    "--no-save",
                ],
            )

            assert result.exit_code == 0
            assert "Set log_level = DEBUG" in result.output
            # Should not show "Configuration saved"
            assert "Configuration saved" not in result.output
