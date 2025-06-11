"""Generic cache manager protocol and interface."""

import time
from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable

from glovebox.core.cache.models import CacheConfig, CacheMetadata, CacheStats


@runtime_checkable
class CacheManager(Protocol):
    """Generic cache manager interface.

    Defines the contract for all cache implementations, enabling
    domain-agnostic caching that can be used across the entire codebase.
    """

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve value from cache.

        Args:
            key: Cache key to retrieve
            default: Default value if key not found

        Returns:
            Cached value or default
        """
        ...

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store value in cache.

        Args:
            key: Cache key to store under
            value: Value to cache
            ttl: Time-to-live in seconds (None for no expiration)
        """
        ...

    def delete(self, key: str) -> bool:
        """Remove value from cache.

        Args:
            key: Cache key to remove

        Returns:
            True if key was removed, False if not found
        """
        ...

    def clear(self) -> None:
        """Clear all entries from cache."""
        ...

    def exists(self, key: str) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key to check

        Returns:
            True if key exists and is not expired
        """
        ...

    def get_metadata(self, key: str) -> CacheMetadata | None:
        """Get metadata for cache entry.

        Args:
            key: Cache key to get metadata for

        Returns:
            Cache metadata or None if not found
        """
        ...

    def get_stats(self) -> CacheStats:
        """Get cache performance statistics.

        Returns:
            Current cache statistics
        """
        ...

    def cleanup(self) -> int:
        """Remove expired entries and enforce size limits.

        Returns:
            Number of entries removed
        """
        ...


class BaseCacheManager(ABC):
    """Base implementation for cache managers.

    Provides common functionality and patterns for cache implementations.
    """

    def __init__(self, config: CacheConfig | None = None):
        """Initialize base cache manager.

        Args:
            config: Cache configuration options
        """
        self.config = config or CacheConfig()
        self.stats = CacheStats(
            total_entries=0,
            total_size_bytes=0,
            hit_count=0,
            miss_count=0,
            eviction_count=0,
            error_count=0,
        )
        self._last_cleanup = time.time()

    @abstractmethod
    def _get_raw(self, key: str) -> Any:
        """Get raw value from underlying storage."""
        pass

    @abstractmethod
    def _set_raw(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set raw value in underlying storage."""
        pass

    @abstractmethod
    def _delete_raw(self, key: str) -> bool:
        """Delete raw value from underlying storage."""
        pass

    @abstractmethod
    def _clear_raw(self) -> None:
        """Clear all values from underlying storage."""
        pass

    @abstractmethod
    def _exists_raw(self, key: str) -> bool:
        """Check if key exists in underlying storage."""
        pass

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve value from cache with statistics tracking."""
        try:
            if not self._exists_raw(key):
                self.stats.miss_count += 1
                return default

            value = self._get_raw(key)
            if value is None:
                self.stats.miss_count += 1
                return default

            self.stats.hit_count += 1
            self._maybe_cleanup()
            return value

        except Exception:
            self.stats.error_count += 1
            return default

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store value in cache with statistics tracking."""
        try:
            self._set_raw(key, value, ttl)
            self._maybe_cleanup()

        except Exception:
            self.stats.error_count += 1
            raise

    def delete(self, key: str) -> bool:
        """Remove value from cache with statistics tracking."""
        try:
            result = self._delete_raw(key)
            self._maybe_cleanup()
            return result

        except Exception:
            self.stats.error_count += 1
            return False

    def clear(self) -> None:
        """Clear all entries from cache."""
        try:
            self._clear_raw()
            self.stats = CacheStats(
                total_entries=0,
                total_size_bytes=0,
                hit_count=self.stats.hit_count,
                miss_count=self.stats.miss_count,
                eviction_count=self.stats.eviction_count,
                error_count=self.stats.error_count,
            )

        except Exception:
            self.stats.error_count += 1
            raise

    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            return self._exists_raw(key)

        except Exception:
            self.stats.error_count += 1
            return False

    def get_stats(self) -> CacheStats:
        """Get current cache statistics."""
        return self.stats

    def _maybe_cleanup(self) -> None:
        """Run cleanup if interval has elapsed."""
        now = time.time()
        if now - self._last_cleanup >= self.config.cleanup_interval_seconds:
            self.cleanup()
            self._last_cleanup = now

    @abstractmethod
    def cleanup(self) -> int:
        """Remove expired entries and enforce limits."""
        pass

    def _calculate_size(self, value: Any) -> int:
        """Estimate size of cached value in bytes."""
        import sys

        try:
            return sys.getsizeof(value)
        except Exception:
            # Fallback for objects that don't support getsizeof
            return len(str(value).encode("utf-8"))
