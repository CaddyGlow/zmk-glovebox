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


class ProgressPhasePatterns(GloveboxBaseModel):
    """Regex patterns for detecting compilation progress phases."""

    # Repository download patterns (west update phase)
    repo_download_pattern: str = Field(
        default=r"^From https://github\.com/([^/]+/[^/\s]+)",
        description="Pattern to detect repository downloads during west update"
    )

    # Build start patterns
    build_start_pattern: str = Field(
        default=r"west build.*-b\s+(\w+)",
        description="Pattern to detect start of build for a specific board"
    )

    # Build progress patterns
    build_progress_pattern: str = Field(
        default=r"\[\s*(\d+)/(\d+)\s*\].*Building",
        description="Pattern to detect build progress steps [current/total]"
    )

    # Build completion patterns
    build_complete_pattern: str = Field(
        default=r"Memory region\s+Used Size|FLASH.*region.*overlaps",
        description="Pattern to detect build completion"
    )

    # Board detection patterns
    board_detection_pattern: str = Field(
        default=r"west build.*-b\s+([a-zA-Z0-9_]+)",
        description="Pattern to extract board name from build output"
    )

    # Board completion patterns
    board_complete_pattern: str = Field(
        default=r"Wrote \d+ bytes to zmk\.uf2",
        description="Pattern to detect individual board completion"
    )


class CompilationConfig(GloveboxBaseModel):
    """Base compilation configuration for all strategies."""

    # Core identification
    method_type: str = Field(
        default="zmk_config", description="Compilation method type used as hint"
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

    # Progress tracking patterns
    progress_patterns: ProgressPhasePatterns = Field(
        default_factory=ProgressPhasePatterns,
        description="Regex patterns for tracking compilation progress phases"
    )

    @field_validator("method_type")
    @classmethod
    def validate_method_type(cls, v: str) -> str:
        """Validate compilation method type."""
        if not v or not v.strip():
            raise ValueError("Compilation method type cannot be empty")
        return v.strip()


class ZmkCompilationConfig(CompilationConfig):
    """ZMK compilation configuration with west workspace support."""

    method_type: str = "zmk_config"
    image: str = "zmkfirmware/zmk-build-arm:stable"
    repository: str = "zmkfirmware/zmk"
    branch: str = "main"
    use_cache: bool = Field(
        default=True, description="Enable caching of workspaces and build results"
    )

    build_matrix: BuildMatrix = Field(
        default_factory=lambda: BuildMatrix(board=["nice_nano_v2"])
    )

    # ZMK-specific progress patterns (uses default patterns)
    progress_patterns: ProgressPhasePatterns = Field(
        default_factory=ProgressPhasePatterns,
        description="ZMK-specific progress tracking patterns"
    )


class MoergoCompilationConfig(CompilationConfig):
    """Moergo compilation configuration using Nix toolchain."""

    method_type: str = "moergo"
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

    # MoErgo-specific progress patterns (customized for Nix builds)
    progress_patterns: ProgressPhasePatterns = Field(
        default_factory=lambda: ProgressPhasePatterns(
            # MoErgo doesn't use west update, so no repo download pattern needed
            repo_download_pattern=r"$^|Never match",  # Never matches
            # Nix build patterns
            build_start_pattern=r"building.*glove80|nix-build.*starting",
            build_progress_pattern=r"\[\s*(\d+)/(\d+)\s*\].*Building|Build progress.*board.*:(\d+)/(\d+)",
            build_complete_pattern=r"Wrote \d+ bytes to zmk\.uf2|successful build of",
            board_detection_pattern=r"building.*glove80_([lr]h|unified)|Board:\s*([a-zA-Z0-9_]+)",
            board_complete_pattern=r"Wrote \d+ bytes to zmk\.uf2|successful build.*glove80"
        ),
        description="MoErgo Nix-specific progress tracking patterns"
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
    "ProgressPhasePatterns",
]
