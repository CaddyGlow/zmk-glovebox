"""Tests for CLI config management commands (import/export)."""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from glovebox.cli.app import app
from glovebox.cli.commands import register_all_commands


# Register commands with the app before running tests
register_all_commands(app)


class TestConfigExport:
    """Test cases for config export command."""

    def test_export_yaml_default(self, isolated_cli_environment, cli_runner):
        """Test basic YAML export."""
        export_file = isolated_cli_environment["temp_dir"] / "export.yaml"

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

    def test_export_json_format(self, isolated_cli_environment, cli_runner):
        """Test JSON export format."""
        export_file = isolated_cli_environment["temp_dir"] / "export.json"

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

    def test_export_toml_format(self, isolated_cli_environment, cli_runner):
        """Test TOML export format."""
        export_file = isolated_cli_environment["temp_dir"] / "export.toml"

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

    def test_export_include_defaults(self, isolated_cli_environment, cli_runner):
        """Test export with defaults included."""
        export_file = isolated_cli_environment["temp_dir"] / "export_with_defaults.yaml"

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

    def test_export_no_defaults(self, isolated_cli_environment, cli_runner):
        """Test export without defaults."""
        export_file = isolated_cli_environment["temp_dir"] / "export_no_defaults.yaml"

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

    def test_export_include_descriptions(self, isolated_cli_environment, cli_runner):
        """Test export with descriptions."""
        export_file = isolated_cli_environment["temp_dir"] / "export_with_desc.yaml"

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

    def test_export_no_descriptions(self, isolated_cli_environment, cli_runner):
        """Test export without descriptions."""
        export_file = isolated_cli_environment["temp_dir"] / "export_no_desc.yaml"

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

    def test_export_unsupported_format(self, isolated_cli_environment, cli_runner):
        """Test export with unsupported format."""
        export_file = isolated_cli_environment["temp_dir"] / "export.xml"

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

    def test_import_yaml_basic(self, isolated_cli_environment, cli_runner):
        """Test basic YAML import."""
        # Create a test config file to import
        import_file = isolated_cli_environment["temp_dir"] / "import.yaml"
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

        result = cli_runner.invoke(
            app, ["config", "import", str(import_file), "--force"]
        )

        assert result.exit_code == 0
        assert "Configuration imported successfully" in result.output

    def test_import_json_format(self, isolated_cli_environment, cli_runner):
        """Test JSON import."""
        # Create a test JSON config file
        import_file = isolated_cli_environment["temp_dir"] / "import.json"
        import_data = {
            "profile": "json_keyboard/v1.0",
            "log_level": "ERROR",
        }

        with import_file.open("w") as f:
            json.dump(import_data, f)

        result = cli_runner.invoke(
            app, ["config", "import", str(import_file), "--force"]
        )

        assert result.exit_code == 0
        assert "Configuration imported successfully" in result.output

    def test_import_toml_format(self, isolated_cli_environment, cli_runner):
        """Test TOML import."""
        # Create a test TOML config file
        import_file = isolated_cli_environment["temp_dir"] / "import.toml"
        import_data = {
            "profile": "toml_keyboard/v1.0",
            "log_level": "CRITICAL",
        }

        import tomlkit

        with import_file.open("w") as f:
            tomlkit.dump(import_data, f)

        result = cli_runner.invoke(
            app, ["config", "import", str(import_file), "--force"]
        )

        assert result.exit_code == 0
        assert "Configuration imported successfully" in result.output

    def test_import_dry_run(self, isolated_cli_environment, cli_runner):
        """Test import with dry run."""
        import_file = isolated_cli_environment["temp_dir"] / "import.yaml"
        import_data = {
            "profile": "dry_run_test/v1.0",
            "log_level": "DEBUG",
        }

        with import_file.open("w") as f:
            yaml.dump(import_data, f)

        result = cli_runner.invoke(
            app, ["config", "import", str(import_file), "--dry-run"]
        )

        assert result.exit_code == 0
        assert "Dry run complete - no changes made" in result.output
        assert "Configuration Changes (Dry Run)" in result.output

    def test_import_with_backup(self, isolated_cli_environment, cli_runner):
        """Test import with backup creation."""
        import_file = isolated_cli_environment["temp_dir"] / "import.yaml"
        import_data = {
            "profile": "backup_test/v1.0",
        }

        with import_file.open("w") as f:
            yaml.dump(import_data, f)

        result = cli_runner.invoke(
            app, ["config", "import", str(import_file), "--backup", "--force"]
        )

        assert result.exit_code == 0
        assert "Configuration imported successfully" in result.output

    def test_import_no_backup(self, isolated_cli_environment, cli_runner):
        """Test import without backup."""
        import_file = isolated_cli_environment["temp_dir"] / "import.yaml"
        import_data = {
            "profile": "no_backup_test/v1.0",
        }

        with import_file.open("w") as f:
            yaml.dump(import_data, f)

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

    def test_import_nonexistent_file(self, isolated_cli_environment, cli_runner):
        """Test import with non-existent file."""
        result = cli_runner.invoke(app, ["config", "import", "/nonexistent/file.yaml"])

        assert result.exit_code == 1
        assert "Configuration file not found" in result.output

    def test_import_unsupported_format(self, isolated_cli_environment, cli_runner):
        """Test import with unsupported file format."""
        import_file = isolated_cli_environment["temp_dir"] / "import.xml"
        import_file.write_text("<config></config>")

        result = cli_runner.invoke(app, ["config", "import", str(import_file)])

        assert result.exit_code == 1
        assert "Unsupported file format" in result.output

    def test_import_invalid_yaml(self, isolated_cli_environment, cli_runner):
        """Test import with invalid YAML content."""
        import_file = isolated_cli_environment["temp_dir"] / "invalid.yaml"
        import_file.write_text("invalid: yaml: content: [unclosed")

        result = cli_runner.invoke(app, ["config", "import", str(import_file)])

        assert result.exit_code == 1
        assert "Failed to import configuration" in result.output

    def test_import_with_metadata(self, isolated_cli_environment, cli_runner):
        """Test import with metadata section."""
        import_file = isolated_cli_environment["temp_dir"] / "import_with_metadata.yaml"
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

        result = cli_runner.invoke(
            app, ["config", "import", str(import_file), "--force"]
        )

        assert result.exit_code == 0
        assert "Configuration imported successfully" in result.output
        assert "Imported config generated at" in result.output
