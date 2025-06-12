"""Unified compilation configuration models."""

import os
from abc import ABC
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


def expand_path_variables(path_str: Path) -> Path:
    """Expand environment variables and user home in path string."""
    # First expand environment variables, then user home
    expanded = os.path.expandvars(path_str)
    return Path(expanded).expanduser()


class CompileMethodConfig(BaseModel, ABC):
    """Base configuration for compilation methods."""

    method_type: str


class BuildTargetConfig(BaseModel):
    """Individual build target configuration from build.yaml."""

    board: str
    shield: str | None = None
    cmake_args: list[str] = Field(default_factory=list)
    snippet: str | None = None
    artifact_name: str | None = None


class BuildYamlConfig(BaseModel):
    """Configuration parsed from ZMK config repository build.yaml."""

    board: list[str] = Field(default_factory=list)
    shield: list[str] = Field(default_factory=list)
    include: list[BuildTargetConfig] = Field(default_factory=list)


class ZmkConfigRepoConfig(BaseModel):
    """ZMK config repository configuration for config-based manifests."""

    config_repo_url: str
    config_repo_revision: str = "main"
    build_yaml_path: str = "build.yaml"
    workspace_path: str = "/zmk-config-workspace"
    west_commands: list[str] = Field(
        default_factory=lambda: ["west init -l config", "west update"]
    )
    build_root: str = "build"
    config_path: str = "config"

    @field_validator("workspace_path")
    @classmethod
    def expand_workspace_path(cls, v: str) -> str:
        """Expand environment variables and user home in workspace path."""
        return expand_path_variables(v)

    @field_validator("build_root")
    @classmethod
    def expand_build_root(cls, v: str) -> str:
        """Expand environment variables and user home in build root path."""
        return expand_path_variables(v)

    @field_validator("config_path")
    @classmethod
    def expand_config_path(cls, v: str) -> str:
        """Expand environment variables and user home in config path."""
        return expand_path_variables(v)


class WestWorkspaceConfig(BaseModel):
    """ZMK West workspace configuration for traditional manifests."""

    manifest_url: str = "https://github.com/zmkfirmware/zmk.git"
    manifest_revision: str = "main"
    modules: list[str] = Field(default_factory=list)
    west_commands: list[str] = Field(default_factory=list)
    workspace_path: str = "/zmk-workspace"
    config_path: str = "config"
    build_root: str = "build"

    @field_validator("workspace_path")
    @classmethod
    def expand_workspace_path(cls, v: str) -> str:
        """Expand environment variables and user home in workspace path."""
        return expand_path_variables(v)

    @field_validator("build_root")
    @classmethod
    def expand_build_root(cls, v: str) -> str:
        """Expand environment variables and user home in build root path."""
        return expand_path_variables(v)


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


class CompilationConfig(BaseModel):
    """Unified compilation configuration for all build strategies.

    This replaces the multiple overlapping config classes with a single
    unified configuration that supports all compilation strategies.
    """

    # Build strategy selection
    strategy: Literal[
        "zmk_config",
        "west",
    ] = "zmk_config"

    # Docker configuration (for docker-based strategies)
    image: str = "zmkfirmware/zmk-build-arm:stable"
    repository: str = "zmkfirmware/zmk"
    branch: str = "main"
    jobs: int | None = None
    build_commands: list[str] = Field(default_factory=list)
    environment_template: dict[str, str] = Field(default_factory=dict)
    volume_templates: list[str] = Field(default_factory=list)

    # Build targets
    board_targets: list[str] = Field(default_factory=list)

    # ZMK config repository configuration (strategy: zmk_config)
    zmk_config_repo: ZmkConfigRepoConfig | None = None

    # West workspace configuration (strategy: west)
    west_workspace: WestWorkspaceConfig | None = None

    # Cache configuration
    cache: CacheConfig = Field(default_factory=CacheConfig)

    # Docker user configuration
    docker_user: DockerUserConfig = Field(default_factory=DockerUserConfig)

    config_path: Path = Path("config")
    build_root: Path = Path("build")

    # Workspace configuration
    workspace_root: Path = Path("/workspace")

    cleanup_workspace: bool = True
    preserve_on_failure: bool = False

    # Artifact handling
    artifact_naming: str = (
        "zmk_github_actions"  # zmk_github_actions, descriptive, preserve
    )
    build_matrix_file: Path | None = None  # Path to build.yaml

    @field_validator("config_path")
    @classmethod
    def expand_config_path(cls, v: str) -> Path:
        """Expand environment variables and user home in config path."""
        return Path(expand_path_variables(cls.workspace_root / v))

    @field_validator("build_root")
    @classmethod
    def expand_build_root(cls, v: str) -> Path:
        """Expand environment variables and user home in build root path."""
        return Path(expand_path_variables(cls.workspace_root / v))

    @field_validator("workspace_root")
    @classmethod
    def expand_workspace_root(cls, v: str) -> Path:
        """Expand environment variables and user home in workspace root path."""
        return Path(expand_path_variables(Path(v)))

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

    def is_docker_based(self) -> bool:
        """Check if this configuration uses Docker."""
        return self.strategy in [
            "zmk_config",
            "west",
        ]


__all__ = [
    "CompileMethodConfig",
    "BuildTargetConfig",
    "BuildYamlConfig",
    "ZmkConfigRepoConfig",
    "WestWorkspaceConfig",
    "CacheConfig",
    "DockerUserConfig",
    "CompilationConfig",
]
