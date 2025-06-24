"""Tests for DisabledCache implementation."""

import pytest

from glovebox.core.cache.disabled_cache import DisabledCache


class TestDisabledCache:
    """Test DisabledCache no-op implementation."""

    @pytest.fixture
    def disabled_cache(self):
        """Create a disabled cache instance."""
        return DisabledCache()

    def test_get_always_returns_default(self, disabled_cache):
        """Test that get always returns default value."""
        assert disabled_cache.get("any_key") is None
        assert disabled_cache.get("any_key", "default") == "default"
        assert disabled_cache.get("any_key", 42) == 42

    def test_set_is_noop(self, disabled_cache):
        """Test that set operation is no-op."""
        # Should not raise any errors
        disabled_cache.set("key", "value")
        disabled_cache.set("key", "value", ttl=3600)

        # Value should not be retrievable
        assert disabled_cache.get("key") is None

    def test_delete_always_returns_false(self, disabled_cache):
        """Test that delete always returns False."""
        assert disabled_cache.delete("any_key") is False
        assert disabled_cache.delete("") is False

    def test_clear_is_noop(self, disabled_cache):
        """Test that clear operation is no-op."""
        # Should not raise any errors
        disabled_cache.clear()

    def test_exists_always_returns_false(self, disabled_cache):
        """Test that exists always returns False."""
        assert disabled_cache.exists("any_key") is False
        assert disabled_cache.exists("") is False

    def test_get_metadata_always_returns_none(self, disabled_cache):
        """Test that get_metadata always returns None."""
        assert disabled_cache.get_metadata("any_key") is None
        assert disabled_cache.get_metadata("") is None

    def test_get_stats_returns_empty_stats(self, disabled_cache):
        """Test that get_stats returns empty statistics."""
        stats = disabled_cache.get_stats()

        assert stats.total_entries == 0
        assert stats.total_size_bytes == 0
        assert stats.hit_count == 0
        assert stats.miss_count == 0
        assert stats.eviction_count == 0
        assert stats.error_count == 0
        assert stats.hit_rate == 0.0
        assert stats.miss_rate == 100.0

    def test_cleanup_returns_zero(self, disabled_cache):
        """Test that cleanup returns 0."""
        assert disabled_cache.cleanup() == 0

    def test_close_is_noop(self, disabled_cache):
        """Test that close operation is no-op."""
        # Should not raise any errors
        disabled_cache.close()

    def test_context_manager(self):
        """Test using disabled cache as context manager."""
        with DisabledCache() as cache:
            assert isinstance(cache, DisabledCache)
            cache.set("key", "value")
            assert cache.get("key") is None

    def test_multiple_operations(self, disabled_cache):
        """Test multiple operations in sequence."""
        # Set some values
        disabled_cache.set("key1", "value1")
        disabled_cache.set("key2", "value2", ttl=3600)

        # None should be retrievable
        assert disabled_cache.get("key1") is None
        assert disabled_cache.get("key2") is None

        # Clear and verify still empty
        disabled_cache.clear()
        assert disabled_cache.get_stats().total_entries == 0

        # Cleanup should return 0
        assert disabled_cache.cleanup() == 0

    def test_consistency_across_instances(self):
        """Test that different instances behave consistently."""
        cache1 = DisabledCache()
        cache2 = DisabledCache()

        cache1.set("key", "value")
        assert cache1.get("key") is None
        assert cache2.get("key") is None

        assert cache1.exists("key") is False
        assert cache2.exists("key") is False
