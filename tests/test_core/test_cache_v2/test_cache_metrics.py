"""Tests for cache metrics integration."""

import time
from unittest.mock import Mock, patch

import pytest

from glovebox.core.cache_v2 import (
    create_default_cache,
    get_aggregated_cache_stats,
    reset_shared_cache_instances,
)
from glovebox.core.cache_v2.diskcache_manager import DiskCacheManager
from glovebox.core.cache_v2.models import CacheStats, DiskCacheConfig
from glovebox.metrics.session_metrics import SessionMetrics, create_session_metrics


class TestCacheMetricsIntegration:
    """Test cache metrics integration with SessionMetrics."""

    def test_cache_with_session_metrics(self, tmp_path, isolated_config):
        """Test that cache operations are tracked in SessionMetrics."""
        # Create a mock session metrics
        mock_session_metrics = Mock()
        mock_counter = Mock()
        mock_histogram = Mock()
        mock_labeled_counter = Mock()
        mock_labeled_histogram = Mock()

        # Setup mock returns
        mock_session_metrics.Counter.return_value = mock_counter
        mock_session_metrics.Histogram.return_value = mock_histogram
        mock_counter.labels.return_value = mock_labeled_counter
        mock_histogram.observe = Mock()

        # Create cache with session metrics
        cache = create_default_cache(tag="test", session_metrics=mock_session_metrics)

        # Perform cache operations
        cache.set("key1", "value1")
        result = cache.get("key1")
        assert result == "value1"

        # Verify metrics were called
        assert mock_session_metrics.Counter.called
        assert mock_session_metrics.Histogram.called

    def test_cache_stats_enhanced_with_metrics(self, tmp_path):
        """Test that CacheStats includes metrics-specific fields."""
        config = DiskCacheConfig(cache_path=tmp_path / "test_cache")
        cache_manager = DiskCacheManager(config, tag="test")

        # Perform some operations to generate stats
        cache_manager.set("key1", "value1")
        cache_manager.get("key1")
        cache_manager.get("nonexistent", "default")

        stats = cache_manager.get_stats()

        # Check enhanced fields
        assert hasattr(stats, "operation_count")
        assert hasattr(stats, "total_operation_time")
        assert hasattr(stats, "tag")
        assert hasattr(stats, "avg_operation_time")

        # Check that metrics are tracked
        assert stats.operation_count > 0
        assert stats.total_operation_time > 0
        assert stats.tag == "test"
        assert stats.hit_count >= 1
        assert stats.miss_count >= 1

    def test_cache_stats_to_metrics_dict(self, tmp_path):
        """Test CacheStats conversion to metrics dictionary."""
        stats = CacheStats(
            total_entries=100,
            total_size_bytes=1024,
            hit_count=80,
            miss_count=20,
            eviction_count=5,
            error_count=2,
            operation_count=102,
            total_operation_time=0.5,
            tag="test",
        )

        metrics_dict = stats.to_metrics_dict()

        expected_keys = {
            "total_entries",
            "total_size_bytes",
            "hit_count",
            "miss_count",
            "eviction_count",
            "error_count",
            "operation_count",
            "total_operation_time",
            "hit_rate",
            "miss_rate",
            "avg_operation_time",
            "tag",
        }

        assert set(metrics_dict.keys()) == expected_keys
        assert metrics_dict["hit_rate"] == 80.0
        assert metrics_dict["miss_rate"] == 20.0
        assert metrics_dict["avg_operation_time"] == pytest.approx(0.0049, rel=1e-2)

    def test_aggregated_cache_stats(self, tmp_path, isolated_config):
        """Test aggregated cache statistics across multiple instances."""
        reset_shared_cache_instances()

        # Create multiple caches with different tags
        cache1 = create_default_cache(tag="compilation")
        cache2 = create_default_cache(tag="metrics")
        cache3 = create_default_cache(tag="layout")

        # Perform operations on each cache
        cache1.set("key1", "value1")
        cache1.get("key1")
        cache1.get("missing", "default")

        cache2.set("key2", "value2")
        cache2.get("key2")

        cache3.set("key3", "value3")
        cache3.get("key3")
        cache3.get("missing2", "default")

        # Get aggregated stats
        aggregated = get_aggregated_cache_stats()

        # Check structure
        assert "total_instances" in aggregated
        assert "total_entries" in aggregated
        assert "total_hit_count" in aggregated
        assert "total_miss_count" in aggregated
        assert "overall_hit_rate" in aggregated
        assert "by_tag" in aggregated

        # Check values
        assert aggregated["total_instances"] == 3
        assert aggregated["total_hit_count"] >= 3  # At least 3 hits
        assert aggregated["total_miss_count"] >= 2  # At least 2 misses
        assert "compilation" in aggregated["by_tag"]
        assert "metrics" in aggregated["by_tag"]
        assert "layout" in aggregated["by_tag"]

    def test_cache_operation_timing(self, tmp_path):
        """Test that cache operations are properly timed."""
        config = DiskCacheConfig(cache_path=tmp_path / "test_cache")
        cache_manager = DiskCacheManager(config, tag="timing_test")

        # Perform operations
        start_time = time.perf_counter()
        cache_manager.set("key1", "value1")
        cache_manager.get("key1")
        end_time = time.perf_counter()

        stats = cache_manager.get_stats()

        # Check that timing was recorded
        assert stats.operation_count == 2
        assert stats.total_operation_time > 0
        assert stats.total_operation_time < (
            end_time - start_time
        )  # Should be less than wall time
        assert stats.avg_operation_time > 0

    def test_cache_error_tracking(self, tmp_path):
        """Test that cache errors are properly tracked in metrics."""
        mock_session_metrics = Mock()
        mock_counter = Mock()
        mock_errors_counter = Mock()
        mock_labeled_counter = Mock()

        # Setup mock returns
        mock_session_metrics.Counter.return_value = mock_counter
        mock_counter.labels.return_value = mock_labeled_counter
        mock_errors_counter.labels.return_value = mock_labeled_counter

        # Create cache with metrics
        config = DiskCacheConfig(cache_path=tmp_path / "test_cache")
        cache_manager = DiskCacheManager(
            config, tag="error_test", session_metrics=mock_session_metrics
        )

        # DiskCache handles closed cache gracefully, so let's simulate a different error
        # by patching the underlying cache to raise an exception
        with patch.object(
            cache_manager._cache, "get", side_effect=Exception("Simulated error")
        ):
            result = cache_manager.get("any_key", "default")
            assert result == "default"

        stats = cache_manager.get_stats()
        assert stats.error_count > 0

    def test_cache_without_metrics(self, tmp_path):
        """Test that cache works normally without SessionMetrics."""
        config = DiskCacheConfig(cache_path=tmp_path / "test_cache")
        cache_manager = DiskCacheManager(config, tag="no_metrics")

        # Perform operations
        cache_manager.set("key1", "value1")
        result = cache_manager.get("key1")
        assert result == "value1"

        stats = cache_manager.get_stats()
        assert stats.operation_count > 0
        assert stats.hit_count == 1
        assert stats.miss_count == 0

    def test_real_session_metrics_integration(self, tmp_path, isolated_config):
        """Test integration with real SessionMetrics instance."""
        # Create real SessionMetrics instance
        session_metrics = create_session_metrics("test_session_123")

        # Create cache with real metrics
        cache = create_default_cache(
            tag="real_metrics", session_metrics=session_metrics
        )

        # Perform operations
        cache.set("key1", "value1")
        cache.get("key1")  # hit
        cache.get("missing", "default")  # miss

        # Check that metrics were created
        assert "cache_operations_total" in session_metrics._counters
        assert "cache_operation_duration_seconds" in session_metrics._histograms
        assert "cache_hit_miss_total" in session_metrics._counters
        assert "cache_errors_total" in session_metrics._counters

        # Save and check data structure
        session_metrics.save()
        data = session_metrics._serialize_data()

        # Verify cache metrics are in the data
        cache_ops = data["counters"]["cache_operations_total"]["values"]
        hit_miss = data["counters"]["cache_hit_miss_total"]["values"]
        duration_hist = data["histograms"]["cache_operation_duration_seconds"]

        assert len(cache_ops) > 0
        assert len(hit_miss) > 0
        assert duration_hist["total_count"] > 0


class TestCacheMetricsModels:
    """Test cache metrics model enhancements."""

    def test_cache_stats_default_values(self):
        """Test CacheStats default values for new fields."""
        stats = CacheStats(
            total_entries=0,
            total_size_bytes=0,
            hit_count=0,
            miss_count=0,
            eviction_count=0,
        )

        assert stats.error_count == 0
        assert stats.operation_count == 0
        assert stats.total_operation_time == 0.0
        assert stats.tag is None

    def test_cache_stats_calculated_properties(self):
        """Test calculated properties of CacheStats."""
        stats = CacheStats(
            total_entries=10,
            total_size_bytes=1024,
            hit_count=8,
            miss_count=2,
            eviction_count=1,
            operation_count=12,
            total_operation_time=0.12,
        )

        assert stats.hit_rate == 80.0
        assert stats.miss_rate == 20.0
        assert stats.avg_operation_time == 0.01

    def test_cache_stats_zero_division_safety(self):
        """Test CacheStats handles zero division safely."""
        stats = CacheStats(
            total_entries=0,
            total_size_bytes=0,
            hit_count=0,
            miss_count=0,
            eviction_count=0,
            operation_count=0,
            total_operation_time=0.0,
        )

        assert stats.hit_rate == 0.0
        assert (
            stats.miss_rate == 100.0
        )  # miss_rate = 100.0 - hit_rate when hit_rate is 0
        assert stats.avg_operation_time == 0.0
