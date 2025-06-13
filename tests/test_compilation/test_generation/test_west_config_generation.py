"""Integration tests for .west/config file generation in ZmkConfigContentGenerator."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from glovebox.compilation.generation.zmk_config_generator import (
    ZmkConfigContentGenerator,
)
from glovebox.config.profile import KeyboardProfile


@pytest.fixture
def mock_keyboard_profile():
    """Create a mock keyboard profile for testing."""
    profile = Mock(spec=KeyboardProfile)
    profile.keyboard_name = "test_keyboard"

    # Mock keyboard config
    keyboard_config = Mock()
    keyboard_config.description = "Test Keyboard"
    keyboard_config.vendor = "Test Vendor"
    keyboard_config.key_count = 60
    profile.keyboard_config = keyboard_config

    # Mock firmware config
    firmware_config = Mock()
    build_options = Mock()
    build_options.repository = "zmkfirmware/zmk"
    build_options.branch = "main"
    firmware_config.build_options = build_options
    profile.firmware_config = firmware_config

    return profile


@pytest.fixture
def temp_files():
    """Create temporary keymap and config files for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create mock keymap file
        keymap_file = temp_path / "test.keymap"
        keymap_file.write_text("""
// Test keymap content
#include <behaviors.dtsi>
#include <dt-bindings/zmk/keys.h>

/ {
    keymap {
        compatible = "zmk,keymap";

        default_layer {
            bindings = <&kp A>;
        };
    };
};
""")

        # Create mock config file
        config_file = temp_path / "test.conf"
        config_file.write_text("""
# Test config content
CONFIG_ZMK_KEYBOARD_NAME="test_keyboard"
CONFIG_ZMK_SLEEP=y
""")

        yield {
            "temp_dir": temp_path,
            "keymap_file": keymap_file,
            "config_file": config_file,
        }


class TestWestConfigGeneration:
    """Test .west/config file generation in ZmkConfigContentGenerator."""

    def test_generate_west_config_file_default(self, temp_files, mock_keyboard_profile):
        """Test generating .west/config file with default paths."""
        generator = ZmkConfigContentGenerator()
        workspace_path = temp_files["temp_dir"] / "workspace"
        workspace_path.mkdir()

        # Generate workspace with default paths
        success = generator.generate_config_workspace(
            workspace_path=workspace_path,
            keymap_file=temp_files["keymap_file"],
            config_file=temp_files["config_file"],
            keyboard_profile=mock_keyboard_profile,
            shield_name="test_keyboard",
            board_name="nice_nano_v2",
        )

        assert success

        # Check that .west/config was created
        west_config_path = workspace_path / ".west" / "config"
        assert west_config_path.exists()

        # Verify content
        config_content = west_config_path.read_text()
        assert "[manifest]" in config_content
        assert "[zephyr]" in config_content
        assert "path = config" in config_content
        assert "file = west.yml" in config_content
        assert "base = zephyr" in config_content

    def test_generate_west_config_file_custom_paths(
        self, temp_files, mock_keyboard_profile
    ):
        """Test generating .west/config file with custom paths."""
        generator = ZmkConfigContentGenerator()
        workspace_path = temp_files["temp_dir"] / "workspace"
        workspace_path.mkdir()

        # Create separate config directory
        separate_config_path = temp_files["temp_dir"] / "custom_config"
        separate_config_path.mkdir()

        # Generate workspace with custom paths
        success = generator.generate_config_workspace(
            workspace_path=workspace_path,
            keymap_file=temp_files["keymap_file"],
            config_file=temp_files["config_file"],
            keyboard_profile=mock_keyboard_profile,
            shield_name="test_keyboard",
            board_name="nice_nano_v2",
            separate_config_path=separate_config_path,
            zephyr_base_path="custom/zephyr",
        )

        assert success

        # Check that .west/config was created
        west_config_path = workspace_path / ".west" / "config"
        assert west_config_path.exists()

        # Verify content has custom paths
        config_content = west_config_path.read_text()
        assert "[manifest]" in config_content
        assert "[zephyr]" in config_content
        assert "file = west.yml" in config_content
        assert "base = custom/zephyr" in config_content

        # Should contain relative path to separate config directory
        try:
            relative_path = separate_config_path.relative_to(workspace_path)
            assert f"path = {relative_path}" in config_content
        except ValueError:
            # If paths are not relative, should use absolute path
            assert f"path = {separate_config_path}" in config_content

    def test_west_config_file_parseable(self, temp_files, mock_keyboard_profile):
        """Test that generated .west/config file is parseable by configparser."""
        import configparser

        generator = ZmkConfigContentGenerator()
        workspace_path = temp_files["temp_dir"] / "workspace"
        workspace_path.mkdir()

        # Generate workspace
        success = generator.generate_config_workspace(
            workspace_path=workspace_path,
            keymap_file=temp_files["keymap_file"],
            config_file=temp_files["config_file"],
            keyboard_profile=mock_keyboard_profile,
            shield_name="test_keyboard",
            board_name="nice_nano_v2",
            zephyr_base_path="test/zephyr",
        )

        assert success

        # Parse the generated config file
        west_config_path = workspace_path / ".west" / "config"
        parser = configparser.ConfigParser()
        parser.read(west_config_path)

        # Verify sections and values
        assert "manifest" in parser.sections()
        assert "zephyr" in parser.sections()

        assert parser.get("manifest", "path") == "config"
        assert parser.get("manifest", "file") == "west.yml"
        assert parser.get("zephyr", "base") == "test/zephyr"

    def test_west_config_with_relative_separate_path(
        self, temp_files, mock_keyboard_profile
    ):
        """Test .west/config generation with separate config path relative to workspace."""
        generator = ZmkConfigContentGenerator()
        workspace_path = temp_files["temp_dir"] / "workspace"
        workspace_path.mkdir()

        # Create separate config directory inside workspace
        separate_config_path = workspace_path / "custom_config"
        separate_config_path.mkdir()

        # Generate workspace
        success = generator.generate_config_workspace(
            workspace_path=workspace_path,
            keymap_file=temp_files["keymap_file"],
            config_file=temp_files["config_file"],
            keyboard_profile=mock_keyboard_profile,
            shield_name="test_keyboard",
            board_name="nice_nano_v2",
            separate_config_path=separate_config_path,
            zephyr_base_path="zephyr",
        )

        assert success

        # Check generated config
        west_config_path = workspace_path / ".west" / "config"
        config_content = west_config_path.read_text()

        # Should use relative path
        assert "path = custom_config" in config_content

    def test_west_config_directory_creation(self, temp_files, mock_keyboard_profile):
        """Test that .west directory is created if it doesn't exist."""
        generator = ZmkConfigContentGenerator()
        workspace_path = temp_files["temp_dir"] / "workspace"
        workspace_path.mkdir()

        # Ensure .west directory doesn't exist initially
        west_dir = workspace_path / ".west"
        assert not west_dir.exists()

        # Generate workspace
        success = generator.generate_config_workspace(
            workspace_path=workspace_path,
            keymap_file=temp_files["keymap_file"],
            config_file=temp_files["config_file"],
            keyboard_profile=mock_keyboard_profile,
            shield_name="test_keyboard",
            board_name="nice_nano_v2",
        )

        assert success

        # Check that .west directory and config file were created
        assert west_dir.exists()
        assert west_dir.is_dir()
        assert (west_dir / "config").exists()
        assert (west_dir / "config").is_file()
