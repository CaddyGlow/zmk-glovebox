"""Generic cache system for Glovebox.

Provides domain-agnostic caching infrastructure that can be used
across all domains (layout, config, firmware, compilation).
"""

from pathlib import Path

from glovebox.core.cache.cache_manager import CacheManager
from glovebox.core.cache.filesystem_cache import FilesystemCache
from glovebox.core.cache.memory_cache import MemoryCache
from glovebox.core.cache.models import CacheConfig, CacheKey, CacheMetadata, CacheStats


def create_filesystem_cache(
    cache_root: Path | None = None,
    max_size_mb: int | None = None,
    max_entries: int | None = None,
    default_ttl_hours: int | None = None,
) -> CacheManager:
    """Create a filesystem-based cache manager.

    Args:
        cache_root: Root directory for cache storage
        max_size_mb: Maximum cache size in megabytes
        max_entries: Maximum number of cache entries
        default_ttl_hours: Default time-to-live in hours

    Returns:
        Configured filesystem cache manager
    """
    config = CacheConfig(
        cache_root=cache_root,
        max_size_bytes=max_size_mb * 1024 * 1024 if max_size_mb else None,
        max_entries=max_entries,
        default_ttl_seconds=default_ttl_hours * 3600 if default_ttl_hours else None,
    )
    return FilesystemCache(config)


def create_memory_cache(
    max_size_mb: int | None = None,
    max_entries: int | None = None,
    default_ttl_hours: int | None = None,
) -> CacheManager:
    """Create an in-memory cache manager.

    Args:
        max_size_mb: Maximum cache size in megabytes
        max_entries: Maximum number of cache entries
        default_ttl_hours: Default time-to-live in hours

    Returns:
        Configured memory cache manager
    """
    config = CacheConfig(
        max_size_bytes=max_size_mb * 1024 * 1024 if max_size_mb else None,
        max_entries=max_entries,
        default_ttl_seconds=default_ttl_hours * 3600 if default_ttl_hours else None,
    )
    return MemoryCache(config)


def create_default_cache() -> CacheManager:
    """Create a default cache manager for general use.

    Uses filesystem caching with reasonable defaults:
    - 500MB max size
    - 24 hour default TTL
    - LRU eviction policy

    Returns:
        Default configured cache manager
    """
    return create_filesystem_cache(
        max_size_mb=500,
        max_entries=10000,
        default_ttl_hours=24,
    )


__all__ = [
    "CacheManager",
    "CacheConfig",
    "CacheKey",
    "CacheMetadata",
    "CacheStats",
    "FilesystemCache",
    "MemoryCache",
    "create_filesystem_cache",
    "create_memory_cache",
    "create_default_cache",
]
