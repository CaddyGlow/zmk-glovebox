"""ZMK compilation caching system.

This module implements a modern caching strategy for ZMK firmware compilation
using base dependencies caching for shared components and comprehensive
workspace cache management with rich metadata.

The caching system reduces compilation time by reusing shared dependencies
across multiple builds and provides enhanced cache operations.
"""

# Try to import legacy cache injector if it exists
try:
    from glovebox.compilation.cache.cache_injector import (
        CacheInjectorError,
        inject_base_dependencies_cache_from_workspace,
    )

    _has_cache_injector = True
except ImportError:
    # Define placeholder types if cache injector is not available
    class CacheInjectorError(Exception):
        """Placeholder for cache injector error."""

        pass

    def inject_base_dependencies_cache_from_workspace(*args, **kwargs):
        """Placeholder for cache injector function."""
        raise NotImplementedError("Cache injector not available")

    _has_cache_injector = False

from .models import WorkspaceCacheMetadata
from .workspace_cache_service import (
    WorkspaceAutoDetectionResult,
    WorkspaceCacheResult,
    ZmkWorkspaceCacheService,
    create_zmk_workspace_cache_service,
)


__all__ = [
    "inject_base_dependencies_cache_from_workspace",
    "CacheInjectorError",
    "WorkspaceCacheMetadata",
    "ZmkWorkspaceCacheService",
    "WorkspaceCacheResult",
    "WorkspaceAutoDetectionResult",
    "create_zmk_workspace_cache_service",
]
