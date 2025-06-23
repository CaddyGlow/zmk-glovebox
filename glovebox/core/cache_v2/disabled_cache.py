"""Disabled cache implementation that performs no caching."""

from typing import Any

from glovebox.core.cache_v2.cache_manager import CacheManager
from glovebox.core.cache_v2.models import CacheMetadata, CacheStats


class DisabledCache(CacheManager):
    """No-op cache implementation that doesn't store anything.

    This is used when caching is disabled globally or for specific modules.
    All operations are no-ops that return appropriate default values.
    """

    def get(self, key: str, default: Any = None) -> Any:
        """Always return default value (no caching)."""
        return default

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """No-op set operation."""
        pass

    def delete(self, key: str) -> bool:
        """Always return False (nothing to delete)."""
        return False

    def delete_many(self, keys: list[str]) -> int:
        """Always return 0 (nothing to delete)."""
        return 0

    def clear(self) -> None:
        """No-op clear operation."""
        pass

    def exists(self, key: str) -> bool:
        """Always return False (nothing exists)."""
        return False

    def get_metadata(self, key: str) -> CacheMetadata | None:
        """Always return None (no metadata)."""
        return None

    def get_stats(self) -> CacheStats:
        """Return empty statistics."""
        return CacheStats(
            total_entries=0,
            total_size_bytes=0,
            hit_count=0,
            miss_count=0,
            eviction_count=0,
            error_count=0,
        )

    def cleanup(self) -> int:
        """Return 0 (nothing to clean up)."""
        return 0

    def keys(self) -> list[str]:
        """Always return empty list (no keys)."""
        return []

    def close(self) -> None:
        """No-op close operation."""
        pass

    def __enter__(self) -> "DisabledCache":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        pass
