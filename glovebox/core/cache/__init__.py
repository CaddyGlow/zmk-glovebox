"""DiskCache-based cache system for Glovebox.

This module provides a robust caching infrastructure using DiskCache library
with SQLite backend for safe concurrent access across processes.
"""

import os
from pathlib import Path
from typing import Any

from glovebox.core.cache.cache_coordinator import (
    cleanup_shared_cache_instances,
    get_aggregated_cache_stats,
    get_cache_instance_count,
    get_cache_instance_keys,
    get_shared_cache_instance,
    reset_shared_cache_instances,
)
from glovebox.core.cache.cache_manager import CacheManager
from glovebox.core.cache.diskcache_manager import DiskCacheManager
from glovebox.core.cache.models import DiskCacheConfig


def create_diskcache_manager(
    cache_root: Path,
    enabled: bool = True,
    max_size_gb: int = 2,
    timeout: int = 30,
    tag: str | None = None,
) -> CacheManager:
    """Create a DiskCache-based cache manager.

    Args:
        cache_root: Root directory for cache storage
        enabled: Whether caching is enabled (False returns no-op cache)
        max_size_gb: Maximum cache size in gigabytes
        timeout: Operation timeout in seconds
        tag: Optional tag for cache isolation (creates subdirectory)

    Returns:
        Configured DiskCache manager
    """
    if not enabled:
        return _create_disabled_cache()

    cache_path = cache_root
    if tag:
        cache_path = cache_root / tag

    config = DiskCacheConfig(
        cache_path=cache_path,
        max_size_bytes=max_size_gb * 1024 * 1024 * 1024,
        timeout=timeout,
    )
    return DiskCacheManager(config)


def create_cache_from_user_config(
    user_config: Any, tag: str | None = None, session_metrics: Any = None
) -> CacheManager:
    """Create a cache manager using user configuration with shared coordination.

    Args:
        user_config: User configuration object with cache settings
        tag: Optional tag for cache isolation
        session_metrics: Optional SessionMetrics instance for metrics integration

    Returns:
        Configured cache manager (shared instance when possible)
    """
    # Check global cache disable
    if _is_cache_globally_disabled():
        return _create_disabled_cache()

    # Check if cache is disabled in user config
    if (
        hasattr(user_config, "cache_strategy")
        and user_config.cache_strategy == "disabled"
    ):
        return _create_disabled_cache()

    # Check module-specific cache disable
    if tag and _is_module_cache_disabled(tag):
        return _create_disabled_cache()

    # Use shared cache coordination
    cache_root = getattr(user_config, "cache_path", Path.home() / ".cache" / "glovebox")
    return get_shared_cache_instance(
        cache_root=cache_root,
        tag=tag,
        enabled=True,
        session_metrics=session_metrics,
    )


def create_default_cache(
    tag: str | None = None, session_metrics: Any = None
) -> CacheManager:
    """Create a default cache manager for general use with shared coordination.

    Args:
        tag: Optional tag for cache isolation
        session_metrics: Optional SessionMetrics instance for metrics integration

    Returns:
        Default configured cache manager (shared instance when possible)
    """
    # Check for global disable
    if _is_cache_globally_disabled():
        return _create_disabled_cache()

    # Check module-specific disable
    if tag and _is_module_cache_disabled(tag):
        return _create_disabled_cache()

    # Use XDG cache directory with shared coordination
    cache_root = (
        Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "glovebox"
    )

    return get_shared_cache_instance(
        cache_root=cache_root,
        tag=tag,
        enabled=True,
        max_size_gb=2,
        timeout=30,
        session_metrics=session_metrics,
    )


def _is_cache_globally_disabled() -> bool:
    """Check if caching is globally disabled via environment variable."""
    return os.environ.get("GLOVEBOX_CACHE_GLOBAL", "").lower() in (
        "false",
        "0",
        "disabled",
    )


def _is_module_cache_disabled(module: str) -> bool:
    """Check if caching is disabled for a specific module."""
    env_var = f"GLOVEBOX_CACHE_{module.upper()}"
    return os.environ.get(env_var, "").lower() in ("false", "0", "disabled")


def _create_disabled_cache() -> CacheManager:
    """Create a no-op cache manager that doesn't store anything."""
    from glovebox.core.cache.disabled_cache import DisabledCache

    return DisabledCache()


__all__ = [
    "DiskCacheManager",
    "DiskCacheConfig",
    "create_diskcache_manager",
    "create_cache_from_user_config",
    "create_default_cache",
    "get_shared_cache_instance",
    "reset_shared_cache_instances",
    "get_cache_instance_count",
    "get_cache_instance_keys",
    "cleanup_shared_cache_instances",
    "get_aggregated_cache_stats",
]
