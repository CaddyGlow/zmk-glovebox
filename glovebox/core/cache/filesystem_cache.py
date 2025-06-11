"""Filesystem-based cache implementation."""

import json
import logging
import time
from pathlib import Path
from typing import Any

from glovebox.core.cache.cache_manager import BaseCacheManager
from glovebox.core.cache.models import CacheConfig, CacheMetadata
from glovebox.core.errors import GloveboxError


logger = logging.getLogger(__name__)


class FilesystemCacheError(GloveboxError):
    """Error in filesystem cache operations."""


class FilesystemCache(BaseCacheManager):
    """File system-based cache implementation.

    Stores cached data as JSON files in a directory structure.
    Provides persistent caching across application restarts.
    """

    def __init__(self, config: CacheConfig | None = None):
        """Initialize filesystem cache.

        Args:
            config: Cache configuration with cache_root path
        """
        super().__init__(config)

        if not self.config.cache_root:
            # Default cache location
            import tempfile

            self.config.cache_root = Path(tempfile.gettempdir()) / "glovebox_cache"

        self.cache_root = self.config.cache_root
        self.data_dir = self.cache_root / "data"
        self.metadata_dir = self.cache_root / "metadata"

        # Create cache directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

        logger.debug("Initialized filesystem cache at: %s", self.cache_root)

    def _get_data_path(self, key: str) -> Path:
        """Get file path for cached data."""
        return self.data_dir / f"{key}.json"

    def _get_metadata_path(self, key: str) -> Path:
        """Get file path for cache metadata."""
        return self.metadata_dir / f"{key}.meta.json"

    def _get_raw(self, key: str) -> Any:
        """Get raw value from filesystem."""
        data_path = self._get_data_path(key)
        metadata_path = self._get_metadata_path(key)

        if not data_path.exists() or not metadata_path.exists():
            return None

        try:
            # Load and check metadata
            with metadata_path.open("r") as f:
                metadata_data = json.load(f)
                metadata = CacheMetadata(**metadata_data)

            # Check if expired
            if metadata.is_expired:
                self._delete_raw(key)
                return None

            # Load data
            with data_path.open("r") as f:
                data = json.load(f)

            # Update access metadata
            metadata.touch()
            self._save_metadata(key, metadata)

            return data

        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.warning("Failed to load cache entry %s: %s", key, e)
            # Clean up corrupted cache entry
            self._delete_raw(key)
            return None

    def _set_raw(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set raw value in filesystem."""
        data_path = self._get_data_path(key)
        metadata_path = self._get_metadata_path(key)

        try:
            # Prepare data - ensure it's JSON serializable
            serialized_data = self._prepare_for_serialization(value)

            # Create metadata
            now = time.time()
            ttl_to_use = ttl or self.config.default_ttl_seconds
            size_bytes = self._calculate_size(serialized_data)

            metadata = CacheMetadata(
                key=key,
                size_bytes=size_bytes,
                created_at=now,
                last_accessed=now,
                access_count=1,
                ttl_seconds=ttl_to_use,
            )

            # Save data and metadata atomically
            with data_path.open("w") as f:
                json.dump(serialized_data, f, separators=(",", ":"))

            self._save_metadata(key, metadata)

            # Update statistics
            self.stats.total_entries += 1
            self.stats.total_size_bytes += size_bytes

            logger.debug(
                "Cached entry %s (size: %d bytes, ttl: %s)",
                key,
                size_bytes,
                ttl_to_use,
            )

        except (json.JSONDecodeError, OSError) as e:
            raise FilesystemCacheError(f"Failed to cache entry {key}: {e}") from e

    def _delete_raw(self, key: str) -> bool:
        """Delete raw value from filesystem."""
        data_path = self._get_data_path(key)
        metadata_path = self._get_metadata_path(key)

        deleted = False

        if data_path.exists():
            try:
                data_path.unlink()
                deleted = True
            except OSError as e:
                logger.warning("Failed to delete data file %s: %s", data_path, e)

        if metadata_path.exists():
            try:
                metadata_path.unlink()
                if not deleted:  # Only count as deleted if we removed something
                    deleted = True
            except OSError as e:
                logger.warning(
                    "Failed to delete metadata file %s: %s", metadata_path, e
                )

        if deleted:
            self.stats.total_entries = max(0, self.stats.total_entries - 1)
            logger.debug("Deleted cache entry: %s", key)

        return deleted

    def _clear_raw(self) -> None:
        """Clear all values from filesystem."""
        try:
            # Remove all data files
            for data_file in self.data_dir.glob("*.json"):
                data_file.unlink(missing_ok=True)

            # Remove all metadata files
            for meta_file in self.metadata_dir.glob("*.meta.json"):
                meta_file.unlink(missing_ok=True)

            # Reset size statistics
            self.stats.total_entries = 0
            self.stats.total_size_bytes = 0

            logger.debug("Cleared filesystem cache")

        except OSError as e:
            raise FilesystemCacheError(f"Failed to clear cache: {e}") from e

    def _exists_raw(self, key: str) -> bool:
        """Check if key exists in filesystem."""
        data_path = self._get_data_path(key)
        metadata_path = self._get_metadata_path(key)

        if not data_path.exists() or not metadata_path.exists():
            return False

        # Check if expired
        try:
            with metadata_path.open("r") as f:
                metadata_data = json.load(f)
                metadata = CacheMetadata(**metadata_data)

            if metadata.is_expired:
                self._delete_raw(key)
                return False

            return True

        except (json.JSONDecodeError, OSError, KeyError):
            # Corrupted metadata, treat as non-existent
            self._delete_raw(key)
            return False

    def get_metadata(self, key: str) -> CacheMetadata | None:
        """Get metadata for cache entry."""
        metadata_path = self._get_metadata_path(key)

        if not metadata_path.exists():
            return None

        try:
            with metadata_path.open("r") as f:
                metadata_data = json.load(f)
                return CacheMetadata(**metadata_data)

        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.warning("Failed to load metadata for %s: %s", key, e)
            return None

    def cleanup(self) -> int:
        """Remove expired entries and enforce size limits."""
        removed_count = 0

        try:
            # Collect all cache entries with metadata
            entries = []
            for metadata_file in self.metadata_dir.glob("*.meta.json"):
                key = metadata_file.stem.replace(".meta", "")
                metadata = self.get_metadata(key)

                if not metadata:
                    continue

                if metadata.is_expired:
                    # Remove expired entries
                    if self._delete_raw(key):
                        removed_count += 1
                        self.stats.eviction_count += 1
                else:
                    entries.append((key, metadata))

            # Enforce size limits if configured
            if (
                self.config.max_size_bytes
                and self.stats.total_size_bytes > self.config.max_size_bytes
            ):
                removed_count += self._enforce_size_limit(entries)

            # Enforce entry count limits if configured
            if self.config.max_entries and len(entries) > self.config.max_entries:
                removed_count += self._enforce_entry_limit(entries)

            logger.debug("Cache cleanup removed %d entries", removed_count)

        except Exception as e:
            logger.error("Cache cleanup failed: %s", e)
            self.stats.error_count += 1

        return removed_count

    def _save_metadata(self, key: str, metadata: CacheMetadata) -> None:
        """Save metadata to filesystem."""
        metadata_path = self._get_metadata_path(key)

        metadata_dict = {
            "key": metadata.key,
            "size_bytes": metadata.size_bytes,
            "created_at": metadata.created_at,
            "last_accessed": metadata.last_accessed,
            "access_count": metadata.access_count,
            "ttl_seconds": metadata.ttl_seconds,
            "tags": metadata.tags,
        }

        with metadata_path.open("w") as f:
            json.dump(metadata_dict, f, separators=(",", ":"))

    def _prepare_for_serialization(self, value: Any) -> Any:
        """Prepare value for JSON serialization."""
        if isinstance(value, dict | list | str | int | float | bool) or value is None:
            return value
        elif isinstance(value, Path):
            return str(value)
        elif hasattr(value, "dict"):
            # Pydantic models
            return value.dict()
        elif hasattr(value, "__dict__"):
            # Regular objects with __dict__
            return value.__dict__
        else:
            # Fallback to string representation
            return str(value)

    def _enforce_size_limit(self, entries: list[tuple[str, CacheMetadata]]) -> int:
        """Enforce maximum cache size by removing entries."""
        if not self.config.max_size_bytes:
            return 0

        removed_count = 0
        current_size = sum(metadata.size_bytes for _, metadata in entries)

        if current_size <= self.config.max_size_bytes:
            return 0

        # Sort by eviction policy (default LRU)
        if self.config.eviction_policy == "lru":
            entries.sort(key=lambda x: x[1].last_accessed)
        elif self.config.eviction_policy == "lfu":
            entries.sort(key=lambda x: x[1].access_count)
        elif self.config.eviction_policy == "fifo":
            entries.sort(key=lambda x: x[1].created_at)

        # Remove entries until under size limit
        for key, metadata in entries:
            if current_size <= self.config.max_size_bytes:
                break

            if self._delete_raw(key):
                current_size -= metadata.size_bytes
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
