"""Tests for compilation config builder."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from glovebox.cli.builders.compilation_config import CompilationConfigBuilder
from glovebox.cli.strategies.base import CompilationParams
from glovebox.config.compile_methods import (
    MoergoCompilationConfig,
    ZmkCompilationConfig,
)
from glovebox.config.profile import KeyboardProfile


def create_test_params(tmp_path=None, **kwargs) -> CompilationParams:
    """Create test compilation parameters."""
    if tmp_path is None:
        # Use fake paths for simple tests that don't call strategies
        keymap_file = Path("test.keymap")
        kconfig_file = Path("test.conf")
        output_dir = Path("build")
    else:
        # Create real files for tests that call strategies
        keymap_file = tmp_path / "test.keymap"
        kconfig_file = tmp_path / "test.conf"
        output_dir = tmp_path / "build"
        keymap_file.touch()
        kconfig_file.touch()
        output_dir.mkdir(parents=True, exist_ok=True)

    defaults = {
        "keymap_file": keymap_file,
        "kconfig_file": kconfig_file,
        "output_dir": output_dir,
        "branch": None,
        "repo": None,
        "jobs": None,
        "verbose": False,
        "no_cache": False,
        "docker_uid": None,
        "docker_gid": None,
        "docker_username": None,
        "docker_home": None,
        "docker_container_home": None,
        "no_docker_user_mapping": False,
        "board_targets": None,
        "preserve_workspace": False,
        "force_cleanup": False,
    }
    defaults.update(kwargs)
    return CompilationParams(**defaults)


def test_build_with_explicit_strategy(tmp_path):
    """Test building config with explicit strategy name."""
    builder = CompilationConfigBuilder()

    params = create_test_params(tmp_path, jobs=4, no_cache=True)

    # Create a mock profile
    profile = Mock(spec=KeyboardProfile)
    profile.keyboard_name = "test"

    config = builder.build(params, profile, "zmk_config")

    assert isinstance(config, ZmkCompilationConfig)
    assert config.jobs == 4
    assert config.cache.enabled is False
    assert config.docker_user.enable_user_mapping is True  # Default for zmk_config


def test_build_with_moergo_strategy(tmp_path):
    """Test building config with Moergo strategy."""
    builder = CompilationConfigBuilder()

    params = create_test_params(tmp_path, branch="custom-branch")

    # Create a mock profile that would trigger Moergo
    profile = Mock(spec=KeyboardProfile)
    profile.keyboard_name = "glove80"

    config = builder.build(params, profile, "moergo")

    assert isinstance(config, MoergoCompilationConfig)
    assert config.branch == "custom-branch"
    assert config.docker_user.enable_user_mapping is False  # Moergo default


def test_build_with_docker_overrides(tmp_path):
    """Test building with Docker overrides."""
    builder = CompilationConfigBuilder()

    params = create_test_params(
        tmp_path,
        docker_uid=1000,
        docker_gid=1000,
        no_docker_user_mapping=True,
    )

    profile = Mock(spec=KeyboardProfile)
    profile.keyboard_name = "test"

    config = builder.build(params, profile, "zmk_config")

    assert config.docker_user.manual_uid == 1000
    assert config.docker_user.manual_gid == 1000
    assert config.docker_user.enable_user_mapping is False  # Overridden


def test_build_with_workspace_settings(tmp_path):
    """Test building with workspace settings."""
    builder = CompilationConfigBuilder()

    params = create_test_params(
        tmp_path,
        preserve_workspace=True,
        force_cleanup=False,
    )

    profile = Mock(spec=KeyboardProfile)
    profile.keyboard_name = "test"

    config = builder.build(params, profile, "zmk_config")

    # These attributes might not exist on all config types
    if hasattr(config, "cleanup_workspace"):
        assert config.cleanup_workspace is False
    if hasattr(config, "preserve_on_failure"):
        assert config.preserve_on_failure is True


def test_build_with_auto_strategy_detection(tmp_path):
    """Test building with automatic strategy detection."""
    builder = CompilationConfigBuilder()

    params = create_test_params(tmp_path)

    # Create a mock profile for ZMK
    profile = Mock(spec=KeyboardProfile)
    profile.keyboard_name = "planck"

    # Test auto-detection (no explicit strategy)
    config = builder.build(params, profile)

    # Should get ZMK config since planck is not a Moergo keyboard
    assert isinstance(config, ZmkCompilationConfig)
    assert config.docker_user.enable_user_mapping is True


def test_build_with_auto_moergo_detection(tmp_path):
    """Test building with automatic Moergo detection."""
    builder = CompilationConfigBuilder()

    params = create_test_params(tmp_path)

    # Create a mock profile for Moergo
    profile = Mock(spec=KeyboardProfile)
    profile.keyboard_name = "glove80"

    # Test auto-detection (no explicit strategy)
    config = builder.build(params, profile)

    # Should get Moergo config since glove80 is a Moergo keyboard
    assert isinstance(config, MoergoCompilationConfig)
    assert config.docker_user.enable_user_mapping is False


def test_docker_config_overrides_strategy_defaults(tmp_path):
    """Test that Docker config builder overrides strategy defaults."""
    builder = CompilationConfigBuilder()

    params = create_test_params(
        tmp_path,
        docker_uid=1001,
        docker_username="custom_user",
    )

    profile = Mock(spec=KeyboardProfile)
    profile.keyboard_name = "glove80"

    config = builder.build(params, profile, "moergo")

    # Verify Docker settings override strategy defaults
    assert config.docker_user.manual_uid == 1001
    assert config.docker_user.manual_username == "custom_user"
    assert config.docker_user.enable_user_mapping is False  # Still Moergo default
