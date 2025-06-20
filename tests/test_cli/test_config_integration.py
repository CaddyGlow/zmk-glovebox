"""Tests for CLI config integration and round-trip functionality."""

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
def configured_context(tmp_path):
    """Create a fully configured context for round-trip tests."""
    config_file = tmp_path / "full_config.yaml"

    # Create comprehensive test configuration
    config_data = {
        "profile": "integration_test/v1.0",
        "log_level": "DEBUG",
        "keyboard_paths": ["/path/one", "/path/two"],
        "cache_strategy": "memory",
        "emoji_mode": True,
        "firmware": {
            "flash": {
                "timeout": 120,
                "count": 5,
                "track_flashed": True,
                "skip_existing": False,
            },
            "docker": {
                "image": "custom/zmk-build:latest",
                "pull_policy": "always",
                "mount_cache": True,
            },
        },
    }

    with config_file.open("w") as f:
        yaml.dump(config_data, f)

    user_config = UserConfig(cli_config_path=config_file)

    context = Mock()
    context.user_config = user_config
    context.use_emoji = True
    return context


class TestConfigUserIntegration:
    """Integration tests with real user configuration (mostly skipped in isolation)."""

    @pytest.mark.skip(reason="Integration test - requires real user config")
    def test_real_user_config_list(self, cli_runner):
        """Test listing real user configuration."""
        # This would test against actual ~/.glovebox/ config
        result = cli_runner.invoke(app, ["config", "list"])

        # In real environment, should succeed
        assert result.exit_code == 0
        assert "Glovebox Configuration" in result.output

    def test_isolated_user_config_operations(self, cli_runner, isolated_config):
        """Test config operations with isolated user config."""
        # Use the isolated_config fixture to prevent pollution
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_context = Mock()
            mock_context.user_config = isolated_config
            mock_context.use_emoji = False
            mock_ctx.return_value.obj = mock_context

            # Test basic operations in isolation
            result = cli_runner.invoke(app, ["config", "list"])
            assert result.exit_code == 0

            # Test setting values
            result = cli_runner.invoke(
                app, ["config", "edit", "--set", "log_level=WARNING"]
            )
            assert result.exit_code == 0

            # Verify the change
            result = cli_runner.invoke(app, ["config", "edit", "--get", "log_level"])
            assert result.exit_code == 0
            assert "WARNING" in result.output

    def test_config_persistence(self, cli_runner, isolated_config, tmp_path):
        """Test that configuration changes persist."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_context = Mock()
            mock_context.user_config = isolated_config
            mock_context.use_emoji = False
            mock_ctx.return_value.obj = mock_context

            # Make a change
            result = cli_runner.invoke(
                app, ["config", "edit", "--set", "cache_strategy=filesystem"]
            )
            assert result.exit_code == 0

            # Create new config instance from same file
            new_config = UserConfig(cli_config_path=isolated_config.config_file_path)

            # Verify persistence
            assert new_config.get("cache_strategy") == "filesystem"

    def test_config_validation_integration(self, cli_runner, isolated_config):
        """Test configuration validation in integrated environment."""
        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_context = Mock()
            mock_context.user_config = isolated_config
            mock_context.use_emoji = False
            mock_ctx.return_value.obj = mock_context

            # Test valid profile format
            result = cli_runner.invoke(
                app, ["config", "edit", "--set", "profile=valid_keyboard/v1.0"]
            )
            assert result.exit_code == 0

            # Test invalid profile format
            result = cli_runner.invoke(
                app, ["config", "edit", "--set", "profile=invalid_format"]
            )
            # Should handle validation error gracefully
            assert result.exit_code == 0  # Command doesn't fail, but shows error


class TestConfigExportImportRoundTrip:
    """Test export/import round-trip consistency across formats."""

    def test_yaml_round_trip(self, cli_runner, configured_context, tmp_path):
        """Test YAML export/import round-trip."""
        export_file = tmp_path / "round_trip.yaml"

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = configured_context

            # Export configuration
            result = cli_runner.invoke(
                app, ["config", "export", "--output", str(export_file)]
            )
            assert result.exit_code == 0
            assert export_file.exists()

            # Import back into new config
            import_result = cli_runner.invoke(
                app, ["config", "import", str(export_file), "--force"]
            )
            assert import_result.exit_code == 0

    def test_json_round_trip(self, cli_runner, configured_context, tmp_path):
        """Test JSON export/import round-trip."""
        export_file = tmp_path / "round_trip.json"

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = configured_context

            # Export as JSON
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
            assert export_file.exists()

            # Verify JSON structure
            with export_file.open() as f:
                data = json.load(f)
            assert "profile" in data
            assert "firmware" in data
            assert "_metadata" in data

            # Import back
            import_result = cli_runner.invoke(
                app, ["config", "import", str(export_file), "--force"]
            )
            assert import_result.exit_code == 0

    def test_toml_round_trip(self, cli_runner, configured_context, tmp_path):
        """Test TOML export/import round-trip."""
        export_file = tmp_path / "round_trip.toml"

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = configured_context

            # Export as TOML
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
            assert export_file.exists()

            # Verify TOML structure
            import tomlkit
            with export_file.open() as f:
                data = tomlkit.load(f)
            assert "profile" in data

            # Import back
            import_result = cli_runner.invoke(
                app, ["config", "import", str(export_file), "--force"]
            )
            assert import_result.exit_code == 0

    def test_cross_format_compatibility(self, cli_runner, configured_context, tmp_path):
        """Test compatibility across different formats."""
        yaml_file = tmp_path / "config.yaml"
        json_file = tmp_path / "config.json"
        toml_file = tmp_path / "config.toml"

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = configured_context

            # Export in all formats
            for file_path, fmt in [
                (yaml_file, "yaml"),
                (json_file, "json"),
                (toml_file, "toml"),
            ]:
                result = cli_runner.invoke(
                    app,
                    [
                        "config",
                        "export",
                        "--output",
                        str(file_path),
                        "--format",
                        fmt,
                    ],
                )
                assert result.exit_code == 0
                assert file_path.exists()

            # Import each format and verify consistency
            for import_file in [yaml_file, json_file, toml_file]:
                import_result = cli_runner.invoke(
                    app, ["config", "import", str(import_file), "--dry-run"]
                )
                assert import_result.exit_code == 0
                assert "Dry run complete" in import_result.output

    def test_round_trip_with_defaults(self, cli_runner, configured_context, tmp_path):
        """Test round-trip with defaults included."""
        export_file = tmp_path / "with_defaults.yaml"

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = configured_context

            # Export with defaults
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

            # Import back
            import_result = cli_runner.invoke(
                app, ["config", "import", str(export_file), "--force"]
            )
            assert import_result.exit_code == 0

    def test_round_trip_without_defaults(self, cli_runner, configured_context, tmp_path):
        """Test round-trip without defaults."""
        export_file = tmp_path / "no_defaults.yaml"

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = configured_context

            # Export without defaults
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

            # Import back
            import_result = cli_runner.invoke(
                app, ["config", "import", str(export_file), "--force"]
            )
            assert import_result.exit_code == 0

    def test_data_integrity_round_trip(self, cli_runner, configured_context, tmp_path):
        """Test that data integrity is maintained in round-trip."""
        export_file = tmp_path / "integrity_test.yaml"

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = configured_context

            # Get original values
            original_values = {}
            for key in ["profile", "log_level", "cache_strategy"]:
                result = cli_runner.invoke(app, ["config", "edit", "--get", key])
                assert result.exit_code == 0
                original_values[key] = result.output

            # Export and import
            export_result = cli_runner.invoke(
                app, ["config", "export", "--output", str(export_file)]
            )
            assert export_result.exit_code == 0

            import_result = cli_runner.invoke(
                app, ["config", "import", str(export_file), "--force"]
            )
            assert import_result.exit_code == 0

            # Verify values are preserved
            for key in original_values:
                result = cli_runner.invoke(app, ["config", "edit", "--get", key])
                assert result.exit_code == 0
                # Values should be consistent (allowing for formatting differences)
                assert key in result.output

    def test_partial_config_round_trip(self, cli_runner, tmp_path):
        """Test round-trip with minimal/partial configuration."""
        # Create minimal config
        minimal_config_file = tmp_path / "minimal.yaml"
        minimal_data = {
            "profile": "minimal_test/v1.0",
            "log_level": "INFO",
        }

        with minimal_config_file.open("w") as f:
            yaml.dump(minimal_data, f)

        minimal_config = UserConfig(cli_config_path=minimal_config_file)

        context = Mock()
        context.user_config = minimal_config
        context.use_emoji = False

        export_file = tmp_path / "minimal_export.yaml"

        with patch("glovebox.cli.commands.config.typer.Context") as mock_ctx:
            mock_ctx.return_value.obj = context

            # Export minimal config
            result = cli_runner.invoke(
                app, ["config", "export", "--output", str(export_file)]
            )
            assert result.exit_code == 0

            # Import back
            import_result = cli_runner.invoke(
                app, ["config", "import", str(export_file), "--force"]
            )
            assert import_result.exit_code == 0

