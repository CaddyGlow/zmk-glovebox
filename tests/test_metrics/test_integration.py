"""Integration tests for the metrics system."""

import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from glovebox.core.cache_v2 import create_default_cache
from glovebox.metrics import (
    create_metrics_collector,
    create_metrics_service,
    create_metrics_storage,
)
from glovebox.metrics.models import OperationStatus, OperationType
from glovebox.metrics.service import MetricsService
from glovebox.metrics.storage import MetricsStorage


@pytest.fixture
def test_cache():
    """Create a test cache instance."""
    return create_default_cache(tag="test_metrics")


@pytest.fixture
def metrics_storage_with_cache(test_cache):
    """Create a metrics storage with test cache."""
    return MetricsStorage(test_cache)


@pytest.fixture
def metrics_service_with_storage(metrics_storage_with_cache):
    """Create a metrics service with test storage."""
    return MetricsService(metrics_storage_with_cache)


class TestMetricsSystemIntegration:
    """Test the complete metrics system integration."""

    def test_end_to_end_metrics_collection(self, metrics_service_with_storage):
        """Test complete metrics collection flow."""
        service = metrics_service_with_storage

        # Create a collector and use it to track an operation
        collector = create_metrics_collector(
            operation_type=OperationType.LAYOUT_COMPILATION,
            operation_id="integration-test-op",
        )
        collector.metrics_service = service  # Use our test service

        with collector as m:
            m.set_context(
                keyboard_name="glove80",
                firmware_version="v25.05",
                layer_count=5,
                binding_count=80,
            )
            m.set_cache_info(cache_hit=False, cache_key="layout:test123")

            with m.time_operation("parsing"):
                time.sleep(0.001)  # Simulate parsing time

            with m.time_operation("generation"):
                time.sleep(0.002)  # Simulate generation time

        # Verify the operation was stored
        stored_operations = service.get_operation_metrics(limit=1)
        assert len(stored_operations) == 1

        operation = stored_operations[0]
        assert operation.operation_id == "integration-test-op"
        assert operation.operation_type == OperationType.LAYOUT_COMPILATION
        assert operation.status == OperationStatus.SUCCESS
        assert operation.keyboard_name == "glove80"
        assert operation.firmware_version == "v25.05"
        assert operation.cache_hit is False
        assert operation.cache_key == "layout:test123"

        # Verify duration was calculated
        assert operation.duration_seconds is not None
        assert operation.duration_seconds > 0

    def test_metrics_summary_generation(self, metrics_service_with_storage):
        """Test generating summary from stored metrics."""
        service = metrics_service_with_storage

        # Create multiple operations with different outcomes
        operations_data = [
            (OperationType.LAYOUT_COMPILATION, OperationStatus.SUCCESS, 1.0),
            (OperationType.LAYOUT_COMPILATION, OperationStatus.FAILURE, 0.5),
            (OperationType.FIRMWARE_COMPILATION, OperationStatus.SUCCESS, 30.0),
            (OperationType.FIRMWARE_COMPILATION, OperationStatus.SUCCESS, 25.0),
        ]

        for op_type, status, _duration in operations_data:
            collector = create_metrics_collector(operation_type=op_type)
            collector.metrics_service = service

            if status == OperationStatus.FAILURE:
                with pytest.raises(ValueError), collector:
                    time.sleep(0.001)  # Minimal delay
                    raise ValueError("Test failure")
            else:
                with collector:
                    time.sleep(0.001)  # Minimal delay

        # Generate summary
        summary = service.generate_summary()

        # Due to shared cache, we may have operations from other tests
        # Just verify that we have some operations and the success rates make sense
        assert summary.total_operations >= 4
        assert summary.successful_operations >= 3
        assert summary.failed_operations >= 1
        # Check that success rates are reasonable (between 0 and 1)
        if summary.layout_success_rate is not None:
            assert 0 <= summary.layout_success_rate <= 1
        if summary.firmware_success_rate is not None:
            assert 0 <= summary.firmware_success_rate <= 1

    def test_metrics_export_and_import_cycle(
        self, metrics_service_with_storage, tmp_path
    ):
        """Test exporting metrics and verifying the exported data."""
        service = metrics_service_with_storage

        # Create some test operations
        for i in range(3):
            collector = create_metrics_collector(
                operation_type=OperationType.LAYOUT_COMPILATION,
                operation_id=f"export-test-{i}",
            )
            collector.metrics_service = service

            with collector as m:
                m.set_context(keyboard_name="glove80", test_run=i)
                time.sleep(0.001)

        # Export metrics
        export_file = tmp_path / "metrics_export.json"
        snapshot = service.export_metrics(output_file=export_file)

        # Verify export file was created and has correct content
        assert export_file.exists()
        assert snapshot.total_operations >= 3  # May have operations from other tests
        assert len(snapshot.operations) >= 3

        # Verify file content is valid JSON
        import json

        with export_file.open() as f:
            exported_data = json.load(f)

        assert exported_data["total_operations"] >= 3
        assert len(exported_data["operations"]) >= 3
        # At least our test operations should be present
        test_ops = [
            op
            for op in exported_data["operations"]
            if op["operation_id"].startswith("export-test-")
        ]
        assert len(test_ops) == 3
        assert all(op["operation_type"] == "layout_compilation" for op in test_ops)

    def test_metrics_cleanup_and_filtering(self, metrics_service_with_storage):
        """Test metrics cleanup and filtering functionality."""
        service = metrics_service_with_storage

        # Create operations with different types and times
        layout_collector = create_metrics_collector(
            operation_type=OperationType.LAYOUT_COMPILATION,
            operation_id="cleanup-layout",
        )
        layout_collector.metrics_service = service

        firmware_collector = create_metrics_collector(
            operation_type=OperationType.FIRMWARE_COMPILATION,
            operation_id="cleanup-firmware",
        )
        firmware_collector.metrics_service = service

        # Execute operations
        with layout_collector:
            time.sleep(0.001)

        with firmware_collector:
            time.sleep(0.001)

        # Verify both operations are stored
        all_operations = service.get_operation_metrics()
        assert len(all_operations) >= 2

        # Test filtering by operation type
        layout_operations = service.get_operation_metrics(
            operation_type=OperationType.LAYOUT_COMPILATION
        )
        firmware_operations = service.get_operation_metrics(
            operation_type=OperationType.FIRMWARE_COMPILATION
        )

        assert any(op.operation_id == "cleanup-layout" for op in layout_operations)
        assert any(op.operation_id == "cleanup-firmware" for op in firmware_operations)

        # Test clearing specific operation type
        deleted_count = service.clear_metrics(
            operation_type=OperationType.LAYOUT_COMPILATION
        )
        assert deleted_count > 0

        # Verify only layout operations were cleared
        remaining_operations = service.get_operation_metrics()
        assert not any(
            op.operation_type == OperationType.LAYOUT_COMPILATION
            for op in remaining_operations
        )

    def test_metrics_persistence_across_service_instances(self, test_cache):
        """Test that metrics persist across different service instances."""
        # Create first service instance and store metrics
        storage1 = MetricsStorage(test_cache)
        service1 = MetricsService(storage1)

        collector = create_metrics_collector(
            operation_type=OperationType.LAYOUT_COMPILATION,
            operation_id="persistence-test",
        )
        collector.metrics_service = service1

        with collector as m:
            m.set_context(test_key="test_value")
            time.sleep(0.001)

        # Create second service instance and verify metrics are accessible
        storage2 = MetricsStorage(test_cache)
        service2 = MetricsService(storage2)

        operations = service2.get_operation_metrics()
        assert len(operations) >= 1

        # Find our test operation
        test_op = next(
            (op for op in operations if op.operation_id == "persistence-test"), None
        )
        assert test_op is not None
        assert test_op.operation_type == OperationType.LAYOUT_COMPILATION

    def test_concurrent_metrics_collection(self, metrics_service_with_storage):
        """Test concurrent metrics collection doesn't interfere."""
        service = metrics_service_with_storage

        # Start multiple collectors simultaneously
        collectors = []
        for i in range(3):
            collector = create_metrics_collector(
                operation_type=OperationType.LAYOUT_COMPILATION,
                operation_id=f"concurrent-{i}",
            )
            collector.metrics_service = service
            collectors.append(collector)

        # Use collectors in nested contexts
        with collectors[0] as c0:
            c0.set_context(collector_id=0)
            with collectors[1] as c1:
                c1.set_context(collector_id=1)
                with collectors[2] as c2:
                    c2.set_context(collector_id=2)
                    time.sleep(0.001)

        # Verify all operations were stored correctly
        operations = service.get_operation_metrics(limit=10)
        concurrent_ops = [
            op for op in operations if op.operation_id.startswith("concurrent-")
        ]

        assert len(concurrent_ops) == 3
        # Verify each operation has correct data
        for i in range(3):
            op = next(
                op for op in concurrent_ops if op.operation_id == f"concurrent-{i}"
            )
            assert op.status == OperationStatus.SUCCESS

    def test_error_handling_in_integration(self, metrics_service_with_storage):
        """Test error handling in integrated metrics flow."""
        service = metrics_service_with_storage

        # Test successful operation
        success_collector = create_metrics_collector(
            operation_type=OperationType.LAYOUT_COMPILATION,
            operation_id="error-test-success",
        )
        success_collector.metrics_service = service

        with success_collector:
            time.sleep(0.001)

        # Test operation with exception
        error_collector = create_metrics_collector(
            operation_type=OperationType.LAYOUT_COMPILATION,
            operation_id="error-test-failure",
        )
        error_collector.metrics_service = service

        with pytest.raises(ValueError), error_collector:
            time.sleep(0.001)
            raise ValueError("Test error")

        # Verify both operations were recorded
        operations = service.get_operation_metrics(limit=10)
        test_ops = [
            op for op in operations if op.operation_id.startswith("error-test-")
        ]

        assert len(test_ops) == 2

        success_op = next(
            op for op in test_ops if op.operation_id == "error-test-success"
        )
        error_op = next(
            op for op in test_ops if op.operation_id == "error-test-failure"
        )

        assert success_op.status == OperationStatus.SUCCESS
        assert error_op.status == OperationStatus.FAILURE
        assert error_op.error_message == "Test error"

    def test_factory_functions_integration(self):
        """Test that factory functions create properly integrated components."""
        # Test factory functions create compatible components
        service = create_metrics_service()
        storage = create_metrics_storage()
        collector = create_metrics_collector(OperationType.LAYOUT_COMPILATION)

        # Verify types are correct
        assert service is not None
        assert storage is not None
        assert collector is not None

        # Verify collector has a metrics service
        assert collector.metrics_service is not None
        assert collector.operation_type == OperationType.LAYOUT_COMPILATION
        assert collector.operation_id is not None

    def test_performance_with_large_dataset(self, metrics_service_with_storage):
        """Test metrics system performance with larger dataset."""
        service = metrics_service_with_storage

        # Create a moderate number of operations to test performance
        num_operations = 50

        start_time = time.time()

        for i in range(num_operations):
            collector = create_metrics_collector(
                operation_type=OperationType.LAYOUT_COMPILATION,
                operation_id=f"perf-test-{i}",
            )
            collector.metrics_service = service

            with collector as m:
                m.set_context(iteration=i)
                # No sleep here to test actual performance

        collection_time = time.time() - start_time

        # Verify all operations were stored
        operations = service.get_operation_metrics(limit=num_operations + 10)
        perf_ops = [op for op in operations if op.operation_id.startswith("perf-test-")]
        assert len(perf_ops) == num_operations

        # Test summary generation performance
        summary_start = time.time()
        summary = service.generate_summary()
        summary_time = time.time() - summary_start

        assert summary.total_operations >= num_operations

        # Performance assertions (reasonable thresholds)
        assert collection_time < 5.0  # Should collect 50 operations in under 5 seconds
        assert summary_time < 1.0  # Summary generation should be under 1 second

        print(
            f"Collection time for {num_operations} operations: {collection_time:.3f}s"
        )
        print(f"Summary generation time: {summary_time:.3f}s")
