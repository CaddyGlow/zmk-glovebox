"""Models package for cross-domain core models."""

from .docker import DockerUserContext
from .results import BaseResult


__all__ = [
    "BaseResult",
    "DockerUserContext",
]
