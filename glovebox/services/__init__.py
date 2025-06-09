"""Services package for cross-domain business logic services."""

from .base_service import BaseService, BaseServiceProtocol


__all__ = [
    # Base service protocol and implementation
    "BaseServiceProtocol",
    "BaseService",
]
