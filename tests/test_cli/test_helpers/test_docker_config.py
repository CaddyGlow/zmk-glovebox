"""Tests for Docker config builder."""

from pathlib import Path

import pytest

from glovebox.cli.helpers.docker_config import DockerConfigBuilder


pytestmark = [pytest.mark.docker, pytest.mark.integration]


def test_build_standard_strategy_defaults():
    """Test default config for standard strategies."""
    config = DockerConfigBuilder.build_from_params("zmk_config")

    assert config.enable_user_mapping is True
    assert config.manual_uid is None
    assert config.manual_gid is None


def test_build_moergo_strategy_defaults():
    """Test default config for Moergo strategy."""
    config = DockerConfigBuilder.build_from_params("moergo")

    assert config.enable_user_mapping is False


def test_build_with_overrides():
    """Test building with parameter overrides."""
    config = DockerConfigBuilder.build_from_params(
        strategy="zmk_config",
        docker_uid=1000,
        docker_gid=1000,
        docker_username="testuser",
        docker_home="/home/test",
        docker_container_home="/tmp/test",
        no_docker_user_mapping=True,
    )

    assert config.manual_uid == 1000
    assert config.manual_gid == 1000
    assert config.manual_username == "testuser"
    assert config.host_home_dir == Path("/home/test")
    assert config.container_home_dir == "/tmp/test"
    assert config.enable_user_mapping is False


def test_no_docker_mapping_overrides_strategy():
    """Test that no_docker_user_mapping overrides strategy defaults."""
    # Even for standard strategy, should disable mapping
    config = DockerConfigBuilder.build_from_params(
        strategy="zmk_config", no_docker_user_mapping=True
    )

    assert config.enable_user_mapping is False


def test_moergo_with_manual_uid():
    """Test Moergo strategy with manual UID override."""
    config = DockerConfigBuilder.build_from_params(
        strategy="moergo",
        docker_uid=1001,
        docker_gid=1001,
    )

    # Should still disable user mapping by default for Moergo
    assert config.enable_user_mapping is False
    assert config.manual_uid == 1001
    assert config.manual_gid == 1001


def test_partial_docker_overrides():
    """Test building with partial Docker overrides."""
    config = DockerConfigBuilder.build_from_params(
        strategy="zmk_config",
        docker_uid=1000,
        # Only UID override, no GID
        docker_home="/custom/home",
    )

    assert config.manual_uid == 1000
    assert config.manual_gid is None  # Not overridden
    assert config.host_home_dir == Path("/custom/home")
    assert config.container_home_dir == "/tmp"  # Default
    assert config.enable_user_mapping is True  # Default for zmk_config
