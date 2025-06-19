"""Tests for CLI keyboard commands."""

import json
from unittest.mock import Mock, patch

import pytest

from glovebox.cli.app import app
from glovebox.cli.commands import register_all_commands
from glovebox.config.models import KeyboardConfig


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


class TestKeyboardList:
    """Test keyboard list command."""

    def test_list_keyboards_text_format(self, cli_runner):
        """Test keyboard list with text format."""
        with patch(
            "glovebox.cli.commands.keyboard.info.get_available_keyboards"
        ) as mock_get_keyboards:
            mock_get_keyboards.return_value = ["keyboard1", "keyboard2", "keyboard3"]

            result = cli_runner.invoke(app, ["keyboard", "list"])

            assert result.exit_code == 0
            assert "Available keyboard configurations (3):" in result.output
            assert "keyboard1" in result.output
            assert "keyboard2" in result.output
            assert "keyboard3" in result.output

    def test_list_keyboards_verbose_text_format(self, cli_runner, mock_keyboard_config):
        """Test keyboard list with verbose text format."""
        with (
            patch(
                "glovebox.cli.commands.keyboard.info.get_available_keyboards"
            ) as mock_get_keyboards,
            patch(
                "glovebox.cli.commands.keyboard.info.load_keyboard_config"
            ) as mock_load_config,
        ):
            mock_get_keyboards.return_value = ["test_keyboard"]
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(app, ["keyboard", "list", "--verbose"])

            assert result.exit_code == 0
            assert "Available Keyboard Configurations (1):" in result.output
            assert "test_keyboard" in result.output
            assert "Test keyboard description" in result.output
            assert "Test Vendor" in result.output

    def test_list_keyboards_json_format(self, cli_runner):
        """Test keyboard list with JSON format."""
        with patch(
            "glovebox.cli.commands.keyboard.info.get_available_keyboards"
        ) as mock_get_keyboards:
            mock_get_keyboards.return_value = ["keyboard1", "keyboard2"]

            result = cli_runner.invoke(app, ["keyboard", "list", "--format", "json"])

            assert result.exit_code == 0
            output_data = json.loads(result.output)
            assert "keyboards" in output_data
            assert len(output_data["keyboards"]) == 2
            assert output_data["keyboards"][0]["name"] == "keyboard1"
            assert output_data["keyboards"][1]["name"] == "keyboard2"

    def test_list_keyboards_verbose_json_format(self, cli_runner, mock_keyboard_config):
        """Test keyboard list with verbose JSON format."""
        with (
            patch(
                "glovebox.cli.commands.keyboard.info.get_available_keyboards"
            ) as mock_get_keyboards,
            patch(
                "glovebox.cli.commands.keyboard.info.load_keyboard_config"
            ) as mock_load_config,
        ):
            mock_get_keyboards.return_value = ["test_keyboard"]
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app, ["keyboard", "list", "--verbose", "--format", "json"]
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

    def test_list_keyboards_no_keyboards_found(self, cli_runner):
        """Test keyboard list when no keyboards are found."""
        with patch(
            "glovebox.cli.commands.keyboard.info.get_available_keyboards"
        ) as mock_get_keyboards:
            mock_get_keyboards.return_value = []

            result = cli_runner.invoke(app, ["keyboard", "list"])

            assert result.exit_code == 0
            assert "No keyboards found" in result.output

    def test_list_keyboards_load_error(self, cli_runner):
        """Test keyboard list when keyboard config fails to load."""
        with (
            patch(
                "glovebox.cli.commands.keyboard.info.get_available_keyboards"
            ) as mock_get_keyboards,
            patch(
                "glovebox.cli.commands.keyboard.info.load_keyboard_config"
            ) as mock_load_config,
        ):
            mock_get_keyboards.return_value = ["broken_keyboard"]
            mock_load_config.side_effect = Exception("Configuration file not found")

            result = cli_runner.invoke(app, ["keyboard", "list", "--verbose"])

            assert result.exit_code == 0
            assert "broken_keyboard" in result.output
            assert "Error: Configuration file not found" in result.output


class TestKeyboardEdit:
    """Test keyboard edit command."""

    def test_edit_keyboard_get_operation(self, cli_runner, mock_keyboard_config):
        """Test keyboard edit with --get operation."""
        with (
            patch(
                "glovebox.cli.commands.keyboard.edit.get_available_keyboards"
            ) as mock_get_keyboards,
            patch(
                "glovebox.cli.commands.keyboard.edit.load_keyboard_config"
            ) as mock_load_config,
        ):
            mock_get_keyboards.return_value = ["test_keyboard"]
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app, ["keyboard", "edit", "test_keyboard", "--get", "description"]
            )

            assert result.exit_code == 0
            assert "description: Test keyboard description" in result.output

    def test_edit_keyboard_get_multiple_operations(
        self, cli_runner, mock_keyboard_config
    ):
        """Test keyboard edit with multiple --get operations."""
        with (
            patch(
                "glovebox.cli.commands.keyboard.edit.get_available_keyboards"
            ) as mock_get_keyboards,
            patch(
                "glovebox.cli.commands.keyboard.edit.load_keyboard_config"
            ) as mock_load_config,
        ):
            mock_get_keyboards.return_value = ["test_keyboard"]
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app,
                [
                    "keyboard",
                    "edit",
                    "test_keyboard",
                    "--get",
                    "description",
                    "--get",
                    "vendor",
                ],
            )

            assert result.exit_code == 0
            assert "description: Test keyboard description" in result.output
            assert "vendor: Test Vendor" in result.output

    def test_edit_keyboard_set_operation_not_supported(
        self, cli_runner, mock_keyboard_config
    ):
        """Test keyboard edit with --set operation (should show not supported message)."""
        with (
            patch(
                "glovebox.cli.commands.keyboard.edit.get_available_keyboards"
            ) as mock_get_keyboards,
            patch(
                "glovebox.cli.commands.keyboard.edit.load_keyboard_config"
            ) as mock_load_config,
        ):
            mock_get_keyboards.return_value = ["test_keyboard"]
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app,
                [
                    "keyboard",
                    "edit",
                    "test_keyboard",
                    "--set",
                    "description=New Description",
                ],
            )

            assert result.exit_code == 1
            assert (
                "Direct editing of keyboard configuration values is not yet supported"
                in result.output
            )
            assert (
                "Use --interactive mode to edit the YAML files directly"
                in result.output
            )

    def test_edit_keyboard_not_found(self, cli_runner):
        """Test keyboard edit with non-existent keyboard."""
        with patch(
            "glovebox.cli.commands.keyboard.edit.get_available_keyboards"
        ) as mock_get_keyboards:
            mock_get_keyboards.return_value = ["other_keyboard"]

            result = cli_runner.invoke(
                app, ["keyboard", "edit", "nonexistent", "--get", "description"]
            )

            assert result.exit_code == 1
            assert "Keyboard 'nonexistent' not found" in result.output
            assert "Available keyboards: other_keyboard" in result.output

    def test_edit_keyboard_load_error(self, cli_runner):
        """Test keyboard edit when keyboard config fails to load."""
        with (
            patch(
                "glovebox.cli.commands.keyboard.edit.get_available_keyboards"
            ) as mock_get_keyboards,
            patch(
                "glovebox.cli.commands.keyboard.edit.load_keyboard_config"
            ) as mock_load_config,
        ):
            mock_get_keyboards.return_value = ["test_keyboard"]
            mock_load_config.side_effect = Exception("Configuration file corrupted")

            result = cli_runner.invoke(
                app, ["keyboard", "edit", "test_keyboard", "--get", "description"]
            )

            assert result.exit_code == 1
            assert (
                "Failed to load keyboard configuration: Configuration file corrupted"
                in result.output
            )

    def test_edit_keyboard_no_operations(self, cli_runner, mock_keyboard_config):
        """Test keyboard edit without any operations."""
        with (
            patch(
                "glovebox.cli.commands.keyboard.edit.get_available_keyboards"
            ) as mock_get_keyboards,
            patch(
                "glovebox.cli.commands.keyboard.edit.load_keyboard_config"
            ) as mock_load_config,
        ):
            mock_get_keyboards.return_value = ["test_keyboard"]
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(app, ["keyboard", "edit", "test_keyboard"])

            assert result.exit_code == 1
            assert "At least one operation" in result.output

    def test_edit_keyboard_interactive_mode_conflict(
        self, cli_runner, mock_keyboard_config
    ):
        """Test keyboard edit with --interactive and other operations (should fail)."""
        with (
            patch(
                "glovebox.cli.commands.keyboard.edit.get_available_keyboards"
            ) as mock_get_keyboards,
            patch(
                "glovebox.cli.commands.keyboard.edit.load_keyboard_config"
            ) as mock_load_config,
        ):
            mock_get_keyboards.return_value = ["test_keyboard"]
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app,
                [
                    "keyboard",
                    "edit",
                    "test_keyboard",
                    "--interactive",
                    "--get",
                    "description",
                ],
            )

            assert result.exit_code == 1
            assert (
                "Interactive mode (--interactive) cannot be combined with other operations"
                in result.output
            )

    def test_edit_keyboard_interactive_mode_help(self, cli_runner):
        """Test keyboard edit help includes --interactive option."""
        result = cli_runner.invoke(app, ["keyboard", "edit", "--help"])
        assert result.exit_code == 0
        assert "--interactive" in result.output
        assert "interactive editing" in result.output


class TestKeyboardShow:
    """Test keyboard show command."""

    def test_show_keyboard_text_format(self, cli_runner, mock_keyboard_config):
        """Test keyboard show with text format."""
        with patch(
            "glovebox.cli.commands.keyboard.info.load_keyboard_config"
        ) as mock_load_config:
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(app, ["keyboard", "show", "test_keyboard"])

            assert result.exit_code == 0
            # Check unified output format structure
            assert "keyboard: test_keyboard" in result.output
            assert "description: Test keyboard description" in result.output
            assert "vendor: Test Vendor" in result.output
            assert "key_count: 84" in result.output
            assert "flash_methods:" in result.output
            assert "device_query" in result.output
            assert "compile_methods:" in result.output
            assert "method_type" in result.output
            assert "firmwares:" in result.output
            assert "firmware_count: 2" in result.output

    def test_show_keyboard_with_profile_option(self, cli_runner, mock_keyboard_config):
        """Test keyboard show with --profile option."""
        with patch(
            "glovebox.cli.commands.keyboard.info.load_keyboard_config"
        ) as mock_load_config:
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app, ["keyboard", "show", "--profile", "test_keyboard"]
            )

            assert result.exit_code == 0
            assert "keyboard: test_keyboard" in result.output
            assert "description: Test keyboard description" in result.output

    def test_show_keyboard_with_profile_and_firmware(
        self, cli_runner, mock_keyboard_config
    ):
        """Test keyboard show with --profile option including firmware."""
        with patch(
            "glovebox.cli.commands.keyboard.info.load_keyboard_config"
        ) as mock_load_config:
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app, ["keyboard", "show", "--profile", "test_keyboard/v1.0"]
            )

            assert result.exit_code == 0
            assert "keyboard: test_keyboard" in result.output
            assert "selected_firmware: v1.0" in result.output
            assert "firmware_details:" in result.output

    def test_show_keyboard_with_positional_firmware(
        self, cli_runner, mock_keyboard_config
    ):
        """Test keyboard show with positional firmware argument."""
        with patch(
            "glovebox.cli.commands.keyboard.info.load_keyboard_config"
        ) as mock_load_config:
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app, ["keyboard", "show", "test_keyboard", "v2.0"]
            )

            assert result.exit_code == 0
            assert "keyboard: test_keyboard" in result.output
            assert "selected_firmware: v2.0" in result.output
            assert "firmware_details:" in result.output

    def test_show_keyboard_profile_and_positional_conflict(self, cli_runner):
        """Test keyboard show with both --profile and positional arguments (should fail)."""
        result = cli_runner.invoke(
            app, ["keyboard", "show", "test_keyboard", "--profile", "other_keyboard"]
        )

        assert result.exit_code == 1
        assert "Cannot use both --profile and positional arguments" in result.output

    def test_show_keyboard_no_keyboard_specified(self, cli_runner):
        """Test keyboard show without keyboard name."""
        result = cli_runner.invoke(app, ["keyboard", "show"])

        assert result.exit_code == 1
        assert "Keyboard name is required" in result.output

    def test_show_keyboard_firmware_not_found(self, cli_runner, mock_keyboard_config):
        """Test keyboard show with non-existent firmware."""
        with patch(
            "glovebox.cli.commands.keyboard.info.load_keyboard_config"
        ) as mock_load_config:
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app, ["keyboard", "show", "test_keyboard", "nonexistent"]
            )

            assert result.exit_code == 0  # Should still succeed but show error
            assert "keyboard: test_keyboard" in result.output
            assert "selected_firmware: nonexistent" in result.output
            assert (
                "firmware_error: Firmware version 'nonexistent' not found"
                in result.output
            )

    def test_show_keyboard_json_format(self, cli_runner, mock_keyboard_config):
        """Test keyboard show with JSON format."""
        with patch(
            "glovebox.cli.commands.keyboard.info.load_keyboard_config"
        ) as mock_load_config:
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app, ["keyboard", "show", "test_keyboard", "--format", "json"]
            )

            assert result.exit_code == 0
            output_data = json.loads(result.output)
            assert output_data["keyboard"] == "test_keyboard"
            assert output_data["description"] == "Test keyboard description"
            assert output_data["vendor"] == "Test Vendor"
            assert output_data["key_count"] == 84

            # Check structure with current model fields
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

    def test_show_keyboard_verbose_format(self, cli_runner, mock_keyboard_config):
        """Test keyboard show with verbose format."""
        with patch(
            "glovebox.cli.commands.keyboard.info.load_keyboard_config"
        ) as mock_load_config:
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app, ["keyboard", "show", "test_keyboard", "--verbose"]
            )

            assert result.exit_code == 0
            assert "keyboard: test_keyboard" in result.output
            assert "description: Test keyboard description" in result.output
            # Verbose should include additional details
            assert "flash_methods:" in result.output
            assert "compile_methods:" in result.output
            assert "firmwares:" in result.output

    def test_show_keyboard_not_found(self, cli_runner):
        """Test keyboard show when keyboard is not found."""
        with patch(
            "glovebox.cli.commands.keyboard.info.load_keyboard_config"
        ) as mock_load_config:
            mock_load_config.side_effect = Exception("Keyboard configuration not found")

            result = cli_runner.invoke(app, ["keyboard", "show", "nonexistent"])

            assert result.exit_code == 1
            assert "Keyboard configuration not found" in result.output


class TestKeyboardFirmwares:
    """Test keyboard firmwares command."""

    def test_firmwares_text_format(self, cli_runner, mock_keyboard_config):
        """Test keyboard firmwares with text format."""
        with patch(
            "glovebox.cli.commands.keyboard.firmwares.load_keyboard_config"
        ) as mock_load_config:
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(app, ["keyboard", "firmwares", "test_keyboard"])

            assert result.exit_code == 0
            assert "Found 2 firmware(s) for test_keyboard:" in result.output
            assert "v1.0" in result.output
            assert "v2.0" in result.output

    def test_firmwares_json_format(self, cli_runner, mock_keyboard_config):
        """Test keyboard firmwares with JSON format."""
        with patch(
            "glovebox.cli.commands.keyboard.firmwares.load_keyboard_config"
        ) as mock_load_config:
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app, ["keyboard", "firmwares", "test_keyboard", "--format", "json"]
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
        """Test keyboard firmwares when no firmwares are found."""
        mock_config = KeyboardConfig.model_validate(
            {
                "keyboard": "minimal_keyboard",
                "description": "Minimal keyboard",
                "vendor": "Test Vendor",
                "key_count": 10,
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
            "glovebox.cli.commands.keyboard.firmwares.load_keyboard_config"
        ) as mock_load_config:
            mock_load_config.return_value = mock_config

            result = cli_runner.invoke(
                app, ["keyboard", "firmwares", "minimal_keyboard"]
            )

            assert result.exit_code == 0
            assert "No firmwares found for minimal_keyboard" in result.output


class TestKeyboardFirmware:
    """Test keyboard firmware command."""

    def test_firmware_text_format(self, cli_runner, mock_keyboard_config):
        """Test keyboard firmware with text format."""
        with patch(
            "glovebox.cli.commands.keyboard.firmwares.load_keyboard_config"
        ) as mock_load_config:
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app, ["keyboard", "firmware", "test_keyboard", "v1.0"]
            )

            assert result.exit_code == 0
            assert "Firmware: v1.0 for test_keyboard" in result.output
            assert "Version: v1.0" in result.output
            assert "Description: Test firmware v1.0" in result.output
            assert "Build Options:" in result.output
            assert "repository: https://github.com/moergo-sc/zmk" in result.output
            assert "branch: glove80" in result.output

    def test_firmware_json_format(self, cli_runner, mock_keyboard_config):
        """Test keyboard firmware with JSON format."""
        with patch(
            "glovebox.cli.commands.keyboard.firmwares.load_keyboard_config"
        ) as mock_load_config:
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app,
                ["keyboard", "firmware", "test_keyboard", "v2.0", "--format", "json"],
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
        """Test keyboard firmware when firmware is not found."""
        with patch(
            "glovebox.cli.commands.keyboard.firmwares.load_keyboard_config"
        ) as mock_load_config:
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app, ["keyboard", "firmware", "test_keyboard", "nonexistent"]
            )

            assert result.exit_code == 1
            assert "Firmware nonexistent not found for test_keyboard" in result.output
            assert "Available firmwares:" in result.output
            assert "v1.0" in result.output
            assert "v2.0" in result.output


class TestKeyboardTabCompletion:
    """Test keyboard command tab completion."""

    def test_keyboard_name_completion(self):
        """Test that keyboard name completion works."""
        from glovebox.cli.commands.keyboard.info import complete_keyboard_names

        with patch(
            "glovebox.cli.commands.keyboard.info.get_available_keyboards"
        ) as mock_get_keyboards:
            mock_get_keyboards.return_value = ["glove80", "moonlander", "ergodox"]

            # Test partial match
            completions = complete_keyboard_names("glo")
            assert "glove80" in completions
            assert "moonlander" not in completions
            assert "ergodox" not in completions

            # Test exact match
            completions = complete_keyboard_names("glove80")
            assert "glove80" in completions

            # Test no match
            completions = complete_keyboard_names("xyz")
            assert len(completions) == 0

    def test_keyboard_name_completion_exception_handling(self):
        """Test that keyboard completion handles exceptions gracefully."""
        from glovebox.cli.commands.keyboard.info import complete_keyboard_names

        with patch(
            "glovebox.cli.commands.keyboard.info.get_available_keyboards"
        ) as mock_get_keyboards:
            mock_get_keyboards.side_effect = Exception("Config error")

            # Should return empty list on exception
            completions = complete_keyboard_names("glo")
            assert completions == []


class TestKeyboardIntegration:
    """Integration tests for keyboard commands."""

    def test_keyboard_commands_available(self, cli_runner):
        """Test that all keyboard commands are properly registered."""
        result = cli_runner.invoke(app, ["keyboard", "--help"])

        assert result.exit_code == 0
        assert "list" in result.output
        assert "show" in result.output
        assert "edit" in result.output
        assert "firmwares" in result.output
        assert "firmware" in result.output

    def test_keyboard_list_help(self, cli_runner):
        """Test keyboard list help command."""
        result = cli_runner.invoke(app, ["keyboard", "list", "--help"])

        assert result.exit_code == 0
        assert "List available keyboard configurations" in result.output
        assert "--verbose" in result.output
        assert "--format" in result.output

    def test_keyboard_show_help(self, cli_runner):
        """Test keyboard show help command."""
        result = cli_runner.invoke(app, ["keyboard", "show", "--help"])

        assert result.exit_code == 0
        assert "Show details of a specific keyboard configuration" in result.output
        assert "--profile" in result.output
        assert "--format" in result.output
        assert "--verbose" in result.output

    def test_keyboard_edit_help(self, cli_runner):
        """Test keyboard edit help command."""
        result = cli_runner.invoke(app, ["keyboard", "edit", "--help"])

        assert result.exit_code == 0
        assert "Unified keyboard configuration editing command" in result.output
        assert "--get" in result.output
        assert "--set" in result.output
        assert "--add" in result.output
        assert "--remove" in result.output
        assert "--clear" in result.output
        assert "--interactive" in result.output

    def test_keyboard_firmwares_help(self, cli_runner):
        """Test keyboard firmwares help command."""
        result = cli_runner.invoke(app, ["keyboard", "firmwares", "--help"])

        assert result.exit_code == 0
        assert "List available firmware configurations for a keyboard" in result.output
        assert "--format" in result.output

    def test_keyboard_firmware_help(self, cli_runner):
        """Test keyboard firmware help command."""
        result = cli_runner.invoke(app, ["keyboard", "firmware", "--help"])

        assert result.exit_code == 0
        assert "Show details of a specific firmware configuration" in result.output
        assert "--format" in result.output


class TestKeyboardErrorHandling:
    """Test keyboard command error handling."""

    def test_keyboard_show_missing_argument(self, cli_runner):
        """Test keyboard show without keyboard name argument."""
        result = cli_runner.invoke(app, ["keyboard", "show"])

        assert result.exit_code == 1  # Our custom error handling
        assert "Keyboard name is required" in result.output

    def test_keyboard_firmware_missing_arguments(self, cli_runner):
        """Test keyboard firmware without required arguments."""
        result = cli_runner.invoke(app, ["keyboard", "firmware"])

        assert result.exit_code == 2  # Typer missing argument error
        assert "Missing argument" in result.output

    def test_keyboard_firmwares_missing_argument(self, cli_runner):
        """Test keyboard firmwares without keyboard name argument."""
        result = cli_runner.invoke(app, ["keyboard", "firmwares"])

        assert result.exit_code == 2  # Typer missing argument error
        assert "Missing argument" in result.output

    def test_keyboard_invalid_format(self, cli_runner, mock_keyboard_config):
        """Test keyboard commands with invalid format option."""
        with patch(
            "glovebox.cli.commands.keyboard.info.load_keyboard_config"
        ) as mock_load_config:
            mock_load_config.return_value = mock_keyboard_config

            result = cli_runner.invoke(
                app, ["keyboard", "show", "test_keyboard", "--format", "invalid"]
            )

            # Current implementation doesn't validate format - outputs text format
            assert result.exit_code == 0
            assert "keyboard: test_keyboard" in result.output
