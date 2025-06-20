"""Tests for CLI config list and show commands."""

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
    """Create a mock app context with user config."""
    context = Mock()
    context.user_config = user_config_fixture
    context.use_emoji = False
    return context


class TestConfigList:
    """Test cases for config list command."""

    def test_config_list_basic(self, cli_runner, mock_app_context):
        """Test basic config list command."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(app, ["config", "list"])

            assert result.exit_code == 0
            assert "Glovebox Configuration" in result.output
            assert "Setting" in result.output
            assert "Value" in result.output

    def test_config_list_with_defaults(self, cli_runner, mock_app_context):
        """Test config list with defaults option."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(app, ["config", "list", "--defaults"])

            assert result.exit_code == 0
            assert "Default" in result.output

    def test_config_list_with_sources(self, cli_runner, mock_app_context):
        """Test config list with sources option."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(app, ["config", "list", "--sources"])

            assert result.exit_code == 0
            assert "Source" in result.output

    def test_config_list_with_descriptions(self, cli_runner, mock_app_context):
        """Test config list with descriptions option."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(app, ["config", "list", "--descriptions"])

            assert result.exit_code == 0
            assert "Description" in result.output

    def test_config_list_all_options(self, cli_runner, mock_app_context):
        """Test config list with all options enabled."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(
                app, ["config", "list", "--defaults", "--sources", "--descriptions"]
            )

            assert result.exit_code == 0
            assert "Default" in result.output
            assert "Source" in result.output
            assert "Description" in result.output


class TestConfigShow:
    """Test cases for legacy config show command."""

    def test_show_config(self, cli_runner, mock_app_context):
        """Test legacy show config command."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            result = cli_runner.invoke(app, ["config", "show"])

            # Should redirect to list command or show deprecation
            assert result.exit_code == 0


class TestConfigInvalidFormat:
    """Test cases for invalid format handling."""

    def test_list_invalid_format(self, cli_runner, mock_app_context):
        """Test list command with invalid format options."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            # Test with unknown option
            result = cli_runner.invoke(app, ["config", "list", "--unknown-option"])

            # Should fail with error about unknown option
            assert result.exit_code != 0 or "unknown" in result.output.lower()

    def test_show_keyboard_invalid_format(self, cli_runner, mock_app_context):
        """Test show keyboard command with invalid format."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context

            # Test keyboard command with invalid parameters
            result = cli_runner.invoke(app, ["keyboard", "show", "nonexistent"])

            # Should handle gracefully
            assert result.exit_code != 0 or "not found" in result.output.lower()
