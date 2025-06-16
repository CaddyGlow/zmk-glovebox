"""Service compilation configuration models for simplified services.

This module provides streamlined configuration models used by the compilation
services. These configs are derived from the full keyboard configuration models
defined in compile_methods.py through conversion functions.

Architecture Overview:
- YAML keyboard configs use full-featured models from compile_methods.py
- CLI converts these to service models for the simplified compilation services
- Service models contain only fields actually used by the compilation services
"""

from pydantic import BaseModel, Field

from glovebox.compilation.models.build_matrix import BuildMatrix


class ServiceCompileConfig(BaseModel):
    """Base service configuration for compilation methods."""

    type: str
    image: str
    repository: str = "zmkfirmware/zmk"
    branch: str = "main"
    build_matrix: BuildMatrix = Field(
        default_factory=lambda: BuildMatrix(board=["nice_nano_v2"])
    )


class ServiceZmkConfig(ServiceCompileConfig):
    """Service ZMK compilation configuration.

    Contains only the fields actually used by ZmkConfigSimpleService:
    - strategy: identifies the compilation strategy
    - image: Docker image for compilation
    - repository: ZMK repository URL
    - branch: ZMK branch to use
    - boards: list of board targets to build
    - shields: list of shield targets (empty for non-shield keyboards)
    """

    type: str = "zmk_config"
    image: str = "zmkfirmware/zmk-build-arm:stable"
    repository: str = "zmkfirmware/zmk"
    branch: str = "main"
    build_matrix: BuildMatrix = Field(
        default_factory=lambda: BuildMatrix(board=["nice_nano_v2"])
    )
    use_cache: bool = True


class ServiceMoergoConfig(ServiceCompileConfig):
    """Service Moergo compilation configuration.

    Contains only the fields actually used by MoergoSimpleService:
    - strategy: identifies the compilation strategy
    - image: Docker image for compilation
    - repository: ZMK repository URL
    - branch: ZMK branch to use
    - boards: list of board targets to build
    - shields: list of shield targets (empty for Glove80)
    """

    type: str = "moergo"
    image: str = "glove80-zmk-config-docker"
    repository: str = "https://github.com/moergo-sc/zmk"
    branch: str = "v25.05"
    build_matrix: BuildMatrix = Field(
        default_factory=lambda: BuildMatrix(board=["glove80_lh", "glove80_rh"])
    )


# Type union for service configurations
ServiceCompileConfigUnion = ServiceZmkConfig | ServiceMoergoConfig


__all__ = [
    "ServiceCompileConfig",
    "ServiceZmkConfig",
    "ServiceMoergoConfig",
    "ServiceCompileConfigUnion",
]
