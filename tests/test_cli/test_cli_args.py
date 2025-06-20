"""Tests for CLI argument parsing."""

from unittest.mock import patch

from glovebox.cli import app
from glovebox.cli.commands import register_all_commands


# Register commands with the app before running tests
register_all_commands(app)


def test_version_flag(cli_runner):
    """Test --version flag."""
    with patch("glovebox.cli.app.__version__", "1.2.3"):
        result = cli_runner.invoke(app, ["--version"], catch_exceptions=False)
        # When using --version, Typer raises typer.Exit() which is treated as exit code 0
        assert "Glovebox v1.2.3" in result.output


def test_verbose_flag(cli_runner):
    """Test --verbose flag sets log level correctly."""
    with (
        patch("glovebox.cli.app.setup_logging") as mock_setup_logging,
        patch("subprocess.run"),  # Mock subprocess to avoid running actual commands
        patch("glovebox.config.keyboard_profile.KeyboardConfig"),  # Mock config
    ):
        result = cli_runner.invoke(app, ["-vv", "status"], catch_exceptions=False)
        mock_setup_logging.assert_called_once()
        args, kwargs = mock_setup_logging.call_args
        assert kwargs["level"] == 10  # DEBUG level


def test_debug_flag(cli_runner):
    """Test --debug flag sets log level correctly."""
    with (
        patch("glovebox.cli.app.setup_logging") as mock_setup_logging,
        patch("subprocess.run"),  # Mock subprocess to avoid running actual commands
        patch("glovebox.config.keyboard_profile.KeyboardConfig"),  # Mock config
    ):
        result = cli_runner.invoke(app, ["--debug", "status"], catch_exceptions=False)
        mock_setup_logging.assert_called_once()
        args, kwargs = mock_setup_logging.call_args
        assert kwargs["level"] == 10  # DEBUG level


def test_single_verbose_flag(cli_runner):
    """Test -v flag sets INFO log level."""
    with (
        patch("glovebox.cli.app.setup_logging") as mock_setup_logging,
        patch("subprocess.run"),  # Mock subprocess to avoid running actual commands
        patch("glovebox.config.keyboard_profile.KeyboardConfig"),  # Mock config
    ):
        result = cli_runner.invoke(app, ["-v", "status"], catch_exceptions=False)
        mock_setup_logging.assert_called_once()
        args, kwargs = mock_setup_logging.call_args
        assert kwargs["level"] == 20  # INFO level


def test_debug_flag_precedence_over_verbose(cli_runner):
    """Test --debug flag takes precedence over -v flags."""
    with (
        patch("glovebox.cli.app.setup_logging") as mock_setup_logging,
        patch("subprocess.run"),  # Mock subprocess to avoid running actual commands
        patch("glovebox.config.keyboard_profile.KeyboardConfig"),  # Mock config
    ):
        result = cli_runner.invoke(
            app, ["--debug", "-v", "status"], catch_exceptions=False
        )
        mock_setup_logging.assert_called_once()
        args, kwargs = mock_setup_logging.call_args
        assert kwargs["level"] == 10  # DEBUG level (--debug wins)


def test_help_command(cli_runner):
    """Test help command shows available commands."""
    result = cli_runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Glovebox ZMK Keyboard Management Tool" in result.output
    assert "layout" in result.output
    assert "firmware" in result.output
    assert "config" in result.output
    assert "status" in result.output


def test_layout_help(cli_runner):
    """Test layout help shows subcommands."""
    result = cli_runner.invoke(app, ["layout", "--help"])
    assert result.exit_code == 0
    assert "compile" in result.output
    assert "decompose" in result.output
    assert "compose" in result.output
    assert "show" in result.output
    assert "validate" in result.output


def test_firmware_help(cli_runner):
    """Test firmware help shows subcommands."""
    result = cli_runner.invoke(app, ["firmware", "--help"])
    assert result.exit_code == 0
    assert "compile" in result.output
    assert "flash" in result.output


def test_config_help(cli_runner):
    """Test config help shows subcommands."""
    result = cli_runner.invoke(app, ["config", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "show" in result.output


def test_missing_required_args(cli_runner):
    """Test missing required arguments return error."""
    # Test layout compile missing args
    result = cli_runner.invoke(app, ["layout", "compile"])
    assert (
        result.exit_code != 0
    )  # Just check that it failed, error message format may vary

    # Test layout decompose missing args
    result = cli_runner.invoke(app, ["layout", "decompose"])
    assert (
        result.exit_code != 0
    )  # Just check that it failed, error message format may vary

    # Test firmware compile missing args
    result = cli_runner.invoke(app, ["firmware", "compile"])
    assert (
        result.exit_code != 0
    )  # Just check that it failed, error message format may vary

    # Test firmware flash missing args
    result = cli_runner.invoke(app, ["firmware", "flash"])
    assert (
        result.exit_code != 0
    )  # Just check that it failed, error message format may vary


def test_invalid_command(cli_runner):
    """Test invalid command returns error."""
    result = cli_runner.invoke(app, ["invalid-command"])
    assert result.exit_code != 0
    assert "No such command" in result.output


def test_invalid_subcommand(cli_runner):
    """Test invalid subcommand returns error."""
    result = cli_runner.invoke(app, ["layout", "invalid-subcommand"])
    assert result.exit_code != 0
    assert "No such command" in result.output
