"""Unified compilation configuration models."""

import os
from abc import ABC
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


def expand_path_variables(path_str: str) -> str:
    """Expand environment variables and user home in path string."""
    # First expand environment variables, then user home
    expanded = os.path.expandvars(path_str)
    return str(Path(expanded).expanduser())


class CompileMethodConfig(BaseModel, ABC):
    """Base configuration for compilation methods."""

    method_type: str
    fallback_methods: list[str] = Field(default_factory=list)


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


class WestWorkspaceConfig(BaseModel):
    """ZMK West workspace configuration for traditional manifests."""

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
        "docker",
        "local",
        "cross",
        "qemu",
        "cmake",
        "make",
        "ninja",
        "custom",
    ] = "west"

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

    # Workspace configuration
    workspace_root: Path | None = None
    cleanup_workspace: bool = True
    preserve_on_failure: bool = False

    # Artifact handling
    artifact_naming: str = (
        "zmk_github_actions"  # zmk_github_actions, descriptive, preserve
    )
    build_matrix_file: Path | None = None  # Path to build.yaml

    # Fallback methods
    fallback_methods: list[str] = Field(default_factory=list)

    # Local compilation paths (strategy: local)
    zmk_path: Path | None = None
    toolchain_path: Path | None = None
    zephyr_base: Path | None = None

    # Cross-compilation settings (strategy: cross)
    target_arch: str | None = None
    sysroot: Path | None = None
    toolchain_prefix: str | None = None
    cmake_toolchain: Path | None = None

    # QEMU settings (strategy: qemu)
    qemu_target: str | None = None
    test_runners: list[str] = Field(default_factory=list)

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

    @model_validator(mode="before")
    @classmethod
    def handle_backward_compatibility(
        cls, values: dict[str, Any] | object
    ) -> dict[str, Any] | object:
        """Handle backward compatibility for renamed fields."""
        if isinstance(values, dict):
            # Handle build_strategy -> strategy mapping
            if "build_strategy" in values and "strategy" not in values:
                values["strategy"] = values.pop("build_strategy")

            # Handle cache_workspace -> cache.enabled mapping
            if "cache_workspace" in values and "cache" not in values:
                values["cache"] = {"enabled": values.pop("cache_workspace")}
            elif "cache_workspace" in values and isinstance(values.get("cache"), dict):
                values["cache"]["enabled"] = values.pop("cache_workspace")

            # Handle user mapping fields -> docker_user mapping
            user_mapping_fields = ["enable_user_mapping", "detect_user_automatically"]
            docker_user_data = {}
            for field in user_mapping_fields:
                if field in values:
                    docker_user_data[field] = values.pop(field)
            if docker_user_data and "docker_user" not in values:
                values["docker_user"] = docker_user_data
            elif docker_user_data and isinstance(values.get("docker_user"), dict):
                values["docker_user"].update(docker_user_data)

        return values

    def is_docker_based(self) -> bool:
        """Check if this configuration uses Docker."""
        return self.strategy in [
            "zmk_config",
            "west",
            "docker",
            "cmake",
            "make",
            "ninja",
            "custom",
        ]

    def get_method_type(self) -> str:
        """Get the method type for compatibility with existing code."""
        return "generic_docker" if self.is_docker_based() else self.strategy

    @property
    def method_type(self) -> str:
        """Backward compatibility property for method_type."""
        return self.get_method_type()

    @property
    def build_strategy(self) -> str:
        """Backward compatibility property for build_strategy."""
        return self.strategy

    @property
    def cache_workspace(self) -> bool:
        """Backward compatibility property for cache_workspace."""
        return self.cache.enabled

    @property
    def enable_user_mapping(self) -> bool:
        """Backward compatibility property for enable_user_mapping."""
        return self.docker_user.enable_user_mapping

    @property
    def detect_user_automatically(self) -> bool:
        """Backward compatibility property for detect_user_automatically."""
        return self.docker_user.detect_user_automatically

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Override model_dump to include computed properties for backward compatibility."""
        data = super().model_dump(**kwargs)
        # Add computed properties for backward compatibility
        data["method_type"] = self.method_type
        data["build_strategy"] = self.build_strategy
        data["cache_workspace"] = self.cache_workspace
        data["enable_user_mapping"] = self.enable_user_mapping
        data["detect_user_automatically"] = self.detect_user_automatically
        return data


# Backward compatibility alias
GenericDockerCompileConfig = CompilationConfig


__all__ = [
    "CompileMethodConfig",
    "BuildTargetConfig",
    "BuildYamlConfig",
    "ZmkConfigRepoConfig",
    "WestWorkspaceConfig",
    "DockerCompileConfig",
    "CacheConfig",
    "DockerUserConfig",
    "CompilationConfig",
    "GenericDockerCompileConfig",  # Backward compatibility
    "LocalCompileConfig",
    "CrossCompileConfig",
    "QemuCompileConfig",
]
