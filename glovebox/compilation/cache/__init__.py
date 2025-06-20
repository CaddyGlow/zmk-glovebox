"""ZMK compilation caching system.

This module implements a modern caching strategy for ZMK firmware compilation
using base dependencies caching for shared components and comprehensive
workspace cache management with rich metadata.

The caching system reduces compilation time by reusing shared dependencies
across multiple builds and provides enhanced cache operations.
"""

from typing import Any


# Legacy cache injector support (optional dependency)
# Define placeholder types first
class CacheInjectorError(Exception):
    """Cache injector error (placeholder or imported)."""

    pass


def inject_base_dependencies_cache_from_workspace(*args: Any, **kwargs: Any) -> None:
    """Cache injector function (placeholder or imported)."""
    raise NotImplementedError("Cache injector not available")


_has_cache_injector = False

# Try to import actual implementations
try:
    from glovebox.compilation.cache.cache_injector import (  # type: ignore[import-untyped]
        CacheInjectorError as _CacheInjectorError,
    )
    from glovebox.compilation.cache.cache_injector import (
        inject_base_dependencies_cache_from_workspace as _inject_func,
    )

    # Replace placeholders with actual implementations
    CacheInjectorError = _CacheInjectorError  # type: ignore[misc]
    inject_base_dependencies_cache_from_workspace = _inject_func
    _has_cache_injector = True
except ImportError:
    # Keep placeholder implementations
    pass

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
