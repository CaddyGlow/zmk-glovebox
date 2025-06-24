"""Cache coordination utilities for shared cache instance management.

This module provides utilities for coordinating cache instances across domains
while following the established factory function pattern from CLAUDE.md.
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional

from glovebox.core.logging import get_logger

from .cache_manager import CacheManager
from .disabled_cache import DisabledCache
from .diskcache_manager import DiskCacheManager
from .models import DiskCacheConfig


logger = get_logger(__name__)

# Shared cache instances registry
_shared_cache_instances: dict[str, CacheManager] = {}


def get_shared_cache_instance(
    cache_root: Path,
    tag: str | None = None,
    enabled: bool = True,
    max_size_gb: int = 2,
    timeout: int = 30,
    session_metrics: Any | None = None,
) -> CacheManager:
    """Get shared cache instance, creating if needed.

    This function coordinates cache instances across domains to ensure
    a single cache instance is shared when appropriate, following the
    factory function pattern established in CLAUDE.md.

    Args:
        cache_root: Root directory for cache storage
        tag: Optional tag for cache isolation
        enabled: Whether caching is enabled
        max_size_gb: Maximum cache size in GB
        timeout: Cache operation timeout in seconds
        session_metrics: Optional SessionMetrics instance for metrics integration

    Returns:
        Shared cache manager instance
    """
    if not enabled:
        return DisabledCache()

    # Create cache key for instance coordination
    cache_key = f"{cache_root.resolve()}:{tag or 'default'}"

    if cache_key not in _shared_cache_instances:

        # Create tag-specific cache directory
        cache_dir = cache_root / (tag or "default")

        # Create DiskCacheConfig and DiskCacheManager
        config = DiskCacheConfig(
            cache_path=cache_dir,
            max_size_bytes=max_size_gb * 1024 * 1024 * 1024,
            timeout=timeout,
        )
        _shared_cache_instances[cache_key] = DiskCacheManager(
            config, tag=tag, session_metrics=session_metrics
        )
    else:
        logger.debug("Reusing existing shared cache instance: %s", cache_key)

    return _shared_cache_instances[cache_key]


def reset_shared_cache_instances() -> None:
    """Reset all shared cache instances.

    This is primarily used for testing to ensure clean state between tests.
    Follows the testing isolation requirements from CLAUDE.md.
    """
    import shutil

    global _shared_cache_instances

    logger.debug("Resetting %d shared cache instances", len(_shared_cache_instances))

    # Close all existing cache instances
    for cache_key, cache_instance in _shared_cache_instances.items():
        try:
            if hasattr(cache_instance, "close"):
                cache_instance.close()
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.warning(
                "Error closing cache instance %s: %s", cache_key, e, exc_info=exc_info
            )

    # Clear the registry
    _shared_cache_instances.clear()

    # Clean up workspace cache directories for test isolation
    try:
        workspace_cache_dir = Path.home() / ".cache" / "glovebox" / "workspace"
        if workspace_cache_dir.exists():
            shutil.rmtree(workspace_cache_dir, ignore_errors=True)
            logger.debug(
                "Cleaned up workspace cache directory: %s", workspace_cache_dir
            )
    except Exception as e:
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.warning(
            "Error cleaning workspace cache directory: %s", e, exc_info=exc_info
        )


def get_cache_instance_count() -> int:
    """Get the number of active shared cache instances.

    Returns:
        Number of active cache instances
    """
    return len(_shared_cache_instances)


def get_cache_instance_keys() -> list[str]:
    """Get list of active cache instance keys.

    Returns:
        List of cache instance keys for debugging
    """
    return list(_shared_cache_instances.keys())


def cleanup_shared_cache_instances() -> dict[str, int]:
    """Clean up expired entries across all shared cache instances.

    Returns:
        Dictionary mapping cache keys to number of entries cleaned up
    """
    cleanup_results = {}

    for cache_key, cache_instance in _shared_cache_instances.items():
        try:
            if hasattr(cache_instance, "cleanup"):
                cleanup_count = cache_instance.cleanup()
                cleanup_results[cache_key] = cleanup_count
                logger.debug(
                    "Cleaned up %d entries from cache instance: %s",
                    cleanup_count,
                    cache_key,
                )
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.warning(
                "Error cleaning up cache instance %s: %s",
                cache_key,
                e,
                exc_info=exc_info,
            )
            cleanup_results[cache_key] = 0

    return cleanup_results


def get_aggregated_cache_stats() -> dict[str, Any]:
    """Get aggregated cache statistics across all shared cache instances.

    Returns:
        Dictionary with aggregated cache statistics and per-tag breakdown
    """
    aggregated_stats: dict[str, Any] = {
        "total_instances": len(_shared_cache_instances),
        "total_entries": 0,
        "total_size_bytes": 0,
        "total_hit_count": 0,
        "total_miss_count": 0,
        "total_eviction_count": 0,
        "total_error_count": 0,
        "total_operation_count": 0,
        "total_operation_time": 0.0,
        "overall_hit_rate": 0.0,
        "overall_avg_operation_time": 0.0,
        "by_tag": {},
    }

    for cache_key, cache_instance in _shared_cache_instances.items():
        try:
            if hasattr(cache_instance, "get_stats"):
                stats = cache_instance.get_stats()

                # Add to totals
                aggregated_stats["total_entries"] += stats.total_entries
                aggregated_stats["total_size_bytes"] += stats.total_size_bytes
                aggregated_stats["total_hit_count"] += stats.hit_count
                aggregated_stats["total_miss_count"] += stats.miss_count
                aggregated_stats["total_eviction_count"] += stats.eviction_count
                aggregated_stats["total_error_count"] += stats.error_count
                aggregated_stats["total_operation_count"] += stats.operation_count
                aggregated_stats["total_operation_time"] += stats.total_operation_time

                # Store per-tag breakdown
                tag = stats.tag or "default"
                aggregated_stats["by_tag"][tag] = stats.to_metrics_dict()

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.warning(
                "Error getting stats from cache instance %s: %s",
                cache_key,
                e,
                exc_info=exc_info,
            )

    # Calculate overall rates
    total_requests = (
        aggregated_stats["total_hit_count"] + aggregated_stats["total_miss_count"]
    )
    if total_requests > 0:
        aggregated_stats["overall_hit_rate"] = (
            aggregated_stats["total_hit_count"] / total_requests
        ) * 100.0

    if aggregated_stats["total_operation_count"] > 0:
        aggregated_stats["overall_avg_operation_time"] = (
            aggregated_stats["total_operation_time"]
            / aggregated_stats["total_operation_count"]
        )

    return aggregated_stats
