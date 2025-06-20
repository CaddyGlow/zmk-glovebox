"""Tests for metrics models."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from glovebox.metrics.models import (
    ErrorCategory,
    FirmwareMetrics,
    FlashMetrics,
    LayoutMetrics,
    MetricsSnapshot,
    MetricsSummary,
    OperationMetrics,
    OperationStatus,
    OperationType,
)


class TestOperationMetrics:
    """Test the base OperationMetrics model."""

    def test_basic_creation(self):
        """Test basic metrics creation."""
        start_time = datetime.now()
        metrics = OperationMetrics(
            operation_id="test-123",
            operation_type=OperationType.LAYOUT_COMPILATION,
            status=OperationStatus.SUCCESS,
            start_time=start_time,
        )

        assert metrics.operation_id == "test-123"
        assert metrics.operation_type == OperationType.LAYOUT_COMPILATION
        assert metrics.status == OperationStatus.SUCCESS
        assert metrics.start_time == start_time
        assert metrics.end_time is None
        assert metrics.duration_seconds is None

    def test_duration_computation(self):
        """Test automatic duration computation from start/end times."""
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=5.5)

        metrics = OperationMetrics(
            operation_id="test-123",
            operation_type=OperationType.LAYOUT_COMPILATION,
            status=OperationStatus.SUCCESS,
            start_time=start_time,
            end_time=end_time,
        )

        assert metrics.duration_seconds is not None
        assert (
            abs(metrics.duration_seconds - 5.5) < 0.1
        )  # Allow small floating point differences

    def test_explicit_duration_preserved(self):
        """Test that explicitly set duration is preserved."""
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=5.5)

        metrics = OperationMetrics(
            operation_id="test-123",
            operation_type=OperationType.LAYOUT_COMPILATION,
            status=OperationStatus.SUCCESS,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=10.0,  # Explicitly set different value
        )

        assert metrics.duration_seconds == 10.0  # Explicit value preserved

    def test_serialization(self):
        """Test model serialization and deserialization."""
        start_time = datetime.now()
        metrics = OperationMetrics(
            operation_id="test-123",
            operation_type=OperationType.LAYOUT_COMPILATION,
            status=OperationStatus.SUCCESS,
            start_time=start_time,
            profile_name="glove80/v25.05",
            keyboard_name="glove80",
            firmware_version="v25.05",
        )

        # Test to_dict
        data = metrics.to_dict()
        assert data["operation_id"] == "test-123"
        assert data["operation_type"] == "layout_compilation"
        assert data["status"] == "success"

        # Test model_validate
        deserialized = OperationMetrics.model_validate(data)
        assert deserialized.operation_id == metrics.operation_id
        assert deserialized.operation_type == metrics.operation_type
        assert deserialized.status == metrics.status


class TestLayoutMetrics:
    """Test LayoutMetrics model."""

    def test_layout_specific_fields(self):
        """Test layout-specific fields."""
        metrics = LayoutMetrics(
            operation_id="layout-123",
            status=OperationStatus.SUCCESS,
            start_time=datetime.now(),
            input_file=Path("/path/to/layout.json"),
            output_directory=Path("/path/to/output"),
            layer_count=5,
            binding_count=80,
            behavior_count=12,
        )

        assert metrics.operation_type == OperationType.LAYOUT_COMPILATION
        assert metrics.input_file == Path("/path/to/layout.json")
        assert metrics.layer_count == 5
        assert metrics.binding_count == 80
        assert metrics.behavior_count == 12

    def test_timing_fields(self):
        """Test layout timing fields."""
        metrics = LayoutMetrics(
            operation_id="layout-123",
            status=OperationStatus.SUCCESS,
            start_time=datetime.now(),
            parsing_time_seconds=0.1,
            validation_time_seconds=0.05,
            generation_time_seconds=0.3,
        )

        assert metrics.parsing_time_seconds == 0.1
        assert metrics.validation_time_seconds == 0.05
        assert metrics.generation_time_seconds == 0.3


class TestFirmwareMetrics:
    """Test FirmwareMetrics model."""

    def test_firmware_specific_fields(self):
        """Test firmware-specific fields."""
        metrics = FirmwareMetrics(
            operation_id="firmware-123",
            status=OperationStatus.SUCCESS,
            start_time=datetime.now(),
            compilation_strategy="zmk_config",
            board_targets=["glove80_lh", "glove80_rh"],
            docker_image="zmkfirmware/zmk:latest",
            workspace_path=Path("/tmp/zmk_workspace"),
        )

        assert metrics.operation_type == OperationType.FIRMWARE_COMPILATION
        assert metrics.compilation_strategy == "zmk_config"
        assert metrics.board_targets == ["glove80_lh", "glove80_rh"]
        assert metrics.docker_image == "zmkfirmware/zmk:latest"

    def test_build_results(self):
        """Test build result fields."""
        metrics = FirmwareMetrics(
            operation_id="firmware-123",
            status=OperationStatus.SUCCESS,
            start_time=datetime.now(),
            artifacts_generated=2,
            firmware_size_bytes=1024000,
        )

        assert metrics.artifacts_generated == 2
        assert metrics.firmware_size_bytes == 1024000


class TestFlashMetrics:
    """Test FlashMetrics model."""

    def test_flash_specific_fields(self):
        """Test flash-specific fields."""
        metrics = FlashMetrics(
            operation_id="flash-123",
            status=OperationStatus.SUCCESS,
            start_time=datetime.now(),
            device_path="/dev/disk2",
            device_vendor_id="2341",
            device_product_id="805a",
            firmware_file=Path("/path/to/firmware.uf2"),
            firmware_size_bytes=460800,
        )

        assert metrics.operation_type == OperationType.FIRMWARE_FLASH
        assert metrics.device_path == "/dev/disk2"
        assert metrics.device_vendor_id == "2341"
        assert metrics.device_product_id == "805a"
        assert metrics.firmware_size_bytes == 460800


class TestMetricsSummary:
    """Test MetricsSummary model."""

    def test_basic_summary(self):
        """Test basic summary creation."""
        start_time = datetime.now() - timedelta(days=7)
        end_time = datetime.now()

        summary = MetricsSummary(
            start_time=start_time,
            end_time=end_time,
            total_operations=10,
            successful_operations=8,
            failed_operations=2,
        )

        assert summary.total_operations == 10
        assert summary.successful_operations == 8
        assert summary.failed_operations == 2

    def test_performance_stats(self):
        """Test performance statistics."""
        summary = MetricsSummary(
            start_time=datetime.now() - timedelta(days=1),
            end_time=datetime.now(),
            total_operations=5,
            successful_operations=5,
            failed_operations=0,
            average_duration_seconds=2.5,
            median_duration_seconds=2.0,
            fastest_operation_seconds=0.5,
            slowest_operation_seconds=5.0,
        )

        assert summary.average_duration_seconds == 2.5
        assert summary.median_duration_seconds == 2.0
        assert summary.fastest_operation_seconds == 0.5
        assert summary.slowest_operation_seconds == 5.0

    def test_error_breakdown(self):
        """Test error breakdown functionality."""
        error_breakdown = {
            ErrorCategory.COMPILATION_ERROR: 3,
            ErrorCategory.FILE_ERROR: 1,
        }

        summary = MetricsSummary(
            start_time=datetime.now() - timedelta(days=1),
            end_time=datetime.now(),
            total_operations=10,
            successful_operations=6,
            failed_operations=4,
            error_breakdown=error_breakdown,
            most_common_error=ErrorCategory.COMPILATION_ERROR,
        )

        assert summary.error_breakdown[ErrorCategory.COMPILATION_ERROR] == 3
        assert summary.error_breakdown[ErrorCategory.FILE_ERROR] == 1
        assert summary.most_common_error == ErrorCategory.COMPILATION_ERROR


class TestMetricsSnapshot:
    """Test MetricsSnapshot model."""

    def test_snapshot_creation(self):
        """Test snapshot creation with metrics data."""
        operations = [
            OperationMetrics(
                operation_id="op-1",
                operation_type=OperationType.LAYOUT_COMPILATION,
                status=OperationStatus.SUCCESS,
                start_time=datetime.now(),
            ),
            OperationMetrics(
                operation_id="op-2",
                operation_type=OperationType.FIRMWARE_COMPILATION,
                status=OperationStatus.FAILURE,
                start_time=datetime.now(),
            ),
        ]

        summary = MetricsSummary(
            start_time=datetime.now() - timedelta(days=1),
            end_time=datetime.now(),
            total_operations=2,
            successful_operations=1,
            failed_operations=1,
        )

        snapshot = MetricsSnapshot(
            glovebox_version="1.0.0",
            operations=operations,
            summary=summary,
            total_operations=2,
        )

        assert snapshot.glovebox_version == "1.0.0"
        assert len(snapshot.operations) == 2
        assert snapshot.summary == summary
        assert snapshot.total_operations == 2

    def test_snapshot_serialization(self):
        """Test snapshot JSON serialization."""
        snapshot = MetricsSnapshot(
            glovebox_version="1.0.0",
            operations=[
                OperationMetrics(
                    operation_id="op-1",
                    operation_type=OperationType.LAYOUT_COMPILATION,
                    status=OperationStatus.SUCCESS,
                    start_time=datetime.now(),
                )
            ],
            total_operations=1,
        )

        # Test serialization doesn't raise errors
        data = snapshot.to_dict()
        assert data["glovebox_version"] == "1.0.0"
        assert len(data["operations"]) == 1
        assert data["total_operations"] == 1

        # Test JSON serialization
        json_str = json.dumps(data, default=str)
        assert "op-1" in json_str


class TestEnums:
    """Test enum definitions."""

    def test_operation_type_values(self):
        """Test OperationType enum values."""
        assert OperationType.LAYOUT_COMPILATION.value == "layout_compilation"
        assert OperationType.FIRMWARE_COMPILATION.value == "firmware_compilation"
        assert OperationType.FIRMWARE_FLASH.value == "firmware_flash"
        assert OperationType.LAYOUT_VALIDATION.value == "layout_validation"
        assert OperationType.LAYOUT_GENERATION.value == "layout_generation"

    def test_operation_status_values(self):
        """Test OperationStatus enum values."""
        assert OperationStatus.SUCCESS.value == "success"
        assert OperationStatus.FAILURE.value == "failure"
        assert OperationStatus.TIMEOUT.value == "timeout"
        assert OperationStatus.CANCELLED.value == "cancelled"

    def test_error_category_values(self):
        """Test ErrorCategory enum values."""
        assert ErrorCategory.VALIDATION_ERROR.value == "validation_error"
        assert ErrorCategory.COMPILATION_ERROR.value == "compilation_error"
        assert ErrorCategory.DOCKER_ERROR.value == "docker_error"
        assert ErrorCategory.FILE_ERROR.value == "file_error"
        assert ErrorCategory.NETWORK_ERROR.value == "network_error"
        assert ErrorCategory.TIMEOUT_ERROR.value == "timeout_error"
        assert ErrorCategory.UNKNOWN_ERROR.value == "unknown_error"
