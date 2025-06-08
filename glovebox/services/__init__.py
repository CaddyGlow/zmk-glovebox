"""Services package for cross-domain business logic services."""

from glovebox.protocols.behavior_protocols import (
    BehaviorRegistryProtocol,
)

from .base_service import BaseService, BaseServiceImpl


__all__ = [
    # Base service protocol and implementation
    "BaseService",
    "BaseServiceImpl",
]
