"""Tests for metrics storage."""

from datetime import datetime, timedelta
from unittest.mock import ANY, Mock

import pytest

from glovebox.core.cache_v2.cache_manager import CacheManager
from glovebox.metrics.models import (
    ErrorCategory,
    FirmwareMetrics,
    LayoutMetrics,
    OperationMetrics,
    OperationStatus,
    OperationType,
)
from glovebox.metrics.storage import MetricsStorage


@pytest.fixture
def mock_cache():
    """Create a mock cache manager for testing."""
    cache = Mock(spec=CacheManager)
    # Set up default cache behavior
    cache.get.return_value = None
    cache.set.return_value = True
    cache.delete.return_value = True
    return cache


@pytest.fixture
def metrics_storage(mock_cache):
    """Create a MetricsStorage instance for testing."""
    return MetricsStorage(mock_cache)


@pytest.fixture
def sample_operation_metrics():
    """Create sample operation metrics for testing."""
    return OperationMetrics(
        operation_id="test-op-123",
        operation_type=OperationType.LAYOUT_COMPILATION,
        status=OperationStatus.SUCCESS,
        start_time=datetime.now(),
        end_time=datetime.now() + timedelta(seconds=2),
        profile_name="glove80/v25.05",
        keyboard_name="glove80",
        firmware_version="v25.05",
    )


@pytest.fixture
def sample_layout_metrics():
    """Create sample layout metrics for testing."""
    return LayoutMetrics(
        operation_id="layout-op-456",
        start_time=datetime.now(),
        end_time=datetime.now() + timedelta(seconds=1.5),
        status=OperationStatus.SUCCESS,
        layer_count=5,
        binding_count=80,
        behavior_count=12,
    )


@pytest.fixture
def sample_firmware_metrics():
    """Create sample firmware metrics for testing."""
    return FirmwareMetrics(
        operation_id="firmware-op-789",
        start_time=datetime.now(),
        end_time=datetime.now() + timedelta(seconds=30),
        status=OperationStatus.SUCCESS,
        compilation_strategy="zmk_config",
        board_targets=["glove80_lh", "glove80_rh"],
        artifacts_generated=2,
        firmware_size_bytes=1024000,
    )


class TestMetricsStorage:
    """Test MetricsStorage functionality."""

    def test_store_operation_metrics(
        self, metrics_storage, mock_cache, sample_operation_metrics
    ):
        """Test storing operation metrics."""
        metrics_storage.store_operation_metrics(sample_operation_metrics)

        # Verify cache.set was called with correct key and data
        expected_key = "metrics:operations:test-op-123"
        mock_cache.set.assert_any_call(
            expected_key, sample_operation_metrics.to_dict(), ttl=30 * 24 * 60 * 60
        )

        # Verify index update was called
        index_key = "metrics:operations:index"
        mock_cache.set.assert_any_call(index_key, ANY, ttl=30 * 24 * 60 * 60)

    def test_get_operation_metrics_by_id(
        self, metrics_storage, mock_cache, sample_operation_metrics
    ):
        """Test retrieving specific operation by ID."""
        # Mock cache response
        mock_cache.get.return_value = sample_operation_metrics.to_dict()

        result = metrics_storage.get_operation_metrics(operation_id="test-op-123")

        assert len(result) == 1
        assert result[0].operation_id == "test-op-123"
        assert result[0].operation_type == OperationType.LAYOUT_COMPILATION

    def test_get_operation_metrics_all(self, metrics_storage, mock_cache):
        """Test retrieving all operations."""
        # Mock operations index
        operations_index = {
            "op-1": {
                "operation_type": "layout_compilation",
                "start_time": datetime.now().isoformat(),
                "status": "success",
                "profile_name": "glove80/v25.05",
                "keyboard_name": "glove80",
            },
            "op-2": {
                "operation_type": "firmware_compilation",
                "start_time": datetime.now().isoformat(),
                "status": "failure",
                "profile_name": "glove80/v25.05",
                "keyboard_name": "glove80",
            },
        }

        # Mock individual operation data
        op1_data = {
            "operation_id": "op-1",
            "operation_type": "layout_compilation",
            "status": "success",
            "start_time": datetime.now().isoformat(),
            "end_time": (datetime.now() + timedelta(seconds=1)).isoformat(),
        }

        op2_data = {
            "operation_id": "op-2",
            "operation_type": "firmware_compilation",
            "status": "failure",
            "start_time": datetime.now().isoformat(),
            "end_time": (datetime.now() + timedelta(seconds=5)).isoformat(),
        }

        def cache_get_side_effect(key, default=None):
            cache_data = {
                "metrics:operations:index": operations_index,
                "metrics:operations:op-1": op1_data,
                "metrics:operations:op-2": op2_data,
            }
            return cache_data.get(key, default)

        mock_cache.get.side_effect = cache_get_side_effect

        result = metrics_storage.get_operation_metrics()

        assert len(result) == 2
        # Verify correct deserialization based on operation type
        layout_op = next((op for op in result if op.operation_id == "op-1"), None)
        firmware_op = next((op for op in result if op.operation_id == "op-2"), None)

        assert layout_op is not None
        assert isinstance(layout_op, LayoutMetrics)
        assert layout_op.operation_type == OperationType.LAYOUT_COMPILATION

        assert firmware_op is not None
        assert isinstance(firmware_op, FirmwareMetrics)
        assert firmware_op.operation_type == OperationType.FIRMWARE_COMPILATION

    def test_get_operation_metrics_with_filters(self, metrics_storage, mock_cache):
        """Test retrieving operations with filters."""
        start_time = datetime.now() - timedelta(hours=1)
        end_time = datetime.now()

        # Mock operations index with varied timestamps
        operations_index = {
            "old-op": {
                "operation_type": "layout_compilation",
                "start_time": (datetime.now() - timedelta(days=2)).isoformat(),
                "status": "success",
                "profile_name": "glove80/v25.05",
                "keyboard_name": "glove80",
            },
            "recent-op": {
                "operation_type": "layout_compilation",
                "start_time": (datetime.now() - timedelta(minutes=30)).isoformat(),
                "status": "success",
                "profile_name": "glove80/v25.05",
                "keyboard_name": "glove80",
            },
            "firmware-op": {
                "operation_type": "firmware_compilation",
                "start_time": (datetime.now() - timedelta(minutes=15)).isoformat(),
                "status": "success",
                "profile_name": "glove80/v25.05",
                "keyboard_name": "glove80",
            },
        }

        recent_op_data = {
            "operation_id": "recent-op",
            "operation_type": "layout_compilation",
            "status": "success",
            "start_time": (datetime.now() - timedelta(minutes=30)).isoformat(),
            "end_time": (datetime.now() - timedelta(minutes=29)).isoformat(),
        }

        def cache_get_side_effect(key, default=None):
            if key == "metrics:operations:index":
                return operations_index
            elif key == "metrics:operations:recent-op":
                return recent_op_data
            return default

        mock_cache.get.side_effect = cache_get_side_effect

        # Test filtering by operation type and time range
        result = metrics_storage.get_operation_metrics(
            operation_type=OperationType.LAYOUT_COMPILATION,
            start_time=start_time,
            end_time=end_time,
        )

        assert len(result) == 1
        assert result[0].operation_id == "recent-op"

    def test_get_operation_metrics_with_limit(self, metrics_storage, mock_cache):
        """Test retrieving operations with limit."""
        # Mock multiple operations
        operations_index = {}
        operation_data = {}

        for i in range(5):
            op_id = f"op-{i}"
            start_time = datetime.now() - timedelta(minutes=i)
            operations_index[op_id] = {
                "operation_type": "layout_compilation",
                "start_time": start_time.isoformat(),
                "status": "success",
                "profile_name": "glove80/v25.05",
                "keyboard_name": "glove80",
            }
            operation_data[f"metrics:operations:{op_id}"] = {
                "operation_id": op_id,
                "operation_type": "layout_compilation",
                "status": "success",
                "start_time": start_time.isoformat(),
                "end_time": (start_time + timedelta(seconds=1)).isoformat(),
            }

        def cache_get_side_effect(key, default=None):
            if key == "metrics:operations:index":
                return operations_index
            return operation_data.get(key, default)

        mock_cache.get.side_effect = cache_get_side_effect

        result = metrics_storage.get_operation_metrics(limit=3)

        assert len(result) == 3
        # Should be sorted by start time (most recent first)
        assert result[0].operation_id == "op-0"  # Most recent

    def test_delete_operation_metrics_by_id(self, metrics_storage, mock_cache):
        """Test deleting specific operation by ID."""
        mock_cache.delete.return_value = True

        deleted_count = metrics_storage.delete_operation_metrics(
            operation_id="test-op-123"
        )

        assert deleted_count == 1
        expected_key = "metrics:operations:test-op-123"
        mock_cache.delete.assert_called_with(expected_key)

    def test_delete_operation_metrics_before_time(self, metrics_storage, mock_cache):
        """Test deleting operations before specified time."""
        cutoff_time = datetime.now() - timedelta(days=1)

        # Mock operations index
        operations_index = {
            "old-op": {
                "operation_type": "layout_compilation",
                "start_time": (datetime.now() - timedelta(days=2)).isoformat(),
                "status": "success",
                "profile_name": "glove80/v25.05",
                "keyboard_name": "glove80",
            },
            "recent-op": {
                "operation_type": "layout_compilation",
                "start_time": datetime.now().isoformat(),
                "status": "success",
                "profile_name": "glove80/v25.05",
                "keyboard_name": "glove80",
            },
        }

        mock_cache.get.return_value = operations_index
        mock_cache.delete.return_value = True

        deleted_count = metrics_storage.delete_operation_metrics(
            before_time=cutoff_time
        )

        assert deleted_count == 1
        mock_cache.delete.assert_any_call("metrics:operations:old-op")

    def test_get_metrics_count(self, metrics_storage, mock_cache):
        """Test getting total metrics count."""
        operations_index: dict[str, dict[str, str]] = {
            "op-1": {},
            "op-2": {},
            "op-3": {},
        }
        mock_cache.get.return_value = operations_index

        count = metrics_storage.get_metrics_count()

        assert count == 3

    def test_clear_all_metrics(self, metrics_storage, mock_cache):
        """Test clearing all metrics."""
        operations_index: dict[str, dict[str, str]] = {"op-1": {}, "op-2": {}}
        mock_cache.get.return_value = operations_index
        mock_cache.delete.return_value = True

        deleted_count = metrics_storage.clear_all_metrics()

        assert deleted_count == 2
        # Verify all operations and index are deleted
        mock_cache.delete.assert_any_call("metrics:operations:op-1")
        mock_cache.delete.assert_any_call("metrics:operations:op-2")
        mock_cache.delete.assert_any_call("metrics:operations:index")

    def test_duration_computation_during_deserialization(
        self, metrics_storage, mock_cache
    ):
        """Test that duration is computed during deserialization when missing."""
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=3.5)

        # Mock operation data without duration_seconds
        operation_data = {
            "operation_id": "test-op",
            "operation_type": "layout_compilation",
            "status": "success",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": None,  # Missing duration
        }

        mock_cache.get.return_value = operation_data

        result = metrics_storage.get_operation_metrics(operation_id="test-op")

        assert len(result) == 1
        # Duration should be computed during deserialization
        assert result[0].duration_seconds == 3.5

    def test_error_handling_in_get_operations(self, metrics_storage, mock_cache):
        """Test error handling during operation retrieval."""
        # Mock operations index
        operations_index = {
            "valid-op": {
                "operation_type": "layout_compilation",
                "start_time": datetime.now().isoformat(),
                "status": "success",
                "profile_name": "glove80/v25.05",
                "keyboard_name": "glove80",
            },
            "invalid-op": {
                "operation_type": "layout_compilation",
                "start_time": datetime.now().isoformat(),
                "status": "success",
                "profile_name": "glove80/v25.05",
                "keyboard_name": "glove80",
            },
        }

        valid_data = {
            "operation_id": "valid-op",
            "operation_type": "layout_compilation",
            "status": "success",
            "start_time": datetime.now().isoformat(),
        }

        def cache_get_side_effect(key, default=None):
            cache_data = {
                "metrics:operations:index": operations_index,
                "metrics:operations:valid-op": valid_data,
                "metrics:operations:invalid-op": {
                    "invalid": "data"
                },  # Invalid data that will cause validation error
            }
            return cache_data.get(key, default)

        mock_cache.get.side_effect = cache_get_side_effect

        result = metrics_storage.get_operation_metrics()

        # Should only return valid operations, invalid ones should be skipped
        assert len(result) == 1
        assert result[0].operation_id == "valid-op"


class TestDeserializationHelper:
    """Test the _deserialize_operation_metrics helper method."""

    def test_deserialize_layout_metrics(self, metrics_storage):
        """Test deserializing layout metrics."""
        data = {
            "operation_id": "layout-op",
            "operation_type": "layout_compilation",
            "status": "success",
            "start_time": datetime.now().isoformat(),
            "layer_count": 5,
            "binding_count": 80,
        }

        result = metrics_storage._deserialize_operation_metrics(data)

        assert isinstance(result, LayoutMetrics)
        assert result.operation_id == "layout-op"
        assert result.layer_count == 5
        assert result.binding_count == 80

    def test_deserialize_firmware_metrics(self, metrics_storage):
        """Test deserializing firmware metrics."""
        data = {
            "operation_id": "firmware-op",
            "operation_type": "firmware_compilation",
            "status": "success",
            "start_time": datetime.now().isoformat(),
            "compilation_strategy": "zmk_config",
            "artifacts_generated": 2,
        }

        result = metrics_storage._deserialize_operation_metrics(data)

        assert isinstance(result, FirmwareMetrics)
        assert result.operation_id == "firmware-op"
        assert result.compilation_strategy == "zmk_config"
        assert result.artifacts_generated == 2

    def test_deserialize_unknown_type_fallback(self, metrics_storage):
        """Test deserializing unknown operation type falls back to base model."""
        data = {
            "operation_id": "unknown-op",
            "operation_type": "layout_validation",  # Use a valid enum value
            "status": "success",
            "start_time": datetime.now().isoformat(),
        }

        result = metrics_storage._deserialize_operation_metrics(data)

        assert isinstance(result, OperationMetrics)
        assert not isinstance(result, LayoutMetrics | FirmwareMetrics)
        assert result.operation_id == "unknown-op"
