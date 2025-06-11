"""Test VolumeManager class."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.compilation.configuration.volume_manager import (
    VolumeManager,
    VolumeManagerError,
    create_volume_manager,
)
from glovebox.config.compile_methods import CompilationConfig


class TestVolumeManager:
    """Test VolumeManager functionality."""

    def setup_method(self):
        """Set up test instance."""
        self.manager = VolumeManager()

    def test_initialization(self):
        """Test manager initialization."""
        assert hasattr(self.manager, "logger")

    def test_create_volume_manager(self):
        """Test factory function."""
        manager = create_volume_manager()
        assert isinstance(manager, VolumeManager)

    def test_prepare_volumes_basic(self):
        """Test basic volume preparation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            keymap_file = temp_path / "keymap.keymap"
            config_file = temp_path / "config.conf"
            output_dir = temp_path / "output"

            # Create test files
            keymap_file.touch()
            config_file.touch()
            output_dir.mkdir()

            config = Mock(spec=CompilationConfig)
            config.volume_templates = [
                "{keymap_dir}:/workspace/keymap:ro",
                "{output_dir}:/workspace/output",
            ]

            result = self.manager.prepare_volumes(
                config, keymap_file, config_file, output_dir
            )

            assert len(result) == 2
            assert f"{temp_path}:/workspace/keymap:ro" in result
            assert f"{output_dir}:/workspace/output" in result

    def test_prepare_volumes_with_context(self):
        """Test volume preparation with additional context."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            keymap_file = temp_path / "keymap.keymap"
            config_file = temp_path / "config.conf"
            output_dir = temp_path / "output"

            keymap_file.touch()
            config_file.touch()
            output_dir.mkdir()

            config = Mock(spec=CompilationConfig)
            config.volume_templates = [
                "{custom_path}:/workspace/custom",
            ]

            result = self.manager.prepare_volumes(
                config, keymap_file, config_file, output_dir, custom_path=str(temp_path)
            )

            assert len(result) == 1
            assert f"{temp_path}:/workspace/custom" in result

    def test_prepare_volumes_missing_source(self):
        """Test error handling for missing source paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            keymap_file = temp_path / "keymap.keymap"
            config_file = temp_path / "config.conf"
            output_dir = temp_path / "output"

            keymap_file.touch()
            config_file.touch()
            # Don't create output_dir

            config = Mock(spec=CompilationConfig)
            config.volume_templates = [
                "/nonexistent/path:/workspace/missing",
            ]

            with pytest.raises(VolumeManagerError, match="Source path does not exist"):
                self.manager.prepare_volumes(
                    config, keymap_file, config_file, output_dir
                )

    def test_prepare_volumes_docker_volume(self):
        """Test Docker named volumes (skip existence check)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            keymap_file = temp_path / "keymap.keymap"
            config_file = temp_path / "config.conf"
            output_dir = temp_path / "output"

            keymap_file.touch()
            config_file.touch()
            output_dir.mkdir()

            config = Mock(spec=CompilationConfig)
            config.volume_templates = [
                "zmk-cache:/workspace/cache",  # Docker volume name
            ]

            result = self.manager.prepare_volumes(
                config, keymap_file, config_file, output_dir
            )

            assert len(result) == 1
            assert "zmk-cache:/workspace/cache" in result

    def test_expand_volume_template_missing_variable(self):
        """Test error handling for missing template variables."""
        template = "{missing_var}:/workspace"
        context = {"keymap_dir": "/test"}

        with pytest.raises(VolumeManagerError, match="Missing template variable"):
            self.manager._expand_volume_template(template, context)

    def test_expand_volume_template_invalid_format(self):
        """Test error handling for invalid volume format."""
        template = "/invalid/format"  # Missing colon
        context: dict[str, str] = {}

        with pytest.raises(VolumeManagerError, match="Invalid volume format"):
            self.manager._expand_volume_template(template, context)

    def test_build_template_context(self):
        """Test template context building."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            keymap_file = temp_path / "keymap.keymap"
            config_file = temp_path / "config.conf"
            output_dir = temp_path / "output"

            keymap_file.touch()
            config_file.touch()
            output_dir.mkdir()

            context = self.manager._build_template_context(
                keymap_file, config_file, output_dir, custom_var="custom_value"
            )

            assert "keymap_file" in context
            assert "keymap_dir" in context
            assert "config_file" in context
            assert "config_dir" in context
            assert "output_dir" in context
            assert "project_root" in context
            assert "home_dir" in context
            assert "cwd" in context
            assert "custom_var" in context
            assert context["custom_var"] == "custom_value"

    def test_find_project_root_with_git(self):
        """Test project root detection with .git directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            git_dir = temp_path / ".git"
            git_dir.mkdir()

            subdir = temp_path / "subdir"
            subdir.mkdir()
            test_file = subdir / "test.txt"
            test_file.touch()

            root = self.manager._find_project_root(test_file)
            assert root == temp_path

    def test_find_project_root_with_pyproject(self):
        """Test project root detection with pyproject.toml."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            pyproject_file = temp_path / "pyproject.toml"
            pyproject_file.touch()

            subdir = temp_path / "subdir" / "nested"
            subdir.mkdir(parents=True)
            test_file = subdir / "test.txt"
            test_file.touch()

            root = self.manager._find_project_root(test_file)
            assert root == temp_path

    def test_find_project_root_fallback(self):
        """Test project root fallback to current directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            test_file = temp_path / "test.txt"
            test_file.touch()

            with patch("pathlib.Path.cwd", return_value=temp_path):
                root = self.manager._find_project_root(test_file)
                assert root == temp_path

    def test_validate_volume_templates_valid(self):
        """Test validation of valid volume templates."""
        templates = [
            "/path/to/source:/target",
            "/source:/target:ro",
            "{keymap_dir}:/workspace",
            "named-volume:/data",
        ]

        result = self.manager.validate_volume_templates(templates)
        assert result is True

    def test_validate_volume_templates_empty(self):
        """Test validation fails for empty templates."""
        templates = ["", "  "]

        with pytest.raises(VolumeManagerError, match="Empty volume template"):
            self.manager.validate_volume_templates(templates)

    def test_validate_volume_templates_no_colon(self):
        """Test validation fails for templates without colon."""
        templates = ["/invalid/format"]

        with pytest.raises(VolumeManagerError, match="Must contain ':'"):
            self.manager.validate_volume_templates(templates)

    def test_validate_volume_templates_with_variables(self):
        """Test validation of templates with variables."""
        templates = [
            "{keymap_dir}:/workspace",
            "{output_dir}:/output:rw",
        ]

        with patch.object(self.manager.logger, "debug") as mock_debug:
            result = self.manager.validate_volume_templates(templates)
            assert result is True
            # Should log detected variables
            assert mock_debug.call_count >= 2


class TestVolumeManagerIntegration:
    """Test VolumeManager integration scenarios."""

    def setup_method(self):
        """Set up test instance."""
        self.manager = VolumeManager()

    def test_zmk_build_volumes(self):
        """Test typical ZMK build volume configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create ZMK-like directory structure
            config_dir = temp_path / "config"
            config_dir.mkdir()
            keymap_file = config_dir / "glove80.keymap"
            config_file = config_dir / "glove80.conf"
            output_dir = temp_path / "firmware"

            keymap_file.touch()
            config_file.touch()
            output_dir.mkdir()

            config = Mock(spec=CompilationConfig)
            config.volume_templates = [
                "{config_dir}:/workspace/config:ro",
                "{output_dir}:/workspace/firmware",
                "zmk-modules:/workspace/modules:ro",
            ]

            result = self.manager.prepare_volumes(
                config, keymap_file, config_file, output_dir
            )

            assert len(result) == 3
            assert f"{config_dir}:/workspace/config:ro" in result
            assert f"{output_dir}:/workspace/firmware" in result
            assert "zmk-modules:/workspace/modules:ro" in result

    def test_corne_build_volumes(self):
        """Test Corne keyboard volume configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create Corne-like structure
            keymap_file = temp_path / "corne.keymap"
            config_file = temp_path / "corne.conf"
            output_dir = temp_path / "build"

            keymap_file.touch()
            config_file.touch()
            output_dir.mkdir()

            config = Mock(spec=CompilationConfig)
            config.volume_templates = [
                "{keymap_file}:/workspace/corne.keymap:ro",
                "{config_file}:/workspace/corne.conf:ro",
                "{output_dir}:/workspace/build",
            ]

            result = self.manager.prepare_volumes(
                config, keymap_file, config_file, output_dir
            )

            assert len(result) == 3
            # Check file-level mounts
            assert f"{keymap_file}:/workspace/corne.keymap:ro" in result
            assert f"{config_file}:/workspace/corne.conf:ro" in result
            assert f"{output_dir}:/workspace/build" in result

    def test_complex_template_expansion(self):
        """Test complex template expansion with multiple variables."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            keymap_file = temp_path / "keymap.keymap"
            config_file = temp_path / "config.conf"
            output_dir = temp_path / "output"

            # Create additional directories for volume mounts
            cache_dir = temp_path / "cache"
            zmk_dir = temp_path / ".zmk"

            keymap_file.touch()
            config_file.touch()
            output_dir.mkdir()
            cache_dir.mkdir()
            zmk_dir.mkdir()

            config = Mock(spec=CompilationConfig)
            config.volume_templates = [
                "{cache_dir}:/workspace/cache",
                "{zmk_dir}:/workspace/user",
            ]

            result = self.manager.prepare_volumes(
                config,
                keymap_file,
                config_file,
                output_dir,
                cache_dir=str(cache_dir),
                zmk_dir=str(zmk_dir),
            )

            assert len(result) == 2
            # Should contain expanded paths
            for volume in result:
                assert ":/workspace/" in volume
                assert "{" not in volume  # No unexpanded templates
