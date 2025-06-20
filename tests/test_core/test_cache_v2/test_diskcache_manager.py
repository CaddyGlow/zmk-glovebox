"""Tests for DiskCacheManager implementation."""

import time
from pathlib import Path
from unittest.mock import Mock

import pytest

from glovebox.core.cache_v2.diskcache_manager import DiskCacheManager
from glovebox.core.cache_v2.models import DiskCacheConfig


@pytest.fixture
def cache_config(tmp_path):
    """Create a test cache configuration."""
    return DiskCacheConfig(
        cache_path=tmp_path / "test_cache",
        max_size_bytes=10 * 1024 * 1024,  # 10MB
        timeout=5,
    )


@pytest.fixture
def cache_manager(cache_config):
    """Create a test cache manager."""
    manager = DiskCacheManager(cache_config)
    yield manager
    manager.close()


class TestDiskCacheManager:
    """Test DiskCacheManager basic functionality."""

    def test_init_creates_cache_directory(self, cache_config):
        """Test that cache directory is created on initialization."""
        assert not cache_config.cache_path.exists()

        with DiskCacheManager(cache_config) as manager:
            assert cache_config.cache_path.exists()
            assert cache_config.cache_path.is_dir()

    def test_set_and_get_basic(self, cache_manager):
        """Test basic set and get operations."""
        cache_manager.set("test_key", "test_value")
        result = cache_manager.get("test_key")
        assert result == "test_value"

    def test_get_with_default(self, cache_manager):
        """Test get with default value for missing key."""
        result = cache_manager.get("missing_key", "default_value")
        assert result == "default_value"

    def test_get_missing_key_no_default(self, cache_manager):
        """Test get with missing key and no default."""
        result = cache_manager.get("missing_key")
        assert result is None

    def test_set_with_ttl(self, cache_manager):
        """Test setting value with TTL."""
        cache_manager.set("ttl_key", "ttl_value", ttl=1)

        # Should be available immediately
        assert cache_manager.get("ttl_key") == "ttl_value"

        # Should expire after TTL
        time.sleep(1.1)
        assert cache_manager.get("ttl_key", "expired") == "expired"

    def test_delete_existing_key(self, cache_manager):
        """Test deleting existing key."""
        cache_manager.set("delete_key", "delete_value")
        assert cache_manager.get("delete_key") == "delete_value"

        result = cache_manager.delete("delete_key")
        assert result is True
        assert cache_manager.get("delete_key") is None

    def test_delete_missing_key(self, cache_manager):
        """Test deleting missing key."""
        result = cache_manager.delete("missing_key")
        assert result is False

    def test_exists_with_existing_key(self, cache_manager):
        """Test exists with existing key."""
        cache_manager.set("exists_key", "exists_value")
        assert cache_manager.exists("exists_key") is True

    def test_exists_with_missing_key(self, cache_manager):
        """Test exists with missing key."""
        assert cache_manager.exists("missing_key") is False

    def test_clear_cache(self, cache_manager):
        """Test clearing all cache entries."""
        cache_manager.set("key1", "value1")
        cache_manager.set("key2", "value2")

        assert cache_manager.get("key1") == "value1"
        assert cache_manager.get("key2") == "value2"

        cache_manager.clear()

        assert cache_manager.get("key1") is None
        assert cache_manager.get("key2") is None

    def test_get_stats(self, cache_manager):
        """Test getting cache statistics."""
        initial_stats = cache_manager.get_stats()

        # Initial stats
        assert initial_stats.hit_count >= 0
        assert initial_stats.miss_count >= 0
        assert initial_stats.total_entries >= 0

        # Record initial hit/miss counts
        initial_hits = initial_stats.hit_count
        initial_misses = initial_stats.miss_count

        # Add some data and verify stats update
        cache_manager.set("stats_key", "stats_value")
        cache_manager.get("stats_key")  # Hit
        cache_manager.get("missing_key")  # Miss

        updated_stats = cache_manager.get_stats()
        assert updated_stats.hit_count == initial_hits + 1
        assert updated_stats.miss_count == initial_misses + 1

    def test_get_metadata(self, cache_manager):
        """Test getting cache entry metadata."""
        cache_manager.set("meta_key", "meta_value")
        metadata = cache_manager.get_metadata("meta_key")

        assert metadata is not None
        assert metadata.key == "meta_key"
        assert metadata.size_bytes > 0
        assert metadata.created_at > 0
        assert metadata.access_count >= 0

    def test_get_metadata_missing_key(self, cache_manager):
        """Test getting metadata for missing key."""
        metadata = cache_manager.get_metadata("missing_key")
        assert metadata is None

    def test_cleanup(self, cache_manager):
        """Test cache cleanup operation."""
        cache_manager.set("cleanup_key", "cleanup_value")
        evicted = cache_manager.cleanup()
        assert evicted >= 0  # DiskCache may or may not evict anything

    def test_context_manager(self, cache_config):
        """Test using cache manager as context manager."""
        with DiskCacheManager(cache_config) as manager:
            manager.set("context_key", "context_value")
            assert manager.get("context_key") == "context_value"

        # Cache should still be accessible after context manager
        with DiskCacheManager(cache_config) as manager:
            assert manager.get("context_key") == "context_value"

    def test_error_handling(self, cache_manager, monkeypatch):
        """Test error handling in cache operations."""
        # Mock the internal cache to raise exceptions
        mock_cache = Mock()
        mock_cache.get.side_effect = Exception("Test error")
        mock_cache.set.side_effect = Exception("Test error")
        mock_cache.delete.side_effect = Exception("Test error")

        # Mock __contains__ method properly
        mock_cache.__contains__ = Mock(side_effect=Exception("Test error"))

        monkeypatch.setattr(cache_manager, "_cache", mock_cache)

        # Get should return default on error
        assert cache_manager.get("error_key", "default") == "default"

        # Set should raise exception
        with pytest.raises(OSError):
            cache_manager.set("error_key", "error_value")

        # Delete should return False on error
        assert cache_manager.delete("error_key") is False

        # Exists should return False on error
        assert cache_manager.exists("error_key") is False

        # Stats should track errors
        stats = cache_manager.get_stats()
        assert stats.error_count > 0


class TestDiskCacheConfiguration:
    """Test DiskCache configuration handling."""

    def test_config_path_creation(self, tmp_path):
        """Test that cache path is created correctly."""
        cache_path = tmp_path / "custom_cache"
        config = DiskCacheConfig(cache_path=cache_path)

        with DiskCacheManager(config):
            assert cache_path.exists()
            assert cache_path.is_dir()

    def test_config_defaults(self, tmp_path):
        """Test default configuration values."""
        config = DiskCacheConfig(cache_path=tmp_path / "default_test")

        assert config.max_size_bytes == 2 * 1024 * 1024 * 1024  # 2GB
        assert config.timeout == 30
        assert config.eviction_policy == "least-recently-stored"

    def test_config_custom_values(self, tmp_path):
        """Test custom configuration values."""
        config = DiskCacheConfig(
            cache_path=tmp_path / "custom_test",
            max_size_bytes=100 * 1024 * 1024,  # 100MB
            timeout=60,
        )

        assert config.max_size_bytes == 100 * 1024 * 1024
        assert config.timeout == 60

    def test_config_path_string_conversion(self, tmp_path):
        """Test that string paths are converted to Path objects."""
        config = DiskCacheConfig(cache_path=str(tmp_path / "string_path"))
        assert isinstance(config.cache_path, Path)
