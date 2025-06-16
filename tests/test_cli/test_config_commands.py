"""Tests for CLI config commands."""

import json
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
                    "method_type": "docker",
                    "image": "zmkfirmware/zmk-build-arm:stable",
                    "repository": "https://github.com/moergo-sc/zmk",
                    "branch": "glove80",
                    "fallback_methods": ["local"],
                }
            ],
            "flash_methods": [
                {
                    "method_type": "usb",
                    "device_query": "BOOTLOADER",
                    "mount_timeout": 30,
                    "copy_timeout": 60,
                    "sync_after_copy": True,
                    "fallback_methods": ["dfu"],
                },
                {
                    "method_type": "dfu",
                    "device_query": "DFU",
                    "vid": "0x16C0",
                    "pid": "0x27DB",
                    "interface": 0,
                    "alt_setting": 0,
                    "timeout": 30,
                    "fallback_methods": [],
                },
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
            assert "'method_type': 'usb'" in result.output
            assert "compile_methods:" in result.output
            assert "'method_type': 'docker'" in result.output
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

            # Check new structure with multiple methods support
            assert "flash_methods" in output_data
            assert len(output_data["flash_methods"]) == 2
            assert output_data["flash_methods"][0]["method_type"] == "usb"
            assert output_data["flash_methods"][1]["method_type"] == "dfu"

            assert "flash" in output_data
            assert output_data["flash"]["primary_method"] == "usb"
            assert output_data["flash"]["total_methods"] == 2

            assert "compile_methods" in output_data
            assert len(output_data["compile_methods"]) == 1
            assert output_data["compile_methods"][0]["method_type"] == "docker"

            assert "build" in output_data
            assert output_data["build"]["primary_method"] == "docker"
            assert output_data["build"]["total_methods"] == 1

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
                "flash": {
                    "method": "usb_mount",
                    "query": "BOOTLOADER",
                    "usb_vid": "0x16C0",
                    "usb_pid": "0x27DB",
                },
                "build": {
                    "method": "docker",
                    "docker_image": "zmkfirmware/zmk-build-arm:stable",
                    "repository": "https://github.com/moergo-sc/zmk",
                    "branch": "glove80",
                },
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

    @pytest.mark.skip(
        reason="TODO: Fix CLI context passing - context.obj not properly passed to command functions"
    )
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

    @pytest.mark.skip(
        reason="TODO: Fix CLI context passing - context.obj not properly passed to command functions"
    )
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

    @pytest.mark.skip(
        reason="TODO: Fix CLI context passing - context.obj not properly passed to command functions"
    )
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

    @pytest.mark.skip(
        reason="TODO: Fix CLI context passing - context.obj not properly passed to command functions"
    )
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

    @pytest.mark.skip(
        reason="TODO: Fix CLI context passing - context.obj not properly passed to command functions"
    )
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
