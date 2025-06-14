"""Tests for Moergo strategy."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from glovebox.cli.strategies.base import CompilationParams
from glovebox.cli.strategies.moergo import MoergoStrategy, create_moergo_strategy
from glovebox.config.compile_methods import MoergoCompilationConfig
from glovebox.config.profile import KeyboardProfile


class TestMoergoStrategy:
    """Test Moergo compilation strategy."""

    def test_strategy_creation(self):
        """Test creating Moergo strategy."""
        strategy = create_moergo_strategy()
        assert strategy.name == "moergo"
        assert strategy.get_service_name() == "moergo_compilation"

    def test_supports_profile_moergo_keyboard(self):
        """Test strategy supports Moergo keyboards."""
        strategy = MoergoStrategy()
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "glove80_moergo"

        assert strategy.supports_profile(profile) is True

    def test_supports_profile_glove80_keyboard(self):
        """Test strategy supports Glove80 keyboards."""
        strategy = MoergoStrategy()
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "glove80"

        assert strategy.supports_profile(profile) is True

    def test_supports_profile_standard_keyboard(self):
        """Test strategy does not support standard keyboards."""
        strategy = MoergoStrategy()
        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "planck"

        assert strategy.supports_profile(profile) is False

    def test_extract_docker_image_from_profile(self):
        """Test extracting Docker image from profile."""
        strategy = MoergoStrategy()

        # Mock profile with firmware config
        docker_config = Mock()
        docker_config.image = "custom-moergo:latest"

        firmware_version = Mock()
        firmware_version.docker_config = docker_config

        profile = Mock(spec=KeyboardProfile)
        profile.firmware_version = firmware_version

        image = strategy.extract_docker_image(profile)
        assert image == "custom-moergo:latest"

    def test_extract_docker_image_default(self):
        """Test extracting default Docker image."""
        strategy = MoergoStrategy()
        profile = Mock(spec=KeyboardProfile)
        profile.firmware_version = None

        image = strategy.extract_docker_image(profile)
        assert image == "glove80-zmk-config-docker"

    def test_build_config_basic(self, tmp_path):
        """Test building basic Moergo compilation configuration."""
        strategy = MoergoStrategy()

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
            branch="v25.05",
            repo=None,
            jobs=2,
            verbose=True,
            no_cache=False,
            docker_uid=1000,
            docker_gid=1000,
            docker_username="user",
            docker_home="/home/user",
            docker_container_home="/home/builder",
            no_docker_user_mapping=False,
            board_targets="glove80",
            preserve_workspace=False,
            force_cleanup=False,
            clear_cache=False,
        )

        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "glove80_moergo"

        config = strategy.build_config(params, profile)

        assert isinstance(config, MoergoCompilationConfig)
        assert config.jobs == 2
        assert config.branch == "v25.05"
        assert config.docker_user.enable_user_mapping is True
        assert config.docker_user.manual_uid == 1000
        assert config.workspace_path.host_path == output_dir
        assert config.workspace_path.container_path == "/config"

    def test_build_config_disabled_user_mapping(self, tmp_path):
        """Test building configuration with disabled user mapping."""
        strategy = MoergoStrategy()

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
            preserve_workspace=False,
            force_cleanup=False,
            clear_cache=False,
        )

        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "glove80"

        config = strategy.build_config(params, profile)

        assert config.docker_user.enable_user_mapping is False
        assert config.branch == "v25.05"  # Default branch

    def test_get_repository_branch_from_params(self, tmp_path):
        """Test getting repository branch from parameters."""
        strategy = MoergoStrategy()

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
            branch="custom-branch",
            repo=None,
            jobs=None,
            verbose=False,
            no_cache=False,
            docker_uid=None,
            docker_gid=None,
            docker_username=None,
            docker_home=None,
            docker_container_home=None,
            no_docker_user_mapping=True,
            board_targets=None,
            preserve_workspace=False,
            force_cleanup=False,
            clear_cache=False,
        )

        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "glove80"

        branch = strategy._get_repository_branch(params, profile)
        assert branch == "custom-branch"

    def test_get_repository_branch_from_profile(self, tmp_path):
        """Test getting repository branch from profile."""
        strategy = MoergoStrategy()

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
            no_docker_user_mapping=True,
            board_targets=None,
            preserve_workspace=False,
            force_cleanup=False,
            clear_cache=False,
        )

        # Mock profile with firmware version
        firmware_version = Mock()
        firmware_version.version = "v26.01"

        profile = Mock(spec=KeyboardProfile)
        profile.keyboard_name = "glove80"
        profile.firmware_version = firmware_version

        branch = strategy._get_repository_branch(params, profile)
        assert branch == "v26.01"

    def test_build_moergo_commands(self, tmp_path):
        """Test building Moergo-specific commands."""
        strategy = MoergoStrategy()

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
            no_docker_user_mapping=True,
            board_targets=None,
            preserve_workspace=False,
            force_cleanup=False,
            clear_cache=False,
        )

        commands = strategy._build_moergo_commands(params)

        assert "cd /config" in commands
        assert "export UID=$(id -u)" in commands
        assert "export GID=$(id -g)" in commands
        assert any("nix-build" in cmd for cmd in commands)
        assert any("install" in cmd and "glove80.uf2" in cmd for cmd in commands)
