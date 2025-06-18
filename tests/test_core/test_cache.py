"""Comprehensive tests for filesystem cache implementation.

Tests cover file locking, race conditions, concurrent access,
environment variables, and cache cleanup functionality.
"""

import json
import multiprocessing
import os
import tempfile
import time
import typing
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from glovebox.core.cache import (
    CacheConfig,
    CacheMetadata,
    FilesystemCache,
    create_default_cache,
    create_filesystem_cache,
)
from glovebox.core.cache.filesystem_cache import FilesystemCacheError


class TestFilesystemCache:
    """Test filesystem cache functionality."""

    @pytest.fixture
    def temp_cache_dir(self) -> typing.Generator[Path, None, None]:
        """Create temporary cache directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def cache_config(self, temp_cache_dir: Path) -> CacheConfig:
        """Create cache configuration."""
        return CacheConfig(
            cache_root=temp_cache_dir,
            default_ttl_seconds=3600,
            max_size_bytes=1024 * 1024,  # 1MB
            max_entries=100,
        )

    @pytest.fixture
    def filesystem_cache(self, cache_config: CacheConfig) -> FilesystemCache:
        """Create filesystem cache instance."""
        return FilesystemCache(cache_config)

    def test_cache_initialization(self, filesystem_cache: FilesystemCache):
        """Test cache initializes correctly."""
        assert filesystem_cache.cache_root.exists()
        assert filesystem_cache.data_dir.exists()
        assert filesystem_cache.metadata_dir.exists()
        assert filesystem_cache.use_file_locking is True

    def test_cache_initialization_with_config(self, temp_cache_dir: Path):
        """Test cache initialization with explicit configuration."""
        config = CacheConfig(
            cache_root=temp_cache_dir,
            cache_strategy="shared",
            use_file_locking=False,
        )
        cache = FilesystemCache(config)
        assert cache.use_file_locking is False
        assert cache.config.cache_strategy == "shared"

    def test_basic_cache_operations(self, filesystem_cache: FilesystemCache):
        """Test basic get/set/delete operations."""
        key = "test_key"
        value = {"data": "test_value", "number": 42}

        # Test set
        filesystem_cache.set(key, value)
        assert filesystem_cache.exists(key)

        # Test get
        retrieved = filesystem_cache.get(key)
        assert retrieved == value

        # Test delete
        assert filesystem_cache.delete(key) is True
        assert not filesystem_cache.exists(key)
        assert filesystem_cache.get(key) is None

    def test_cache_with_ttl(self, filesystem_cache: FilesystemCache):
        """Test cache expiration with TTL."""
        key = "expiring_key"
        value = "expiring_value"

        # Set with short TTL
        filesystem_cache.set(key, value, ttl=1)
        assert filesystem_cache.exists(key)
        assert filesystem_cache.get(key) == value

        # Wait for expiration
        time.sleep(1.1)

        # Should be expired
        assert not filesystem_cache.exists(key)
        assert filesystem_cache.get(key) is None

    def test_metadata_operations(self, filesystem_cache: FilesystemCache):
        """Test metadata retrieval and updates."""
        key = "metadata_test"
        value = {"test": "data"}

        filesystem_cache.set(key, value)

        # Get metadata
        metadata = filesystem_cache.get_metadata(key)
        assert metadata is not None
        assert metadata.key == key
        assert metadata.access_count >= 1
        assert metadata.size_bytes > 0

        # Access again to update metadata
        filesystem_cache.get(key)
        updated_metadata = filesystem_cache.get_metadata(key)
        assert updated_metadata is not None
        assert updated_metadata.access_count > metadata.access_count

    def test_cache_serialization(self, filesystem_cache: FilesystemCache):
        """Test serialization of different data types."""
        test_cases = [
            ("string", "test_string"),
            ("integer", 42),
            ("float", 3.14),
            ("boolean", True),
            ("none", None),
            ("list", [1, 2, 3, "test"]),
            ("dict", {"nested": {"data": "value"}}),
            ("path", Path("/test/path")),
        ]

        for key, value in test_cases:
            filesystem_cache.set(key, value)
            retrieved = filesystem_cache.get(key)

            if isinstance(value, Path):
                assert retrieved == str(value)
            else:
                assert retrieved == value

    def test_cache_cleanup(self, filesystem_cache: FilesystemCache):
        """Test cache cleanup functionality."""
        # Add some entries
        for i in range(5):
            filesystem_cache.set(f"key_{i}", f"value_{i}")

        # Add expired entry
        filesystem_cache.set("expired_key", "expired_value", ttl=1)
        time.sleep(1.1)

        # Run cleanup
        removed_count = filesystem_cache.cleanup()
        assert removed_count >= 1  # At least the expired entry

        # Expired entry should be gone
        assert not filesystem_cache.exists("expired_key")

    def test_cache_clear(self, filesystem_cache: FilesystemCache):
        """Test cache clear functionality."""
        # Add multiple entries
        for i in range(5):
            filesystem_cache.set(f"key_{i}", f"value_{i}")

        # Clear cache
        filesystem_cache.clear()

        # All entries should be gone
        for i in range(5):
            assert not filesystem_cache.exists(f"key_{i}")

    def test_corrupted_cache_handling(self, filesystem_cache: FilesystemCache):
        """Test handling of corrupted cache files."""
        key = "corrupted_key"

        # Create corrupted data file
        data_path = filesystem_cache._get_data_path(key)
        data_path.write_text("invalid json content")

        # Create valid metadata
        metadata = CacheMetadata(
            key=key,
            size_bytes=100,
            created_at=time.time(),
            last_accessed=time.time(),
            access_count=1,
            ttl_seconds=3600,
        )
        filesystem_cache._save_metadata(key, metadata)

        # Should handle corruption gracefully
        assert filesystem_cache.get(key) is None
        assert not filesystem_cache.exists(key)

    def test_file_locking_enabled(self, filesystem_cache: FilesystemCache):
        """Test file locking context manager."""
        key = "lock_test"

        # Test read lock
        with filesystem_cache._file_lock(key, "read"):
            # Should not raise any exceptions
            pass

        # Test write lock
        with filesystem_cache._file_lock(key, "write"):
            # Should not raise any exceptions
            pass

        # Test delete lock
        with filesystem_cache._file_lock(key, "delete"):
            # Should not raise any exceptions
            pass

    def test_file_locking_disabled(self, temp_cache_dir: Path):
        """Test cache with file locking disabled."""
        config = CacheConfig(
            cache_root=temp_cache_dir,
            use_file_locking=False,
        )
        cache = FilesystemCache(config)

        # File locking should be disabled
        assert cache.use_file_locking is False

        # Operations should still work
        cache.set("test", "value")
        assert cache.get("test") == "value"


class TestConcurrentAccess:
    """Test concurrent access scenarios."""

    @pytest.fixture
    def shared_cache_dir(self) -> typing.Generator[Path, None, None]:
        """Create shared cache directory for concurrent tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_concurrent_read_write(self, shared_cache_dir: Path):
        """Test concurrent read/write operations."""
        config = CacheConfig(cache_root=shared_cache_dir)

        def write_worker(worker_id: int) -> str:
            """Worker function to write to cache."""
            cache = FilesystemCache(config)
            key = f"worker_{worker_id}"
            value = f"data_from_worker_{worker_id}"

            cache.set(key, value)
            return f"Worker {worker_id} wrote {key}"

        def read_worker(worker_id: int) -> str:
            """Worker function to read from cache."""
            cache = FilesystemCache(config)
            # Try to read keys from other workers
            found_keys = []

            for i in range(5):
                key = f"worker_{i}"
                if cache.exists(key):
                    value = cache.get(key)
                    found_keys.append(f"{key}={value}")

            return f"Worker {worker_id} found: {found_keys}"

        # Run concurrent workers
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit write tasks
            write_futures = [executor.submit(write_worker, i) for i in range(5)]

            # Submit read tasks
            read_futures = [executor.submit(read_worker, i) for i in range(5, 10)]

            # Wait for all tasks
            all_futures = write_futures + read_futures
            results = []

            for future in as_completed(all_futures):
                try:
                    result = future.result(timeout=10)
                    results.append(result)
                except Exception as e:
                    pytest.fail(f"Concurrent operation failed: {e}")

        # Verify all workers completed
        assert len(results) == 10

    def test_concurrent_cache_cleanup(self, shared_cache_dir: Path):
        """Test concurrent cache cleanup operations."""
        config = CacheConfig(cache_root=shared_cache_dir)

        def cleanup_worker(worker_id: int) -> int:
            """Worker function to perform cache cleanup."""
            cache = FilesystemCache(config)

            # Add some entries first
            for i in range(5):
                cache.set(f"cleanup_{worker_id}_{i}", f"value_{i}", ttl=1)

            # Wait for expiration
            time.sleep(1.1)

            # Perform cleanup
            return cache.cleanup()

        # Run concurrent cleanup workers
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(cleanup_worker, i) for i in range(5)]

            results = []
            for future in as_completed(futures):
                try:
                    removed_count = future.result(timeout=15)
                    results.append(removed_count)
                except Exception as e:
                    pytest.fail(f"Concurrent cleanup failed: {e}")

        # All workers should complete successfully
        assert len(results) == 5

    def test_process_isolation(self):
        """Test process-isolated cache directories."""
        import subprocess
        import sys

        # Use subprocess instead of multiprocessing to avoid pickling issues
        script = """
import os
from glovebox.core.cache import create_default_cache
cache = create_default_cache()
print(f"{os.getpid()}|{cache.cache_root}")
"""

        results = []
        for _ in range(3):
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                cwd="/home/rick/projects/glovebox",
            )
            if result.returncode == 0:
                pid_str, cache_root = result.stdout.strip().split("|")
                results.append((int(pid_str), cache_root))

        # Each process should have different cache directories
        pids = [result[0] for result in results]
        cache_roots = [result[1] for result in results]

        assert len(set(pids)) == 3  # Different PIDs
        assert len(set(cache_roots)) == 3  # Different cache roots

        # Cache roots should contain process PID
        for pid, cache_root in results:
            assert f"proc_{pid}" in cache_root


class TestCacheStrategies:
    """Test different cache strategies."""

    def test_cache_strategy_process_isolated(self):
        """Test process isolated cache strategy (default)."""
        cache = create_default_cache(cache_strategy="process_isolated")
        assert (
            f"proc_{os.getpid()}" in str(cache.cache_root)
            if hasattr(cache, "cache_root")
            else True
        )

    def test_cache_strategy_shared(self):
        """Test shared cache strategy."""
        cache = create_default_cache(cache_strategy="shared")
        assert (
            f"proc_{os.getpid()}" not in str(cache.cache_root)
            if hasattr(cache, "cache_root")
            else True
        )

    def test_cache_strategy_disabled(self):
        """Test disabled cache strategy."""
        cache = create_default_cache(cache_strategy="disabled")
        # Should return memory cache
        from glovebox.core.cache.memory_cache import MemoryCache

        assert isinstance(cache, MemoryCache)

    def test_file_locking_configuration(self):
        """Test file locking configuration."""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_cache_dir = Path(temp_dir)

            # Test enabled (default)
            config = CacheConfig(cache_root=temp_cache_dir, use_file_locking=True)
            cache = FilesystemCache(config)
            assert cache.use_file_locking is True

            # Test disabled
            config = CacheConfig(
                cache_root=temp_cache_dir / "disabled", use_file_locking=False
            )
            cache = FilesystemCache(config)
            assert cache.use_file_locking is False


class TestCacheErrorHandling:
    """Test error handling scenarios."""

    def test_invalid_cache_root_permissions(self):
        """Test handling of invalid cache root permissions."""
        # Try to create cache in read-only location
        readonly_path = Path("/readonly_location_that_should_not_exist")
        config = CacheConfig(cache_root=readonly_path)

        # Should raise appropriate error when trying to create directories
        with pytest.raises((OSError, PermissionError, FilesystemCacheError)):
            FilesystemCache(config)

    def test_disk_full_simulation(self):
        """Test handling of disk full scenarios."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(cache_root=Path(temp_dir))
            filesystem_cache = FilesystemCache(config)

            # Mock disk full error
            with (
                patch(
                    "pathlib.Path.open", side_effect=OSError("No space left on device")
                ),
                pytest.raises(FilesystemCacheError),
            ):
                filesystem_cache.set("test_key", "test_value")

    def test_corrupted_metadata_handling(self):
        """Test handling of corrupted metadata files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(cache_root=Path(temp_dir))
            filesystem_cache = FilesystemCache(config)

            key = "corrupted_metadata"
            value = "test_value"

            # Set valid entry first
            filesystem_cache.set(key, value)

            # Corrupt metadata file
            metadata_path = filesystem_cache._get_metadata_path(key)
            metadata_path.write_text("invalid json")

            # Should handle gracefully
            assert filesystem_cache.get(key) is None
            assert not filesystem_cache.exists(key)
            assert filesystem_cache.get_metadata(key) is None

    def test_race_condition_handling(self):
        """Test handling of race conditions during file operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(cache_root=Path(temp_dir))
            filesystem_cache = FilesystemCache(config)

            key = "race_condition_test"

            # Mock file deletion during read (simulating race condition)
            original_open = Path.open

            def mock_open(*args, **kwargs):
                # Delete file after first access
                if "race_condition_test" in str(args[0]):
                    result = original_open(*args, **kwargs)
                    # Simulate file being deleted by another process
                    args[0].unlink(missing_ok=True)
                    return result
                return original_open(*args, **kwargs)

            with patch.object(Path, "open", side_effect=mock_open):
                # Should handle race condition gracefully
                result = filesystem_cache.get(key)
                assert result is None


class TestCacheIntegration:
    """Integration tests for cache functionality."""

    def test_cache_factory_functions(self):
        """Test cache factory functions."""
        # Test filesystem cache creation
        fs_cache = create_filesystem_cache(
            max_size_mb=10,
            max_entries=100,
            default_ttl_hours=2,
        )
        assert isinstance(fs_cache, FilesystemCache)
        assert fs_cache.config.max_size_bytes == 10 * 1024 * 1024
        assert fs_cache.config.max_entries == 100
        assert fs_cache.config.default_ttl_seconds == 2 * 3600

        # Test default cache creation
        default_cache = create_default_cache()
        assert default_cache is not None

    def test_cache_statistics(self):
        """Test cache statistics tracking."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(cache_root=Path(temp_dir))
            filesystem_cache = FilesystemCache(config)

            # Add entries
            for i in range(5):
                filesystem_cache.set(f"stats_key_{i}", f"value_{i}")

            # Run cleanup to recalculate stats
            filesystem_cache.cleanup()

            stats = filesystem_cache.get_stats()
            assert stats.total_entries >= 5
            assert stats.total_size_bytes > 0
            assert stats.hit_count >= 0
            assert stats.miss_count >= 0

    def test_end_to_end_cache_workflow(self):
        """Test complete cache workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(cache_root=Path(temp_dir))
            filesystem_cache = FilesystemCache(config)

            # Store complex data
            complex_data = {
                "user": {"name": "test", "id": 123},
                "settings": {"theme": "dark", "notifications": True},
                "history": [1, 2, 3, 4, 5],
            }

            # Cache the data
            cache_key = "user_session_123"
            filesystem_cache.set(cache_key, complex_data, ttl=3600)

            # Verify storage
            assert filesystem_cache.exists(cache_key)

            # Retrieve and verify
            retrieved_data = filesystem_cache.get(cache_key)
            assert retrieved_data == complex_data

            # Check metadata
            metadata = filesystem_cache.get_metadata(cache_key)
            assert metadata is not None
            assert metadata.key == cache_key
            assert metadata.ttl_seconds == 3600

            # Update data
            if isinstance(complex_data, dict) and "settings" in complex_data and isinstance(complex_data["settings"], dict):
                complex_data["settings"]["theme"] = "light"
                filesystem_cache.set(cache_key, complex_data)

                # Verify update
                updated_data = filesystem_cache.get(cache_key)
                assert isinstance(updated_data, dict) and "settings" in updated_data
                assert isinstance(updated_data["settings"], dict)
                assert updated_data["settings"]["theme"] == "light"

            # Clean up
            assert filesystem_cache.delete(cache_key) is True
            assert not filesystem_cache.exists(cache_key)

    def test_cache_persistence_across_instances(self):
        """Test cache persistence across different cache instances."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(cache_root=Path(temp_dir))

            # Create first cache instance and store data
            cache1 = FilesystemCache(config)
            test_data = {"persistent": "data", "number": 42}
            cache1.set("persistent_key", test_data)

            # Create second cache instance with same config
            cache2 = FilesystemCache(config)

            # Should be able to retrieve data from first instance
            retrieved_data = cache2.get("persistent_key")
            assert retrieved_data == test_data

            # Verify metadata is also accessible
            metadata = cache2.get_metadata("persistent_key")
            assert metadata is not None
            assert metadata.key == "persistent_key"
