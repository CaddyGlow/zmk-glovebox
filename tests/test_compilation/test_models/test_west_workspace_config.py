"""Tests for WestWorkspaceConfig models."""

import tempfile
from pathlib import Path

import pytest

from glovebox.compilation.models.west_config import (
    WestManifestSection,
    WestWorkspaceConfig,
    WestZephyrSection,
)


class TestWestManifestSection:
    """Tests for WestManifestSection."""

    def test_default_values(self):
        """Test default values for WestManifestSection."""
        section = WestManifestSection()
        assert section.path == "config"
        assert section.file == "west.yml"

    def test_custom_values(self):
        """Test custom values for WestManifestSection."""
        section = WestManifestSection(path="custom/config", file="custom.yml")
        assert section.path == "custom/config"
        assert section.file == "custom.yml"


class TestWestZephyrSection:
    """Tests for WestZephyrSection."""

    def test_default_values(self):
        """Test default values for WestZephyrSection."""
        section = WestZephyrSection()
        assert section.base == "zephyr"

    def test_custom_values(self):
        """Test custom values for WestZephyrSection."""
        section = WestZephyrSection(base="custom/zephyr")
        assert section.base == "custom/zephyr"


class TestWestWorkspaceConfig:
    """Tests for WestWorkspaceConfig."""

    def test_create_default(self):
        """Test creating default WestWorkspaceConfig."""
        config = WestWorkspaceConfig.create_default()

        assert config.manifest.path == "config"
        assert config.manifest.file == "west.yml"
        assert config.zephyr.base == "zephyr"

    def test_create_default_with_custom_paths(self):
        """Test creating WestWorkspaceConfig with custom paths."""
        config = WestWorkspaceConfig.create_default(
            config_path="custom/config", zephyr_base="custom/zephyr"
        )

        assert config.manifest.path == "custom/config"
        assert config.manifest.file == "west.yml"
        assert config.zephyr.base == "custom/zephyr"

    def test_to_ini_string_default(self):
        """Test serializing default config to INI string."""
        config = WestWorkspaceConfig.create_default()
        ini_content = config.to_ini_string()

        # Check that the INI content contains expected sections and values
        assert "[manifest]" in ini_content
        assert "[zephyr]" in ini_content
        assert "path = config" in ini_content
        assert "file = west.yml" in ini_content
        assert "base = zephyr" in ini_content

    def test_to_ini_string_custom(self):
        """Test serializing custom config to INI string."""
        config = WestWorkspaceConfig.create_default(
            config_path="custom/path", zephyr_base="custom/zephyr"
        )
        ini_content = config.to_ini_string()

        # Check that the INI content contains custom values
        assert "[manifest]" in ini_content
        assert "[zephyr]" in ini_content
        assert "path = custom/path" in ini_content
        assert "file = west.yml" in ini_content
        assert "base = custom/zephyr" in ini_content

    def test_from_ini_file(self):
        """Test loading WestWorkspaceConfig from INI file."""
        # Create a temporary INI file
        ini_content = """[manifest]
path = test/config
file = test.yml

[zephyr]
base = test/zephyr
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write(ini_content)
            temp_path = Path(f.name)

        try:
            # Load config from file
            config = WestWorkspaceConfig.from_ini_file(temp_path)

            # Verify loaded values
            assert config.manifest.path == "test/config"
            assert config.manifest.file == "test.yml"
            assert config.zephyr.base == "test/zephyr"
        finally:
            # Clean up
            temp_path.unlink()

    def test_round_trip_serialization(self):
        """Test round-trip serialization (create -> serialize -> deserialize)."""
        # Create original config
        original_config = WestWorkspaceConfig.create_default(
            config_path="round/trip/config", zephyr_base="round/trip/zephyr"
        )

        # Serialize to INI
        ini_content = original_config.to_ini_string()

        # Write to temporary file and read back
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write(ini_content)
            temp_path = Path(f.name)

        try:
            # Load config from file
            loaded_config = WestWorkspaceConfig.from_ini_file(temp_path)

            # Verify they match
            assert loaded_config.manifest.path == original_config.manifest.path
            assert loaded_config.manifest.file == original_config.manifest.file
            assert loaded_config.zephyr.base == original_config.zephyr.base
        finally:
            # Clean up
            temp_path.unlink()

    def test_ini_format_compliance(self):
        """Test that generated INI follows standard format."""
        config = WestWorkspaceConfig.create_default(
            config_path="format/test", zephyr_base="format/zephyr"
        )
        ini_content = config.to_ini_string()

        # Should be parseable by configparser
        import configparser

        parser = configparser.ConfigParser()
        parser.read_string(ini_content)

        # Verify sections exist
        assert "manifest" in parser.sections()
        assert "zephyr" in parser.sections()

        # Verify values
        assert parser.get("manifest", "path") == "format/test"
        assert parser.get("manifest", "file") == "west.yml"
        assert parser.get("zephyr", "base") == "format/zephyr"

    def test_edge_cases(self):
        """Test edge cases and special characters."""
        # Test with paths containing spaces and special characters
        config = WestWorkspaceConfig.create_default(
            config_path="path with spaces/config",
            zephyr_base="zephyr-with-dashes_and_underscores",
        )

        # Should serialize and deserialize correctly
        ini_content = config.to_ini_string()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write(ini_content)
            temp_path = Path(f.name)

        try:
            loaded_config = WestWorkspaceConfig.from_ini_file(temp_path)
            assert loaded_config.manifest.path == "path with spaces/config"
            assert loaded_config.zephyr.base == "zephyr-with-dashes_and_underscores"
        finally:
            temp_path.unlink()
