"""Minimal compilation configuration models for simplified services.

This module provides stripped-down configuration models that match the actual
usage in the simplified compilation services, eliminating 90%+ of unused complexity.
"""

from pydantic import BaseModel


class MinimalCompileConfig(BaseModel):
    """Base minimal configuration for compilation methods."""

    strategy: str
    image: str


class MinimalZmkConfig(MinimalCompileConfig):
    """Minimal ZMK compilation configuration.

    Contains only the fields actually used by ZmkConfigSimpleService:
    - strategy: identifies the compilation strategy
    - image: Docker image for compilation
    """

    strategy: str = "zmk_config"
    image: str = "zmkfirmware/zmk-build-arm:stable"


class MinimalMoergoConfig(MinimalCompileConfig):
    """Minimal Moergo compilation configuration.

    Contains only the fields actually used by MoergoSimpleService:
    - strategy: identifies the compilation strategy
    - image: Docker image for compilation
    """

    strategy: str = "moergo"
    image: str = "glove80-zmk-config-docker"


# Type union for minimal configurations
MinimalCompileConfigUnion = MinimalZmkConfig | MinimalMoergoConfig


__all__ = [
    "MinimalCompileConfig",
    "MinimalZmkConfig",
    "MinimalMoergoConfig",
    "MinimalCompileConfigUnion",
]
