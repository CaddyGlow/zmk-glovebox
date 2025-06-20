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

from pydantic import Field, field_validator

from glovebox.compilation.models.build_matrix import BuildMatrix
from glovebox.models.base import GloveboxBaseModel
from glovebox.models.docker_path import DockerPath


def expand_path_variables(path_str: Path) -> Path:
    """Expand environment variables and user home in path string."""
    expanded = os.path.expandvars(str(path_str))
    return Path(expanded).expanduser()


class DockerUserConfig(GloveboxBaseModel):
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


class ZmkWorkspaceConfig(GloveboxBaseModel):
    """ZMK workspace configuration for zmk_config strategy."""

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


class CompilationConfig(GloveboxBaseModel):
    """Base compilation configuration for all strategies."""

    # Core identification
    strategy: str = Field(
        default="zmk_config", description="Compilation strategy type used as hint"
    )

    # Docker configuration
    image: str = Field(
        default="zmkfirmware/zmk-build-arm:stable", description="docker image to use"
    )

    # Repository configuration (used by services)
    repository: str = Field(
        default="zmkfirmware/zmk", description="Repository to use to build the firmware"
    )
    branch: str = Field(
        default="main", description="Branch to use to build the firmware"
    )

    # Build matrix (used by services)
    build_matrix: BuildMatrix = Field(
        default_factory=lambda: BuildMatrix(board=["nice_nano_v2"])
    )

    # Docker user configuration
    docker_user: DockerUserConfig = Field(
        default_factory=DockerUserConfig,
        description="Settings to drop docker privileges, used to fix volume permission error",
    )

    @field_validator("strategy")
    @classmethod
    def validate_strategy(cls, v: str) -> str:
        """Validate compilation type."""
        if not v or not v.strip():
            raise ValueError("Compilation strategy cannot be empty")
        return v.strip()


class ZmkCompilationConfig(CompilationConfig):
    """ZMK compilation configuration with west workspace support."""

    strategy: str = "zmk_config"
    image: str = "zmkfirmware/zmk-build-arm:stable"
    repository: str = "zmkfirmware/zmk"
    branch: str = "main"
    use_cache: bool = Field(
        default=True, description="Enable caching of workspaces and build results"
    )

    build_matrix: BuildMatrix = Field(
        default_factory=lambda: BuildMatrix(board=["nice_nano_v2"])
    )


class MoergoCompilationConfig(CompilationConfig):
    """Moergo compilation configuration using Nix toolchain."""

    strategy: str = "moergo"
    image: str = "glove80-zmk-config-docker"
    repository: str = "moergo-sc/zmk"
    branch: str = "v25.05"

    # Build matrix for Moergo (typically Glove80 left/right)
    build_matrix: BuildMatrix = Field(
        default_factory=lambda: BuildMatrix(board=["glove80_lh", "glove80_rh"])
    )

    # Disable user mapping for Moergo by default
    docker_user: DockerUserConfig = Field(
        default_factory=lambda: DockerUserConfig(enable_user_mapping=False)
    )


# Type union for all compilation configurations
CompilationConfigUnion = MoergoCompilationConfig | ZmkCompilationConfig


__all__ = [
    "CompilationConfig",
    "ZmkCompilationConfig",
    "MoergoCompilationConfig",
    "CompilationConfigUnion",
    "DockerUserConfig",
    "ZmkWorkspaceConfig",
]
