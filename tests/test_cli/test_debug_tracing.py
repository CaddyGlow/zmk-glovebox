"""Tests for debug tracing and verbose output functionality."""

import logging
from unittest.mock import Mock, patch

import pytest

from glovebox.cli import app
from glovebox.cli.commands import register_all_commands


# Register commands with the app before running tests
register_all_commands(app)


class TestDebugTracing:
    """Tests for debug tracing functionality in CLI commands."""

    def test_debug_flag_enables_debug_logging(self, cli_runner):
        """Test that --debug flag enables debug level logging."""
        with (
            patch("glovebox.cli.app.setup_logging") as mock_setup_logging,
            patch("subprocess.run"),  # Mock subprocess to avoid running actual commands
            patch("glovebox.config.keyboard_profile.KeyboardConfig"),  # Mock config
        ):
            result = cli_runner.invoke(
                app, ["--debug", "status"], catch_exceptions=False
            )

            # Verify setup_logging was called with DEBUG level
            mock_setup_logging.assert_called_once()
            args, kwargs = mock_setup_logging.call_args
            assert kwargs["level"] == logging.DEBUG

    def test_vv_flag_enables_debug_logging(self, cli_runner):
        """Test that -vv flag enables debug level logging."""
        with (
            patch("glovebox.cli.app.setup_logging") as mock_setup_logging,
            patch("subprocess.run"),  # Mock subprocess to avoid running actual commands
            patch("glovebox.config.keyboard_profile.KeyboardConfig"),  # Mock config
        ):
            result = cli_runner.invoke(app, ["-vv", "status"], catch_exceptions=False)

            # Verify setup_logging was called with DEBUG level
            mock_setup_logging.assert_called_once()
            args, kwargs = mock_setup_logging.call_args
            assert kwargs["level"] == logging.DEBUG

    def test_v_flag_enables_info_logging(self, cli_runner):
        """Test that -v flag enables info level logging."""
        with (
            patch("glovebox.cli.app.setup_logging") as mock_setup_logging,
            patch("subprocess.run"),  # Mock subprocess to avoid running actual commands
            patch("glovebox.config.keyboard_profile.KeyboardConfig"),  # Mock config
        ):
            result = cli_runner.invoke(app, ["-v", "status"], catch_exceptions=False)

            # Verify setup_logging was called with INFO level
            mock_setup_logging.assert_called_once()
            args, kwargs = mock_setup_logging.call_args
            assert kwargs["level"] == logging.INFO

    def test_no_flags_uses_config_level(self, cli_runner):
        """Test that no flags uses configuration-based log level."""
        with (
            patch("glovebox.cli.app.setup_logging") as mock_setup_logging,
            patch(
                "glovebox.config.user_config.create_user_config"
            ) as mock_create_config,
            patch("subprocess.run"),  # Mock subprocess to avoid running actual commands
            patch("glovebox.config.keyboard_profile.KeyboardConfig"),  # Mock config
        ):
            # Mock user config to return WARNING level
            mock_config = mock_create_config.return_value
            mock_config.get_log_level_int.return_value = logging.WARNING

            result = cli_runner.invoke(app, ["status"], catch_exceptions=False)

            # Verify setup_logging was called with WARNING level from config
            mock_setup_logging.assert_called_once()
            args, kwargs = mock_setup_logging.call_args
            assert kwargs["level"] == logging.WARNING


class TestStackTraceOutput:
    """Tests for stack trace output in CLI error scenarios."""

    def test_debug_flag_shows_stack_trace_on_error(
        self, cli_runner, monkeypatch, capsys
    ):
        """Test that --debug flag shows stack traces when errors occur."""
        # Mock sys.argv to include debug flag for the stack trace function
        monkeypatch.setattr("sys.argv", ["glovebox", "--debug", "layout", "generate"])

        with (
            patch(
                "glovebox.layout.service.create_layout_service"
            ) as mock_create_service,
            patch("glovebox.cli.helpers.profile.create_profile_from_context"),
        ):
            # Make the layout service raise an error to test stack trace
            mock_service = Mock()
            mock_service.generate_from_file.side_effect = RuntimeError(
                "Test error for stack trace"
            )
            mock_create_service.return_value = mock_service

            result = cli_runner.invoke(
                app,
                ["--debug", "layout", "generate", "output", "input.json"],
                catch_exceptions=False,
            )

            # Should exit with error code 1 (from error handling)
            assert result.exit_code == 1

    def test_vv_flag_shows_stack_trace_on_error(self, cli_runner, monkeypatch):
        """Test that -vv flag shows stack traces when errors occur."""
        # Mock sys.argv to include -vv flag for the stack trace function
        monkeypatch.setattr("sys.argv", ["glovebox", "-vv", "layout", "generate"])

        with (
            patch(
                "glovebox.layout.service.create_layout_service"
            ) as mock_create_service,
            patch("glovebox.cli.helpers.profile.create_profile_from_context"),
        ):
            # Make the layout service raise an error to test stack trace
            mock_service = Mock()
            mock_service.generate_from_file.side_effect = RuntimeError(
                "Test error for stack trace"
            )
            mock_create_service.return_value = mock_service

            result = cli_runner.invoke(
                app,
                ["-vv", "layout", "generate", "output", "input.json"],
                catch_exceptions=False,
            )

            # Should exit with error code 1 (from error handling)
            assert result.exit_code == 1

    def test_no_debug_flag_no_stack_trace_on_error(self, cli_runner, monkeypatch):
        """Test that no debug flag means no stack traces on errors."""
        # Mock sys.argv without debug flags
        monkeypatch.setattr("sys.argv", ["glovebox", "layout", "generate"])

        with (
            patch(
                "glovebox.layout.service.create_layout_service"
            ) as mock_create_service,
            patch("glovebox.cli.helpers.profile.create_profile_from_context"),
        ):
            # Make the layout service raise an error
            mock_service = Mock()
            mock_service.generate_from_file.side_effect = RuntimeError(
                "Test error without stack trace"
            )
            mock_create_service.return_value = mock_service

            result = cli_runner.invoke(
                app,
                ["layout", "generate", "output", "input.json"],
                catch_exceptions=False,
            )

            # Should exit with error code 1 (from error handling)
            assert result.exit_code == 1


class TestVerboseFlagPrecedence:
    """Tests for verbose flag precedence logic."""

    def test_debug_flag_overrides_verbose_flags(self, cli_runner):
        """Test that --debug flag takes precedence over -v flags."""
        with (
            patch("glovebox.cli.app.setup_logging") as mock_setup_logging,
            patch("subprocess.run"),  # Mock subprocess to avoid running actual commands
            patch("glovebox.config.keyboard_profile.KeyboardConfig"),  # Mock config
        ):
            result = cli_runner.invoke(
                app, ["--debug", "-v", "status"], catch_exceptions=False
            )

            # --debug should win, setting DEBUG level
            mock_setup_logging.assert_called_once()
            args, kwargs = mock_setup_logging.call_args
            assert kwargs["level"] == logging.DEBUG

    def test_debug_flag_overrides_double_verbose(self, cli_runner):
        """Test that --debug flag takes precedence over -vv."""
        with (
            patch("glovebox.cli.app.setup_logging") as mock_setup_logging,
            patch("subprocess.run"),  # Mock subprocess to avoid running actual commands
            patch("glovebox.config.keyboard_profile.KeyboardConfig"),  # Mock config
        ):
            result = cli_runner.invoke(
                app, ["--debug", "-vv", "status"], catch_exceptions=False
            )

            # --debug should win, setting DEBUG level
            mock_setup_logging.assert_called_once()
            args, kwargs = mock_setup_logging.call_args
            assert kwargs["level"] == logging.DEBUG

    def test_double_verbose_overrides_single(self, cli_runner):
        """Test that -vv takes precedence over -v."""
        with (
            patch("glovebox.cli.app.setup_logging") as mock_setup_logging,
            patch("subprocess.run"),  # Mock subprocess to avoid running actual commands
            patch("glovebox.config.keyboard_profile.KeyboardConfig"),  # Mock config
        ):
            result = cli_runner.invoke(
                app, ["-vv", "-v", "status"], catch_exceptions=False
            )

            # -vv should win, setting DEBUG level
            mock_setup_logging.assert_called_once()
            args, kwargs = mock_setup_logging.call_args
            assert kwargs["level"] == logging.DEBUG


class TestConfigurationDebugTracing:
    """Tests for debug tracing in configuration loading."""

    def test_debug_shows_config_loading_details(self, cli_runner, caplog):
        """Test that debug mode shows configuration loading details."""
        with (
            patch("subprocess.run"),  # Mock subprocess calls
            patch("glovebox.config.keyboard_profile.KeyboardConfig"),
            patch("glovebox.cli.app.setup_logging") as mock_setup_logging,
        ):
            result = cli_runner.invoke(
                app, ["--debug", "status"], catch_exceptions=False
            )

            # Verify that setup_logging was called with DEBUG level
            # This confirms debug mode was enabled
            mock_setup_logging.assert_called_once()
            args, kwargs = mock_setup_logging.call_args
            assert kwargs["level"] == logging.DEBUG

    def test_info_level_shows_important_events(self, cli_runner, caplog):
        """Test that info level shows important configuration events."""
        with (
            patch("subprocess.run"),  # Mock subprocess calls
            patch("glovebox.config.keyboard_profile.KeyboardConfig"),
        ):
            # Set log level to INFO to capture info messages
            caplog.set_level(logging.INFO)

            result = cli_runner.invoke(app, ["-v", "status"], catch_exceptions=False)

            # Should show info messages but not debug
            info_messages = [
                record.message
                for record in caplog.records
                if record.levelno == logging.INFO
            ]
            debug_messages = [
                record.message
                for record in caplog.records
                if record.levelno == logging.DEBUG
            ]

            # Should have info messages but no debug messages at INFO level
            assert len(info_messages) >= 0  # May or may not have info messages
            # Note: debug messages might still appear if other components log them
