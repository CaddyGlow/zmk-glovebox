"""Method-specific configuration models for compilation methods."""

from abc import ABC
from pathlib import Path

from pydantic import BaseModel, Field


class CompileMethodConfig(BaseModel, ABC):
    """Base configuration for compilation methods."""

    method_type: str
    fallback_methods: list[str] = Field(default_factory=list)


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
