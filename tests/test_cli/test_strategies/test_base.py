"""Tests for base strategy classes."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from glovebox.cli.strategies.base import BaseCompilationStrategy, CompilationParams
from glovebox.config.profile import KeyboardProfile


class TestCompilationStrategy(BaseCompilationStrategy):
    """Test implementation of base strategy."""

    def supports_profile(self, profile: KeyboardProfile) -> bool:
        return True

    def extract_docker_image(self, profile: KeyboardProfile) -> str:
        return "test-image:latest"

    def build_config(self, params: CompilationParams, profile: KeyboardProfile):
        return Mock()

    def get_service_name(self) -> str:
        return "test_service"


class TestCompilationParams:
    """Test CompilationParams dataclass."""

    def test_compilation_params_creation(self, tmp_path):
        """Test creating CompilationParams."""
        keymap_file = tmp_path / "test.keymap"
        kconfig_file = tmp_path / "test.conf"
        output_dir = tmp_path / "output"

        keymap_file.touch()
        kconfig_file.touch()

        params = CompilationParams(
            keymap_file=keymap_file,
            kconfig_file=kconfig_file,
            output_dir=output_dir,
            branch=None,
            repo=None,
            jobs=None,
            verbose=False,
            no_cache=False,
            docker_uid=None,
            docker_gid=None,
            docker_username=None,
            docker_home=None,
            docker_container_home=None,
            no_docker_user_mapping=False,
            board_targets=None,
            preserve_workspace=False,
            force_cleanup=False,
            clear_cache=False,
        )

        assert params.keymap_file == keymap_file
        assert params.kconfig_file == kconfig_file
        assert params.output_dir == output_dir
        assert params.verbose is False


class TestBaseCompilationStrategy:
    """Test BaseCompilationStrategy abstract class."""

    def test_strategy_name(self):
        """Test strategy name property."""
        strategy = TestCompilationStrategy("test_strategy")
        assert strategy.name == "test_strategy"

    def test_default_docker_image(self):
        """Test default Docker image generation."""
        strategy = TestCompilationStrategy("test")
        profile = Mock(spec=KeyboardProfile)

        image = strategy._get_default_docker_image(profile)
        assert image == "zmkfirmware/zmk-build-arm:stable"

    def test_validate_params_success(self, tmp_path):
        """Test parameter validation with valid files."""
        strategy = TestCompilationStrategy("test")

        keymap_file = tmp_path / "test.keymap"
        kconfig_file = tmp_path / "test.conf"
        output_dir = tmp_path / "output"

        keymap_file.touch()
        kconfig_file.touch()
        output_dir.mkdir()

        params = CompilationParams(
            keymap_file=keymap_file,
            kconfig_file=kconfig_file,
            output_dir=output_dir,
            branch=None,
            repo=None,
            jobs=None,
            verbose=False,
            no_cache=False,
            docker_uid=None,
            docker_gid=None,
            docker_username=None,
            docker_home=None,
            docker_container_home=None,
            no_docker_user_mapping=False,
            board_targets=None,
            preserve_workspace=False,
            force_cleanup=False,
            clear_cache=False,
        )

        # Should not raise
        strategy._validate_params(params)

    def test_validate_params_missing_keymap(self, tmp_path):
        """Test parameter validation with missing keymap file."""
        strategy = TestCompilationStrategy("test")

        keymap_file = tmp_path / "missing.keymap"
        kconfig_file = tmp_path / "test.conf"
        output_dir = tmp_path / "output"

        kconfig_file.touch()
        output_dir.mkdir()

        params = CompilationParams(
            keymap_file=keymap_file,
            kconfig_file=kconfig_file,
            output_dir=output_dir,
            branch=None,
            repo=None,
            jobs=None,
            verbose=False,
            no_cache=False,
            docker_uid=None,
            docker_gid=None,
            docker_username=None,
            docker_home=None,
            docker_container_home=None,
            no_docker_user_mapping=False,
            board_targets=None,
            preserve_workspace=False,
            force_cleanup=False,
            clear_cache=False,
        )

        with pytest.raises(ValueError, match="Keymap file not found"):
            strategy._validate_params(params)
