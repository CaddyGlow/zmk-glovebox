"""In-memory cache implementation."""

import logging
import time
from typing import Any

from glovebox.core.cache.cache_manager import BaseCacheManager
from glovebox.core.cache.models import CacheConfig, CacheEntry, CacheMetadata


logger = logging.getLogger(__name__)


class MemoryCache(BaseCacheManager):
    """In-memory cache implementation.

    Stores cached data in memory for fast access.
    Data is lost when the application restarts.
    """

    def __init__(self, config: CacheConfig | None = None):
        """Initialize memory cache.

        Args:
            config: Cache configuration options
        """
        super().__init__(config)
        self._cache: dict[str, CacheEntry] = {}
        logger.debug("Initialized memory cache")

    def _get_raw(self, key: str) -> Any:
        """Get raw value from memory."""
        entry = self._cache.get(key)
        if not entry:
            return None

        # Check if expired
        if entry.is_expired:
            del self._cache[key]
            self.stats.total_entries -= 1
            self.stats.total_size_bytes -= entry.metadata.size_bytes
            return None

        # Update access metadata
        entry.touch()
        return entry.data

    def _set_raw(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set raw value in memory."""
        now = time.time()
        ttl_to_use = ttl or self.config.default_ttl_seconds
        size_bytes = self._calculate_size(value)

        metadata = CacheMetadata(
            key=key,
            size_bytes=size_bytes,
            created_at=now,
            last_accessed=now,
            access_count=1,
            ttl_seconds=ttl_to_use,
        )

        entry = CacheEntry(data=value, metadata=metadata)

        # Remove existing entry if present
        if key in self._cache:
            old_entry = self._cache[key]
            self.stats.total_size_bytes -= old_entry.metadata.size_bytes
        else:
            self.stats.total_entries += 1

        self._cache[key] = entry
        self.stats.total_size_bytes += size_bytes

        logger.debug(
            "Cached entry %s in memory (size: %d bytes, ttl: %s)",
            key,
            size_bytes,
            ttl_to_use,
        )

    def _delete_raw(self, key: str) -> bool:
        """Delete raw value from memory."""
        entry = self._cache.pop(key, None)
        if entry:
            self.stats.total_entries -= 1
            self.stats.total_size_bytes -= entry.metadata.size_bytes
            logger.debug("Deleted cache entry from memory: %s", key)
            return True
        return False

    def _clear_raw(self) -> None:
        """Clear all values from memory."""
        self._cache.clear()
        self.stats.total_entries = 0
        self.stats.total_size_bytes = 0
        logger.debug("Cleared memory cache")

    def _exists_raw(self, key: str) -> bool:
        """Check if key exists in memory."""
        entry = self._cache.get(key)
        if not entry:
            return False

        # Check if expired
        if entry.is_expired:
            del self._cache[key]
            self.stats.total_entries -= 1
            self.stats.total_size_bytes -= entry.metadata.size_bytes
            return False

        return True

    def get_metadata(self, key: str) -> CacheMetadata | None:
        """Get metadata for cache entry."""
        entry = self._cache.get(key)
        if not entry:
            return None

        # Check if expired
        if entry.is_expired:
            del self._cache[key]
            self.stats.total_entries -= 1
            self.stats.total_size_bytes -= entry.metadata.size_bytes
            return None

        return entry.metadata

    def cleanup(self) -> int:
        """Remove expired entries and enforce limits."""
        removed_count = 0

        try:
            # Remove expired entries
            expired_keys = []
            for key, entry in self._cache.items():
                if entry.is_expired:
                    expired_keys.append(key)

            for key in expired_keys:
                if self._delete_raw(key):
                    removed_count += 1
                    self.stats.eviction_count += 1

            # Collect remaining entries for limit enforcement
            entries = [(k, v.metadata) for k, v in self._cache.items()]

            # Enforce size limits if configured
            if (
                self.config.max_size_bytes
                and self.stats.total_size_bytes > self.config.max_size_bytes
            ):
                removed_count += self._enforce_size_limit(entries)

            # Enforce entry count limits if configured
            if self.config.max_entries and len(entries) > self.config.max_entries:
                removed_count += self._enforce_entry_limit(entries)

            logger.debug("Memory cache cleanup removed %d entries", removed_count)

        except Exception as e:
            logger.error("Memory cache cleanup failed: %s", e)
            self.stats.error_count += 1

        return removed_count

    def _enforce_size_limit(self, entries: list[tuple[str, CacheMetadata]]) -> int:
        """Enforce maximum cache size by removing entries."""
        if (
            not self.config.max_size_bytes
            or self.stats.total_size_bytes <= self.config.max_size_bytes
        ):
            return 0

        removed_count = 0

        # Sort by eviction policy (default LRU)
        if self.config.eviction_policy == "lru":
            entries.sort(key=lambda x: x[1].last_accessed)
        elif self.config.eviction_policy == "lfu":
            entries.sort(key=lambda x: x[1].access_count)
        elif self.config.eviction_policy == "fifo":
            entries.sort(key=lambda x: x[1].created_at)

        # Remove entries until under size limit
        for key, _metadata in entries:
            if self.stats.total_size_bytes <= self.config.max_size_bytes:
                break

            if self._delete_raw(key):
                removed_count += 1
                self.stats.eviction_count += 1

        return removed_count

    def _enforce_entry_limit(self, entries: list[tuple[str, CacheMetadata]]) -> int:
        """Enforce maximum entry count by removing entries."""
        if not self.config.max_entries or len(entries) <= self.config.max_entries:
            return 0

        removed_count = 0
        entries_to_remove = len(entries) - self.config.max_entries

        # Sort by eviction policy (default LRU)
        if self.config.eviction_policy == "lru":
            entries.sort(key=lambda x: x[1].last_accessed)
        elif self.config.eviction_policy == "lfu":
            entries.sort(key=lambda x: x[1].access_count)
        elif self.config.eviction_policy == "fifo":
            entries.sort(key=lambda x: x[1].created_at)

        # Remove oldest entries
        for key, _metadata in entries[:entries_to_remove]:
            if self._delete_raw(key):
                removed_count += 1
                self.stats.eviction_count += 1

        return removed_count

    def get_all_keys(self) -> list[str]:
        """Get all cache keys (for debugging and management)."""
        return list(self._cache.keys())

    def get_size_info(self) -> dict[str, int]:
        """Get detailed size information."""
        return {
            "total_entries": len(self._cache),
            "total_size_bytes": self.stats.total_size_bytes,
            "average_size_bytes": (
                self.stats.total_size_bytes // len(self._cache) if self._cache else 0
            ),
        }
