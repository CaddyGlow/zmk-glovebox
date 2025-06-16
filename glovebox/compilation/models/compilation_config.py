"""Unified compilation configuration models.

This module provides unified configuration models for all compilation strategies,
eliminating the need for separate 'full' and 'service' configuration classes.
These models serve both YAML loading and service usage.

Architecture:
- Single source of truth for compilation configuration
- Support both rich YAML configuration and simplified service interfaces
- Domain-driven design - compilation domain owns its configuration models
"""

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from glovebox.compilation.models.build_matrix import BuildMatrix
from glovebox.models.docker_path import DockerPath


def expand_path_variables(path_str: Path) -> Path:
    """Expand environment variables and user home in path string."""
    expanded = os.path.expandvars(str(path_str))
    return Path(expanded).expanduser()


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


class CacheConfig(BaseModel):
    """Configuration for cache management."""

    enabled: bool = True
    max_age_hours: float = 24.0
    max_cache_size_gb: float = 5.0
    cleanup_interval_hours: float = 6.0
    enable_compression: bool = True
    enable_smart_invalidation: bool = True


class ZmkWorkspaceConfig(BaseModel):
    """ZMK workspace configuration for zmk_config strategy."""

    repository: str = "zmkfirmware/zmk"
    branch: str = "main"

    workspace_path: DockerPath = Field(
        default_factory=lambda: DockerPath(
            host_path=Path("/workspace"), container_path="/workspace"
        )
    )
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


class CompilationConfig(BaseModel):
    """Base compilation configuration for all strategies."""

    # Core identification
    type: str  # Strategy type: "zmk_config", "moergo", etc.

    # Docker configuration
    image: str = "zmkfirmware/zmk-build-arm:stable"
    jobs: int | None = None
    build_commands: list[str] = Field(default_factory=list)
    entrypoint_command: str | None = None

    # Repository configuration (used by services)
    repository: str = "zmkfirmware/zmk"
    branch: str = "main"

    # Build matrix (used by services)
    build_matrix: BuildMatrix = Field(
        default_factory=lambda: BuildMatrix(board=["nice_nano_v2"])
    )

    # Workspace management
    cleanup_workspace: bool = True
    preserve_on_failure: bool = False

    # Docker user configuration
    docker_user: DockerUserConfig = Field(default_factory=DockerUserConfig)

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate compilation type."""
        if not v or not v.strip():
            raise ValueError("Compilation type cannot be empty")
        return v.strip()


class ZmkCompilationConfig(CompilationConfig):
    """ZMK compilation configuration with west workspace support."""

    type: str = "zmk_config"
    image: str = "zmkfirmware/zmk-build-arm:stable"
    repository: str = "zmkfirmware/zmk"
    branch: str = "main"

    # ZMK-specific configuration
    cache: CacheConfig = Field(default_factory=CacheConfig)
    artifact_naming: str = "zmk_github_actions"
    workspace: ZmkWorkspaceConfig = Field(default_factory=ZmkWorkspaceConfig)
    use_cache: bool = True

    # Build configuration (from old build_config field)
    build_matrix: BuildMatrix = Field(
        default_factory=lambda: BuildMatrix(board=["nice_nano_v2"])
    )

    @field_validator("build_matrix", mode="before")
    @classmethod
    def convert_build_config(cls, v: Any) -> BuildMatrix:
        """Convert legacy build_config to build_matrix."""
        if isinstance(v, dict):
            return BuildMatrix(**v)
        return v if v is not None else BuildMatrix(board=["nice_nano_v2"])


class MoergoCompilationConfig(CompilationConfig):
    """Moergo compilation configuration using Nix toolchain."""

    type: str = "moergo"
    image: str = "glove80-zmk-config-docker"
    repository: str = "moergo-sc/zmk"
    branch: str = "v25.05"

    # Moergo-specific workspace configuration
    workspace_path: DockerPath = Field(
        default_factory=lambda: DockerPath(
            host_path=Path("/workspace"), container_path="/workspace"
        )
    )

    # Build matrix for Moergo (typically Glove80 left/right)
    build_matrix: BuildMatrix = Field(
        default_factory=lambda: BuildMatrix(board=["glove80_lh", "glove80_rh"])
    )

    # Disable user mapping for Moergo by default
    docker_user: DockerUserConfig = Field(
        default_factory=lambda: DockerUserConfig(enable_user_mapping=False)
    )


# Type union for all compilation configurations
CompilationConfigUnion = ZmkCompilationConfig | MoergoCompilationConfig


__all__ = [
    "CompilationConfig",
    "ZmkCompilationConfig",
    "MoergoCompilationConfig",
    "CompilationConfigUnion",
    "DockerUserConfig",
    "CacheConfig",
    "ZmkWorkspaceConfig",
]
