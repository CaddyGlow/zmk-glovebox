"""Tests for config management with IconMode integration."""

from typing import TYPE_CHECKING, cast
from unittest.mock import Mock, patch

import pytest
import typer

from glovebox.cli.commands.config.management import _show_all_config
from glovebox.cli.helpers.theme import IconMode


if TYPE_CHECKING:
    from glovebox.cli.app import AppContext


class MockUserConfig:
    """Mock UserConfig for testing."""

    def __init__(self, icon_mode_value=IconMode.EMOJI):
        self.config_values = {
            "icon_mode": icon_mode_value,
            "log_level": "INFO",
            "profile": "glove80/v25.05",
        }

    def get(self, key: str) -> object:
        """Get configuration value."""
        return self.config_values.get(key)

    def get_source(self, key: str) -> str:
        """Get configuration source."""
        return "config_file" if key in self.config_values else "default"


class MockAppContext:
    """Mock AppContext for testing."""

    def __init__(self, user_config: MockUserConfig):
        self.user_config = user_config


class TestConfigIconModeDisplay:
    """Tests for config management IconMode display."""

    @patch("glovebox.cli.commands.config.management.Console")
    @patch("glovebox.cli.commands.config.management.Table")
    def test_format_value_handles_icon_mode_enum(
        self, mock_table_class, mock_console_class
    ):
        """Test that format_value properly handles IconMode enum values."""
        # Mock the console and table
        mock_console = Mock()
        mock_table = Mock()
        mock_console_class.return_value = mock_console
        mock_table_class.return_value = mock_table

        # Create mock app context with IconMode enum
        user_config = MockUserConfig(IconMode.NERDFONT)
        app_ctx = MockAppContext(user_config)

        # Call the function
        _show_all_config(
            cast("AppContext", app_ctx),
            show_all=True,
            show_sources=False,
            show_defaults=False,
            show_descriptions=False,
        )

        # Check that table.add_row was called with formatted enum value
        table_calls = mock_table.add_row.call_args_list

        # Find the icon_mode row
        icon_mode_row = None
        for call in table_calls:
            args = call[0]
            if len(args) >= 2 and args[0] == "icon_mode":
                icon_mode_row = args
                break

        assert icon_mode_row is not None, "icon_mode row should be present"
        assert icon_mode_row[1] == "nerdfont", (
            f"Expected 'nerdfont', got '{icon_mode_row[1]}'"
        )

    @patch("glovebox.cli.commands.config.management.Console")
    @patch("glovebox.cli.commands.config.management.Table")
    def test_format_value_handles_icon_mode_string(
        self, mock_table_class, mock_console_class
    ):
        """Test that format_value properly handles IconMode string values."""
        # Mock the console and table
        mock_console = Mock()
        mock_table = Mock()
        mock_console_class.return_value = mock_console
        mock_table_class.return_value = mock_table

        # Create mock app context with string value
        user_config = MockUserConfig("text")
        app_ctx = MockAppContext(user_config)

        # Call the function
        _show_all_config(
            cast("AppContext", app_ctx),
            show_all=True,
            show_sources=False,
            show_defaults=False,
            show_descriptions=False,
        )

        # Check that table.add_row was called with string value
        table_calls = mock_table.add_row.call_args_list

        # Find the icon_mode row
        icon_mode_row = None
        for call in table_calls:
            args = call[0]
            if len(args) >= 2 and args[0] == "icon_mode":
                icon_mode_row = args
                break

        assert icon_mode_row is not None, "icon_mode row should be present"
        assert icon_mode_row[1] == "text", f"Expected 'text', got '{icon_mode_row[1]}'"

    @patch("glovebox.cli.commands.config.management.Console")
    @patch("glovebox.cli.commands.config.management.Table")
    def test_format_value_handles_none_values(
        self, mock_table_class, mock_console_class
    ):
        """Test that format_value properly handles None values."""
        # Mock the console and table
        mock_console = Mock()
        mock_table = Mock()
        mock_console_class.return_value = mock_console
        mock_table_class.return_value = mock_table

        # Create mock app context with None value
        user_config = MockUserConfig(None)
        app_ctx = MockAppContext(user_config)

        # Call the function
        _show_all_config(
            cast("AppContext", app_ctx),
            show_all=True,
            show_sources=False,
            show_defaults=False,
            show_descriptions=False,
        )

        # Check that table.add_row was called with "null"
        table_calls = mock_table.add_row.call_args_list

        # Find the icon_mode row
        icon_mode_row = None
        for call in table_calls:
            args = call[0]
            if len(args) >= 2 and args[0] == "icon_mode":
                icon_mode_row = args
                break

        assert icon_mode_row is not None, "icon_mode row should be present"
        assert icon_mode_row[1] == "null", f"Expected 'null', got '{icon_mode_row[1]}'"

    @patch("glovebox.cli.commands.config.management.Console")
    @patch("glovebox.cli.commands.config.management.Table")
    def test_format_value_handles_list_values(
        self, mock_table_class, mock_console_class
    ):
        """Test that format_value properly handles list values."""
        # Mock the console and table
        mock_console = Mock()
        mock_table = Mock()
        mock_console_class.return_value = mock_console
        mock_table_class.return_value = mock_table

        # Create mock app context with list value
        user_config = MockUserConfig()
        user_config.config_values["profiles_paths"] = ["/path/one", "/path/two"]
        app_ctx = MockAppContext(user_config)

        # Call the function
        _show_all_config(
            cast("AppContext", app_ctx),
            show_all=True,
            show_sources=False,
            show_defaults=False,
            show_descriptions=False,
        )

        # Check that table.add_row was called with formatted list
        table_calls = mock_table.add_row.call_args_list

        # Find the profiles_paths row
        profiles_paths_row = None
        for call in table_calls:
            args = call[0]
            if len(args) >= 2 and args[0] == "profiles_paths":
                profiles_paths_row = args
                break

        assert profiles_paths_row is not None, "profiles_paths row should be present"
        assert "/path/one" in profiles_paths_row[1], "List should contain first path"
        assert "/path/two" in profiles_paths_row[1], "List should contain second path"

    @patch("glovebox.cli.commands.config.management.Console")
    @patch("glovebox.cli.commands.config.management.Table")
    def test_format_value_handles_empty_list(
        self, mock_table_class, mock_console_class
    ):
        """Test that format_value properly handles empty list values."""
        # Mock the console and table
        mock_console = Mock()
        mock_table = Mock()
        mock_console_class.return_value = mock_console
        mock_table_class.return_value = mock_table

        # Create mock app context with empty list
        user_config = MockUserConfig()
        user_config.config_values["profiles_paths"] = []
        app_ctx = MockAppContext(user_config)

        # Call the function
        _show_all_config(
            cast("AppContext", app_ctx),
            show_all=True,
            show_sources=False,
            show_defaults=False,
            show_descriptions=False,
        )

        # Check that table.add_row was called with "(empty list)"
        table_calls = mock_table.add_row.call_args_list

        # Find the profiles_paths row
        profiles_paths_row = None
        for call in table_calls:
            args = call[0]
            if len(args) >= 2 and args[0] == "profiles_paths":
                profiles_paths_row = args
                break

        assert profiles_paths_row is not None, "profiles_paths row should be present"
        assert profiles_paths_row[1] == "(empty list)", (
            f"Expected '(empty list)', got '{profiles_paths_row[1]}'"
        )

    @patch("glovebox.cli.commands.config.management.Console")
    @patch("glovebox.cli.commands.config.management.Table")
    def test_icon_mode_appears_in_config_list(
        self, mock_table_class, mock_console_class
    ):
        """Test that icon_mode field appears in configuration list."""
        # Mock the console and table
        mock_console = Mock()
        mock_table = Mock()
        mock_console_class.return_value = mock_console
        mock_table_class.return_value = mock_table

        # Create mock app context
        user_config = MockUserConfig(IconMode.TEXT)
        app_ctx = MockAppContext(user_config)

        # Call the function
        _show_all_config(
            cast("AppContext", app_ctx),
            show_all=True,
            show_sources=False,
            show_defaults=False,
            show_descriptions=False,
        )

        # Check that icon_mode was included in the configuration
        table_calls = mock_table.add_row.call_args_list
        config_keys = [call[0][0] for call in table_calls if len(call[0]) >= 1]

        assert "icon_mode" in config_keys, "icon_mode should appear in config list"
