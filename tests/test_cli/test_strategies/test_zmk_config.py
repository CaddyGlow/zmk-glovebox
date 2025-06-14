"""Tests for ZMK config strategy."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.cli.strategies.base import CompilationParams
from glovebox.cli.strategies.zmk_config import (
    ZmkConfigStrategy,
    create_zmk_config_strategy,
)
from glovebox.config.compile_methods import ZmkCompilationConfig
from glovebox.config.profile import KeyboardProfile


class TestZmkConfigStrategy:
    """Test ZMK config compilation strategy."""

    def test_strategy_creation(self):
        """Test creating ZMK config strategy."""
        strategy = create_zmk_config_strategy()
        assert strategy.name == "zmk_config"
        assert strategy.get_service_name() == "zmk_config_compilation"

    def test_supports_profile_standard_keyboard(self):
        """Test strategy supports standard keyboard profiles."""
        strategy = ZmkConfigStrategy()
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "planck"

        assert strategy.supports_profile(profile) is True

    def test_supports_profile_moergo_keyboard(self):
        """Test strategy does not support Moergo keyboards."""
        strategy = ZmkConfigStrategy()
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "glove80"

        assert strategy.supports_profile(profile) is False

    def test_extract_docker_image_from_profile(self):
        """Test extracting Docker image from profile."""
        strategy = ZmkConfigStrategy()

        # Mock profile with firmware config
        docker_config = Mock()
        docker_config.image = "custom-zmk:latest"

        firmware_version = Mock()
        firmware_version.docker_config = docker_config

        profile = Mock(spec=KeyboardProfile)
        profile.firmware_version = firmware_version

        image = strategy.extract_docker_image(profile)
        assert image == "custom-zmk:latest"

    def test_extract_docker_image_default(self):
        """Test extracting default Docker image."""
        strategy = ZmkConfigStrategy()
        profile = Mock(spec=KeyboardProfile)
        profile.firmware_version = None

        image = strategy.extract_docker_image(profile)
        assert image == "zmkfirmware/zmk-build-arm:stable"

    def test_build_config_basic(self, tmp_path):
        """Test building basic ZMK compilation configuration."""
        strategy = ZmkConfigStrategy()

        # Create test files
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
            jobs=4,
            verbose=True,
            no_cache=False,
            docker_uid=1000,
            docker_gid=1000,
            docker_username="user",
            docker_home="/home/user",
            docker_container_home="/home/builder",
            no_docker_user_mapping=False,
            board_targets="nice_nano_v2",
        )

        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "planck"

        config = strategy.build_config(params, profile)

        assert isinstance(config, ZmkCompilationConfig)
        assert config.jobs == 4
        assert config.docker_user.manual_uid == 1000
        assert config.docker_user.manual_gid == 1000
        assert config.docker_user.manual_username == "user"
        assert config.cache.enabled is True

    def test_build_config_with_no_cache(self, tmp_path):
        """Test building configuration with caching disabled."""
        strategy = ZmkConfigStrategy()

        # Create test files
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
            no_cache=True,
            docker_uid=None,
            docker_gid=None,
            docker_username=None,
            docker_home=None,
            docker_container_home=None,
            no_docker_user_mapping=True,
            board_targets=None,
        )

        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "planck"

        config = strategy.build_config(params, profile)

        assert config.cache.enabled is False
        assert config.docker_user.enable_user_mapping is False

    def test_is_moergo_profile(self):
        """Test Moergo profile detection."""
        strategy = ZmkConfigStrategy()

        # Test Moergo profile
        moergo_profile = Mock(spec=KeyboardProfile)
        moergo_profile.keyboard_name = "glove80_moergo"
        assert strategy._is_moergo_profile(moergo_profile) is True

        # Test Glove80 profile
        glove80_profile = Mock(spec=KeyboardProfile)
        glove80_profile.keyboard_name = "glove80"
        assert strategy._is_moergo_profile(glove80_profile) is True

        # Test standard profile
        standard_profile = Mock(spec=KeyboardProfile)
        standard_profile.keyboard_name = "planck"
        assert strategy._is_moergo_profile(standard_profile) is False

    def test_build_workspace_config(self, tmp_path):
        """Test building workspace configuration."""
        strategy = ZmkConfigStrategy()

        # Create test files
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
            repo="https://github.com/user/zmk-config",
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
        )

        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "planck"

        workspace_config = strategy._build_workspace_config(params, profile)

        assert workspace_config.build_matrix_file == Path("build.yaml")
        assert workspace_config.config_repo_url == "https://github.com/user/zmk-config"
        assert workspace_config.workspace_path.container_path == "/workspace"
        assert workspace_config.config_path.container_path == "/workspace/config"
        assert workspace_config.build_root.container_path == "/workspace/build"
