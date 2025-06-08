"""Services package for unified business logic services."""

from glovebox.protocols.behavior_protocols import (
    BehaviorRegistry,
    BehaviorRegistryProtocol,
)

from .base_service import BaseService, BaseServiceImpl
from .behavior_service import BehaviorRegistryImpl, create_behavior_registry
from .build_service import BuildService, create_build_service
from .flash_service import FlashService, create_flash_service


__all__ = [
    # Base service protocol and implementation
    "BaseService",
    "BaseServiceImpl",
    # Protocol types
    "BehaviorRegistry",
    "BehaviorRegistryProtocol",
    # Service implementations
    "FlashService",
    "create_flash_service",
    "BehaviorRegistryImpl",
    "create_behavior_registry",
    "BuildService",
    "create_build_service",
]
