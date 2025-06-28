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
                    "method_type": "zmk_config",
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


class TestConfigEdit:
    """Test config edit command with current interface."""

    def test_get_single_value(self, isolated_cli_environment, cli_runner):
        """Test getting a single configuration value."""
        # Set up a config value first
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--set", "log_level=ERROR", "--save"],
        )
        assert result.exit_code == 0

        # Now get the value
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--get", "log_level", "--no-save"],
        )
        assert result.exit_code == 0
        assert "log_level: ERROR" in result.output

    def test_get_multiple_values(self, isolated_cli_environment, cli_runner):
        """Test getting multiple configuration values."""
        # Set up some config values first
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--set",
                "log_level=WARNING",
                "--set",
                "disable_version_checks=true",
                "--save",
            ],
        )
        assert result.exit_code == 0

        # Now get both values
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--get",
                "log_level",
                "--get",
                "disable_version_checks",
                "--no-save",
            ],
        )
        assert result.exit_code == 0
        assert "log_level: WARNING" in result.output
        assert "disable_version_checks: True" in result.output

    def test_get_comma_separated_values(self, isolated_cli_environment, cli_runner):
        """Test getting multiple configuration values using comma-separated field names."""
        # Set up some config values first
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--set",
                "log_level=INFO",
                "--set",
                "disable_version_checks=false",
                "--set",
                "emoji_mode=true",
                "--save",
            ],
        )
        assert result.exit_code == 0

        # Now get multiple values using comma-separated syntax
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--get",
                "log_level,disable_version_checks,emoji_mode",
                "--no-save",
            ],
        )
        assert result.exit_code == 0
        assert "log_level: INFO" in result.output
        assert "disable_version_checks: False" in result.output
        assert "emoji_mode: True" in result.output

    def test_get_comma_separated_with_spaces(
        self, isolated_cli_environment, cli_runner
    ):
        """Test getting multiple configuration values with spaces in comma-separated field names."""
        # Set up some config values first
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--set",
                "log_level=DEBUG",
                "--set",
                "emoji_mode=false",
                "--save",
            ],
        )
        assert result.exit_code == 0

        # Now get multiple values using comma-separated syntax with spaces
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--get",
                "log_level, emoji_mode",
                "--no-save",
            ],
        )
        assert result.exit_code == 0
        assert "log_level: DEBUG" in result.output
        assert "emoji_mode: False" in result.output

    def test_get_mixed_comma_and_flag_syntax(
        self, isolated_cli_environment, cli_runner
    ):
        """Test mixing comma-separated and multiple flag syntax for getting values."""
        # Set up some config values first
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--set",
                "log_level=ERROR",
                "--set",
                "disable_version_checks=true",
                "--set",
                "emoji_mode=false",
                "--save",
            ],
        )
        assert result.exit_code == 0

        # Mix comma-separated and individual flags
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--get",
                "log_level,disable_version_checks",
                "--get",
                "emoji_mode",
                "--no-save",
            ],
        )
        assert result.exit_code == 0
        assert "log_level: ERROR" in result.output
        assert "disable_version_checks: True" in result.output
        assert "emoji_mode: False" in result.output

    def test_set_single_value(self, isolated_cli_environment, cli_runner):
        """Test setting a single configuration value."""
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--set", "log_level=INFO", "--no-save"],
        )
        assert result.exit_code == 0
        assert "Set log_level = INFO" in result.output

    def test_set_multiple_values(self, isolated_cli_environment, cli_runner):
        """Test setting multiple configuration values."""
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--set",
                "log_level=ERROR",
                "--set",
                "disable_version_checks=false",
                "--no-save",
            ],
        )
        assert result.exit_code == 0
        assert "Set log_level = ERROR" in result.output
        assert "Set disable_version_checks = False" in result.output

    def test_add_to_list(self, isolated_cli_environment, cli_runner):
        """Test adding values to a list configuration."""
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--add",
                "keyboard_paths=/test/unique/add/path",
                "--no-save",
            ],
        )
        assert result.exit_code == 0
        assert "Added '/test/unique/add/path' to keyboard_paths" in result.output

    def test_remove_from_list(self, isolated_cli_environment, cli_runner):
        """Test removing values from a list configuration."""
        # First add a value and save it
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--add",
                "keyboard_paths=/test/unique/remove/path",
                "--save",
            ],
        )
        assert result.exit_code == 0

        # Then remove it
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--remove",
                "keyboard_paths=/test/unique/remove/path",
                "--no-save",
            ],
        )
        assert result.exit_code == 0
        assert "Removed '/test/unique/remove/path' from keyboard_paths" in result.output

    def test_clear_list(self, isolated_cli_environment, cli_runner):
        """Test clearing a list configuration."""
        # First add some values and save them
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--add",
                "keyboard_paths=/test/clear/path1",
                "--add",
                "keyboard_paths=/test/clear/path2",
                "--save",
            ],
        )
        assert result.exit_code == 0

        # Then clear the list
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--clear", "keyboard_paths", "--no-save"],
        )
        assert result.exit_code == 0
        assert "Cleared all values from keyboard_paths" in result.output

    def test_clear_regular_field(self, isolated_cli_environment, cli_runner):
        """Test clearing a regular field to default."""
        # First set a value to something non-default and save it
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--set", "log_level=ERROR", "--save"],
        )
        assert result.exit_code == 0

        # Then clear it
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--clear", "log_level", "--no-save"],
        )
        assert result.exit_code == 0
        assert "Cleared log_level" in result.output

    def test_combined_operations(self, isolated_cli_environment, cli_runner):
        """Test multiple operations in one command."""
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--set",
                "log_level=WARNING",
                "--add",
                "keyboard_paths=/test/combined/path",
                "--no-save",
            ],
        )
        assert result.exit_code == 0
        assert "Set log_level = WARNING" in result.output
        assert "Added '/test/combined/path' to keyboard_paths" in result.output

    def test_invalid_key(self, isolated_cli_environment, cli_runner):
        """Test handling of invalid configuration key."""
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--get", "invalid_key", "--no-save"],
        )
        assert result.exit_code == 0  # Should not fail, just warn
        assert "Unknown configuration key: invalid_key" in result.output

    def test_invalid_key_value_format(self, isolated_cli_environment, cli_runner):
        """Test handling of invalid key=value format."""
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--set", "invalid_format", "--no-save"],
        )
        assert result.exit_code == 0  # Should not fail, just warn
        assert "Error" in result.output or "Invalid" in result.output

    def test_no_operation_specified(self, isolated_cli_environment, cli_runner):
        """Test error when no operation is specified."""
        result = cli_runner.invoke(
            app,
            ["config", "edit"],
        )
        assert result.exit_code == 1
        assert "At least one operation" in result.output

    def test_save_configuration(self, isolated_cli_environment, cli_runner):
        """Test saving configuration to file."""
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--set", "log_level=DEBUG", "--save"],
        )
        assert result.exit_code == 0
        assert "Set log_level = DEBUG" in result.output
        assert "Configuration saved" in result.output


class TestConfigRemove:
    """Test config edit --remove command (now integrated into edit)."""

    def test_remove_from_keyboard_paths(self, isolated_cli_environment, cli_runner):
        """Test removing a path from keyboard_paths list."""
        # First add some paths and save them
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--add",
                "keyboard_paths=/test/remove_test/path1",
                "--add",
                "keyboard_paths=/test/remove_test/path2",
                "--save",
            ],
        )
        assert result.exit_code == 0

        # Remove one path
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--remove",
                "keyboard_paths=/test/remove_test/path1",
                "--no-save",
            ],
        )
        assert result.exit_code == 0
        assert "Removed '/test/remove_test/path1' from keyboard_paths" in result.output

    def test_remove_nonexistent_value(self, isolated_cli_environment, cli_runner):
        """Test removing a value that doesn't exist."""
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--remove", "keyboard_paths=/nonexistent", "--no-save"],
        )
        assert result.exit_code == 0
        assert "Value '/nonexistent' not found in keyboard_paths" in result.output

    def test_remove_from_non_list_field(self, isolated_cli_environment, cli_runner):
        """Test error when trying to remove from non-list field."""
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--remove", "log_level=DEBUG", "--no-save"],
        )
        assert result.exit_code == 0
        assert "Configuration key 'log_level' is not a list" in result.output

    def test_remove_multiple_values(self, isolated_cli_environment, cli_runner):
        """Test removing multiple values in one command."""
        # First add some paths and save them
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--add",
                "keyboard_paths=/test/multi_remove/path1",
                "--add",
                "keyboard_paths=/test/multi_remove/path2",
                "--add",
                "keyboard_paths=/test/multi_remove/path3",
                "--save",
            ],
        )
        assert result.exit_code == 0

        # Remove multiple paths
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--remove",
                "keyboard_paths=/test/multi_remove/path1",
                "--remove",
                "keyboard_paths=/test/multi_remove/path2",
                "--no-save",
            ],
        )
        assert result.exit_code == 0
        assert "Removed '/test/multi_remove/path1' from keyboard_paths" in result.output
        assert "Removed '/test/multi_remove/path2' from keyboard_paths" in result.output


class TestConfigClear:
    """Test config edit --clear command (now integrated into edit)."""

    def test_clear_list_field(self, isolated_cli_environment, cli_runner):
        """Test clearing a list configuration field."""
        # First add some values
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--add",
                "keyboard_paths=/test/clear_field/path1",
                "--add",
                "keyboard_paths=/test/clear_field/path2",
                "--no-save",
            ],
        )
        assert result.exit_code == 0

        # Clear the list
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--clear", "keyboard_paths", "--no-save"],
        )
        assert result.exit_code == 0
        assert "Cleared all values from keyboard_paths" in result.output

    def test_clear_already_empty_list(self, isolated_cli_environment, cli_runner):
        """Test clearing an already empty list."""
        # First clear any existing items
        cli_runner.invoke(
            app,
            ["config", "edit", "--clear", "keyboard_paths", "--save"],
        )

        # Now clear again - should be empty
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--clear", "keyboard_paths", "--no-save"],
        )
        assert result.exit_code == 0
        assert "List 'keyboard_paths' is already empty" in result.output

    def test_clear_regular_field(self, isolated_cli_environment, cli_runner):
        """Test clearing a regular field to default value."""
        # First set a value
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--set", "log_level=DEBUG", "--no-save"],
        )
        assert result.exit_code == 0

        # Clear it
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--clear", "log_level", "--no-save"],
        )
        assert result.exit_code == 0
        assert "Cleared log_level" in result.output

    def test_clear_multiple_fields(self, isolated_cli_environment, cli_runner):
        """Test clearing multiple fields in one command."""
        # First set some values and save them
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--set",
                "log_level=DEBUG",
                "--add",
                "keyboard_paths=/test/isolated_clear_multiple_fields/path",
                "--save",
            ],
        )
        assert result.exit_code == 0

        # Clear both
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--clear",
                "log_level",
                "--clear",
                "keyboard_paths",
                "--no-save",
            ],
        )
        assert result.exit_code == 0
        assert "Cleared log_level" in result.output
        # Accept either message - depends on whether the list had items or was already empty
        assert (
            "Cleared all values from keyboard_paths" in result.output
            or "List 'keyboard_paths' is already empty" in result.output
        )

    def test_clear_invalid_field(self, isolated_cli_environment, cli_runner):
        """Test clearing an invalid configuration field."""
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--clear", "invalid_field", "--no-save"],
        )
        assert result.exit_code == 0
        assert "Unknown configuration key: invalid_field" in result.output


class TestConfigInteractive:
    """Test interactive configuration editing functionality."""

    def test_interactive_mode_exclusive_with_get(
        self, isolated_cli_environment, cli_runner
    ):
        """Test that interactive mode cannot be combined with get operations."""
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--interactive", "--get", "log_level"],
        )
        assert result.exit_code == 1
        assert (
            "Interactive mode (--interactive) cannot be combined with other operations"
            in result.output
        )

    def test_interactive_mode_exclusive_with_set(
        self, isolated_cli_environment, cli_runner
    ):
        """Test that interactive mode cannot be combined with set operations."""
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--interactive", "--set", "log_level=DEBUG"],
        )
        assert result.exit_code == 1
        assert (
            "Interactive mode (--interactive) cannot be combined with other operations"
            in result.output
        )

    def test_interactive_mode_exclusive_with_clear(
        self, isolated_cli_environment, cli_runner
    ):
        """Test that interactive mode cannot be combined with clear operations."""
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--interactive", "--clear", "log_level"],
        )
        assert result.exit_code == 1
        assert (
            "Interactive mode (--interactive) cannot be combined with other operations"
            in result.output
        )

    def test_interactive_mode_exclusive_with_add(
        self, isolated_cli_environment, cli_runner
    ):
        """Test that interactive mode cannot be combined with add operations."""
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--interactive", "--add", "keyboard_paths=/test"],
        )
        assert result.exit_code == 1
        assert (
            "Interactive mode (--interactive) cannot be combined with other operations"
            in result.output
        )

    def test_interactive_mode_exclusive_with_remove(
        self, isolated_cli_environment, cli_runner
    ):
        """Test that interactive mode cannot be combined with remove operations."""
        result = cli_runner.invoke(
            app,
            ["config", "edit", "--interactive", "--remove", "keyboard_paths=/test"],
        )
        assert result.exit_code == 1
        assert (
            "Interactive mode (--interactive) cannot be combined with other operations"
            in result.output
        )
