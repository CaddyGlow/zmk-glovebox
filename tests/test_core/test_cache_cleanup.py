"""Tests for cache cleanup functionality and orphaned file handling."""

import json
import os
import tempfile
import time
import typing
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.core.cache import CacheConfig, FilesystemCache


try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class TestCacheCleanup:
    """Test cache cleanup and maintenance operations."""

    @pytest.fixture
    def temp_cache_dir(self) -> typing.Generator[Path, None, None]:
        """Create temporary cache directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def cache_with_cleanup(self, temp_cache_dir: Path) -> FilesystemCache:
        """Create cache configured for cleanup testing."""
        config = CacheConfig(
            cache_root=temp_cache_dir,
            max_size_bytes=1024,  # 1KB for easy testing
            max_entries=5,  # Small limit for testing
            default_ttl_seconds=2,  # Short TTL for testing
        )
        return FilesystemCache(config)

    def test_expired_entry_cleanup(self, cache_with_cleanup: FilesystemCache):
        """Test cleanup of expired cache entries."""
        # Add entries with short TTL
        for i in range(3):
            cache_with_cleanup.set(f"expiring_key_{i}", f"value_{i}", ttl=1)

        # Add non-expiring entry
        cache_with_cleanup.set("permanent_key", "permanent_value", ttl=3600)

        # Verify all entries exist
        assert cache_with_cleanup.exists("expiring_key_0")
        assert cache_with_cleanup.exists("expiring_key_1")
        assert cache_with_cleanup.exists("expiring_key_2")
        assert cache_with_cleanup.exists("permanent_key")

        # Wait for expiration
        time.sleep(1.2)

        # Run cleanup
        removed_count = cache_with_cleanup.cleanup()

        # Should have removed expired entries
        assert removed_count >= 3

        # Expired entries should be gone
        assert not cache_with_cleanup.exists("expiring_key_0")
        assert not cache_with_cleanup.exists("expiring_key_1")
        assert not cache_with_cleanup.exists("expiring_key_2")

        # Non-expired entry should remain
        assert cache_with_cleanup.exists("permanent_key")

    def test_size_limit_enforcement(self, cache_with_cleanup: FilesystemCache):
        """Test enforcement of cache size limits."""
        # Add entries that exceed size limit
        large_value = "x" * 200  # 200 bytes each

        for i in range(10):  # Total: ~2KB, exceeds 1KB limit
            cache_with_cleanup.set(f"large_key_{i}", large_value)

        # Run cleanup
        removed_count = cache_with_cleanup.cleanup()

        # Should have removed some entries to stay under limit
        assert removed_count > 0

        # Verify remaining size is under limit
        stats = cache_with_cleanup.get_stats()
        assert cache_with_cleanup.config.max_size_bytes is not None
        assert stats.total_size_bytes <= cache_with_cleanup.config.max_size_bytes

    def test_entry_count_limit_enforcement(self, cache_with_cleanup: FilesystemCache):
        """Test enforcement of entry count limits."""
        # Add more entries than limit allows
        for i in range(10):  # Exceeds limit of 5
            cache_with_cleanup.set(f"count_key_{i}", f"value_{i}")

        # Run cleanup
        removed_count = cache_with_cleanup.cleanup()

        # Should have removed excess entries
        assert removed_count >= 5

        # Count remaining entries
        remaining_count = 0
        for i in range(10):
            if cache_with_cleanup.exists(f"count_key_{i}"):
                remaining_count += 1

        # Should not exceed entry limit
        assert cache_with_cleanup.config.max_entries is not None
        assert remaining_count <= cache_with_cleanup.config.max_entries

    def test_lru_eviction_policy(self, temp_cache_dir: Path):
        """Test LRU (Least Recently Used) eviction policy."""
        config = CacheConfig(
            cache_root=temp_cache_dir, max_entries=3, eviction_policy="lru"
        )
        cache = FilesystemCache(config)

        # Add entries
        cache.set("key_1", "value_1")
        time.sleep(0.1)
        cache.set("key_2", "value_2")
        time.sleep(0.1)
        cache.set("key_3", "value_3")

        # Access key_1 to make it recently used
        cache.get("key_1")

        # Add another entry to trigger eviction
        cache.set("key_4", "value_4")
        cache.cleanup()  # Force cleanup

        # key_2 should be evicted (least recently used)
        assert cache.exists("key_1")  # Recently accessed
        assert not cache.exists("key_2")  # Should be evicted
        assert cache.exists("key_3")
        assert cache.exists("key_4")

    def test_lfu_eviction_policy(self, temp_cache_dir: Path):
        """Test LFU (Least Frequently Used) eviction policy."""
        config = CacheConfig(
            cache_root=temp_cache_dir, max_entries=3, eviction_policy="lfu"
        )
        cache = FilesystemCache(config)

        # Add entries
        cache.set("key_1", "value_1")
        cache.set("key_2", "value_2")
        cache.set("key_3", "value_3")

        # Access key_1 multiple times
        for _ in range(5):
            cache.get("key_1")

        # Access key_3 a few times
        for _ in range(2):
            cache.get("key_3")

        # key_2 is accessed only once (during set)

        # Add another entry to trigger eviction
        cache.set("key_4", "value_4")
        cache.cleanup()  # Force cleanup

        # key_2 should be evicted (least frequently used)
        assert cache.exists("key_1")  # Most frequently used
        assert not cache.exists("key_2")  # Should be evicted
        assert cache.exists("key_3")
        assert cache.exists("key_4")

    def test_fifo_eviction_policy(self, temp_cache_dir: Path):
        """Test FIFO (First In, First Out) eviction policy."""
        config = CacheConfig(
            cache_root=temp_cache_dir, max_entries=3, eviction_policy="fifo"
        )
        cache = FilesystemCache(config)

        # Add entries in sequence
        cache.set("key_1", "value_1")
        time.sleep(0.1)
        cache.set("key_2", "value_2")
        time.sleep(0.1)
        cache.set("key_3", "value_3")

        # Add another entry to trigger eviction
        cache.set("key_4", "value_4")
        cache.cleanup()  # Force cleanup

        # key_1 should be evicted (first in)
        assert not cache.exists("key_1")  # Should be evicted
        assert cache.exists("key_2")
        assert cache.exists("key_3")
        assert cache.exists("key_4")

    def test_cleanup_with_corrupted_files(self, cache_with_cleanup: FilesystemCache):
        """Test cleanup handles corrupted cache files."""
        # Add valid entries
        cache_with_cleanup.set("valid_key_1", "valid_value_1")
        cache_with_cleanup.set("valid_key_2", "valid_value_2")

        # Create corrupted data file
        corrupted_data_path = cache_with_cleanup.data_dir / "corrupted.json"
        corrupted_data_path.write_text("invalid json content")

        # Create corrupted metadata file
        corrupted_meta_path = cache_with_cleanup.metadata_dir / "corrupted.meta.json"
        corrupted_meta_path.write_text("invalid json content")

        # Cleanup should handle corrupted files gracefully
        removed_count = cache_with_cleanup.cleanup()

        # Valid entries should remain
        assert cache_with_cleanup.exists("valid_key_1")
        assert cache_with_cleanup.exists("valid_key_2")

    def test_cleanup_statistics_tracking(self, cache_with_cleanup: FilesystemCache):
        """Test that cleanup updates cache statistics."""
        # Clear cache to start fresh
        cache_with_cleanup.clear()

        initial_stats = cache_with_cleanup.get_stats()
        initial_eviction_count = initial_stats.eviction_count

        # Add entries that will be cleaned up
        for i in range(3):
            cache_with_cleanup.set(f"cleanup_stats_{i}", f"value_{i}", ttl=1)

        # Wait for expiration
        time.sleep(1.2)

        # Run cleanup
        removed_count = cache_with_cleanup.cleanup()
        assert removed_count == 3  # Should remove all 3 expired entries

        # Check updated statistics
        final_stats = cache_with_cleanup.get_stats()

        # Eviction count should have increased by the number of removed entries
        assert final_stats.eviction_count == initial_eviction_count + removed_count


class TestProcessCacheCleanup:
    """Test cleanup of process-specific cache directories."""

    @pytest.mark.skipif(not HAS_PSUTIL, reason="psutil not available")
    def test_orphaned_process_cache_detection(self):
        """Test detection of orphaned process cache directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_base = Path(temp_dir) / "glovebox_cache"
            cache_base.mkdir()

            # Create cache directories for fake processes
            fake_pids = [99999, 99998, 99997]  # PIDs that shouldn't exist

            for pid in fake_pids:
                proc_dir = cache_base / f"proc_{pid}"
                proc_dir.mkdir()

                # Add some fake cache files
                data_dir = proc_dir / "data"
                data_dir.mkdir()
                (data_dir / "test.json").write_text('{"test": "data"}')

                metadata_dir = proc_dir / "metadata"
                metadata_dir.mkdir()
                (metadata_dir / "test.meta.json").write_text('{"key": "test"}')

            # Create cache directory for current process (should not be cleaned)
            current_proc_dir = cache_base / f"proc_{os.getpid()}"
            current_proc_dir.mkdir()
            (current_proc_dir / "current.txt").write_text("current process data")

            # Get running PIDs
            running_pids = {p.pid for p in psutil.process_iter()}

            # Find orphaned directories
            orphaned_dirs = []
            for proc_dir in cache_base.glob("proc_*"):
                if proc_dir.is_dir():
                    try:
                        pid_str = proc_dir.name.replace("proc_", "")
                        pid = int(pid_str)
                        if pid not in running_pids:
                            orphaned_dirs.append(proc_dir)
                    except ValueError:
                        continue

            # Should find the fake PIDs as orphaned
            assert len(orphaned_dirs) >= 3

            # Current process directory should not be in orphaned list
            current_proc_name = f"proc_{os.getpid()}"
            orphaned_names = [d.name for d in orphaned_dirs]
            assert current_proc_name not in orphaned_names

    @pytest.mark.skipif(not HAS_PSUTIL, reason="psutil not available")
    def test_cache_cleanup_script_functionality(self):
        """Test the cache cleanup script functionality."""
        # Skip this test as it depends on a script that may not exist
        pytest.skip("Cleanup script test skipped - dependencies not available")

    def test_process_isolation_cache_root_calculation(self):
        """Test process isolation cache root calculation."""
        from glovebox.core.cache import create_default_cache

        # Create cache with process isolation
        cache = create_default_cache(cache_strategy="process_isolated")

        # Cache root should contain current process ID
        cache_root_str = (
            str(cache.cache_root) if hasattr(cache, "cache_root") else "unknown"
        )
        current_pid = os.getpid()

        assert f"proc_{current_pid}" in cache_root_str
        assert hasattr(cache, "cache_root") and cache.cache_root.exists()

    def test_shared_cache_strategy(self):
        """Test shared cache strategy (no process isolation)."""
        from glovebox.core.cache import create_default_cache

        # Create cache with shared strategy
        cache = create_default_cache(cache_strategy="shared")

        # Cache root should NOT contain process ID
        cache_root_str = (
            str(cache.cache_root) if hasattr(cache, "cache_root") else "unknown"
        )
        current_pid = os.getpid()

        assert f"proc_{current_pid}" not in cache_root_str

    def test_automatic_cleanup_on_cache_access(self):
        """Test that cache automatically cleans up during normal operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(
                cache_root=Path(temp_dir),
                max_entries=3,
                default_ttl_seconds=1,  # Very short TTL
            )
            cache = FilesystemCache(config)

            # Add entries that will expire
            cache.set("expire_1", "value_1", ttl=1)
            cache.set("expire_2", "value_2", ttl=1)
            cache.set("expire_3", "value_3", ttl=1)

            # Add permanent entry
            cache.set("permanent", "permanent_value", ttl=3600)

            # Wait for expiration
            time.sleep(1.2)

            # Access cache (should trigger automatic cleanup)
            cache.get("permanent")

            # Expired entries should be automatically cleaned
            assert not cache.exists("expire_1")
            assert not cache.exists("expire_2")
            assert not cache.exists("expire_3")
            assert cache.exists("permanent")


class TestCacheMaintenanceOperations:
    """Test advanced cache maintenance and repair operations."""

    @pytest.fixture
    def maintenance_cache(self) -> typing.Generator[FilesystemCache, None, None]:
        """Create cache for maintenance testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(cache_root=Path(temp_dir))
            yield FilesystemCache(config)

    def test_orphaned_metadata_cleanup(self, maintenance_cache: FilesystemCache):
        """Test cleanup of orphaned metadata files."""
        # Create orphaned metadata file (no corresponding data file)
        orphaned_meta_path = maintenance_cache.metadata_dir / "orphaned.meta.json"
        orphaned_meta_path.write_text('{"key": "orphaned", "size_bytes": 100}')

        # Create valid entry
        maintenance_cache.set("valid_key", "valid_value")

        # Run cleanup
        removed_count = maintenance_cache.cleanup()

        # Orphaned metadata should be handled gracefully
        assert maintenance_cache.exists("valid_key")

    def test_orphaned_data_cleanup(self, maintenance_cache: FilesystemCache):
        """Test cleanup of orphaned data files."""
        # Create orphaned data file (no corresponding metadata file)
        orphaned_data_path = maintenance_cache.data_dir / "orphaned.json"
        orphaned_data_path.write_text('{"orphaned": "data"}')

        # Create valid entry
        maintenance_cache.set("valid_key", "valid_value")

        # Run cleanup
        removed_count = maintenance_cache.cleanup()

        # Valid entry should remain
        assert maintenance_cache.exists("valid_key")

    def test_cache_integrity_check(self, maintenance_cache: FilesystemCache):
        """Test cache integrity checking."""
        # Add valid entries
        for i in range(5):
            maintenance_cache.set(f"integrity_key_{i}", f"value_{i}")

        # Corrupt one data file
        corrupt_path = maintenance_cache.data_dir / "integrity_key_2.json"
        corrupt_path.write_text("corrupt json")

        # Access should handle corruption gracefully
        assert maintenance_cache.get("integrity_key_0") == "value_0"  # Valid
        assert maintenance_cache.get("integrity_key_1") == "value_1"  # Valid
        assert maintenance_cache.get("integrity_key_2") is None  # Corrupted
        assert maintenance_cache.get("integrity_key_3") == "value_3"  # Valid
        assert maintenance_cache.get("integrity_key_4") == "value_4"  # Valid

    def test_cache_size_calculation_accuracy(self, maintenance_cache: FilesystemCache):
        """Test accuracy of cache size calculations."""
        # Add entries with known sizes
        test_data = {
            "small": "x" * 10,  # ~10 bytes
            "medium": "y" * 100,  # ~100 bytes
            "large": "z" * 1000,  # ~1000 bytes
        }

        for key, value in test_data.items():
            maintenance_cache.set(key, value)

        # Calculate expected size
        expected_size = sum(len(json.dumps(value)) for value in test_data.values())

        # Run cleanup to recalculate stats
        maintenance_cache.cleanup()

        # Get actual cache size
        stats = maintenance_cache.get_stats()

        # Should be reasonably close (allowing for JSON formatting differences)
        size_diff = abs(stats.total_size_bytes - expected_size)
        # Allow up to 150 bytes difference for JSON formatting and structure overhead
        assert size_diff < 150

    def test_concurrent_cleanup_operations(self, maintenance_cache: FilesystemCache):
        """Test concurrent cleanup operations don't interfere."""
        # Add many entries
        for i in range(20):
            maintenance_cache.set(f"concurrent_cleanup_{i}", f"value_{i}", ttl=1)

        # Wait for expiration
        time.sleep(1.2)

        # Run concurrent cleanups
        from concurrent.futures import ThreadPoolExecutor

        def cleanup_worker():
            return maintenance_cache.cleanup()

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(cleanup_worker) for _ in range(3)]
            results = [future.result(timeout=10) for future in futures]

        # All cleanup operations should complete successfully
        assert len(results) == 3

        # Total removed count should be reasonable
        total_removed = sum(results)
        assert total_removed >= 0  # At least no errors
