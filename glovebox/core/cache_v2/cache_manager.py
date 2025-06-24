"""Generic cache manager protocol and interface."""

from typing import Any, Protocol, runtime_checkable

from glovebox.core.cache_v2.models import CacheMetadata, CacheStats


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

    def delete_many(self, keys: list[str]) -> int:
        """Remove multiple values from cache.

        Args:
            keys: List of cache keys to remove

        Returns:
            Number of keys successfully deleted
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

    def keys(self) -> list[str]:
        """Get all cache keys.

        Returns:
            List of all cache keys (excluding expired entries)
        """
        ...

    def close(self) -> None:
        """Close the cache and release resources."""
        ...
