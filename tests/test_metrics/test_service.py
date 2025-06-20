"""Tests for metrics service."""

import statistics
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from glovebox.metrics.models import (
    ErrorCategory,
    FirmwareMetrics,
    LayoutMetrics,
    OperationMetrics,
    OperationStatus,
    OperationType,
)
from glovebox.metrics.protocols import MetricsStorageProtocol
from glovebox.metrics.service import MetricsService


@pytest.fixture
def mock_storage():
    """Create a mock storage for testing."""
    return Mock(spec=MetricsStorageProtocol)


@pytest.fixture
def metrics_service(mock_storage):
    """Create a MetricsService instance for testing."""
    return MetricsService(mock_storage)


@pytest.fixture
def sample_operations():
    """Create sample operations for testing."""
    now = datetime.now()
    return [
        LayoutMetrics(
            operation_id="layout-1",
            operation_type=OperationType.LAYOUT_COMPILATION,
            status=OperationStatus.SUCCESS,
            start_time=now - timedelta(minutes=30),
            end_time=now - timedelta(minutes=29, seconds=58),
            duration_seconds=2.0,
            layer_count=5,
            binding_count=80,
        ),
        FirmwareMetrics(
            operation_id="firmware-1",
            operation_type=OperationType.FIRMWARE_COMPILATION,
            status=OperationStatus.SUCCESS,
            start_time=now - timedelta(minutes=20),
            end_time=now - timedelta(minutes=19, seconds=30),
            duration_seconds=30.0,
            compilation_strategy="zmk_config",
            artifacts_generated=2,
        ),
        LayoutMetrics(
            operation_id="layout-2",
            operation_type=OperationType.LAYOUT_COMPILATION,
            status=OperationStatus.FAILURE,
            start_time=now - timedelta(minutes=10),
            end_time=now - timedelta(minutes=9, seconds=59),
            duration_seconds=1.0,
            error_message="Validation failed",
            error_category=ErrorCategory.VALIDATION_ERROR,
        ),
    ]


class TestMetricsService:
    """Test MetricsService functionality."""

    def test_record_operation_start(self, metrics_service, mock_storage):
        """Test recording operation start."""
        operation_id = "test-op-123"
        operation_type = OperationType.LAYOUT_COMPILATION
        context = {"keyboard_name": "glove80", "layer_count": 5}

        metrics_service.record_operation_start(operation_id, operation_type, context)

        # Verify operation is tracked as active
        assert operation_id in metrics_service._active_operations
        active_op = metrics_service._active_operations[operation_id]
        assert active_op.operation_id == operation_id
        assert active_op.operation_type == operation_type

    def test_record_operation_start_with_layout_type(
        self, metrics_service, mock_storage
    ):
        """Test recording layout operation start creates LayoutMetrics."""
        operation_id = "layout-op-123"
        operation_type = OperationType.LAYOUT_COMPILATION

        metrics_service.record_operation_start(operation_id, operation_type)

        active_op = metrics_service._active_operations[operation_id]
        assert isinstance(active_op, LayoutMetrics)
        assert active_op.operation_type == OperationType.LAYOUT_COMPILATION

    def test_record_operation_start_with_firmware_type(
        self, metrics_service, mock_storage
    ):
        """Test recording firmware operation start creates FirmwareMetrics."""
        operation_id = "firmware-op-123"
        operation_type = OperationType.FIRMWARE_COMPILATION

        metrics_service.record_operation_start(operation_id, operation_type)

        active_op = metrics_service._active_operations[operation_id]
        assert isinstance(active_op, FirmwareMetrics)
        assert active_op.operation_type == OperationType.FIRMWARE_COMPILATION

    def test_record_operation_end_success(self, metrics_service, mock_storage):
        """Test recording successful operation end."""
        # Start operation first
        operation_id = "test-op-123"
        metrics_service.record_operation_start(
            operation_id, OperationType.LAYOUT_COMPILATION
        )

        # End operation successfully
        results = {"layer_count": 5, "binding_count": 80}
        metrics_service.record_operation_end(
            operation_id, success=True, results=results
        )

        # Verify storage was called
        mock_storage.store_operation_metrics.assert_called_once()
        stored_metrics = mock_storage.store_operation_metrics.call_args[0][0]
        assert stored_metrics.operation_id == operation_id
        assert stored_metrics.status == OperationStatus.SUCCESS
        assert stored_metrics.end_time is not None

        # Verify operation removed from active list
        assert operation_id not in metrics_service._active_operations

    def test_record_operation_end_failure(self, metrics_service, mock_storage):
        """Test recording failed operation end."""
        # Start operation first
        operation_id = "test-op-123"
        metrics_service.record_operation_start(
            operation_id, OperationType.LAYOUT_COMPILATION
        )

        # End operation with failure
        error_message = "Compilation failed"
        error_details = {"exception_type": "ValidationError"}
        metrics_service.record_operation_end(
            operation_id,
            success=False,
            error_message=error_message,
            error_details=error_details,
        )

        # Verify storage was called with error information
        mock_storage.store_operation_metrics.assert_called_once()
        stored_metrics = mock_storage.store_operation_metrics.call_args[0][0]
        assert stored_metrics.status == OperationStatus.FAILURE
        assert stored_metrics.error_message == error_message
        assert stored_metrics.error_details == error_details
        assert stored_metrics.error_category is not None  # Should be categorized

    def test_record_operation_end_unknown_operation(
        self, metrics_service, mock_storage
    ):
        """Test recording end for unknown operation."""
        # Try to end operation that wasn't started
        operation_id = "unknown-op"
        metrics_service.record_operation_end(operation_id, success=True)

        # Should not call storage
        mock_storage.store_operation_metrics.assert_not_called()

    def test_get_operation_metrics(
        self, metrics_service, mock_storage, sample_operations
    ):
        """Test retrieving operation metrics."""
        mock_storage.get_operation_metrics.return_value = sample_operations

        result = metrics_service.get_operation_metrics(
            operation_type=OperationType.LAYOUT_COMPILATION, limit=10
        )

        assert result == sample_operations
        mock_storage.get_operation_metrics.assert_called_once_with(
            operation_type=OperationType.LAYOUT_COMPILATION,
            start_time=None,
            end_time=None,
            limit=10,
        )

    def test_generate_summary_empty(self, metrics_service, mock_storage):
        """Test generating summary with no metrics."""
        mock_storage.get_operation_metrics.return_value = []

        summary = metrics_service.generate_summary()

        assert summary.total_operations == 0
        assert summary.successful_operations == 0
        assert summary.failed_operations == 0

    def test_generate_summary_with_data(
        self, metrics_service, mock_storage, sample_operations
    ):
        """Test generating summary with sample data."""
        mock_storage.get_operation_metrics.return_value = sample_operations

        summary = metrics_service.generate_summary()

        assert summary.total_operations == 3
        assert summary.successful_operations == 2
        assert summary.failed_operations == 1

        # Test operation-specific success rates
        assert summary.layout_success_rate == 0.5  # 1 success out of 2 layout ops
        assert summary.firmware_success_rate == 1.0  # 1 success out of 1 firmware op

        # Test performance statistics
        expected_durations = [2.0, 30.0, 1.0]
        assert summary.average_duration_seconds == statistics.mean(expected_durations)
        assert summary.median_duration_seconds == statistics.median(expected_durations)
        assert summary.fastest_operation_seconds == min(expected_durations)
        assert summary.slowest_operation_seconds == max(expected_durations)

        # Test error breakdown
        assert summary.error_breakdown[ErrorCategory.VALIDATION_ERROR] == 1
        assert summary.most_common_error == ErrorCategory.VALIDATION_ERROR

    def test_export_metrics(self, metrics_service, mock_storage, sample_operations):
        """Test exporting metrics."""
        mock_storage.get_operation_metrics.return_value = sample_operations

        snapshot = metrics_service.export_metrics()

        assert snapshot.total_operations == 3
        assert len(snapshot.operations) == 3
        assert snapshot.summary is not None
        assert snapshot.summary.total_operations == 3

    def test_export_metrics_to_file(
        self, metrics_service, mock_storage, sample_operations, tmp_path
    ):
        """Test exporting metrics to file."""
        mock_storage.get_operation_metrics.return_value = sample_operations
        output_file = tmp_path / "metrics_export.json"

        snapshot = metrics_service.export_metrics(output_file=output_file)

        assert output_file.exists()
        assert snapshot.total_operations == 3

        # Verify file content is valid JSON
        import json

        with output_file.open() as f:
            data = json.load(f)
        assert data["total_operations"] == 3
        assert len(data["operations"]) == 3

    def test_clear_metrics(self, metrics_service, mock_storage):
        """Test clearing metrics."""
        mock_storage.delete_operation_metrics.return_value = 5

        deleted_count = metrics_service.clear_metrics()

        assert deleted_count == 5
        mock_storage.delete_operation_metrics.assert_called_once_with(before_time=None)

    def test_clear_metrics_by_type(
        self, metrics_service, mock_storage, sample_operations
    ):
        """Test clearing metrics by operation type."""
        # Mock getting operations of specific type
        layout_operations = [
            op
            for op in sample_operations
            if op.operation_type == OperationType.LAYOUT_COMPILATION
        ]
        mock_storage.get_operation_metrics.return_value = layout_operations
        mock_storage.delete_operation_metrics.return_value = 1

        deleted_count = metrics_service.clear_metrics(
            operation_type=OperationType.LAYOUT_COMPILATION
        )

        assert deleted_count == 2  # Should delete each operation individually
        # Verify get_operation_metrics was called to find operations of the type
        mock_storage.get_operation_metrics.assert_called_once_with(
            operation_type=OperationType.LAYOUT_COMPILATION
        )

    def test_clear_metrics_before_time(self, metrics_service, mock_storage):
        """Test clearing metrics before specific time."""
        cutoff_time = datetime.now() - timedelta(days=7)
        mock_storage.delete_operation_metrics.return_value = 3

        deleted_count = metrics_service.clear_metrics(before_time=cutoff_time)

        assert deleted_count == 3
        mock_storage.delete_operation_metrics.assert_called_once_with(
            before_time=cutoff_time
        )

    def test_get_metrics_count(self, metrics_service, mock_storage):
        """Test getting metrics count."""
        mock_storage.get_metrics_count.return_value = 42

        count = metrics_service.get_metrics_count()

        assert count == 42
        mock_storage.get_metrics_count.assert_called_once()

    def test_error_categorization(self, metrics_service):
        """Test error categorization logic."""
        test_cases = [
            ("Validation failed", ErrorCategory.VALIDATION_ERROR),
            ("Invalid schema", ErrorCategory.VALIDATION_ERROR),
            ("Build failed", ErrorCategory.COMPILATION_ERROR),
            ("West compilation error", ErrorCategory.COMPILATION_ERROR),
            ("Docker container failed", ErrorCategory.DOCKER_ERROR),
            ("File not found", ErrorCategory.FILE_ERROR),
            ("Permission denied", ErrorCategory.FILE_ERROR),
            ("Connection timeout", ErrorCategory.NETWORK_ERROR),
            ("HTTP 500 error", ErrorCategory.NETWORK_ERROR),
            ("Operation timed out", ErrorCategory.TIMEOUT_ERROR),
            ("Random error message", ErrorCategory.UNKNOWN_ERROR),
        ]

        for error_message, expected_category in test_cases:
            category = metrics_service._categorize_error(error_message, {})
            assert category == expected_category, f"Failed for: {error_message}"

    def test_error_categorization_none_message(self, metrics_service):
        """Test error categorization with None message."""
        category = metrics_service._categorize_error(None, {})
        assert category == ErrorCategory.UNKNOWN_ERROR

    def test_context_application_in_operation_start(
        self, metrics_service, mock_storage
    ):
        """Test that context is properly applied during operation start."""
        operation_id = "test-op"
        context = {
            "keyboard_name": "glove80",
            "layer_count": 5,
            "binding_count": 80,
            "profile_name": "glove80/v25.05",
        }

        metrics_service.record_operation_start(
            operation_id, OperationType.LAYOUT_COMPILATION, context
        )

        active_op = metrics_service._active_operations[operation_id]
        assert isinstance(active_op, LayoutMetrics)
        assert active_op.keyboard_name == "glove80"
        assert active_op.layer_count == 5
        assert active_op.binding_count == 80
        assert active_op.profile_name == "glove80/v25.05"

    def test_results_application_in_operation_end(self, metrics_service, mock_storage):
        """Test that results are properly applied during operation end."""
        operation_id = "test-op"
        metrics_service.record_operation_start(
            operation_id, OperationType.FIRMWARE_COMPILATION
        )

        results = {
            "artifacts_generated": 2,
            "firmware_size_bytes": 1024000,
            "compilation_strategy": "zmk_config",
        }

        metrics_service.record_operation_end(
            operation_id, success=True, results=results
        )

        # Verify results were applied to the stored metrics
        mock_storage.store_operation_metrics.assert_called_once()
        stored_metrics = mock_storage.store_operation_metrics.call_args[0][0]
        assert isinstance(stored_metrics, FirmwareMetrics)
        assert stored_metrics.artifacts_generated == 2
        assert stored_metrics.firmware_size_bytes == 1024000
        assert stored_metrics.compilation_strategy == "zmk_config"

    def test_error_handling_in_service_methods(self, metrics_service, mock_storage):
        """Test error handling in service methods."""
        # Mock storage to raise exception
        mock_storage.get_operation_metrics.side_effect = Exception("Storage error")
        mock_storage.get_metrics_count.side_effect = Exception("Storage error")
        mock_storage.delete_operation_metrics.side_effect = Exception("Storage error")

        # Should not raise exception, should return empty results
        summary = metrics_service.generate_summary()
        assert summary.total_operations == 0

        # Should not raise exception for other methods either
        count = metrics_service.get_metrics_count()
        assert count == 0  # Error case returns 0

        deleted_count = metrics_service.clear_metrics()
        assert deleted_count == 0  # Error case returns 0
