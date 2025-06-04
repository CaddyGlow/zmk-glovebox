"""Basic tests for CLI functionality."""

import json
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import typer
from typer.testing import CliRunner

from glovebox.cli import app
from glovebox.models.results import BuildResult, FlashResult, KeymapResult


@pytest.fixture
def cli_runner():
    """Return a Typer CLI test runner."""
    return CliRunner()


def test_help_command(cli_runner):
    """Test help command shows available commands."""
    result = cli_runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "keymap" in result.output
    assert "firmware" in result.output
    assert "config" in result.output


def test_keymap_help(cli_runner):
    """Test keymap help shows subcommands."""
    result = cli_runner.invoke(app, ["keymap", "--help"])
    assert result.exit_code == 0
    assert "compile" in result.output
    assert "split" in result.output
    assert "merge" in result.output
    assert "show" in result.output
    assert "validate" in result.output


def test_keymap_subcommands(cli_runner):
    """Test keymap subcommand help."""
    # Test each subcommand help
    for cmd in ["compile", "split", "merge", "show", "validate"]:
        result = cli_runner.invoke(
            app, ["keymap", cmd, "--help"], catch_exceptions=False
        )
        assert result.exit_code == 0
        assert cmd in result.output.lower()


def test_firmware_help(cli_runner):
    """Test firmware help shows correct options."""
    result = cli_runner.invoke(app, ["firmware", "--help"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "compile" in result.output
    assert "flash" in result.output


def test_config_list(cli_runner):
    """Test config list command."""
    # For this simple test, we'll just verify the command runs without error
    result = cli_runner.invoke(app, ["config", "list"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "keyboard configuration" in result.output


def test_status_command(cli_runner):
    """Test status command."""
    with patch("subprocess.run") as mock_run:
        # Mock subprocess results
        mock_process = Mock()
        mock_process.stdout = "Docker version 24.0.5"
        mock_run.return_value = mock_process

        result = cli_runner.invoke(app, ["status"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "Glovebox v" in result.output
        assert "System Dependencies" in result.output
        assert "Environment" in result.output
