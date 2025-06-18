"""Filesystem-based cache implementation."""

import contextlib
import fcntl
import json
import logging
import os
import tempfile
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
            # Default cache location with process isolation
            cache_base = Path(tempfile.gettempdir()) / "glovebox_cache"

            # Use config strategy (required parameter)
            cache_strategy = self.config.cache_strategy or "process_isolated"

            if cache_strategy == "shared":
                # Shared cache (original behavior) - may have race conditions
                self.config.cache_root = cache_base
            elif cache_strategy == "process_isolated":
                # Process-specific cache directories (default)
                self.config.cache_root = cache_base / f"proc_{os.getpid()}"
            elif cache_strategy == "disabled":
                # Use memory cache instead
                raise FilesystemCacheError(
                    "Filesystem cache disabled via GLOVEBOX_CACHE_STRATEGY=disabled"
                )
            else:
                # Treat unknown strategies as shared
                self.config.cache_root = cache_base

        self.cache_root = self.config.cache_root
        self.data_dir = self.cache_root / "data"
        self.metadata_dir = self.cache_root / "metadata"

        # Create cache directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

        # Use config file locking setting
        self.use_file_locking = self.config.use_file_locking

        logger.debug("Initialized filesystem cache at: %s", self.cache_root)
        logger.debug("File locking enabled: %s", self.use_file_locking)

    @contextlib.contextmanager
    def _file_lock(self, key: str, operation: str = "read", timeout: float = 5.0):
        """Context manager for file locking to prevent race conditions.

        Args:
            key: Cache key to lock
            operation: "read", "write", or "delete"
            timeout: Maximum time to wait for lock in seconds
        """
        # Skip locking if disabled
        if not self.use_file_locking:
            yield
            return

        lock_path = self.cache_root / f"{key}.lock"
        lock_file = None

        try:
            # Create lock file
            lock_file = lock_path.open("w")

            # Choose lock type based on operation
            if operation == "read":
                lock_type = fcntl.LOCK_SH  # Shared lock for reads
            else:
                lock_type = fcntl.LOCK_EX  # Exclusive lock for writes/deletes

            # Try to acquire lock with timeout
            start_time = time.time()
            while True:
                try:
                    fcntl.flock(lock_file.fileno(), lock_type | fcntl.LOCK_NB)
                    break  # Lock acquired
                except OSError:
                    if time.time() - start_time > timeout:
                        logger.debug(
                            "Lock timeout for key %s operation %s", key, operation
                        )
                        # Proceed without lock after timeout
                        break
                    time.sleep(0.01)  # Short wait before retry

            yield

        except OSError as e:
            logger.debug("File locking failed for key %s: %s", key, e)
            # Continue without locking - cache is resilient
            yield

        finally:
            # Clean up lock file
            if lock_file:
                try:
                    lock_file.close()
                    lock_path.unlink(missing_ok=True)
                except OSError:
                    pass  # Ignore cleanup errors

    def _get_data_path(self, key: str) -> Path:
        """Get file path for cached data."""
        return self.data_dir / f"{key}.json"

    def _get_metadata_path(self, key: str) -> Path:
        """Get file path for cache metadata."""
        return self.metadata_dir / f"{key}.meta.json"

    def _get_raw(self, key: str) -> Any:
        """Get raw value from filesystem with file locking."""
        data_path = self._get_data_path(key)
        metadata_path = self._get_metadata_path(key)

        # First, check existence and read metadata under read lock
        metadata = None
        data = None
        needs_deletion = False
        needs_update = False

        with self._file_lock(key, "read"):
            if not data_path.exists() or not metadata_path.exists():
                return None

            try:
                # Load and check metadata
                with metadata_path.open("r") as f:
                    metadata_data = json.load(f)
                    metadata = CacheMetadata(**metadata_data)

                # Check if expired
                if metadata.is_expired:
                    needs_deletion = True
                    return None

                # Load data
                with data_path.open("r") as f:
                    data = json.load(f)

                needs_update = True

            except (json.JSONDecodeError, OSError, KeyError) as e:
                # Only log warnings for actual corruption, not empty files (which may be race conditions)
                if isinstance(e, json.JSONDecodeError) and "Expecting value" in str(e):
                    logger.debug(
                        "Cache entry %s appears empty (possible race condition): %s",
                        key,
                        e,
                    )
                else:
                    logger.warning("Failed to load cache entry %s: %s", key, e)
                needs_deletion = True
                return None

        # Handle deletion outside of read lock to avoid deadlock
        if needs_deletion:
            with self._file_lock(key, "delete"):
                self._delete_raw_unlocked(key)
            return None

        # Update metadata outside of read lock to avoid deadlock
        if needs_update and metadata:
            with self._file_lock(key, "write"):
                metadata.touch()
                self._save_metadata(key, metadata)

        return data

    def _set_raw(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set raw value in filesystem with file locking."""
        with self._file_lock(key, "write"):
            data_path = self._get_data_path(key)
            metadata_path = self._get_metadata_path(key)

            try:
                # Prepare data - ensure it's JSON serializable
                serialized_data = self._prepare_for_serialization(value)

                # Get existing metadata to preserve access count (read directly, we already have write lock)
                existing_metadata = None
                if metadata_path.exists():
                    try:
                        with metadata_path.open("r") as f:
                            metadata_data = json.load(f)
                            existing_metadata = CacheMetadata(**metadata_data)
                    except (json.JSONDecodeError, OSError, KeyError):
                        # Ignore errors, treat as new entry
                        pass

                # Create metadata
                now = time.time()
                ttl_to_use = ttl or self.config.default_ttl_seconds
                size_bytes = self._calculate_size(serialized_data)

                metadata = CacheMetadata(
                    key=key,
                    size_bytes=size_bytes,
                    created_at=existing_metadata.created_at
                    if existing_metadata
                    else now,
                    last_accessed=now,
                    access_count=existing_metadata.access_count
                    if existing_metadata
                    else 1,
                    ttl_seconds=ttl_to_use,
                )

                # Save data and metadata atomically
                with data_path.open("w") as f:
                    json.dump(serialized_data, f, separators=(",", ":"))

                self._save_metadata(key, metadata)

                # Update statistics
                # Note: total_entries and total_size_bytes are recalculated during cleanup

                logger.debug(
                    "Cached entry %s (size: %d bytes, ttl: %s)",
                    key,
                    size_bytes,
                    ttl_to_use,
                )

            except (json.JSONDecodeError, OSError) as e:
                raise FilesystemCacheError(f"Failed to cache entry {key}: {e}") from e

    def _delete_raw(self, key: str) -> bool:
        """Delete raw value from filesystem with file locking."""
        with self._file_lock(key, "delete"):
            return self._delete_raw_unlocked(key)

    def _delete_raw_unlocked(self, key: str) -> bool:
        """Delete raw value from filesystem without locking (assumes caller has lock)."""
        data_path = self._get_data_path(key)
        metadata_path = self._get_metadata_path(key)

        deleted = False

        if data_path.exists():
            try:
                data_path.unlink()
                deleted = True
            except OSError as e:
                # Only warn if it's not a "file not found" error (race condition)
                if e.errno != 2:  # ENOENT - No such file or directory
                    logger.warning("Failed to delete data file %s: %s", data_path, e)
                else:
                    logger.debug(
                        "Data file %s already deleted (race condition)", data_path
                    )

        if metadata_path.exists():
            try:
                metadata_path.unlink()
                if not deleted:  # Only count as deleted if we removed something
                    deleted = True
            except OSError as e:
                # Only warn if it's not a "file not found" error (race condition)
                if e.errno != 2:  # ENOENT - No such file or directory
                    logger.warning(
                        "Failed to delete metadata file %s: %s", metadata_path, e
                    )
                else:
                    logger.debug(
                        "Metadata file %s already deleted (race condition)",
                        metadata_path,
                    )

        if deleted:
            # Note: stats are recalculated during cleanup
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

            # Note: stats are recalculated during cleanup

            logger.debug("Cleared filesystem cache")

        except OSError as e:
            raise FilesystemCacheError(f"Failed to clear cache: {e}") from e

    def _exists_raw(self, key: str) -> bool:
        """Check if key exists in filesystem with file locking."""
        needs_deletion = False
        exists = False

        with self._file_lock(key, "read"):
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
                    needs_deletion = True
                else:
                    # Also verify data file is valid by trying to read it
                    try:
                        with data_path.open("r") as f:
                            json.load(f)  # Just validate it's valid JSON
                        exists = True
                    except (json.JSONDecodeError, OSError):
                        # Data file is corrupted
                        needs_deletion = True

            except (json.JSONDecodeError, OSError, KeyError):
                # Corrupted metadata, treat as non-existent
                needs_deletion = True

        # Handle deletion outside of read lock to avoid deadlock
        if needs_deletion:
            with self._file_lock(key, "delete"):
                self._delete_raw_unlocked(key)
            return False

        return exists

    def get_metadata(self, key: str) -> CacheMetadata | None:
        """Get metadata for cache entry with file locking."""
        with self._file_lock(key, "read"):
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
                    with self._file_lock(key, "delete"):
                        if self._delete_raw_unlocked(key):
                            removed_count += 1
                            self.stats.eviction_count += 1
                else:
                    entries.append((key, metadata))

            # Recalculate current size from actual entries
            current_total_size = sum(metadata.size_bytes for _, metadata in entries)
            self.stats.total_size_bytes = current_total_size

            # Enforce size limits if configured
            if (
                self.config.max_size_bytes
                and current_total_size > self.config.max_size_bytes
            ):
                removed_count += self._enforce_size_limit(entries)

            # Update entry count
            self.stats.total_entries = len(entries)

            # Enforce entry count limits if configured
            if self.config.max_entries and len(entries) > self.config.max_entries:
                removed_count += self._enforce_entry_limit(entries)

            # Recalculate stats after cleanup
            remaining_entries = []
            for metadata_file in self.metadata_dir.glob("*.meta.json"):
                key = metadata_file.stem.replace(".meta", "")
                metadata = self.get_metadata(key)
                if metadata and not metadata.is_expired:
                    remaining_entries.append(metadata)

            self.stats.total_entries = len(remaining_entries)
            self.stats.total_size_bytes = sum(m.size_bytes for m in remaining_entries)

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
            # Sort by access count, then by last accessed time as tie-breaker
            entries.sort(key=lambda x: (x[1].access_count, x[1].last_accessed))
        elif self.config.eviction_policy == "fifo":
            entries.sort(key=lambda x: x[1].created_at)

        # Remove entries until under size limit
        for key, metadata in entries:
            if current_size <= self.config.max_size_bytes:
                break

            with self._file_lock(key, "delete"):
                if self._delete_raw_unlocked(key):
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
            # Sort by access count, then by last accessed time as tie-breaker
            entries.sort(key=lambda x: (x[1].access_count, x[1].last_accessed))
        elif self.config.eviction_policy == "fifo":
            entries.sort(key=lambda x: x[1].created_at)

        # Remove oldest entries
        for key, _metadata in entries[:entries_to_remove]:
            with self._file_lock(key, "delete"):
                if self._delete_raw_unlocked(key):
                    removed_count += 1
                    self.stats.eviction_count += 1

        return removed_count
