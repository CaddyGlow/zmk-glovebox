"""ZMK compilation caching system.

This module implements a modern caching strategy for ZMK firmware compilation
using base dependencies caching for shared components and comprehensive
workspace cache management with rich metadata.

The caching system reduces compilation time by reusing shared dependencies
across multiple builds and provides enhanced cache operations.
"""

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from glovebox.config.user_config import UserConfig


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

from glovebox.core.cache_v2 import create_cache_from_user_config  # noqa: E402
from glovebox.core.cache_v2.cache_manager import CacheManager  # noqa: E402

from .models import WorkspaceCacheMetadata  # noqa: E402
from .workspace_cache_service import (  # noqa: E402
    WorkspaceAutoDetectionResult,
    WorkspaceCacheResult,
    ZmkWorkspaceCacheService,
    create_zmk_workspace_cache_service,
)


def create_compilation_cache_service(
    user_config: "UserConfig",
) -> tuple[CacheManager, ZmkWorkspaceCacheService]:
    """Factory function for compilation cache service with shared coordination.

    This function follows the established factory function pattern from CLAUDE.md
    and provides unified cache management for the compilation domain.

    Args:
        user_config: User configuration instance

    Returns:
        Tuple of (cache_manager, workspace_cache_service) using shared coordination
    """
    # Use shared cache coordination for compilation domain
    cache_manager = create_cache_from_user_config(
        user_config._config, tag="compilation"
    )

    # Create workspace cache service with shared cache
    workspace_service = create_zmk_workspace_cache_service(user_config, cache_manager)

    return cache_manager, workspace_service


__all__ = [
    "inject_base_dependencies_cache_from_workspace",
    "CacheInjectorError",
    "WorkspaceCacheMetadata",
    "ZmkWorkspaceCacheService",
    "WorkspaceCacheResult",
    "WorkspaceAutoDetectionResult",
    "create_zmk_workspace_cache_service",
    "create_compilation_cache_service",
]
