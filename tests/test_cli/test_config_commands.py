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
                    "type": "zmk_config",
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
        with patch(
            "glovebox.cli.commands.config.get_available_keyboards"
        ) as mock_get_keyboards:
            mock_get_keyboards.return_value = ["keyboard1", "keyboard2", "keyboard3"]

            result = cli_runner.invoke(app, ["config", "list"])

            assert result.exit_code == 0
            assert "Available keyboard configurations (3):" in result.output
            assert "keyboard1" in result.output
            assert "keyboard2" in result.output
            assert "keyboard3" in result.output

    def test_config_list_verbose_text_format(self, cli_runner, mock_keyboard_config):
        """Test config list with verbose text format."""
        with (
            patch(
                "glovebox.cli.commands.config.get_available_keyboards"
            ) as mock_get_keyboards,
            patch(
                "glovebox.cli.commands.config.load_keyboard_config_with_includes"
            ) as mock_load_config,
        ):
            mock_get_keyboards.return_value = ["test_keyboard"]
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(app, ["config", "list", "--verbose"])

            assert result.exit_code == 0
            assert "Available Keyboard Configurations (1):" in result.output
            assert "test_keyboard" in result.output
            assert "Test keyboard description" in result.output
            assert "Test Vendor" in result.output

    def test_config_list_json_format(self, cli_runner):
        """Test config list with JSON format."""
        with patch(
            "glovebox.cli.commands.config.get_available_keyboards"
        ) as mock_get_keyboards:
            mock_get_keyboards.return_value = ["keyboard1", "keyboard2"]

            result = cli_runner.invoke(app, ["config", "list", "--format", "json"])

            assert result.exit_code == 0
            output_data = json.loads(result.output)
            assert "keyboards" in output_data
            assert len(output_data["keyboards"]) == 2
            assert output_data["keyboards"][0]["name"] == "keyboard1"
            assert output_data["keyboards"][1]["name"] == "keyboard2"

    def test_config_list_verbose_json_format(self, cli_runner, mock_keyboard_config):
        """Test config list with verbose JSON format."""
        with (
            patch(
                "glovebox.cli.commands.config.get_available_keyboards"
            ) as mock_get_keyboards,
            patch(
                "glovebox.cli.commands.config.load_keyboard_config_with_includes"
            ) as mock_load_config,
            patch("glovebox.core.logging.get_logger") as mock_logger,
        ):
            # Suppress logging to prevent interference with JSON output
            mock_logger.return_value.info = Mock()
            mock_logger.return_value.debug = Mock()

            mock_get_keyboards.return_value = ["test_keyboard"]
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app, ["config", "list", "--verbose", "--format", "json"]
            )

            assert result.exit_code == 0
            output_data = json.loads(result.output)
            assert "keyboards" in output_data
            assert len(output_data["keyboards"]) == 1
            keyboard_data = output_data["keyboards"][0]
            assert keyboard_data["name"] == "test_keyboard"
            assert keyboard_data["description"] == "Test keyboard description"
            assert keyboard_data["vendor"] == "Test Vendor"
            assert keyboard_data["key_count"] == 84

    def test_config_list_no_keyboards_found(self, cli_runner):
        """Test config list when no keyboards are found."""
        with patch(
            "glovebox.cli.commands.config.get_available_keyboards"
        ) as mock_get_keyboards:
            mock_get_keyboards.return_value = []

            result = cli_runner.invoke(app, ["config", "list"])

            assert result.exit_code == 0
            assert "No keyboards found" in result.output

    def test_config_list_keyboard_load_error(self, cli_runner):
        """Test config list when keyboard config fails to load."""
        with (
            patch(
                "glovebox.cli.commands.config.get_available_keyboards"
            ) as mock_get_keyboards,
            patch(
                "glovebox.cli.commands.config.load_keyboard_config_with_includes"
            ) as mock_load_config,
        ):
            mock_get_keyboards.return_value = ["broken_keyboard"]
            mock_load_config.side_effect = Exception("Configuration file not found")

            result = cli_runner.invoke(app, ["config", "list", "--verbose"])

            assert result.exit_code == 0
            assert "broken_keyboard" in result.output
            assert "Error: Configuration file not found" in result.output


class TestConfigShowKeyboard:
    """Test config show-keyboard command."""

    def test_show_keyboard_text_format(self, cli_runner, mock_keyboard_config):
        """Test show-keyboard with text format (new unified output format)."""
        with patch(
            "glovebox.cli.commands.config.load_keyboard_config_with_includes"
        ) as mock_load_config:
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app, ["config", "show-keyboard", "test_keyboard"]
            )

            assert result.exit_code == 0
            # Check new unified output format structure
            assert "keyboard: test_keyboard" in result.output
            assert "description: Test keyboard description" in result.output
            assert "vendor: Test Vendor" in result.output
            assert "key_count: 84" in result.output
            assert "flash_methods:" in result.output
            assert "device_query" in result.output
            assert "compile_methods:" in result.output
            assert "type" in result.output
            assert "firmwares:" in result.output
            assert "firmware_count: 2" in result.output

    def test_show_keyboard_json_format(self, cli_runner, mock_keyboard_config):
        """Test show-keyboard with JSON format (new unified output format)."""
        with patch(
            "glovebox.cli.commands.config.load_keyboard_config_with_includes"
        ) as mock_load_config:
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app, ["config", "show-keyboard", "test_keyboard", "--format", "json"]
            )

            assert result.exit_code == 0
            output_data = json.loads(result.output)
            assert output_data["keyboard"] == "test_keyboard"
            assert output_data["description"] == "Test keyboard description"
            assert output_data["vendor"] == "Test Vendor"
            assert output_data["key_count"] == 84

            # Check new structure with current model fields
            assert "flash_methods" in output_data
            assert len(output_data["flash_methods"]) == 1
            assert "device_query" in output_data["flash_methods"][0]

            assert "compile_methods" in output_data
            assert len(output_data["compile_methods"]) == 1
            assert output_data["compile_methods"][0]["method_type"] == "zmk_config"

            assert "firmwares" in output_data
            assert "v1.0" in output_data["firmwares"]
            assert "v2.0" in output_data["firmwares"]
            assert output_data["firmware_count"] == 2

    def test_show_keyboard_not_found(self, cli_runner):
        """Test show-keyboard when keyboard is not found."""
        with patch(
            "glovebox.cli.commands.config.load_keyboard_config_with_includes"
        ) as mock_load_config:
            mock_load_config.side_effect = Exception("Keyboard configuration not found")

            result = cli_runner.invoke(app, ["config", "show-keyboard", "nonexistent"])

            assert result.exit_code == 1
            assert "Keyboard configuration not found" in result.output


class TestConfigFirmwares:
    """Test config firmwares command."""

    def test_firmwares_text_format(self, cli_runner, mock_keyboard_config):
        """Test firmwares with text format."""
        with patch(
            "glovebox.cli.commands.config.load_keyboard_config_with_includes"
        ) as mock_load_config:
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(app, ["config", "firmwares", "test_keyboard"])

            assert result.exit_code == 0
            assert "Found 2 firmware(s) for test_keyboard:" in result.output
            assert "v1.0" in result.output
            assert "v2.0" in result.output

    def test_firmwares_verbose_text_format(self, cli_runner, mock_keyboard_config):
        """Test firmwares with verbose text format."""
        with patch(
            "glovebox.cli.commands.config.load_keyboard_config_with_includes"
        ) as mock_load_config:
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app, ["config", "firmwares", "test_keyboard", "--verbose"]
            )

            assert result.exit_code == 0
            assert "Available Firmware Versions for test_keyboard (2):" in result.output
            assert "• v1.0" in result.output
            assert "Version: v1.0" in result.output
            assert "Description: Test firmware v1.0" in result.output
            assert "Build Options:" in result.output
            assert "repository: https://github.com/moergo-sc/zmk" in result.output
            assert "branch: glove80" in result.output

    def test_firmwares_json_format(self, cli_runner, mock_keyboard_config):
        """Test firmwares with JSON format."""
        with patch(
            "glovebox.cli.commands.config.load_keyboard_config_with_includes"
        ) as mock_load_config:
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app, ["config", "firmwares", "test_keyboard", "--format", "json"]
            )

            assert result.exit_code == 0
            output_data = json.loads(result.output)
            assert output_data["keyboard"] == "test_keyboard"
            assert "firmwares" in output_data
            assert len(output_data["firmwares"]) == 2
            firmware_names = [fw["name"] for fw in output_data["firmwares"]]
            assert "v1.0" in firmware_names
            assert "v2.0" in firmware_names

    def test_firmwares_no_firmwares_found(self, cli_runner):
        """Test firmwares when no firmwares are found."""
        mock_config = KeyboardConfig.model_validate(
            {
                "keyboard": "minimal_keyboard",
                "description": "Minimal keyboard",
                "vendor": "Test Vendor",
                "key_count": 10,
                "compile_methods": [
                    {
                        "type": "zmk_config",
                        "image": "zmkfirmware/zmk-build-arm:stable",
                        "repository": "zmkfirmware/zmk",
                        "branch": "main",
                        "build_matrix": {"board": ["nice_nano_v2"]},
                    }
                ],
                "flash_methods": [
                    {
                        "device_query": "BOOTLOADER",
                        "mount_timeout": 30,
                        "copy_timeout": 60,
                        "sync_after_copy": True,
                    }
                ],
                # No firmwares section
            }
        )

        with patch(
            "glovebox.cli.commands.config.load_keyboard_config_with_includes"
        ) as mock_load_config:
            mock_load_config.return_value = mock_config

            result = cli_runner.invoke(app, ["config", "firmwares", "minimal_keyboard"])

            assert result.exit_code == 0
            assert "No firmwares found for minimal_keyboard" in result.output


class TestConfigFirmware:
    """Test config firmware command."""

    def test_firmware_text_format(self, cli_runner, mock_keyboard_config):
        """Test firmware with text format."""
        with patch(
            "glovebox.cli.commands.config.load_keyboard_config_with_includes"
        ) as mock_load_config:
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app, ["config", "firmware", "test_keyboard", "v1.0"]
            )

            assert result.exit_code == 0
            assert "Firmware: v1.0 for test_keyboard" in result.output
            assert "Version: v1.0" in result.output
            assert "Description: Test firmware v1.0" in result.output
            assert "Build Options:" in result.output
            assert "repository: https://github.com/moergo-sc/zmk" in result.output
            assert "branch: glove80" in result.output

    def test_firmware_json_format(self, cli_runner, mock_keyboard_config):
        """Test firmware with JSON format."""
        with patch(
            "glovebox.cli.commands.config.load_keyboard_config_with_includes"
        ) as mock_load_config:
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app, ["config", "firmware", "test_keyboard", "v2.0", "--format", "json"]
            )

            assert result.exit_code == 0
            output_data = json.loads(result.output)
            assert output_data["keyboard"] == "test_keyboard"
            assert output_data["firmware"] == "v2.0"
            assert "config" in output_data
            config = output_data["config"]
            assert config["version"] == "v2.0"
            assert config["description"] == "Test firmware v2.0"

    def test_firmware_not_found(self, cli_runner, mock_keyboard_config):
        """Test firmware when firmware is not found."""
        with patch(
            "glovebox.cli.commands.config.load_keyboard_config_with_includes"
        ) as mock_load_config:
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app, ["config", "firmware", "test_keyboard", "nonexistent"]
            )

            assert result.exit_code == 1
            assert "Firmware nonexistent not found for test_keyboard" in result.output
            assert "Available firmwares:" in result.output
            assert "v1.0" in result.output
            assert "v2.0" in result.output


class TestConfigSet:
    """Test config set command."""

    def test_set_valid_string_config(self, cli_runner, mock_app_context):
        """Test setting a valid string configuration value."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(
                app, ["config", "set", "profile", "glove80/v26.0"], obj=mock_app_context
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
                ["config", "set", "firmware.flash.track_flashed", "true"],
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
                ["config", "set", "firmware.flash.timeout", "120"],
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
                app, ["config", "set", "invalid.key", "value"], obj=mock_app_context
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
                ["config", "set", "firmware.flash.timeout", "not_a_number"],
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
                ["config", "set", "profile", "test/v1.0", "--no-save"],
                obj=mock_app_context,
            )

        assert result.exit_code == 0
        assert "Set profile = test/v1.0" in result.output
        assert "Configuration saved" not in result.output


class TestConfigShow:
    """Test config show command."""

    # @pytest.mark.skip(
    #     reason="TODO: Fix CLI context passing - context.obj not properly passed to command functions"
    # )
    def test_show_config_basic(self, cli_runner, mock_app_context):
        """Test show config with basic output."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_app_context
            result = cli_runner.invoke(app, ["config", "show"], obj=mock_app_context)

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
                app, ["config", "show", "--sources"], obj=mock_app_context
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
            "glovebox.cli.commands.config.load_keyboard_config_with_includes"
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
            app, ["config", "set", "profile", "integration_test/v3.0"], obj=app_context
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

        result = cli_runner.invoke(app, ["config", "show"], obj=app_context)

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
            app, ["config", "show", "--sources"], obj=app_context
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
            app, ["config", "set", "firmware.flash.timeout", "90"], obj=app_context
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
            ["config", "set", "firmware.flash.track_flashed", "false"],
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
            app, ["config", "set", "profile", "persistent_test/v2.0"], obj=app_context
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
