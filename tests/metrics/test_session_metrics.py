"""Comprehensive tests for SessionMetrics system."""

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from glovebox.metrics.session_metrics import (
    SessionCounter,
    SessionGauge,
    SessionHistogram,
    SessionMetrics,
    SessionMetricsLabeled,
    SessionSummary,
    create_session_metrics,
)


def create_test_session_metrics(session_id: str = "test-session") -> SessionMetrics:
    """Helper to create SessionMetrics for testing with cache."""
    from glovebox.core.cache_v2 import create_default_cache

    cache_manager = create_default_cache(tag="test_metrics")
    return SessionMetrics(cache_manager, session_id)


class TestSessionCounter:
    """Test SessionCounter functionality with prometheus_client compatibility."""

    def test_counter_basic_increment(self):
        """Test basic counter increment without labels."""
        counter = SessionCounter("test_counter", "Test counter")

        # Initial value should be 0
        assert counter._values[()] == 0

        # Increment by 1 (default)
        counter.inc()
        assert counter._values[()] == 1

        # Increment by custom amount
        counter.inc(5)
        assert counter._values[()] == 6

    def test_counter_with_labels(self):
        """Test counter with labels - prometheus_client compatible."""
        counter = SessionCounter("test_counter", "Test counter", ["method", "status"])

        # Test positional label arguments
        labeled_counter = counter.labels("GET", "success")
        assert isinstance(labeled_counter, SessionMetricsLabeled)

        labeled_counter.inc()
        assert counter._values[("GET", "success")] == 1  # Should be incremented to 1
        labeled_counter.inc()
        assert counter._values[("GET", "success")] == 2

        # Test keyword label arguments
        labeled_counter2 = counter.labels(method="POST", status="error")
        labeled_counter2.inc(3)
        assert counter._values[("POST", "error")] == 3

    def test_counter_label_validation(self):
        """Test counter label validation."""
        counter = SessionCounter("test_counter", "Test counter", ["method", "status"])

        # Should raise error for wrong number of positional args
        with pytest.raises(ValueError, match="Expected 2 label values, got 1"):
            counter.labels("GET")

        # Should raise error for missing keyword args
        with pytest.raises(ValueError, match="Missing label values"):
            counter.labels(method="GET")

        # Should raise error for mixing positional and keyword args
        with pytest.raises(
            ValueError, match="Cannot mix positional and keyword arguments"
        ):
            counter.labels("GET", status="success")

    def test_counter_without_labels_requires_no_labels_call(self):
        """Test that counter without labels raises error on labels() call."""
        counter = SessionCounter("test_counter", "Test counter")

        with pytest.raises(ValueError, match="Counter was not declared with labels"):
            counter.labels("some_label")

    def test_counter_with_labels_requires_labels_call(self):
        """Test that counter with labels raises error on direct inc() call."""
        counter = SessionCounter("test_counter", "Test counter", ["method"])

        with pytest.raises(
            ValueError, match="Counter with labels requires labels\\(\\) call"
        ):
            counter.inc()


class TestSessionGauge:
    """Test SessionGauge functionality with prometheus_client compatibility."""

    def test_gauge_basic_operations(self):
        """Test basic gauge operations without labels."""
        gauge = SessionGauge("test_gauge", "Test gauge")

        # Initial value should be 0
        assert gauge._values[()] == 0

        # Test set
        gauge.set(10)
        assert gauge._values[()] == 10

        # Test increment
        gauge.inc()
        assert gauge._values[()] == 11

        gauge.inc(5)
        assert gauge._values[()] == 16

        # Test decrement
        gauge.dec()
        assert gauge._values[()] == 15

        gauge.dec(3)
        assert gauge._values[()] == 12

    def test_gauge_set_to_current_time(self):
        """Test gauge set_to_current_time method."""
        gauge = SessionGauge("test_gauge", "Test gauge")

        with patch("time.time", return_value=1234567890.0):
            gauge.set_to_current_time()
            assert gauge._values[()] == 1234567890.0

    def test_gauge_with_labels(self):
        """Test gauge with labels."""
        gauge = SessionGauge("test_gauge", "Test gauge", ["instance"])

        labeled_gauge = gauge.labels("server1")
        labeled_gauge.set(100)
        assert gauge._values[("server1",)] == 100

        labeled_gauge.inc(50)
        assert gauge._values[("server1",)] == 150

        labeled_gauge.dec(25)
        assert gauge._values[("server1",)] == 125


class TestSessionHistogram:
    """Test SessionHistogram functionality with prometheus_client compatibility."""

    def test_histogram_basic_observe(self):
        """Test basic histogram observe functionality."""
        histogram = SessionHistogram("test_histogram", "Test histogram")

        # Observe some values
        histogram.observe(0.5)
        histogram.observe(1.0)
        histogram.observe(2.5)

        assert len(histogram._observations) == 3
        assert histogram._observations[0]["value"] == 0.5
        assert histogram._observations[1]["value"] == 1.0
        assert histogram._observations[2]["value"] == 2.5

        # Check timestamps are recorded
        for obs in histogram._observations:
            assert "timestamp" in obs
            assert obs["timestamp"] > 0

    def test_histogram_time_context_manager(self):
        """Test histogram time context manager."""
        histogram = SessionHistogram("test_histogram", "Test histogram")

        with (
            patch("time.perf_counter", side_effect=[0.0, 1.5]),
            histogram.time(),
        ):
            pass  # Simulated work

        assert len(histogram._observations) == 1
        assert histogram._observations[0]["value"] == 1.5

    def test_histogram_custom_buckets(self):
        """Test histogram with custom buckets."""
        custom_buckets = [0.1, 0.5, 1.0, 5.0, 10.0, float("inf")]
        histogram = SessionHistogram(
            "test_histogram", "Test histogram", buckets=custom_buckets
        )

        assert histogram.buckets == custom_buckets

    def test_histogram_default_buckets(self):
        """Test histogram with default prometheus buckets."""
        histogram = SessionHistogram("test_histogram", "Test histogram")

        expected_buckets = [
            0.005,
            0.01,
            0.025,
            0.05,
            0.075,
            0.1,
            0.25,
            0.5,
            0.75,
            1.0,
            2.5,
            5.0,
            7.5,
            10.0,
            float("inf"),
        ]
        assert histogram.buckets == expected_buckets


class TestSessionSummary:
    """Test SessionSummary functionality with prometheus_client compatibility."""

    def test_summary_basic_observe(self):
        """Test basic summary observe functionality."""
        summary = SessionSummary("test_summary", "Test summary")

        # Observe some values
        summary.observe(0.1)
        summary.observe(0.2)
        summary.observe(0.3)

        assert len(summary._observations) == 3
        assert summary._observations[0]["value"] == 0.1
        assert summary._observations[1]["value"] == 0.2
        assert summary._observations[2]["value"] == 0.3

    def test_summary_time_context_manager(self):
        """Test summary time context manager."""
        summary = SessionSummary("test_summary", "Test summary")

        with (
            patch("time.perf_counter", side_effect=[0.0, 0.75]),
            summary.time(),
        ):
            pass  # Simulated work

        assert len(summary._observations) == 1
        assert summary._observations[0]["value"] == 0.75


class TestSessionMetrics:
    """Test SessionMetrics main registry class."""

    def test_session_metrics_creation(self, tmp_path):
        """Test SessionMetrics creation and basic functionality."""
        metrics = create_test_session_metrics("test-creation")

        assert metrics.session_uuid == "test-creation"
        assert metrics.session_id.startswith("session_")
        assert len(metrics._counters) == 0
        assert len(metrics._gauges) == 0
        assert len(metrics._histograms) == 0
        assert len(metrics._summaries) == 0

    def test_create_counter(self, tmp_path):
        """Test creating counter through SessionMetrics."""
        metrics = create_test_session_metrics()
        counter = metrics.Counter("test_counter", "Test counter")

        assert isinstance(counter, SessionCounter)
        assert counter.name == "test_counter"
        assert counter.description == "Test counter"
        assert "test_counter" in metrics._counters

        # Requesting same counter should return existing instance
        counter2 = metrics.Counter("test_counter", "Test counter")
        assert counter is counter2

    def test_create_gauge(self, tmp_path):
        """Test creating gauge through SessionMetrics."""
        metrics = create_test_session_metrics()
        gauge = metrics.Gauge("test_gauge", "Test gauge", ["instance"])

        assert isinstance(gauge, SessionGauge)
        assert gauge.name == "test_gauge"
        assert gauge.labelnames == ["instance"]
        assert "test_gauge" in metrics._gauges

    def test_create_histogram(self, tmp_path):
        """Test creating histogram through SessionMetrics."""
        metrics = create_test_session_metrics()
        histogram = metrics.Histogram("test_histogram", "Test histogram")

        assert isinstance(histogram, SessionHistogram)
        assert histogram.name == "test_histogram"
        assert "test_histogram" in metrics._histograms

    def test_create_summary(self, tmp_path):
        """Test creating summary through SessionMetrics."""
        metrics = create_test_session_metrics()
        summary = metrics.Summary("test_summary", "Test summary")

        assert isinstance(summary, SessionSummary)
        assert summary.name == "test_summary"
        assert "test_summary" in metrics._summaries

    def test_activity_logging(self, tmp_path):
        """Test that metrics updates are logged in activity log."""
        metrics = create_test_session_metrics()

        counter = metrics.Counter("test_counter", "Test counter")
        counter.inc(5)

        gauge = metrics.Gauge("test_gauge", "Test gauge")
        gauge.set(10)

        histogram = metrics.Histogram("test_histogram", "Test histogram")
        histogram.observe(1.5)

        # Check activity log has entries
        assert len(metrics._activity_log) >= 3

        # Find the counter update
        counter_update = next(
            (
                log
                for log in metrics._activity_log
                if log["metric_name"] == "test_counter" and log["operation"] == "update"
            ),
            None,
        )
        assert counter_update is not None
        assert counter_update["value"] == 5

        # Find the histogram observation
        histogram_obs = next(
            (
                log
                for log in metrics._activity_log
                if log["metric_name"] == "test_histogram"
                and log["operation"] == "observe"
            ),
            None,
        )
        assert histogram_obs is not None
        assert histogram_obs["value"] == 1.5


class TestSessionMetricsSerialization:
    """Test SessionMetrics JSON serialization functionality."""

    def test_save_metrics_to_cache(self, tmp_path):
        """Test saving metrics to cache."""
        from glovebox.core.cache_v2 import create_default_cache

        cache_manager = create_default_cache(tag="test_metrics")
        session_uuid = "test-save-metrics"
        metrics = SessionMetrics(cache_manager, session_uuid)

        # Create and use various metrics
        counter = metrics.Counter("operations_total", "Total operations", ["type"])
        counter.labels("layout").inc(5)
        counter.labels("firmware").inc(3)

        gauge = metrics.Gauge("active_tasks", "Active tasks")
        gauge.set(10)

        histogram = metrics.Histogram("request_duration", "Request duration")
        histogram.observe(1.5)
        histogram.observe(2.3)

        summary = metrics.Summary("response_size", "Response size")
        summary.observe(1024)

        # Save metrics
        metrics.save()

        # Verify data was cached
        data = cache_manager.get(session_uuid)
        assert data is not None

        # Check session info
        assert "session_info" in data
        assert "session_id" in data["session_info"]
        assert "start_time" in data["session_info"]
        assert "end_time" in data["session_info"]
        assert "duration_seconds" in data["session_info"]

        # Check counters
        assert "operations_total" in data["counters"]
        counter_data = data["counters"]["operations_total"]
        assert counter_data["description"] == "Total operations"
        assert counter_data["labelnames"] == ["type"]
        assert "('layout',)" in counter_data["values"]
        assert counter_data["values"]["('layout',)"] == 5

        # Check gauges
        assert "active_tasks" in data["gauges"]
        assert data["gauges"]["active_tasks"]["values"]["()"] == 10

        # Check histograms
        assert "request_duration" in data["histograms"]
        histogram_data = data["histograms"]["request_duration"]
        assert histogram_data["total_count"] == 2
        assert histogram_data["total_sum"] == 3.8  # 1.5 + 2.3
        assert len(histogram_data["bucket_counts"]) > 0

        # Check summaries
        assert "response_size" in data["summaries"]
        summary_data = data["summaries"]["response_size"]
        assert summary_data["total_count"] == 1
        assert summary_data["total_sum"] == 1024

    def test_serialize_histogram_buckets(self, tmp_path):
        """Test histogram bucket calculation in serialization."""
        metrics = create_test_session_metrics()
        histogram = metrics.Histogram(
            "test_hist", "Test histogram", [0.1, 0.5, 1.0, float("inf")]
        )

        # Add observations
        histogram.observe(0.05)  # Below first bucket
        histogram.observe(0.3)  # In second bucket
        histogram.observe(0.8)  # In third bucket
        histogram.observe(1.5)  # In infinity bucket

        data = metrics._serialize_data()
        hist_data = data["histograms"]["test_hist"]

        # Check bucket counts
        bucket_counts = hist_data["bucket_counts"]
        assert bucket_counts["0.1"] == 1  # 0.05 <= 0.1
        assert bucket_counts["0.5"] == 2  # 0.05, 0.3 <= 0.5
        assert bucket_counts["1.0"] == 3  # 0.05, 0.3, 0.8 <= 1.0
        assert bucket_counts["inf"] == 4  # All values <= inf

    def test_activity_log_truncation(self, tmp_path):
        """Test that activity log is truncated to last 100 entries."""
        metrics = create_test_session_metrics()
        counter = metrics.Counter("test_counter", "Test counter")

        # Generate more than 100 activity log entries
        for _i in range(150):
            counter.inc()

        data = metrics._serialize_data()

        # Should only keep last 100 entries
        assert len(data["activity_log"]) == 100

    def test_observation_truncation(self, tmp_path):
        """Test that histogram/summary observations are truncated to last 50."""
        metrics = create_test_session_metrics()
        histogram = metrics.Histogram("test_hist", "Test histogram")

        # Generate more than 50 observations
        for i in range(75):
            histogram.observe(i * 0.1)

        data = metrics._serialize_data()
        hist_data = data["histograms"]["test_hist"]

        # Should only keep last 50 observations
        assert len(hist_data["observations"]) == 50


class TestFactoryFunction:
    """Test factory function for creating SessionMetrics."""

    def test_create_session_metrics_function(self, tmp_path):
        """Test create_session_metrics factory function."""
        session_uuid = "test-factory-function"
        metrics = create_session_metrics(session_uuid)

        assert isinstance(metrics, SessionMetrics)
        assert metrics.session_uuid == session_uuid

    def test_create_session_metrics_with_cache_manager(self):
        """Test create_session_metrics with explicit cache manager."""
        from glovebox.core.cache_v2 import create_default_cache

        cache_manager = create_default_cache(tag="test_metrics")
        session_uuid = "test-factory-with-cache"
        metrics = create_session_metrics(session_uuid, cache_manager)

        assert isinstance(metrics, SessionMetrics)
        assert metrics.session_uuid == session_uuid
        assert metrics.cache_manager is cache_manager


class TestSessionInfo:
    """Test session information tracking."""

    def test_cli_args_tracking(self, tmp_path):
        """Test CLI arguments tracking functionality."""
        from glovebox.core.cache_v2 import create_default_cache

        cache_manager = create_default_cache(tag="test_metrics")
        session_uuid = "test-session-cli-args"
        metrics = SessionMetrics(cache_manager, session_uuid)

        # Set CLI args like the actual CLI does
        test_args = ["glovebox", "config", "list", "--defaults", "--sources"]
        metrics.set_cli_args(test_args)

        assert metrics.cli_args == test_args

        # Verify it's serialized correctly
        metrics.save()
        cached_data = cache_manager.get(session_uuid)

        assert cached_data["session_info"]["cli_args"] == test_args

    def test_exit_code_tracking(self, tmp_path):
        """Test exit code tracking functionality."""
        from glovebox.core.cache_v2 import create_default_cache

        cache_manager = create_default_cache(tag="test_metrics")
        session_uuid = "test-session-exit-code"
        metrics = SessionMetrics(cache_manager, session_uuid)

        # Set exit code
        metrics.set_exit_code(0)
        assert metrics.exit_code == 0

        # Set error exit code
        metrics.set_exit_code(1)
        assert metrics.exit_code == 1

        # Verify serialization
        metrics.save()
        cached_data = cache_manager.get(session_uuid)

        assert cached_data["session_info"]["exit_code"] == 1
        assert cached_data["session_info"]["success"] is False

    def test_cli_args_copy_protection(self, tmp_path):
        """Test that CLI args are copied to prevent external mutations."""
        from glovebox.core.cache_v2 import create_default_cache

        cache_manager = create_default_cache(tag="test_metrics")
        session_uuid = "test-session-copy-protection"
        metrics = SessionMetrics(cache_manager, session_uuid)

        # Set CLI args
        original_args = ["glovebox", "config", "list"]
        metrics.set_cli_args(original_args)

        # Modify original list
        original_args.append("--modified")

        # Metrics should be unaffected
        assert len(metrics.cli_args) == 3
        assert "--modified" not in metrics.cli_args


class TestPrometheusClientCompatibility:
    """Test compatibility with prometheus_client patterns."""

    def test_prometheus_counter_pattern(self, tmp_path):
        """Test that code using prometheus_client Counter pattern works identically."""
        metrics = create_test_session_metrics()

        # This should work exactly like prometheus_client
        REQUESTS_TOTAL = metrics.Counter(
            "requests_total", "Total requests", ["method", "endpoint"]
        )

        # Increment with labels - prometheus_client style
        REQUESTS_TOTAL.labels("GET", "/api/users").inc()
        REQUESTS_TOTAL.labels(method="POST", endpoint="/api/login").inc(3)

        assert REQUESTS_TOTAL._values[("GET", "/api/users")] == 1
        assert REQUESTS_TOTAL._values[("POST", "/api/login")] == 3

    def test_prometheus_histogram_timing_pattern(self, tmp_path):
        """Test that prometheus_client timing patterns work identically."""
        metrics = create_test_session_metrics()

        # This should work exactly like prometheus_client
        REQUEST_DURATION = metrics.Histogram(
            "request_duration_seconds", "Request duration"
        )

        # Use as context manager - prometheus_client style
        with (
            patch("time.perf_counter", side_effect=[0.0, 1.25]),
            REQUEST_DURATION.time(),
        ):
            pass  # Simulated work

        assert len(REQUEST_DURATION._observations) == 1
        assert REQUEST_DURATION._observations[0]["value"] == 1.25

    def test_prometheus_gauge_pattern(self, tmp_path):
        """Test that prometheus_client Gauge patterns work identically."""
        metrics = create_test_session_metrics()

        # This should work exactly like prometheus_client
        ACTIVE_CONNECTIONS = metrics.Gauge(
            "active_connections", "Active connections", ["server"]
        )

        ACTIVE_CONNECTIONS.labels("server1").set(50)
        ACTIVE_CONNECTIONS.labels("server1").inc(10)
        ACTIVE_CONNECTIONS.labels("server1").dec(5)

        assert ACTIVE_CONNECTIONS._values[("server1",)] == 55

        # Test set_to_current_time
        with patch("time.time", return_value=1234567890.0):
            ACTIVE_CONNECTIONS.labels("server2").set_to_current_time()
            assert ACTIVE_CONNECTIONS._values[("server2",)] == 1234567890.0
