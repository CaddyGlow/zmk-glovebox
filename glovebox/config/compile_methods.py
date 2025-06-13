"""Unified compilation configuration models."""

import os
from abc import ABC
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from glovebox.core.errors import GloveboxError
from glovebox.models.docker_path import DockerPath

if TYPE_CHECKING:
    from glovebox.compilation.models.build_matrix import BuildYamlConfig


def expand_path_variables(path_str: Path) -> Path:
    """Expand environment variables and user home in path string."""
    # First expand environment variables, then user home
    expanded = os.path.expandvars(str(path_str))
    return Path(expanded).expanduser()


class CompileMethodConfig(BaseModel, ABC):
    """Base configuration for compilation methods."""

    method_type: str




class CacheConfig(BaseModel):
    """Configuration for cache management."""

    enabled: bool = True
    max_age_hours: float = 24.0
    max_cache_size_gb: float = 5.0
    cleanup_interval_hours: float = 6.0
    enable_compression: bool = True
    enable_smart_invalidation: bool = True


class DockerUserConfig(BaseModel):
    """Docker user mapping configuration."""

    enable_user_mapping: bool = True
    detect_user_automatically: bool = True
    manual_uid: int | None = None
    manual_gid: int | None = None
    manual_username: str | None = None
    host_home_dir: Path | None = None
    container_home_dir: str = "/tmp"
    force_manual: bool = False
    debug_user_mapping: bool = False

    @field_validator("host_home_dir", mode="before")
    @classmethod
    def expand_host_home_dir(cls, v: str | Path | None) -> Path | None:
        """Expand user home and environment variables."""
        if v is None:
            return None
        path = Path(v).expanduser()
        return path.resolve() if path.exists() else path


class DockerCompilationConfig(BaseModel):
    """Unified compilation configuration for all build strategies.

    This replaces the multiple overlapping config classes with a single
    unified configuration that supports all compilation strategies.
    """

    # Docker configuration (for docker-based strategies)
    image: str = "zmkfirmware/zmk-build-arm:stable"
    jobs: int | None = None
    build_commands: list[str] = Field(default_factory=list)
    entrypoint_command: str | None = None

    # TODO: Not used in the docker run command
    environment_template: dict[str, str] = Field(default_factory=dict)
    volume_templates: list[str] = Field(default_factory=list)

    # Workspace management configuration
    cleanup_workspace: bool = True
    preserve_on_failure: bool = False

    # Docker user configuration
    docker_user: DockerUserConfig = Field(default_factory=DockerUserConfig)

    @field_validator("volume_templates")
    @classmethod
    def expand_volume_templates(cls, v: list[Path]) -> list[Path]:
        """Expand environment variables and user home in volume templates."""
        return [expand_path_variables(template) for template in v]

    @field_validator("environment_template")
    @classmethod
    def expand_environment_template(cls, v: dict[str, str]) -> dict[str, str]:
        """Expand environment variables and user home in environment template values."""
        return {
            key: str(expand_path_variables(Path(value))) for key, value in v.items()
        }


class ZmkWorkspaceConfig(BaseModel):
    """ZMK config repository configuration for config-based manifests."""

    # Default firmware repository
    repository: str = "zmkfirmware/zmk"
    branch: str = "main"

    # ZMK configuration repository to clone
    config_repo_url: str | None = None
    config_repo_revision: str | None = None

    # Matrix filename
    build_matrix_file: Path = Field(default=Path("build.yaml"))

    # Host and container path mappings
    # if the host path is not specified we don't
    # set the volume.
    workspace_path: DockerPath = Field(
        default_factory=lambda: DockerPath(
            host_path=Path("/workspace"), container_path="/workspace"
        )
    )

    # Path are relative to the workspace path
    build_root: DockerPath = Field(
        default_factory=lambda: DockerPath(
            host_path=Path("build"), container_path="build"
        )
    )
    config_path: DockerPath = Field(
        default_factory=lambda: DockerPath(
            host_path=Path("config"), container_path="config"
        )
    )


class ZmkCompilationConfig(DockerCompilationConfig):
    """ZMK compilation configuration with GitHub Actions artifact naming."""

    # Cache configuration
    cache: CacheConfig = Field(default_factory=CacheConfig)

    artifact_naming: str = "zmk_github_actions"

    build_config: "BuildYamlConfig" = Field(default_factory=lambda: __import__("glovebox.compilation.models.build_matrix", fromlist=["BuildYamlConfig"]).BuildYamlConfig())

    # ZMK workspace configuration
    workspace: ZmkWorkspaceConfig = Field(default_factory=ZmkWorkspaceConfig)


class MoergoCompilationConfig(DockerCompilationConfig):
    """Moergo compilation configuration using simple Docker volume to temp folder."""

    # Docker configuration
    image: str = "glove80-zmk-config-docker"

    # We need to override the entrypoint to be able to
    # execute commands in the container
    entrypoint_command: str | None = "/bin/sh"

    # Repository and firmware branch
    # only branch is used for Moergo
    repository: str = "moergo-sc/zmk"
    branch: str = "v25.05"

    workspace_path: DockerPath = Field(
        default_factory=lambda: DockerPath(
            host_path=Path("/build"), container_path="/config"
        )
    )

    # Build configuration
    build_commands: list[str] = Field(default_factory=list)
    docker_user: DockerUserConfig = DockerUserConfig(enable_user_mapping=False)


__all__ = [
    "CompileMethodConfig",
    "BuildTargetConfig",
    "BuildYamlConfig",
    "ZmkWorkspaceConfig",
    "CacheConfig",
    "DockerUserConfig",
    "DockerCompilationConfig",
    "ZmkCompilationConfig",
    "MoergoCompilationConfig",
]
