"""Method-specific configuration models for compilation methods."""

import os
from abc import ABC
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


def expand_path_variables(path_str: str) -> str:
    """Expand environment variables and user home in path string."""
    # First expand environment variables, then user home
    expanded = os.path.expandvars(path_str)
    return str(Path(expanded).expanduser())


class CompileMethodConfig(BaseModel, ABC):
    """Base configuration for compilation methods."""

    method_type: str
    fallback_methods: list[str] = Field(default_factory=list)


class WestWorkspaceConfig(BaseModel):
    """ZMK West workspace configuration."""

    manifest_url: str = "https://github.com/zmkfirmware/zmk.git"
    manifest_revision: str = "main"
    modules: list[str] = Field(default_factory=list)
    west_commands: list[str] = Field(
        default_factory=lambda: ["west init -l config", "west update"]
    )
    workspace_path: str = "/zmk-workspace"
    config_path: str = "config"

    @field_validator("workspace_path")
    @classmethod
    def expand_workspace_path(cls, v: str) -> str:
        """Expand environment variables and user home in workspace path."""
        return expand_path_variables(v)


class DockerCompileConfig(CompileMethodConfig):
    """Docker-based compilation configuration."""

    method_type: str = "docker"
    image: str = "moergo-zmk-build:latest"
    repository: str = "moergo-sc/zmk"
    branch: str = "main"
    jobs: int | None = None


class LocalCompileConfig(CompileMethodConfig):
    """Local ZMK compilation configuration."""

    method_type: str = "local"
    zmk_path: Path
    toolchain_path: Path | None = None
    zephyr_base: Path | None = None
    jobs: int | None = None


class CrossCompileConfig(CompileMethodConfig):
    """Cross-compilation configuration."""

    method_type: str = "cross"
    target_arch: str  # "arm", "x86_64", etc.
    sysroot: Path
    toolchain_prefix: str  # "arm-none-eabi-"
    cmake_toolchain: Path | None = None


class QemuCompileConfig(CompileMethodConfig):
    """QEMU-based compilation for testing."""

    method_type: str = "qemu"
    qemu_target: str = "native_posix"
    test_runners: list[str] = Field(default_factory=list)


class GenericDockerCompileConfig(DockerCompileConfig):
    """Generic Docker compiler with pluggable build strategies."""

    method_type: str = "generic_docker"
    build_strategy: str = "west"  # "west", "cmake", "make", "ninja", "custom"
    west_workspace: WestWorkspaceConfig | None = None
    build_commands: list[str] = Field(default_factory=list)
    environment_template: dict[str, str] = Field(default_factory=dict)
    volume_templates: list[str] = Field(default_factory=list)
    board_targets: list[str] = Field(default_factory=list)
    cache_workspace: bool = True

    @field_validator("volume_templates")
    @classmethod
    def expand_volume_templates(cls, v: list[str]) -> list[str]:
        """Expand environment variables and user home in volume templates."""
        return [expand_path_variables(template) for template in v]

    @field_validator("environment_template")
    @classmethod
    def expand_environment_template(cls, v: dict[str, str]) -> dict[str, str]:
        """Expand environment variables and user home in environment template values."""
        return {key: expand_path_variables(value) for key, value in v.items()}


__all__ = [
    "CompileMethodConfig",
    "WestWorkspaceConfig",
    "DockerCompileConfig",
    "GenericDockerCompileConfig",
    "LocalCompileConfig",
    "CrossCompileConfig",
    "QemuCompileConfig",
]
