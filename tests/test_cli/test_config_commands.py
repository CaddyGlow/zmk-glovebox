"""Tests for CLI config commands."""

from unittest.mock import Mock

import pytest

from glovebox.cli.app import app
from glovebox.cli.commands import register_all_commands
from glovebox.config.models import (
    KeyboardConfig,
)
from glovebox.config.user_config import UserConfig


pytestmark = [pytest.mark.network, pytest.mark.integration]


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
        result = cli_runner.invoke(app, ["config", "show"])

        assert result.exit_code == 0
        assert "Glovebox Configuration" in result.output
        assert "Setting" in result.output
        assert "Value" in result.output

    def test_config_list_with_defaults(self, cli_runner):
        """Test config list with defaults option."""
        result = cli_runner.invoke(app, ["config", "show", "--defaults"])

        assert result.exit_code == 0
        assert "Glovebox Configuration" in result.output
        assert "Setting" in result.output
        assert "Value" in result.output
        assert "Default" in result.output

    def test_config_list_with_sources(self, cli_runner):
        """Test config list with sources option."""
        result = cli_runner.invoke(app, ["config", "show", "--sources"])

        assert result.exit_code == 0
        assert "Glovebox Configuration" in result.output
        assert "Setting" in result.output
        assert "Value" in result.output
        assert "Source" in result.output

    def test_config_list_with_descriptions(self, cli_runner):
        """Test config list with descriptions option."""
        result = cli_runner.invoke(app, ["config", "show", "--descriptions"])

        assert result.exit_code == 0
        assert "Glovebox Configuration" in result.output
        assert "Setting" in result.output
        assert "Value" in result.output
        assert "Description" in result.output

    def test_config_list_all_options(self, cli_runner):
        """Test config list with all options."""
        result = cli_runner.invoke(
            app, ["config", "show", "--defaults", "--sources", "--descriptions"]
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
                "icon_mode=emoji",
                "--save",
            ],
        )

        # Debug output if command fails
        if result.exit_code != 0:
            print(f"Command failed with exit code {result.exit_code}")
            print(f"STDOUT: {result.stdout}")
            if result.exception:
                print(f"Exception: {result.exception}")
                import traceback

                traceback.print_exception(
                    type(result.exception),
                    result.exception,
                    result.exception.__traceback__,
                )

        assert result.exit_code == 0

        # Now get multiple values using comma-separated syntax
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--get",
                "log_level,disable_version_checks,icon_mode",
                "--no-save",
            ],
        )
        assert result.exit_code == 0
        assert "log_level: INFO" in result.output
        assert "disable_version_checks: False" in result.output
        assert "icon_mode: emoji" in result.output

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
                "icon_mode=text",
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
                "log_level, icon_mode",
                "--no-save",
            ],
        )
        assert result.exit_code == 0
        assert "log_level: DEBUG" in result.output
        assert "icon_mode: text" in result.output

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
                "icon_mode=text",
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
                "icon_mode",
                "--no-save",
            ],
        )
        assert result.exit_code == 0
        assert "log_level: ERROR" in result.output
        assert "disable_version_checks: True" in result.output
        assert "icon_mode: text" in result.output

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
                "--append",
                "profiles_paths=/test/unique/add/path",
                "--no-save",
            ],
        )
        assert result.exit_code == 0
        assert "Appended to profiles_paths" in result.output

    def test_combined_operations(self, isolated_cli_environment, cli_runner):
        """Test multiple operations in one command."""
        result = cli_runner.invoke(
            app,
            [
                "config",
                "edit",
                "--set",
                "log_level=WARNING",
                "--append",
                "profiles_paths=/test/combined/path",
                "--no-save",
            ],
        )
        assert result.exit_code == 0
        assert "Set log_level = WARNING" in result.output
        assert "Appended to profiles_paths" in result.output

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
