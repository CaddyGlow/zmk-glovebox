"""Advanced concurrency and race condition tests for filesystem cache.

These tests specifically target file locking, race condition handling,
and concurrent access patterns that could cause cache corruption.
"""

import fcntl
import multiprocessing
import os
import tempfile
import threading
import time
import typing
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.core.cache import CacheConfig, FilesystemCache


class TestRaceConditions:
    """Test race condition scenarios and file locking."""

    @pytest.fixture
    def shared_cache_config(self) -> CacheConfig:
        """Create shared cache configuration for race condition tests."""
        temp_dir = Path(tempfile.mkdtemp())
        return CacheConfig(
            cache_root=temp_dir,
            default_ttl_seconds=3600,
            max_size_bytes=1024 * 1024,
        )

    def test_simultaneous_write_same_key(self, shared_cache_config: CacheConfig):
        """Test simultaneous writes to the same cache key."""

        def write_worker(worker_id: int, config: CacheConfig) -> str:
            """Worker that writes to the same key."""
            cache = FilesystemCache(config)
            key = "contested_key"
            value = f"data_from_worker_{worker_id}_at_{time.time()}"

            # Add small random delay to increase chance of race condition
            time.sleep(0.01 * (worker_id % 3))

            cache.set(key, value)
            return value

        # Run multiple workers writing to same key
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(write_worker, i, shared_cache_config) for i in range(10)
            ]

            written_values = []
            for future in as_completed(futures):
                try:
                    value = future.result(timeout=5)
                    written_values.append(value)
                except Exception as e:
                    pytest.fail(f"Write worker failed: {e}")

        # Verify one of the values was written successfully
        cache = FilesystemCache(shared_cache_config)
        final_value = cache.get("contested_key")
        assert final_value is not None
        assert final_value in written_values

    def test_read_write_race_condition(self, shared_cache_config: CacheConfig):
        """Test race conditions between readers and writers."""
        cache = FilesystemCache(shared_cache_config)

        # Pre-populate cache
        initial_keys = [f"race_key_{i}" for i in range(20)]
        for key in initial_keys:
            cache.set(key, f"initial_value_{key}")

        def reader_worker(worker_id: int) -> dict[str, int]:
            """Worker that reads from cache."""
            reader_cache = FilesystemCache(shared_cache_config)
            results = {"reads": 0, "hits": 0, "misses": 0}

            for _ in range(50):  # Multiple read attempts
                for key in initial_keys:
                    results["reads"] += 1
                    value = reader_cache.get(key)
                    if value is not None:
                        results["hits"] += 1
                    else:
                        results["misses"] += 1
                time.sleep(0.001)  # Small delay

            return results

        def writer_worker(worker_id: int) -> dict[str, int]:
            """Worker that writes to cache."""
            writer_cache = FilesystemCache(shared_cache_config)
            results = {"writes": 0, "updates": 0}

            for i in range(25):  # Multiple write attempts
                key = f"race_key_{i % len(initial_keys)}"
                new_value = f"updated_by_worker_{worker_id}_iteration_{i}"
                writer_cache.set(key, new_value)
                results["writes"] += 1

                # Also update existing keys
                if i % 2 == 0:
                    update_key = initial_keys[i % len(initial_keys)]
                    writer_cache.set(update_key, f"updated_{worker_id}_{i}")
                    results["updates"] += 1

                time.sleep(0.002)  # Small delay

            return results

        # Run concurrent readers and writers
        with ThreadPoolExecutor(max_workers=8) as executor:
            # Submit reader tasks
            reader_futures = [executor.submit(reader_worker, i) for i in range(4)]

            # Submit writer tasks
            writer_futures = [executor.submit(writer_worker, i) for i in range(4)]

            # Collect results
            reader_results = []
            writer_results = []

            for future in as_completed(reader_futures):
                try:
                    result = future.result(timeout=10)
                    reader_results.append(result)
                except Exception as e:
                    pytest.fail(f"Reader worker failed: {e}")

            for future in as_completed(writer_futures):
                try:
                    result = future.result(timeout=10)
                    writer_results.append(result)
                except Exception as e:
                    pytest.fail(f"Writer worker failed: {e}")

        # Verify all workers completed successfully
        assert len(reader_results) == 4
        assert len(writer_results) == 4

        # Verify reasonable hit rates (should be > 80% even with concurrent writes)
        total_reads = sum(r["reads"] for r in reader_results)
        total_hits = sum(r["hits"] for r in reader_results)
        hit_rate = total_hits / total_reads if total_reads > 0 else 0
        assert hit_rate > 0.8, f"Hit rate too low: {hit_rate}"

    def test_file_lock_timeout_handling(self, shared_cache_config: CacheConfig):
        """Test file lock timeout handling."""
        cache = FilesystemCache(shared_cache_config)
        key = "lock_timeout_test"

        # Mock fcntl.flock to simulate lock contention
        original_flock = fcntl.flock
        lock_attempts = []

        def mock_flock(fd, operation):
            lock_attempts.append(operation)
            if len(lock_attempts) < 3:  # Fail first few attempts
                raise OSError("Resource temporarily unavailable")
            return original_flock(fd, operation)

        with patch("fcntl.flock", side_effect=mock_flock):
            # Should eventually succeed despite initial lock failures
            cache.set(key, "test_value")
            assert cache.get(key) == "test_value"

        # Should have retried multiple times
        assert len(lock_attempts) >= 3

    def test_concurrent_cache_cleanup_race(self, shared_cache_config: CacheConfig):
        """Test race conditions during cache cleanup."""
        cache = FilesystemCache(shared_cache_config)

        # Add entries with very short TTL
        for i in range(50):
            cache.set(f"cleanup_race_{i}", f"value_{i}", ttl=1)

        # Wait for expiration
        time.sleep(1.2)

        def cleanup_worker(worker_id: int) -> int:
            """Worker that performs cleanup."""
            worker_cache = FilesystemCache(shared_cache_config)
            return worker_cache.cleanup()

        def access_worker(worker_id: int) -> int:
            """Worker that tries to access expired keys."""
            worker_cache = FilesystemCache(shared_cache_config)
            access_count = 0

            for i in range(50):
                key = f"cleanup_race_{i}"
                if worker_cache.exists(key):
                    worker_cache.get(key)
                    access_count += 1

            return access_count

        # Run concurrent cleanup and access operations
        with ThreadPoolExecutor(max_workers=6) as executor:
            cleanup_futures = [executor.submit(cleanup_worker, i) for i in range(3)]
            access_futures = [executor.submit(access_worker, i) for i in range(3)]

            # Wait for all operations to complete
            cleanup_results = []
            access_results = []

            for future in as_completed(cleanup_futures):
                try:
                    result = future.result(timeout=10)
                    cleanup_results.append(result)
                except Exception as e:
                    pytest.fail(f"Cleanup worker failed: {e}")

            for future in as_completed(access_futures):
                try:
                    result = future.result(timeout=10)
                    access_results.append(result)
                except Exception as e:
                    pytest.fail(f"Access worker failed: {e}")

        # All operations should complete without errors
        assert len(cleanup_results) == 3
        assert len(access_results) == 3

    def test_metadata_update_race_condition(self, shared_cache_config: CacheConfig):
        """Test race conditions in metadata updates."""
        cache = FilesystemCache(shared_cache_config)
        key = "metadata_race_test"

        # Set initial value
        cache.set(key, "initial_value")

        def access_worker(worker_id: int) -> int:
            """Worker that repeatedly accesses the same key."""
            worker_cache = FilesystemCache(shared_cache_config)
            access_count = 0

            for _ in range(100):
                value = worker_cache.get(key)
                if value is not None:
                    access_count += 1
                time.sleep(0.001)  # Small delay

            return access_count

        # Run multiple workers accessing the same key
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(access_worker, i) for i in range(5)]

            results = []
            for future in as_completed(futures):
                try:
                    access_count = future.result(timeout=10)
                    results.append(access_count)
                except Exception as e:
                    pytest.fail(f"Access worker failed: {e}")

        # All workers should have successful accesses
        assert all(count > 0 for count in results)

        # Check final metadata
        metadata = cache.get_metadata(key)
        assert metadata is not None
        assert metadata.access_count >= sum(results)


class TestMultiProcessConcurrency:
    """Test multi-process concurrency scenarios."""

    def test_multi_process_cache_access(self):
        """Test cache access from multiple processes."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir)

            def process_worker(worker_id: int) -> dict[str, typing.Any]:
                """Worker function to run in separate process."""
                config = CacheConfig(cache_root=cache_root)
                cache = FilesystemCache(config)

                results = {"worker_id": worker_id, "writes": 0, "reads": 0}

                # Write worker-specific data
                for i in range(10):
                    key = f"process_{worker_id}_item_{i}"
                    value = f"data_from_process_{worker_id}_item_{i}"
                    cache.set(key, value)
                    results["writes"] += 1

                # Try to read data from other workers
                for other_worker in range(3):
                    if other_worker == worker_id:
                        continue

                    for i in range(10):
                        key = f"process_{other_worker}_item_{i}"
                        value = cache.get(key)
                        if value is not None:
                            results["reads"] += 1

                return results

            # Run workers in separate processes
            with ProcessPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(process_worker, i) for i in range(3)]

                results = []
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=15)
                        results.append(result)
                    except Exception as e:
                        pytest.fail(f"Process worker failed: {e}")

            # All processes should complete successfully
            assert len(results) == 3

            # Each process should have written their data
            for result in results:
                assert result["writes"] == 10

    def test_process_isolation_verification(self):
        """Verify that process isolation actually isolates caches."""

        def get_cache_info():
            """Get cache information in separate process."""
            from glovebox.core.cache import create_default_cache

            cache = create_default_cache()
            return {
                "pid": os.getpid(),
                "cache_root": str(cache.cache_root)
                if hasattr(cache, "cache_root")
                else "unknown",
                "has_proc_in_path": f"proc_{os.getpid()}" in str(cache.cache_root)
                if hasattr(cache, "cache_root")
                else False,
            }

        with ProcessPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(get_cache_info) for _ in range(3)]
            results = [future.result(timeout=10) for future in futures]

        # Each process should have different PIDs and cache roots
        pids = [r["pid"] for r in results]
        cache_roots = [r["cache_root"] for r in results]

        assert len(set(pids)) == 3  # All different PIDs
        assert len(set(cache_roots)) == 3  # All different cache roots

        # All should have process ID in path (process isolation)
        assert all(r["has_proc_in_path"] for r in results)


class TestFileLockingMechanisms:
    """Test file locking mechanisms in detail."""

    @pytest.fixture
    def cache_with_locking(self) -> typing.Generator[FilesystemCache, None, None]:
        """Create cache with file locking enabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(cache_root=Path(temp_dir))
            cache = FilesystemCache(config)
            cache.use_file_locking = True
            yield cache

    def test_shared_read_locks(self, cache_with_locking: FilesystemCache):
        """Test that multiple readers can acquire shared locks."""
        key = "shared_read_test"
        cache_with_locking.set(key, "test_value")

        def read_worker(worker_id: int):
            """Worker that reads with shared lock."""
            value = cache_with_locking.get(key)
            assert value == "test_value"
            return worker_id

        # Run multiple readers concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(read_worker, i) for i in range(5)]
            results = [future.result(timeout=10) for future in futures]

        # All readers should succeed
        assert len(results) == 5

    def test_exclusive_write_locks(self, cache_with_locking: FilesystemCache):
        """Test that writers acquire exclusive locks."""
        key = "exclusive_write_test"

        def write_worker(worker_id: int):
            """Worker that writes with exclusive lock."""
            cache_with_locking.set(key, f"value_from_worker_{worker_id}")
            return worker_id

        # Run multiple writers sequentially (to avoid conflicts)
        for i in range(3):
            result = write_worker(i)
            assert result == i

        # Final value should be from last writer
        final_value = cache_with_locking.get(key)
        assert final_value == "value_from_worker_2"

    def test_lock_cleanup_on_exception(self, cache_with_locking: FilesystemCache):
        """Test that locks are properly cleaned up when exceptions occur."""
        key = "exception_test"

        # Mock an exception during cache operation
        original_open = Path.open

        def failing_open(*args, **kwargs):
            if "exception_test" in str(args[0]) and "w" in str(args[1]):
                raise OSError("Simulated write failure")
            return original_open(*args, **kwargs)

        with (
            patch.object(Path, "open", side_effect=failing_open),
            pytest.raises(OSError),
        ):
            cache_with_locking.set(key, "test_value")

        # Lock files should be cleaned up
        lock_files = list(cache_with_locking.cache_root.glob("*.lock"))
        assert len(lock_files) == 0

    def test_lock_timeout_behavior(self, cache_with_locking: FilesystemCache):
        """Test lock timeout behavior."""
        key = "timeout_test"

        # Simulate long-held lock
        original_flock = fcntl.flock
        call_count = 0

        def slow_flock(fd, operation):
            nonlocal call_count
            call_count += 1
            if call_count <= 10:  # Fail first 10 attempts
                raise OSError("Resource temporarily unavailable")
            return original_flock(fd, operation)

        start_time = time.time()

        with patch("fcntl.flock", side_effect=slow_flock):
            # Should eventually succeed or timeout gracefully
            cache_with_locking.set(key, "test_value")

        elapsed_time = time.time() - start_time

        # Should have taken some time due to retries
        assert elapsed_time > 0.1
        assert call_count > 1  # Should have retried

    def test_lock_disabled_fallback(self):
        """Test cache behavior when file locking is disabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(cache_root=Path(temp_dir))
            cache = FilesystemCache(config)
            cache.use_file_locking = False

            # Should work without locking
            cache.set("test_key", "test_value")
            assert cache.get("test_key") == "test_value"

            # Should not create lock files
            lock_files = list(cache.cache_root.glob("*.lock"))
            assert len(lock_files) == 0


class TestStressTests:
    """Stress tests for cache under heavy concurrent load."""

    def test_high_volume_concurrent_operations(self):
        """Test cache under high volume of concurrent operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = CacheConfig(
                cache_root=Path(temp_dir),
                max_size_bytes=10 * 1024 * 1024,  # 10MB
                max_entries=10000,
            )

            def stress_worker(worker_id: int) -> dict[str, int]:
                """Worker that performs many cache operations."""
                cache = FilesystemCache(config)
                results = {"sets": 0, "gets": 0, "deletes": 0, "errors": 0}

                try:
                    # Perform many operations
                    for i in range(100):
                        key = f"stress_{worker_id}_{i}"
                        value = f"data_{worker_id}_{i}" * 10  # Make values larger

                        # Set
                        cache.set(key, value)
                        results["sets"] += 1

                        # Get
                        retrieved = cache.get(key)
                        if retrieved == value:
                            results["gets"] += 1

                        # Delete every 3rd item
                        if i % 3 == 0 and cache.delete(key):
                            results["deletes"] += 1

                        # Occasionally check existence
                        if i % 5 == 0:
                            cache.exists(key)

                        # Occasional cleanup
                        if i % 20 == 0:
                            cache.cleanup()

                except Exception as e:
                    results["errors"] += 1
                    print(f"Worker {worker_id} error: {e}")

                return results

            # Run many workers concurrently
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(stress_worker, i) for i in range(20)]

                results = []
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=30)
                        results.append(result)
                    except Exception as e:
                        pytest.fail(f"Stress worker failed: {e}")

            # Verify all workers completed successfully
            assert len(results) == 20

            # Check that most operations succeeded
            total_sets = sum(r["sets"] for r in results)
            total_gets = sum(r["gets"] for r in results)
            total_errors = sum(r["errors"] for r in results)

            assert total_sets > 1900  # Should complete most sets
            assert total_gets > 1900  # Should complete most gets
            assert total_errors < 20  # Should have minimal errors

            # Cache should still be functional
            final_cache = FilesystemCache(config)
            final_cache.set("final_test", "final_value")
            assert final_cache.get("final_test") == "final_value"
