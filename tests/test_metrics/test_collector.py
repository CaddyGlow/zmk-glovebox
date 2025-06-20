"""Tests for metrics collector."""

import time
from datetime import datetime
from unittest.mock import Mock

import pytest

from glovebox.metrics.collector import MetricsCollector
from glovebox.metrics.models import OperationType
from glovebox.metrics.protocols import MetricsServiceProtocol


@pytest.fixture
def mock_metrics_service():
    """Create a mock metrics service for testing."""
    return Mock(spec=MetricsServiceProtocol)


@pytest.fixture
def metrics_collector(mock_metrics_service):
    """Create a MetricsCollector instance for testing."""
    return MetricsCollector(
        operation_type=OperationType.LAYOUT_COMPILATION,
        metrics_service=mock_metrics_service,
        operation_id="test-op-123",
    )


class TestMetricsCollector:
    """Test MetricsCollector functionality."""

    def test_initialization(self, mock_metrics_service):
        """Test collector initialization."""
        collector = MetricsCollector(
            operation_type=OperationType.LAYOUT_COMPILATION,
            metrics_service=mock_metrics_service,
            operation_id="custom-op-id",
        )

        assert collector.operation_type == OperationType.LAYOUT_COMPILATION
        assert collector.metrics_service == mock_metrics_service
        assert collector.operation_id == "custom-op-id"

    def test_initialization_with_auto_generated_id(self, mock_metrics_service):
        """Test collector initialization with auto-generated operation ID."""
        collector = MetricsCollector(
            operation_type=OperationType.FIRMWARE_COMPILATION,
            metrics_service=mock_metrics_service,
        )

        assert collector.operation_type == OperationType.FIRMWARE_COMPILATION
        assert collector.operation_id is not None
        assert len(collector.operation_id) > 0

    def test_context_manager_enter(self, metrics_collector, mock_metrics_service):
        """Test entering the context manager."""
        result = metrics_collector.__enter__()

        assert result is metrics_collector
        # Verify operation start was recorded
        mock_metrics_service.record_operation_start.assert_called_once_with(
            operation_id="test-op-123",
            operation_type=OperationType.LAYOUT_COMPILATION,
            context={},
        )

    def test_context_manager_exit_success(
        self, metrics_collector, mock_metrics_service
    ):
        """Test exiting the context manager successfully."""
        # Enter first
        metrics_collector.__enter__()

        # Exit without exception
        metrics_collector.__exit__(None, None, None)

        # Verify operation end was recorded as success
        mock_metrics_service.record_operation_end.assert_called_once_with(
            operation_id="test-op-123",
            success=True,
            error_message=None,
            error_details=None,
            results={},
        )

    def test_context_manager_exit_with_exception(
        self, metrics_collector, mock_metrics_service
    ):
        """Test exiting the context manager with exception."""
        # Enter first
        metrics_collector.__enter__()

        # Exit with exception
        exc_type = ValueError
        exc_val = ValueError("Test error")
        metrics_collector.__exit__(exc_type, exc_val, None)

        # Verify operation end was recorded as failure
        mock_metrics_service.record_operation_end.assert_called_once_with(
            operation_id="test-op-123",
            success=False,
            error_message="Test error",
            error_details={"exception_type": "ValueError"},
            results={},
        )

    def test_set_context(self, metrics_collector):
        """Test setting operation context."""
        context_data = {
            "keyboard_name": "glove80",
            "layer_count": 5,
            "binding_count": 80,
        }

        metrics_collector.set_context(**context_data)

        assert metrics_collector._context == context_data

    def test_set_context_multiple_calls(self, metrics_collector):
        """Test setting context multiple times merges data."""
        metrics_collector.set_context(keyboard_name="glove80", layer_count=5)
        metrics_collector.set_context(binding_count=80, firmware_version="v25.05")

        expected_context = {
            "keyboard_name": "glove80",
            "layer_count": 5,
            "binding_count": 80,
            "firmware_version": "v25.05",
        }
        assert metrics_collector._context == expected_context

    def test_set_cache_info(self, metrics_collector):
        """Test setting cache information."""
        metrics_collector.set_cache_info(cache_hit=True, cache_key="layout:abc123")

        assert metrics_collector._cache_hit is True
        assert metrics_collector._cache_key == "layout:abc123"

    def test_record_timing(self, metrics_collector):
        """Test recording sub-operation timing."""
        metrics_collector.record_timing("parsing", 0.15)
        metrics_collector.record_timing("validation", 0.05)

        assert metrics_collector._timings["parsing"] == 0.15
        assert metrics_collector._timings["validation"] == 0.05

    def test_time_operation_context_manager(self, metrics_collector):
        """Test the time_operation context manager."""
        with metrics_collector.time_operation("test_operation"):
            time.sleep(0.01)  # Small delay for measurable duration

        # Verify timing was recorded
        assert "test_operation" in metrics_collector._timings
        assert metrics_collector._timings["test_operation"] > 0

    def test_time_operation_with_exception(self, metrics_collector):
        """Test time_operation context manager with exception."""
        with (
            pytest.raises(ValueError),
            metrics_collector.time_operation("failing_operation"),
        ):
            raise ValueError("Test error")

        # Timing should still be recorded even with exception
        assert "failing_operation" in metrics_collector._timings
        assert metrics_collector._timings["failing_operation"] > 0

    def test_full_context_manager_flow(self, metrics_collector, mock_metrics_service):
        """Test complete context manager flow with data collection."""
        context_data = {"keyboard_name": "glove80", "layer_count": 5}

        with metrics_collector as m:
            m.set_context(**context_data)
            m.set_cache_info(cache_hit=False, cache_key="cache:123")
            m.record_timing("parsing", 0.1)

            with m.time_operation("generation"):
                time.sleep(0.001)  # Minimal delay

        # Verify operation start was called
        mock_metrics_service.record_operation_start.assert_called_once()
        start_call = mock_metrics_service.record_operation_start.call_args
        # Context might be empty or contain initial data depending on when set_context was called

        # Verify operation end was called with all collected data
        mock_metrics_service.record_operation_end.assert_called_once()
        end_call = mock_metrics_service.record_operation_end.call_args

        assert end_call[1]["success"] is True
        results = end_call[1]["results"]

        # Check context data was included
        assert results["keyboard_name"] == "glove80"
        assert results["layer_count"] == 5

        # Check cache info was included
        assert results["cache_hit"] is False
        assert results["cache_key"] == "cache:123"

        # Check timing data was included
        assert results["parsing_time_seconds"] == 0.1
        assert "generation_time_seconds" in results
        assert results["generation_time_seconds"] > 0

    def test_error_handling_in_methods(self, mock_metrics_service):
        """Test error handling in collector methods."""
        # Mock service methods to raise exceptions
        mock_metrics_service.record_operation_start.side_effect = Exception(
            "Service error"
        )
        mock_metrics_service.record_operation_end.side_effect = Exception(
            "Service error"
        )

        collector = MetricsCollector(
            operation_type=OperationType.LAYOUT_COMPILATION,
            metrics_service=mock_metrics_service,
        )

        # Should not raise exceptions due to internal error handling
        with collector as m:
            m.set_context(test="data")
            m.set_cache_info(cache_hit=True)
            m.record_timing("test_op", 1.0)

    def test_context_manager_with_no_service(self):
        """Test collector behavior when no metrics service is provided."""
        # This should create a default service
        collector = MetricsCollector(operation_type=OperationType.LAYOUT_COMPILATION)

        assert collector.metrics_service is not None
        assert collector.operation_id is not None

        # Should work without errors
        with collector as m:
            m.set_context(test="data")

    def test_timing_precision(self, metrics_collector):
        """Test that timing measurements have reasonable precision."""
        start_time = time.time()

        with metrics_collector.time_operation("precision_test"):
            time.sleep(0.01)  # 10ms delay

        end_time = time.time()
        actual_duration = end_time - start_time
        recorded_duration = metrics_collector._timings["precision_test"]

        # Recorded duration should be close to actual duration
        assert abs(recorded_duration - actual_duration) < 0.005  # 5ms tolerance

    def test_context_isolation(self, mock_metrics_service):
        """Test that different collector instances have isolated contexts."""
        collector1 = MetricsCollector(
            operation_type=OperationType.LAYOUT_COMPILATION,
            metrics_service=mock_metrics_service,
            operation_id="op-1",
        )

        collector2 = MetricsCollector(
            operation_type=OperationType.FIRMWARE_COMPILATION,
            metrics_service=mock_metrics_service,
            operation_id="op-2",
        )

        collector1.set_context(keyboard="glove80")
        collector2.set_context(strategy="zmk_config")

        assert collector1._context == {"keyboard": "glove80"}
        assert collector2._context == {"strategy": "zmk_config"}

    def test_cache_info_types(self, metrics_collector):
        """Test that cache info accepts correct types."""
        # Test with boolean and string
        metrics_collector.set_cache_info(cache_hit=True, cache_key="test:key")
        assert metrics_collector._cache_hit is True
        assert metrics_collector._cache_key == "test:key"

        # Test with boolean and None
        metrics_collector.set_cache_info(cache_hit=False, cache_key=None)
        assert metrics_collector._cache_hit is False
        assert metrics_collector._cache_key is None  # type: ignore[unreachable]

    def test_timing_multiple_operations(self, metrics_collector):
        """Test recording multiple timed operations."""
        timings = {}

        with metrics_collector.time_operation("op1"):
            time.sleep(0.001)
            timings["op1"] = time.time()

        with metrics_collector.time_operation("op2"):
            time.sleep(0.002)
            timings["op2"] = time.time()

        with metrics_collector.time_operation("op3"):
            time.sleep(0.001)
            timings["op3"] = time.time()

        # All operations should be recorded
        assert len(metrics_collector._timings) == 3
        assert all(duration > 0 for duration in metrics_collector._timings.values())

        # Verify relative timing (op2 should be roughly twice as long as others)
        assert metrics_collector._timings["op2"] > metrics_collector._timings["op1"]
        assert metrics_collector._timings["op2"] > metrics_collector._timings["op3"]
