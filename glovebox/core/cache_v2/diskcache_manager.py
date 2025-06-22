"""DiskCache-based cache manager implementation."""

import logging
import time
from pathlib import Path
from typing import Any

import diskcache  # type: ignore[import-untyped]

from glovebox.core.cache_v2.cache_manager import CacheManager
from glovebox.core.cache_v2.models import CacheMetadata, CacheStats, DiskCacheConfig


logger = logging.getLogger(__name__)


class DiskCacheManager(CacheManager):
    """Cache manager implementation using DiskCache library.

    DiskCache provides SQLite-backed persistent caching with automatic
    concurrency control and eviction policies.
    """

    def __init__(self, config: DiskCacheConfig) -> None:
        """Initialize DiskCache manager.

        Args:
            config: Cache configuration
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Create cache directory
        cache_path = (
            Path(self.config.cache_path)
            if isinstance(self.config.cache_path, str)
            else self.config.cache_path
        )
        cache_path.mkdir(parents=True, exist_ok=True)

        # Initialize DiskCache with configuration
        self._cache = diskcache.Cache(
            directory=str(self.config.cache_path),
            size_limit=self.config.max_size_bytes,
            timeout=self.config.timeout,
            # Use default eviction policy (least-recently-stored)
        )

        # Statistics tracking (DiskCache doesn't provide all stats we need)
        self._stats = CacheStats(
            total_entries=0,
            total_size_bytes=0,
            hit_count=0,
            miss_count=0,
            eviction_count=0,
            error_count=0,
        )

        self.logger.debug("DiskCache initialized at %s", self.config.cache_path)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve value from cache.

        Args:
            key: Cache key to retrieve
            default: Default value if key not found

        Returns:
            Cached value or default
        """
        try:
            # DiskCache.get() returns default if key not found or expired
            value = self._cache.get(key, default=default)

            if value is not default:
                self._stats.hit_count += 1
                self.logger.debug("Cache hit for key: %s", key)
            else:
                self._stats.miss_count += 1
                self.logger.debug("Cache miss for key: %s", key)

            return value

        except Exception as e:
            self._stats.error_count += 1
            self.logger.warning("Cache get error for key %s: %s", key, e)
            return default

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store value in cache.

        Args:
            key: Cache key to store under
            value: Value to cache
            ttl: Time-to-live in seconds (None for no expiration)
        """
        try:
            if ttl is not None:
                # DiskCache uses expire parameter for TTL
                self._cache.set(key, value, expire=ttl)
            else:
                self._cache.set(key, value)

            self.logger.debug("Cached value for key: %s (TTL: %s)", key, ttl)

        except Exception as e:
            self._stats.error_count += 1
            self.logger.warning("Cache set error for key %s: %s", key, e)
            raise

    def delete(self, key: str) -> bool:
        """Remove value from cache.

        Args:
            key: Cache key to remove

        Returns:
            True if key was removed, False if not found
        """
        try:
            # DiskCache.delete() returns True if key existed, False otherwise
            result: bool = self._cache.delete(key)
            self.logger.debug("Deleted cache key: %s (existed: %s)", key, result)
            return result

        except Exception as e:
            self._stats.error_count += 1
            self.logger.warning("Cache delete error for key %s: %s", key, e)
            return False

    def delete_many(self, keys: list[str]) -> int:
        """Remove multiple values from cache.

        Args:
            keys: List of cache keys to remove

        Returns:
            Number of keys successfully deleted
        """
        deleted_count = 0
        for key in keys:
            if self.delete(key):
                deleted_count += 1

        self.logger.debug("Deleted %d/%d cache keys", deleted_count, len(keys))
        return deleted_count

    def clear(self) -> None:
        """Clear all entries from cache."""
        try:
            self._cache.clear()
            # Reset stats except error counters
            self._stats = CacheStats(
                total_entries=0,
                total_size_bytes=0,
                hit_count=self._stats.hit_count,
                miss_count=self._stats.miss_count,
                eviction_count=self._stats.eviction_count,
                error_count=self._stats.error_count,
            )
            self.logger.info("Cache cleared")

        except Exception as e:
            self._stats.error_count += 1
            self.logger.warning("Cache clear error: %s", e)
            raise

    def exists(self, key: str) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key to check

        Returns:
            True if key exists and is not expired
        """
        try:
            # DiskCache doesn't have direct exists(), use __contains__
            return key in self._cache

        except Exception as e:
            self._stats.error_count += 1
            self.logger.warning("Cache exists error for key %s: %s", key, e)
            return False

    def get_metadata(self, key: str) -> CacheMetadata | None:
        """Get metadata for cache entry.

        Args:
            key: Cache key to get metadata for

        Returns:
            Cache metadata or None if not found
        """
        try:
            if key not in self._cache:
                return None

            # DiskCache doesn't expose all metadata we need
            # We'll return basic metadata with current timestamp
            current_time = time.time()

            # Try to estimate size (this is approximate)
            try:
                value = self._cache[key]
                size_bytes = len(str(value).encode("utf-8"))
            except Exception:
                size_bytes = 0

            return CacheMetadata(
                key=key,
                size_bytes=size_bytes,
                created_at=current_time,  # DiskCache doesn't expose creation time
                last_accessed=current_time,
                access_count=1,  # DiskCache doesn't track access count
                ttl_seconds=None,  # Would need to track this separately
            )

        except Exception as e:
            self._stats.error_count += 1
            self.logger.warning("Cache metadata error for key %s: %s", key, e)
            return None

    def get_stats(self) -> CacheStats:
        """Get cache performance statistics.

        Returns:
            Current cache statistics
        """
        try:
            # Update stats with current DiskCache info
            volume_info = self._cache.volume()

            self._stats.total_entries = len(self._cache)
            # volume() returns an integer representing directory size
            if isinstance(volume_info, int):
                self._stats.total_size_bytes = volume_info
            elif isinstance(volume_info, dict):
                self._stats.total_size_bytes = volume_info.get("size", 0)
            else:
                self._stats.total_size_bytes = 0

            return self._stats

        except Exception as e:
            self.logger.warning("Error getting cache stats: %s", e)
            return self._stats

    def cleanup(self) -> int:
        """Remove expired entries and enforce size limits.

        DiskCache handles this automatically, but we can force eviction.

        Returns:
            Number of entries removed (not available from DiskCache)
        """
        try:
            # DiskCache handles cleanup automatically
            # We can call evict() to force cleanup if needed
            evicted: int = self._cache.evict()
            self._stats.eviction_count += evicted

            if evicted > 0:
                self.logger.info("Evicted %d cache entries", evicted)

            return evicted

        except Exception as e:
            self._stats.error_count += 1
            self.logger.warning("Cache cleanup error: %s", e)
            return 0

    def keys(self) -> list[str]:
        """Get all cache keys.

        Returns:
            List of all cache keys (excluding expired entries)
        """
        try:
            # DiskCache provides an iterator over all non-expired keys
            return list(self._cache.iterkeys())

        except Exception as e:
            self._stats.error_count += 1
            self.logger.warning("Cache keys error: %s", e)
            return []

    def close(self) -> None:
        """Close the cache and release resources."""
        try:
            self._cache.close()
            self.logger.debug("Cache closed")
        except Exception as e:
            self.logger.warning("Error closing cache: %s", e)

    def __enter__(self) -> "DiskCacheManager":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()
