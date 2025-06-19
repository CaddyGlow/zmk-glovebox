"""Generic cache system for Glovebox.

Provides domain-agnostic caching infrastructure that can be used
across all domains (layout, config, firmware, compilation).
"""

from pathlib import Path
from typing import Any

from glovebox.core.cache.cache_manager import CacheManager
from glovebox.core.cache.filesystem_cache import FilesystemCache
from glovebox.core.cache.memory_cache import MemoryCache
from glovebox.core.cache.models import CacheConfig, CacheKey, CacheMetadata, CacheStats


def create_filesystem_cache(
    cache_root: Path | None = None,
    max_size_mb: int | None = None,
    max_entries: int | None = None,
    default_ttl_hours: int | None = None,
    use_file_locking: bool = True,
    cache_strategy: str = "shared",
) -> CacheManager:
    """Create a filesystem-based cache manager.

    Args:
        cache_root: Root directory for cache storage
        max_size_mb: Maximum cache size in megabytes
        max_entries: Maximum number of cache entries
        default_ttl_hours: Default time-to-live in hours
        use_file_locking: Enable file locking for concurrent access protection
        cache_strategy: Cache strategy ("process_isolated", "shared", "disabled")

    Returns:
        Configured filesystem cache manager
    """
    config = CacheConfig(
        cache_root=cache_root,
        max_size_bytes=max_size_mb * 1024 * 1024 if max_size_mb else None,
        max_entries=max_entries,
        default_ttl_seconds=default_ttl_hours * 3600 if default_ttl_hours else None,
        use_file_locking=use_file_locking,
        cache_strategy=cache_strategy,
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


def create_cache_from_user_config(user_config: Any) -> CacheManager:
    """Create a cache manager using user configuration.

    Args:
        user_config: User configuration object with cache_strategy and cache_file_locking attributes

    Returns:
        Configured cache manager
    """
    return create_default_cache(
        cache_strategy=user_config.cache_strategy,
        cache_file_locking=user_config.cache_file_locking,
    )


def create_default_cache(
    cache_strategy: str = "process_isolated",
    cache_file_locking: bool = True,
) -> CacheManager:
    """Create a default cache manager for general use.

    Uses filesystem caching with reasonable defaults:
    - 500MB max size
    - 24 hour default TTL
    - LRU eviction policy
    - Process-isolated cache by default with optional file locking

    Args:
        cache_strategy: Cache strategy ("process_isolated", "shared", "disabled")
        cache_file_locking: Enable file locking for concurrent access protection

    Returns:
        Default configured cache manager
    """
    if cache_strategy == "disabled":
        return create_memory_cache(
            max_size_mb=100,  # Smaller for memory
            max_entries=1000,
            default_ttl_hours=1,  # Shorter TTL for memory
        )
    else:
        # Use filesystem cache (process_isolated or shared)
        return create_filesystem_cache(
            max_size_mb=500,
            max_entries=10000,
            default_ttl_hours=24,
            use_file_locking=cache_file_locking,
            cache_strategy=cache_strategy,
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
    "create_cache_from_user_config",
]
