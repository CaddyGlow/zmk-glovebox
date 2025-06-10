"""Workspace configuration models for compilation builds."""

import os
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


def expand_path_variables(path_str: str) -> str:
    """Expand environment variables and user home in path string."""
    # First expand environment variables, then user home
    expanded = os.path.expandvars(path_str)
    return str(Path(expanded).expanduser())


class WestWorkspaceConfig(BaseModel):
    """ZMK West workspace configuration for traditional manifests.

    Configuration for ZMK west workspace initialization and management
    following the traditional ZMK west workspace pattern.
    """

    manifest_url: str = "https://github.com/zmkfirmware/zmk.git"
    manifest_revision: str = "main"
    modules: list[str] = Field(default_factory=list)
    west_commands: list[str] = Field(default_factory=list)
    workspace_path: str = "/zmk-workspace"
    config_path: str = "config"

    @field_validator("workspace_path")
    @classmethod
    def expand_workspace_path(cls, v: str) -> str:
        """Expand environment variables and user home in workspace path."""
        return expand_path_variables(v)


class ZmkConfigRepoConfig(BaseModel):
    """ZMK config repository configuration for config-based manifests.

    Configuration for ZMK config repository workspaces following
    the GitHub Actions workflow pattern for zmk-config repositories.
    """

    config_repo_url: str
    config_repo_revision: str = "main"
    config_path: str = "config"
    build_yaml_path: str = "build.yaml"
    workspace_path: str = "/zmk-config-workspace"
    west_commands: list[str] = Field(
        default_factory=lambda: ["west init -l config", "west update"]
    )

    @field_validator("workspace_path")
    @classmethod
    def expand_workspace_path(cls, v: str) -> str:
        """Expand environment variables and user home in workspace path."""
        return expand_path_variables(v)


class WorkspaceConfig(BaseModel):
    """Base workspace configuration for compilation environments.

    Provides common workspace settings shared across different
    compilation strategies.
    """

    workspace_path: str
    config_path: str = "config"
    cache_enabled: bool = True
    cleanup_on_failure: bool = True

    @field_validator("workspace_path")
    @classmethod
    def expand_workspace_path(cls, v: str) -> str:
        """Expand environment variables and user home in workspace path."""
        return expand_path_variables(v)
