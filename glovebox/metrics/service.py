"""Metrics service implementation for tracking application performance."""

import json
import logging
import statistics
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from glovebox.core.logging import get_logger
from glovebox.core.version_check import ZmkVersionChecker
from glovebox.metrics.models import (
    ErrorCategory,
    FirmwareMetrics,
    LayoutMetrics,
    MetricsSnapshot,
    MetricsSummary,
    OperationMetrics,
    OperationStatus,
    OperationType,
)
from glovebox.metrics.protocols import MetricsServiceProtocol, MetricsStorageProtocol
from glovebox.metrics.storage import create_metrics_storage


class MetricsService:
    """Service for collecting and managing application metrics."""

    def __init__(self, storage: MetricsStorageProtocol) -> None:
        """Initialize metrics service.

        Args:
            storage: Storage backend for metrics data
        """
        self.storage = storage
        self.logger = get_logger(__name__)

        # Track active operations
        self._active_operations: dict[str, OperationMetrics] = {}

    def record_operation_start(
        self,
        operation_id: str,
        operation_type: OperationType,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Record the start of an operation.

        Args:
            operation_id: Unique identifier for the operation
            operation_type: Type of operation being started
            context: Additional context information
        """
        try:
            # Create base metrics object
            metrics: OperationMetrics
            if operation_type == OperationType.LAYOUT_COMPILATION:
                metrics = LayoutMetrics(
                    operation_id=operation_id,
                    operation_type=operation_type,
                    status=OperationStatus.SUCCESS,  # Will be updated on completion
                    start_time=datetime.now(),
                )
            elif operation_type == OperationType.FIRMWARE_COMPILATION:
                metrics = FirmwareMetrics(
                    operation_id=operation_id,
                    operation_type=operation_type,
                    status=OperationStatus.SUCCESS,  # Will be updated on completion
                    start_time=datetime.now(),
                )
            else:
                metrics = OperationMetrics(
                    operation_id=operation_id,
                    operation_type=operation_type,
                    status=OperationStatus.SUCCESS,  # Will be updated on completion
                    start_time=datetime.now(),
                )

            # Apply context if provided
            if context:
                for key, value in context.items():
                    if hasattr(metrics, key):
                        setattr(metrics, key, value)

            # Track as active operation
            self._active_operations[operation_id] = metrics

            self.logger.debug(
                "Started tracking operation %s (%s)", operation_id, operation_type
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to record operation start: %s", e, exc_info=exc_info
            )

    def record_operation_end(
        self,
        operation_id: str,
        success: bool,
        error_message: str | None = None,
        error_details: dict[str, Any] | None = None,
        results: dict[str, Any] | None = None,
    ) -> None:
        """Record the completion of an operation.

        Args:
            operation_id: Unique identifier for the operation
            success: Whether the operation succeeded
            error_message: Error message if operation failed
            error_details: Additional error context
            results: Additional result information
        """
        try:
            # Get active operation
            if operation_id not in self._active_operations:
                self.logger.warning(
                    "Operation %s not found in active operations", operation_id
                )
                return

            metrics = self._active_operations[operation_id]

            # Update completion information
            metrics.end_time = datetime.now()
            metrics.status = (
                OperationStatus.SUCCESS if success else OperationStatus.FAILURE
            )

            if not success:
                metrics.error_message = error_message
                metrics.error_details = error_details
                metrics.error_category = self._categorize_error(
                    error_message, error_details
                )

            # Apply results if provided
            if results:
                for key, value in results.items():
                    if hasattr(metrics, key):
                        setattr(metrics, key, value)

            # Store completed metrics
            self.storage.store_operation_metrics(metrics)

            # Remove from active operations
            del self._active_operations[operation_id]

            self.logger.debug(
                "Completed tracking operation %s (success: %s)", operation_id, success
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to record operation end: %s", e, exc_info=exc_info
            )

    def get_operation_metrics(
        self,
        operation_type: OperationType | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> list[OperationMetrics]:
        """Retrieve operation metrics with filtering.

        Args:
            operation_type: Filter by operation type
            start_time: Filter operations after this time
            end_time: Filter operations before this time
            limit: Maximum number of records to return

        Returns:
            List of matching operation metrics
        """
        return self.storage.get_operation_metrics(
            operation_type=operation_type,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

    def generate_summary(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> MetricsSummary:
        """Generate summary statistics for metrics.

        Args:
            start_time: Start of time range for summary
            end_time: End of time range for summary

        Returns:
            Summary statistics for the specified time range
        """
        try:
            # Get all metrics in time range
            all_metrics = self.storage.get_operation_metrics(
                start_time=start_time,
                end_time=end_time,
            )

            if not all_metrics:
                return MetricsSummary(
                    start_time=start_time or datetime.now(),
                    end_time=end_time or datetime.now(),
                    total_operations=0,
                    successful_operations=0,
                    failed_operations=0,
                )

            # Calculate basic counts
            total_operations = len(all_metrics)
            successful_operations = sum(
                1 for m in all_metrics if m.status == OperationStatus.SUCCESS
            )
            failed_operations = total_operations - successful_operations

            # Calculate success rates by operation type
            layout_metrics = [
                m
                for m in all_metrics
                if m.operation_type == OperationType.LAYOUT_COMPILATION
            ]
            firmware_metrics = [
                m
                for m in all_metrics
                if m.operation_type == OperationType.FIRMWARE_COMPILATION
            ]
            flash_metrics = [
                m
                for m in all_metrics
                if m.operation_type == OperationType.FIRMWARE_FLASH
            ]

            layout_success_rate = None
            if layout_metrics:
                layout_success_rate = sum(
                    1 for m in layout_metrics if m.status == OperationStatus.SUCCESS
                ) / len(layout_metrics)

            firmware_success_rate = None
            if firmware_metrics:
                firmware_success_rate = sum(
                    1 for m in firmware_metrics if m.status == OperationStatus.SUCCESS
                ) / len(firmware_metrics)

            flash_success_rate = None
            if flash_metrics:
                flash_success_rate = sum(
                    1 for m in flash_metrics if m.status == OperationStatus.SUCCESS
                ) / len(flash_metrics)

            # Calculate performance statistics
            durations = [
                m.duration_seconds
                for m in all_metrics
                if m.duration_seconds is not None
            ]

            average_duration = None
            median_duration = None
            fastest_operation = None
            slowest_operation = None

            if durations:
                average_duration = statistics.mean(durations)
                median_duration = statistics.median(durations)
                fastest_operation = min(durations)
                slowest_operation = max(durations)

            # Calculate cache statistics
            cache_enabled_metrics = [m for m in all_metrics if m.cache_hit is not None]
            cache_hit_rate = None
            cache_enabled_operations = len(cache_enabled_metrics)

            if cache_enabled_metrics:
                cache_hits = sum(1 for m in cache_enabled_metrics if m.cache_hit)
                cache_hit_rate = cache_hits / len(cache_enabled_metrics)

            # Analyze errors
            error_breakdown: dict[ErrorCategory, int] = {}
            failed_metrics = [
                m for m in all_metrics if m.status == OperationStatus.FAILURE
            ]

            for metrics in failed_metrics:
                if metrics.error_category:
                    error_breakdown[metrics.error_category] = (
                        error_breakdown.get(metrics.error_category, 0) + 1
                    )

            most_common_error = None
            if error_breakdown:
                most_common_error = max(
                    error_breakdown, key=lambda k: error_breakdown[k]
                )

            # Determine time range
            actual_start_time = start_time
            actual_end_time = end_time

            if all_metrics:
                operation_times = [m.start_time for m in all_metrics if m.start_time]
                if operation_times:
                    if not actual_start_time:
                        actual_start_time = min(operation_times)
                    if not actual_end_time:
                        actual_end_time = max(operation_times)

            return MetricsSummary(
                start_time=actual_start_time or datetime.now(),
                end_time=actual_end_time or datetime.now(),
                total_operations=total_operations,
                successful_operations=successful_operations,
                failed_operations=failed_operations,
                layout_success_rate=layout_success_rate,
                firmware_success_rate=firmware_success_rate,
                flash_success_rate=flash_success_rate,
                average_duration_seconds=average_duration,
                median_duration_seconds=median_duration,
                fastest_operation_seconds=fastest_operation,
                slowest_operation_seconds=slowest_operation,
                cache_hit_rate=cache_hit_rate,
                cache_enabled_operations=cache_enabled_operations,
                error_breakdown=error_breakdown,
                most_common_error=most_common_error,
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to generate metrics summary: %s", e, exc_info=exc_info
            )
            # Return empty summary on error
            return MetricsSummary(
                start_time=start_time or datetime.now(),
                end_time=end_time or datetime.now(),
                total_operations=0,
                successful_operations=0,
                failed_operations=0,
            )

    def export_metrics(
        self,
        output_file: Path | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> MetricsSnapshot:
        """Export metrics data to file or return snapshot.

        Args:
            output_file: File to write exported data to
            start_time: Start of time range to export
            end_time: End of time range to export

        Returns:
            Metrics snapshot containing exported data
        """
        try:
            # Get all operations in range
            operations = self.storage.get_operation_metrics(
                start_time=start_time,
                end_time=end_time,
            )

            # Generate summary
            summary = self.generate_summary(start_time=start_time, end_time=end_time)

            # Get version information
            glovebox_version = None
            try:
                version_checker = ZmkVersionChecker()
                glovebox_version = getattr(version_checker, "glovebox_version", None)
            except Exception:
                pass  # Version info is optional

            # Determine date range
            date_range_start = start_time
            date_range_end = end_time

            if operations:
                operation_times = [op.start_time for op in operations if op.start_time]
                if operation_times:
                    if not date_range_start:
                        date_range_start = min(operation_times)
                    if not date_range_end:
                        date_range_end = max(operation_times)

            # Create snapshot
            snapshot = MetricsSnapshot(
                glovebox_version=glovebox_version,
                operations=operations,
                summary=summary,
                total_operations=len(operations),
                date_range_start=date_range_start,
                date_range_end=date_range_end,
            )

            # Write to file if requested
            if output_file:
                output_file.parent.mkdir(parents=True, exist_ok=True)
                with output_file.open("w", encoding="utf-8") as f:
                    json.dump(snapshot.to_dict(), f, indent=2, default=str)

                self.logger.info("Exported metrics to %s", output_file)

            return snapshot

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Failed to export metrics: %s", e, exc_info=exc_info)
            raise

    def clear_metrics(
        self,
        before_time: datetime | None = None,
        operation_type: OperationType | None = None,
    ) -> int:
        """Clear metrics data with optional filtering.

        Args:
            before_time: Clear metrics before this time
            operation_type: Clear metrics of specific operation type

        Returns:
            Number of records cleared
        """
        try:
            if operation_type and not before_time:
                # Get operations of specific type and delete them
                operations = self.storage.get_operation_metrics(
                    operation_type=operation_type
                )
                deleted_count = 0
                for operation in operations:
                    deleted_count += self.storage.delete_operation_metrics(
                        operation_id=operation.operation_id
                    )
                return deleted_count
            else:
                # Use storage's bulk delete functionality
                return self.storage.delete_operation_metrics(before_time=before_time)

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Failed to clear metrics: %s", e, exc_info=exc_info)
            return 0

    def get_metrics_count(self) -> int:
        """Get total count of stored metrics.

        Returns:
            Total number of metrics records
        """
        try:
            return self.storage.get_metrics_count()
        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Failed to get metrics count: %s", e, exc_info=exc_info)
            return 0

    def _categorize_error(
        self, error_message: str | None, error_details: dict[str, Any] | None
    ) -> ErrorCategory | None:
        """Categorize an error based on message and details.

        Args:
            error_message: Error message to analyze
            error_details: Additional error context

        Returns:
            Categorized error type or None if unable to categorize
        """
        if not error_message:
            return ErrorCategory.UNKNOWN_ERROR

        error_msg_lower = error_message.lower()

        # Validation errors
        if any(
            keyword in error_msg_lower
            for keyword in ["validation", "invalid", "malformed", "schema"]
        ):
            return ErrorCategory.VALIDATION_ERROR

        # Compilation errors
        if any(
            keyword in error_msg_lower
            for keyword in ["compilation", "build", "compile", "west", "ninja"]
        ):
            return ErrorCategory.COMPILATION_ERROR

        # Docker errors
        if any(
            keyword in error_msg_lower for keyword in ["docker", "container", "image"]
        ):
            return ErrorCategory.DOCKER_ERROR

        # File errors
        if any(
            keyword in error_msg_lower
            for keyword in ["file", "directory", "path", "not found", "permission"]
        ):
            return ErrorCategory.FILE_ERROR

        # Network errors
        if any(
            keyword in error_msg_lower
            for keyword in ["network", "connection", "timeout", "dns", "http"]
        ):
            return ErrorCategory.NETWORK_ERROR

        # Timeout errors
        if any(
            keyword in error_msg_lower
            for keyword in ["timeout", "timed out", "deadline"]
        ):
            return ErrorCategory.TIMEOUT_ERROR

        return ErrorCategory.UNKNOWN_ERROR


def create_metrics_service() -> MetricsServiceProtocol:
    """Create metrics service with default storage backend.

    Returns:
        MetricsServiceProtocol: Configured metrics service
    """
    storage = create_metrics_storage()
    return MetricsService(storage)


def generate_operation_id() -> str:
    """Generate a unique operation ID.

    Returns:
        Unique operation identifier
    """
    return str(uuid.uuid4())
