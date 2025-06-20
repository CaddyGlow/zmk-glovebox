"""Tests for CLI config management commands (import/export)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

from glovebox.cli.app import app
from glovebox.cli.commands import register_all_commands
from glovebox.config.user_config import UserConfig


# Register commands with the app before running tests
register_all_commands(app)


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

    with config_file.open("w") as f:
        yaml.dump(config_data, f)

    # Create UserConfig instance with explicit config file path
    user_config = UserConfig(cli_config_path=config_file)
    return user_config


@pytest.fixture
def mock_export_context(user_config_fixture):
    """Create a mock context for export tests."""
    context = Mock()
    context.user_config = user_config_fixture
    context.use_emoji = False
    return context


@pytest.fixture
def mock_import_context(tmp_path):
    """Create a mock context for import tests."""
    # Create a minimal config for import tests
    config_file = tmp_path / "test_config.yaml"
    config_data = {
        "profile": "import_test/v1.0",
        "log_level": "DEBUG",
    }

    with config_file.open("w") as f:
        yaml.dump(config_data, f)

    user_config = UserConfig(cli_config_path=config_file)

    context = Mock()
    context.user_config = user_config
    context.use_emoji = False
    return context


class TestConfigExport:
    """Test cases for config export command."""

    def test_export_yaml_default(self, cli_runner, mock_export_context, tmp_path):
        """Test basic YAML export."""
        export_file = tmp_path / "export.yaml"

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_export_context

            result = cli_runner.invoke(
                app, ["config", "export", "--output", str(export_file)]
            )

            assert result.exit_code == 0
            assert "Configuration exported" in result.output
            assert export_file.exists()

            # Verify YAML content
            with export_file.open() as f:
                exported_data = yaml.safe_load(f)
            assert exported_data is not None
            assert "_metadata" in exported_data

    def test_export_json_format(self, cli_runner, mock_export_context, tmp_path):
        """Test JSON export format."""
        export_file = tmp_path / "export.json"

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_export_context

            result = cli_runner.invoke(
                app,
                [
                    "config",
                    "export",
                    "--output",
                    str(export_file),
                    "--format",
                    "json",
                ],
            )

            assert result.exit_code == 0
            assert "Configuration exported" in result.output
            assert export_file.exists()

            # Verify JSON content
            with export_file.open() as f:
                exported_data = json.load(f)
            assert exported_data is not None
            assert "_metadata" in exported_data

    def test_export_toml_format(self, cli_runner, mock_export_context, tmp_path):
        """Test TOML export format."""
        export_file = tmp_path / "export.toml"

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_export_context

            result = cli_runner.invoke(
                app,
                [
                    "config",
                    "export",
                    "--output",
                    str(export_file),
                    "--format",
                    "toml",
                ],
            )

            assert result.exit_code == 0
            assert "Configuration exported" in result.output
            assert export_file.exists()

            # Verify TOML content
            import tomlkit
            with export_file.open() as f:
                exported_data = tomlkit.load(f)
            assert exported_data is not None

    def test_export_include_defaults(self, cli_runner, mock_export_context, tmp_path):
        """Test export with defaults included."""
        export_file = tmp_path / "export_with_defaults.yaml"

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_export_context

            result = cli_runner.invoke(
                app,
                [
                    "config",
                    "export",
                    "--output",
                    str(export_file),
                    "--include-defaults",
                ],
            )

            assert result.exit_code == 0
            assert "Configuration exported" in result.output

    def test_export_no_defaults(self, cli_runner, mock_export_context, tmp_path):
        """Test export without defaults."""
        export_file = tmp_path / "export_no_defaults.yaml"

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_export_context

            result = cli_runner.invoke(
                app,
                [
                    "config",
                    "export",
                    "--output",
                    str(export_file),
                    "--no-defaults",
                ],
            )

            assert result.exit_code == 0
            assert "Configuration exported" in result.output

    def test_export_include_descriptions(self, cli_runner, mock_export_context, tmp_path):
        """Test export with descriptions."""
        export_file = tmp_path / "export_with_desc.yaml"

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_export_context

            result = cli_runner.invoke(
                app,
                [
                    "config",
                    "export",
                    "--output",
                    str(export_file),
                    "--include-descriptions",
                ],
            )

            assert result.exit_code == 0
            assert "Configuration exported" in result.output

            # Check for comments in YAML
            content = export_file.read_text()
            assert "# Glovebox Configuration Export" in content

    def test_export_no_descriptions(self, cli_runner, mock_export_context, tmp_path):
        """Test export without descriptions."""
        export_file = tmp_path / "export_no_desc.yaml"

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_export_context

            result = cli_runner.invoke(
                app,
                [
                    "config",
                    "export",
                    "--output",
                    str(export_file),
                    "--no-descriptions",
                ],
            )

            assert result.exit_code == 0
            assert "Configuration exported" in result.output

    def test_export_unsupported_format(self, cli_runner, mock_export_context, tmp_path):
        """Test export with unsupported format."""
        export_file = tmp_path / "export.xml"

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_export_context

            result = cli_runner.invoke(
                app,
                [
                    "config",
                    "export",
                    "--output",
                    str(export_file),
                    "--format",
                    "xml",
                ],
            )

            assert result.exit_code == 1
            assert "Unsupported format" in result.output


class TestConfigImport:
    """Test cases for config import command."""

    def test_import_yaml_basic(self, cli_runner, mock_import_context, tmp_path):
        """Test basic YAML import."""
        # Create a test config file to import
        import_file = tmp_path / "import.yaml"
        import_data = {
            "profile": "imported_keyboard/v2.0",
            "log_level": "WARNING",
            "firmware": {
                "flash": {
                    "timeout": 90,
                    "track_flashed": False,
                }
            },
        }

        with import_file.open("w") as f:
            yaml.dump(import_data, f)

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_import_context

            result = cli_runner.invoke(
                app, ["config", "import", str(import_file), "--force"]
            )

            assert result.exit_code == 0
            assert "Configuration imported successfully" in result.output

    def test_import_json_format(self, cli_runner, mock_import_context, tmp_path):
        """Test JSON import."""
        # Create a test JSON config file
        import_file = tmp_path / "import.json"
        import_data = {
            "profile": "json_keyboard/v1.0",
            "log_level": "ERROR",
        }

        with import_file.open("w") as f:
            json.dump(import_data, f)

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_import_context

            result = cli_runner.invoke(
                app, ["config", "import", str(import_file), "--force"]
            )

            assert result.exit_code == 0
            assert "Configuration imported successfully" in result.output

    def test_import_toml_format(self, cli_runner, mock_import_context, tmp_path):
        """Test TOML import."""
        # Create a test TOML config file
        import_file = tmp_path / "import.toml"
        import_data = {
            "profile": "toml_keyboard/v1.0",
            "log_level": "CRITICAL",
        }

        import tomlkit
        with import_file.open("w") as f:
            tomlkit.dump(import_data, f)

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_import_context

            result = cli_runner.invoke(
                app, ["config", "import", str(import_file), "--force"]
            )

            assert result.exit_code == 0
            assert "Configuration imported successfully" in result.output

    def test_import_dry_run(self, cli_runner, mock_import_context, tmp_path):
        """Test import with dry run."""
        import_file = tmp_path / "import.yaml"
        import_data = {
            "profile": "dry_run_test/v1.0",
            "log_level": "DEBUG",
        }

        with import_file.open("w") as f:
            yaml.dump(import_data, f)

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_import_context

            result = cli_runner.invoke(
                app, ["config", "import", str(import_file), "--dry-run"]
            )

            assert result.exit_code == 0
            assert "Dry run complete - no changes made" in result.output
            assert "Configuration Changes (Dry Run)" in result.output

    def test_import_with_backup(self, cli_runner, mock_import_context, tmp_path):
        """Test import with backup creation."""
        import_file = tmp_path / "import.yaml"
        import_data = {
            "profile": "backup_test/v1.0",
        }

        with import_file.open("w") as f:
            yaml.dump(import_data, f)

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_import_context

            result = cli_runner.invoke(
                app, ["config", "import", str(import_file), "--backup", "--force"]
            )

            assert result.exit_code == 0
            assert "Configuration imported successfully" in result.output

    def test_import_no_backup(self, cli_runner, mock_import_context, tmp_path):
        """Test import without backup."""
        import_file = tmp_path / "import.yaml"
        import_data = {
            "profile": "no_backup_test/v1.0",
        }

        with import_file.open("w") as f:
            yaml.dump(import_data, f)

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_import_context

            result = cli_runner.invoke(
                app,
                [
                    "config",
                    "import",
                    str(import_file),
                    "--no-backup",
                    "--force",
                ],
            )

            assert result.exit_code == 0
            assert "Configuration imported successfully" in result.output

    def test_import_nonexistent_file(self, cli_runner, mock_import_context):
        """Test import with non-existent file."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_import_context

            result = cli_runner.invoke(
                app, ["config", "import", "/nonexistent/file.yaml"]
            )

            assert result.exit_code == 1
            assert "Configuration file not found" in result.output

    def test_import_unsupported_format(self, cli_runner, mock_import_context, tmp_path):
        """Test import with unsupported file format."""
        import_file = tmp_path / "import.xml"
        import_file.write_text("<config></config>")

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_import_context

            result = cli_runner.invoke(
                app, ["config", "import", str(import_file)]
            )

            assert result.exit_code == 1
            assert "Unsupported file format" in result.output

    def test_import_invalid_yaml(self, cli_runner, mock_import_context, tmp_path):
        """Test import with invalid YAML content."""
        import_file = tmp_path / "invalid.yaml"
        import_file.write_text("invalid: yaml: content: [unclosed")

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_import_context

            result = cli_runner.invoke(
                app, ["config", "import", str(import_file)]
            )

            assert result.exit_code == 1
            assert "Failed to import configuration" in result.output

    def test_import_with_metadata(self, cli_runner, mock_import_context, tmp_path):
        """Test import with metadata section."""
        import_file = tmp_path / "import_with_metadata.yaml"
        import_data = {
            "profile": "metadata_test/v1.0",
            "log_level": "INFO",
            "_metadata": {
                "generated_at": "2023-01-01T00:00:00",
                "glovebox_version": "1.0.0",
            },
        }

        with import_file.open("w") as f:
            yaml.dump(import_data, f)

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = mock_import_context

            result = cli_runner.invoke(
                app, ["config", "import", str(import_file), "--force"]
            )

            assert result.exit_code == 0
            assert "Configuration imported successfully" in result.output
            assert "Imported config generated at" in result.output

