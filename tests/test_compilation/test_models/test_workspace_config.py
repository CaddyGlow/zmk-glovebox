"""Test workspace configuration models."""

import os
import tempfile
from pathlib import Path

import pytest

from glovebox.compilation.models.workspace_config import (
    WestWorkspaceConfig,
    WorkspaceConfig,
    ZmkConfigRepoConfig,
    expand_path_variables,
)


def test_expand_path_variables():
    """Test path variable expansion."""
    # Test environment variable expansion
    os.environ["TEST_VAR"] = "/test/path"
    expanded = expand_path_variables("${TEST_VAR}/subdir")
    assert expanded == "/test/path/subdir"

    # Test user home expansion
    expanded = expand_path_variables("~/test")
    assert expanded == str(Path.home() / "test")


def test_west_workspace_config_defaults():
    """Test WestWorkspaceConfig with default values."""
    config = WestWorkspaceConfig()

    assert config.manifest_url == "https://github.com/zmkfirmware/zmk.git"
    assert config.manifest_revision == "main"
    assert config.modules == []
    assert config.west_commands == []
    assert config.workspace_path == "/zmk-workspace"
    assert config.config_path == "config"


def test_west_workspace_config_path_expansion():
    """Test workspace path expansion in WestWorkspaceConfig."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        os.environ["WORKSPACE_ROOT"] = tmp_dir

        config = WestWorkspaceConfig(workspace_path="${WORKSPACE_ROOT}/zmk")

        assert config.workspace_path == f"{tmp_dir}/zmk"


def test_zmk_config_repo_config_defaults():
    """Test ZmkConfigRepoConfig with default values."""
    config = ZmkConfigRepoConfig(
        config_repo_url="https://github.com/user/zmk-config.git"
    )

    assert config.config_repo_url == "https://github.com/user/zmk-config.git"
    assert config.config_repo_revision == "main"
    assert config.config_path == "config"
    assert config.build_yaml_path == "build.yaml"
    assert config.workspace_path == "/zmk-config-workspace"
    assert config.west_commands == ["west init -l config", "west update"]


def test_zmk_config_repo_config_path_expansion():
    """Test workspace path expansion in ZmkConfigRepoConfig."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        os.environ["CONFIG_WORKSPACE"] = tmp_dir

        config = ZmkConfigRepoConfig(
            config_repo_url="https://github.com/user/zmk-config.git",
            workspace_path="${CONFIG_WORKSPACE}/zmk-config",
        )

        assert config.workspace_path == f"{tmp_dir}/zmk-config"


def test_workspace_config_base():
    """Test base WorkspaceConfig model."""
    config = WorkspaceConfig(workspace_path="/test/workspace")

    assert config.workspace_path == "/test/workspace"
    assert config.config_path == "config"
    assert config.cache_enabled is True
    assert config.cleanup_on_failure is True


def test_workspace_config_path_expansion():
    """Test workspace path expansion in WorkspaceConfig."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        os.environ["BASE_WORKSPACE"] = tmp_dir

        config = WorkspaceConfig(workspace_path="${BASE_WORKSPACE}/workspace")

        assert config.workspace_path == f"{tmp_dir}/workspace"


def test_west_workspace_config_validation():
    """Test WestWorkspaceConfig model validation."""
    config_data = {
        "manifest_url": "https://github.com/custom/zmk.git",
        "manifest_revision": "custom-branch",
        "modules": ["zmk", "custom-module"],
        "west_commands": ["west init", "west update"],
        "workspace_path": "/custom/workspace",
        "config_path": "custom-config",
    }

    config = WestWorkspaceConfig.model_validate(config_data)

    assert config.manifest_url == "https://github.com/custom/zmk.git"
    assert config.manifest_revision == "custom-branch"
    assert config.modules == ["zmk", "custom-module"]
    assert config.west_commands == ["west init", "west update"]
    assert config.workspace_path == "/custom/workspace"
    assert config.config_path == "custom-config"


def test_zmk_config_repo_config_validation():
    """Test ZmkConfigRepoConfig model validation."""
    config_data = {
        "config_repo_url": "https://github.com/user/my-config.git",
        "config_repo_revision": "feature-branch",
        "config_path": "keyboard-config",
        "build_yaml_path": "custom-build.yaml",
        "workspace_path": "/custom/config-workspace",
        "west_commands": ["west init -l keyboard-config", "west update --narrow"],
    }

    config = ZmkConfigRepoConfig.model_validate(config_data)

    assert config.config_repo_url == "https://github.com/user/my-config.git"
    assert config.config_repo_revision == "feature-branch"
    assert config.config_path == "keyboard-config"
    assert config.build_yaml_path == "custom-build.yaml"
    assert config.workspace_path == "/custom/config-workspace"
    assert config.west_commands == [
        "west init -l keyboard-config",
        "west update --narrow",
    ]
