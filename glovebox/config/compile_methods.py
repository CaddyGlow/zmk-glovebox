"""Method-specific configuration models for compilation methods."""

from abc import ABC
from pathlib import Path

from pydantic import BaseModel, Field


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


__all__ = [
    "CompileMethodConfig",
    "WestWorkspaceConfig",
    "DockerCompileConfig",
    "GenericDockerCompileConfig",
    "LocalCompileConfig",
    "CrossCompileConfig",
    "QemuCompileConfig",
]
