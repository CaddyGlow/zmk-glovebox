"""Test persistent cache statistics functionality."""

import tempfile
import time
import typing
from pathlib import Path

import pytest

from glovebox.core.cache import CacheConfig, FilesystemCache


class TestPersistentCacheStats:
    """Test persistent cache statistics across cache instances."""

    @pytest.fixture
    def temp_cache_dir(self) -> typing.Generator[Path, None, None]:
        """Create temporary cache directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_stats_persistence_across_instances(self, temp_cache_dir: Path):
        """Test that cache statistics persist across different cache instances."""
        config = CacheConfig(cache_root=temp_cache_dir)

        # Create first cache instance and perform operations
        cache1 = FilesystemCache(config)

        # Perform some operations to generate stats
        for i in range(10):
            cache1.set(f"key_{i}", f"value_{i}")

        for i in range(8):
            cache1.get(f"key_{i}")  # 8 hits

        cache1.get("nonexistent_key")  # 1 miss
        cache1.get("another_nonexistent")  # 1 miss

        # Force stats save
        cache1.cleanup()

        # Get stats from first instance
        stats1 = cache1.get_stats()
        assert stats1.hit_count == 8
        assert stats1.miss_count == 2
        assert stats1.total_entries >= 10

        # Create second cache instance with same config
        cache2 = FilesystemCache(config)

        # Stats should be loaded from disk
        stats2 = cache2.get_stats()
        assert stats2.hit_count == 8
        assert stats2.miss_count == 2

        # Perform more operations with second instance
        cache2.get("key_0")  # Another hit
        cache2.get("missing_key")  # Another miss

        stats2_updated = cache2.get_stats()
        assert stats2_updated.hit_count == 9
        assert stats2_updated.miss_count == 3

    def test_stats_file_creation(self, temp_cache_dir: Path):
        """Test that stats file is created correctly."""
        config = CacheConfig(cache_root=temp_cache_dir)
        cache = FilesystemCache(config)

        # Perform operations
        cache.set("test_key", "test_value")
        cache.get("test_key")

        # Force stats save
        cache.cleanup()

        # Check that stats file exists
        stats_file = temp_cache_dir / ".cache_stats.json"
        assert stats_file.exists()

        # Check file contents
        import json

        with stats_file.open("r") as f:
            stats_data = json.load(f)

        assert "hit_count" in stats_data
        assert "miss_count" in stats_data
        assert "eviction_count" in stats_data
        assert "error_count" in stats_data
        assert "last_updated" in stats_data
        assert stats_data["hit_count"] >= 1

    def test_stats_disabled_persistence(self, temp_cache_dir: Path):
        """Test that stats are not persisted when statistics are disabled."""
        config = CacheConfig(cache_root=temp_cache_dir, enable_statistics=False)
        cache = FilesystemCache(config)

        # Perform operations
        cache.set("test_key", "test_value")
        cache.get("test_key")
        cache.cleanup()

        # Stats file should not be created
        stats_file = temp_cache_dir / ".cache_stats.json"
        assert not stats_file.exists()

    def test_corrupted_stats_file_handling(self, temp_cache_dir: Path):
        """Test handling of corrupted stats file."""
        config = CacheConfig(cache_root=temp_cache_dir)

        # Create corrupted stats file
        stats_file = temp_cache_dir / ".cache_stats.json"
        stats_file.write_text("invalid json content")

        # Cache should start with default stats despite corrupted file
        cache = FilesystemCache(config)
        stats = cache.get_stats()

        assert stats.hit_count == 0
        assert stats.miss_count == 0
        assert stats.eviction_count == 0
        assert stats.error_count == 0

    def test_periodic_stats_saving(self, temp_cache_dir: Path):
        """Test that stats are saved periodically during operations."""
        config = CacheConfig(cache_root=temp_cache_dir)
        cache = FilesystemCache(config)

        # Perform many operations to trigger periodic save
        for i in range(150):  # More than the 100 operation threshold
            cache.set(f"key_{i}", f"value_{i}")
            if i % 10 == 0:
                cache.get(f"key_{i}")

        # Stats file should exist due to periodic saving
        stats_file = temp_cache_dir / ".cache_stats.json"
        assert stats_file.exists()

    def test_stats_atomic_write(self, temp_cache_dir: Path):
        """Test that stats file is written atomically."""
        config = CacheConfig(cache_root=temp_cache_dir)
        cache = FilesystemCache(config)

        # Perform operations and save stats
        cache.set("test_key", "test_value")
        cache.get("test_key")
        cache._save_persistent_stats()

        # Check that no temporary file remains
        temp_stats_file = temp_cache_dir / ".cache_stats.json.tmp"
        assert not temp_stats_file.exists()

        # Main stats file should exist
        stats_file = temp_cache_dir / ".cache_stats.json"
        assert stats_file.exists()

    def test_stats_preservation_across_cleanup(self, temp_cache_dir: Path):
        """Test that stats are preserved across cache cleanup operations."""
        config = CacheConfig(
            cache_root=temp_cache_dir,
            max_entries=5,  # Force eviction
        )
        cache = FilesystemCache(config)

        # Add more entries than limit
        for i in range(10):
            cache.set(f"key_{i}", f"value_{i}")
            cache.get(f"key_{i}")  # Generate hits

        initial_stats = cache.get_stats()
        initial_hits = initial_stats.hit_count
        initial_evictions = initial_stats.eviction_count

        # Force cleanup which should evict some entries
        cache.cleanup()

        final_stats = cache.get_stats()

        # Hit count should be preserved
        assert final_stats.hit_count == initial_hits

        # Eviction count should have increased
        assert final_stats.eviction_count > initial_evictions

        # Total entries should be within limit
        assert config.max_entries is not None
        assert final_stats.total_entries <= config.max_entries

    def test_cross_process_stats_sharing(self, temp_cache_dir: Path):
        """Test that stats can be shared across processes (simulation)."""
        config = CacheConfig(cache_root=temp_cache_dir)

        # Simulate first process
        cache1 = FilesystemCache(config)
        cache1.set("shared_key", "shared_value")
        cache1.get("shared_key")
        cache1.cleanup()  # Force save

        # Simulate second process reading existing stats
        cache2 = FilesystemCache(config)
        cache2.set("another_key", "another_value")
        cache2.get("another_key")
        cache2.get("shared_key")  # Should be another hit

        final_stats = cache2.get_stats()

        # Should have accumulated stats from both "processes"
        assert final_stats.hit_count >= 3  # At least 3 hits total
