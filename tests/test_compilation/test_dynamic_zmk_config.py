"""Tests for dynamic ZMK config generation."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from glovebox.compilation.generation.zmk_config_generator import (
    ZmkConfigContentGenerator,
    create_zmk_config_content_generator,
)
from glovebox.config.profile import KeyboardProfile


class TestZmkConfigContentGenerator:
    """Tests for ZMK config content generator."""

    def test_create_zmk_config_content_generator(self):
        """Test factory function creates generator."""
        generator = create_zmk_config_content_generator()
        assert isinstance(generator, ZmkConfigContentGenerator)

    def test_generate_config_workspace_basic(self):
        """Test basic workspace generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"
            keymap_file = Path(temp_dir) / "test.keymap"
            config_file = Path(temp_dir) / "test.conf"

            # Create test files
            keymap_file.write_text("/* Test keymap */\n")
            config_file.write_text("# Test config\n")

            # Create mock keyboard profile
            mock_profile = Mock(spec=KeyboardProfile)
            mock_profile.keyboard_name = "corne"
            mock_profile.keyboard_config = Mock()
            mock_profile.keyboard_config.description = "Corne keyboard"
            mock_profile.keyboard_config.vendor = "foostan"
            mock_profile.keyboard_config.key_count = 42

            generator = ZmkConfigContentGenerator()

            # Generate workspace
            result = generator.generate_config_workspace(
                workspace_path=workspace_path,
                keymap_file=keymap_file,
                config_file=config_file,
                keyboard_profile=mock_profile,
                shield_name="corne",
                board_name="nice_nano_v2",
            )

            assert result is True

            # Check generated files exist
            assert (workspace_path / "build.yaml").exists()
            assert (workspace_path / "config" / "west.yml").exists()
            assert (workspace_path / "config" / "corne.keymap").exists()
            assert (workspace_path / "config" / "corne.conf").exists()
            assert (workspace_path / "README.md").exists()
            assert (workspace_path / ".gitignore").exists()

    def test_create_build_yaml_content_split_keyboard(self):
        """Test build.yaml content for split keyboard."""
        generator = ZmkConfigContentGenerator()

        content = generator._create_build_yaml_content("corne", "nice_nano_v2")

        assert "corne_left" in content
        assert "corne_right" in content
        assert "nice_nano_v2" in content
        assert "include:" in content

    def test_create_build_yaml_content_single_keyboard(self):
        """Test build.yaml content for single keyboard."""
        generator = ZmkConfigContentGenerator()

        content = generator._create_build_yaml_content("planck", "nice_nano_v2")

        assert "planck_left" not in content
        assert "planck_right" not in content
        assert "shield: planck" in content
        assert "nice_nano_v2" in content

    def test_update_for_layout_changes(self):
        """Test updating workspace when layout changes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"
            workspace_path.mkdir(parents=True)
            (workspace_path / "config").mkdir(parents=True)

            # Create initial files
            original_keymap = Path(temp_dir) / "original.keymap"
            original_config = Path(temp_dir) / "original.conf"
            original_keymap.write_text("/* Original keymap */\n")
            original_config.write_text("# Original config\n")

            # Create updated files
            updated_keymap = Path(temp_dir) / "updated.keymap"
            updated_config = Path(temp_dir) / "updated.conf"
            updated_keymap.write_text("/* Updated keymap */\n")
            updated_config.write_text("# Updated config\n")

            generator = ZmkConfigContentGenerator()

            # Update workspace
            result = generator.update_for_layout_changes(
                workspace_path=workspace_path,
                keymap_file=updated_keymap,
                config_file=updated_config,
                shield_name="corne",
            )

            assert result is True

            # Check updated content
            workspace_keymap = workspace_path / "config" / "corne.keymap"
            workspace_config = workspace_path / "config" / "corne.conf"

            assert workspace_keymap.exists()
            assert workspace_config.exists()
            assert "Updated keymap" in workspace_keymap.read_text()
            assert "Updated config" in workspace_config.read_text()

    def test_workspace_generation_with_file_adapter(self):
        """Test workspace generation using file adapter."""
        mock_file_adapter = Mock()
        mock_file_adapter.create_directory.return_value = True
        mock_file_adapter.read_text.return_value = "test content"
        mock_file_adapter.write_text.return_value = None

        mock_profile = Mock(spec=KeyboardProfile)
        mock_profile.keyboard_name = "corne"
        mock_profile.keyboard_config = Mock()
        mock_profile.keyboard_config.description = "Test keyboard"
        mock_profile.keyboard_config.vendor = "test"
        mock_profile.keyboard_config.key_count = 42

        generator = ZmkConfigContentGenerator(file_adapter=mock_file_adapter)

        result = generator.generate_config_workspace(
            workspace_path=Path("/test/workspace"),
            keymap_file=Path("/test/keymap.keymap"),
            config_file=Path("/test/config.conf"),
            keyboard_profile=mock_profile,
        )

        assert result is True

        # Verify file adapter was used
        assert mock_file_adapter.create_directory.called
        assert mock_file_adapter.read_text.called
        assert mock_file_adapter.write_text.called
