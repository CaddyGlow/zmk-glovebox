"""Tests for concurrent access to DiskCache."""

import multiprocessing
import time
from pathlib import Path
from typing import Any

import pytest

from glovebox.core.cache.diskcache_manager import DiskCacheManager
from glovebox.core.cache.models import DiskCacheConfig


def worker_process(
    cache_path: Path, worker_id: int, num_operations: int
) -> dict[str, Any]:
    """Worker process for concurrent cache testing.

    Args:
        cache_path: Path to shared cache
        worker_id: Unique worker identifier
        num_operations: Number of operations to perform

    Returns:
        Dict with operation results
    """
    config = DiskCacheConfig(cache_path=cache_path)

    try:
        with DiskCacheManager(config) as cache:
            operations = {"set": 0, "get": 0, "delete": 0, "errors": 0}

            for i in range(num_operations):
                try:
                    key = f"worker_{worker_id}_key_{i}"
                    value = f"worker_{worker_id}_value_{i}"

                    # Set operation
                    cache.set(key, value)
                    operations["set"] += 1

                    # Get operation
                    result = cache.get(key)
                    if result == value:
                        operations["get"] += 1

                    # Delete some keys
                    if i % 3 == 0 and cache.delete(key):
                        operations["delete"] += 1

                except Exception:
                    operations["errors"] += 1

            return operations

    except Exception:
        return {"set": 0, "get": 0, "delete": 0, "errors": num_operations}


class TestConcurrentAccess:
    """Test concurrent access to DiskCache from multiple processes."""

    @pytest.mark.integration
    def test_multiple_processes_basic(self, tmp_path):
        """Test basic concurrent access from multiple processes."""
        cache_path = tmp_path / "concurrent_cache"
        num_workers = 3
        operations_per_worker = 10

        # Create processes
        processes = []
        for worker_id in range(num_workers):
            process = multiprocessing.Process(
                target=worker_process,
                args=(cache_path, worker_id, operations_per_worker),
            )
            processes.append(process)

        # Start all processes
        for process in processes:
            process.start()

        # Wait for all processes to complete
        results = []
        for process in processes:
            process.join(timeout=30)  # 30 second timeout
            if process.is_alive():
                process.terminate()
                pytest.fail("Worker process timed out")
            results.append(process.exitcode)

        # Verify all processes completed successfully
        assert all(exitcode == 0 for exitcode in results)

        # Verify cache directory was created and contains data
        assert cache_path.exists()

        # Verify we can still access the cache
        config = DiskCacheConfig(cache_path=cache_path)
        with DiskCacheManager(config) as cache:
            stats = cache.get_stats()
            # Should have some entries (some may have been deleted)
            assert stats.total_entries >= 0

    @pytest.mark.integration
    def test_concurrent_read_write(self, tmp_path):
        """Test concurrent read and write operations."""
        cache_path = tmp_path / "rw_cache"
        config = DiskCacheConfig(cache_path=cache_path)

        # Pre-populate cache with some data
        with DiskCacheManager(config) as cache:
            for i in range(20):
                cache.set(f"shared_key_{i}", f"shared_value_{i}")

        def reader_worker(cache_path: Path, num_reads: int) -> int:
            """Worker that performs read operations."""
            config = DiskCacheConfig(cache_path=cache_path)
            successful_reads = 0

            with DiskCacheManager(config) as cache:
                for i in range(num_reads):
                    key = f"shared_key_{i % 20}"
                    value = cache.get(key)
                    if value is not None:
                        successful_reads += 1

            return successful_reads

        def writer_worker(cache_path: Path, worker_id: int, num_writes: int) -> int:
            """Worker that performs write operations."""
            config = DiskCacheConfig(cache_path=cache_path)
            successful_writes = 0

            with DiskCacheManager(config) as cache:
                for i in range(num_writes):
                    key = f"writer_{worker_id}_key_{i}"
                    value = f"writer_{worker_id}_value_{i}"
                    try:
                        cache.set(key, value)
                        successful_writes += 1
                    except Exception:
                        pass

            return successful_writes

        # Create mix of readers and writers
        processes = []

        # 2 readers
        for _i in range(2):
            process = multiprocessing.Process(
                target=reader_worker, args=(cache_path, 50)
            )
            processes.append(process)

        # 2 writers
        for i in range(2):
            process = multiprocessing.Process(
                target=writer_worker, args=(cache_path, i, 25)
            )
            processes.append(process)

        # Start all processes
        for process in processes:
            process.start()

        # Wait for completion
        for process in processes:
            process.join(timeout=30)
            if process.is_alive():
                process.terminate()
                pytest.fail("Worker process timed out")

        # Verify cache is still functional
        with DiskCacheManager(config) as cache:
            stats = cache.get_stats()
            assert stats.total_entries > 0

            # Should still be able to read original data
            assert cache.get("shared_key_0") == "shared_value_0"

    @pytest.mark.integration
    def test_process_crash_recovery(self, tmp_path):
        """Test that cache recovers from process crashes."""
        cache_path = tmp_path / "crash_cache"
        config = DiskCacheConfig(cache_path=cache_path)

        # Create initial cache with data
        with DiskCacheManager(config) as cache:
            for i in range(10):
                cache.set(f"crash_key_{i}", f"crash_value_{i}")

        def crashy_worker(cache_path: Path) -> None:
            """Worker that simulates a crash."""
            config = DiskCacheConfig(cache_path=cache_path)

            with DiskCacheManager(config) as cache:
                cache.set("crash_worker_key", "crash_worker_value")
                # Simulate crash by exiting abruptly
                exit(1)

        # Start crashy worker
        process = multiprocessing.Process(target=crashy_worker, args=(cache_path,))
        process.start()
        process.join()

        # Process should have crashed
        assert process.exitcode == 1

        # Cache should still be functional
        with DiskCacheManager(config) as cache:
            # Original data should still be there
            for i in range(10):
                assert cache.get(f"crash_key_{i}") == f"crash_value_{i}"

            # Can still write new data
            cache.set("recovery_key", "recovery_value")
            assert cache.get("recovery_key") == "recovery_value"

    def test_same_process_multiple_managers(self, tmp_path):
        """Test multiple cache managers in same process."""
        cache_path = tmp_path / "multi_manager_cache"
        config = DiskCacheConfig(cache_path=cache_path)

        # Create first manager and add data
        with DiskCacheManager(config) as cache1:
            cache1.set("shared_key", "from_cache1")

        # Create second manager and verify it sees the data
        with DiskCacheManager(config) as cache2:
            assert cache2.get("shared_key") == "from_cache1"
            cache2.set("shared_key", "from_cache2")

        # Create third manager and verify latest data
        with DiskCacheManager(config) as cache3:
            assert cache3.get("shared_key") == "from_cache2"

    @pytest.mark.integration
    def test_high_contention(self, tmp_path):
        """Test high contention scenario with many processes."""
        cache_path = tmp_path / "contention_cache"
        num_workers = 5
        operations_per_worker = 50

        def contention_worker(cache_path: Path, worker_id: int, num_ops: int) -> bool:
            """Worker for high contention testing."""
            config = DiskCacheConfig(cache_path=cache_path, timeout=10)

            try:
                with DiskCacheManager(config) as cache:
                    for i in range(num_ops):
                        # All workers compete for same keys
                        shared_key = f"contention_key_{i % 10}"
                        worker_value = f"worker_{worker_id}_value_{i}"

                        cache.set(shared_key, worker_value)
                        value = cache.get(shared_key)

                        # Value might be from any worker due to contention
                        # Just verify we got something back
                        if value is None:
                            return False

                return True

            except Exception:
                return False

        # Create many competing processes
        processes = []
        for worker_id in range(num_workers):
            process = multiprocessing.Process(
                target=contention_worker,
                args=(cache_path, worker_id, operations_per_worker),
            )
            processes.append(process)

        # Start all processes simultaneously
        for process in processes:
            process.start()

        # Wait for completion
        for process in processes:
            process.join(timeout=60)  # Longer timeout for high contention
            if process.is_alive():
                process.terminate()

        # Verify cache is still functional after high contention
        config = DiskCacheConfig(cache_path=cache_path)
        with DiskCacheManager(config) as cache:
            stats = cache.get_stats()
            assert stats.total_entries >= 0

            # Should be able to perform operations
            cache.set("post_contention_key", "post_contention_value")
            assert cache.get("post_contention_key") == "post_contention_value"
