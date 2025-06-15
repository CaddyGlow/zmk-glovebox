"""Minimal compilation configuration models for simplified services.

This module provides stripped-down configuration models that match the actual
usage in the simplified compilation services, eliminating 90%+ of unused complexity.
"""

from pydantic import BaseModel


class MinimalCompileConfig(BaseModel):
    """Base minimal configuration for compilation methods."""

    strategy: str
    image: str
    repository: str = "zmkfirmware/zmk"
    branch: str = "main"
    # Build matrix configuration
    boards: list[str] = ["nice_nano_v2"]
    shields: list[str] = []  # Empty for non-shield keyboards
    # Simple caching
    use_cache: bool = True


class MinimalZmkConfig(MinimalCompileConfig):
    """Minimal ZMK compilation configuration.

    Contains only the fields actually used by ZmkConfigSimpleService:
    - strategy: identifies the compilation strategy
    - image: Docker image for compilation
    - repository: ZMK repository URL
    - branch: ZMK branch to use
    - boards: list of board targets to build
    - shields: list of shield targets (empty for non-shield keyboards)
    """

    strategy: str = "zmk_config"
    image: str = "zmkfirmware/zmk-build-arm:stable"
    repository: str = "zmkfirmware/zmk"
    branch: str = "main"
    boards: list[str] = ["nice_nano_v2"]
    shields: list[str] = []


class MinimalMoergoConfig(MinimalCompileConfig):
    """Minimal Moergo compilation configuration.

    Contains only the fields actually used by MoergoSimpleService:
    - strategy: identifies the compilation strategy
    - image: Docker image for compilation
    - repository: ZMK repository URL
    - branch: ZMK branch to use
    - boards: list of board targets to build
    - shields: list of shield targets (empty for Glove80)
    """

    strategy: str = "moergo"
    image: str = "glove80-zmk-config-docker"
    repository: str = "https://github.com/moergo-sc/zmk"
    branch: str = "v25.05"
    boards: list[str] = ["glove80_lh", "glove80_rh"]
    shields: list[str] = []  # Glove80 doesn't use shields


# Type union for minimal configurations
MinimalCompileConfigUnion = MinimalZmkConfig | MinimalMoergoConfig


__all__ = [
    "MinimalCompileConfig",
    "MinimalZmkConfig",
    "MinimalMoergoConfig",
    "MinimalCompileConfigUnion",
]
