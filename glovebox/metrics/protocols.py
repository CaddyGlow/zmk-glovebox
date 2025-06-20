"""Metrics system protocols for type-safe interfaces."""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Protocol, runtime_checkable


if TYPE_CHECKING:
    from glovebox.metrics.models import (
        MetricsSnapshot,
        MetricsSummary,
        OperationMetrics,
        OperationType,
    )


@runtime_checkable
class MetricsStorageProtocol(Protocol):
    """Protocol for metrics storage backends."""

    def store_operation_metrics(self, metrics: "OperationMetrics") -> None:
        """Store operation metrics data.

        Args:
            metrics: Operation metrics to store
        """
        ...

    def get_operation_metrics(
        self,
        operation_id: str | None = None,
        operation_type: Optional["OperationType"] = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> list["OperationMetrics"]:
        """Retrieve operation metrics with optional filtering.

        Args:
            operation_id: Filter by specific operation ID
            operation_type: Filter by operation type
            start_time: Filter operations after this time
            end_time: Filter operations before this time
            limit: Maximum number of records to return

        Returns:
            List of matching operation metrics
        """
        ...

    def delete_operation_metrics(
        self,
        operation_id: str | None = None,
        before_time: datetime | None = None,
    ) -> int:
        """Delete operation metrics.

        Args:
            operation_id: Delete specific operation by ID
            before_time: Delete all operations before this time

        Returns:
            Number of records deleted
        """
        ...

    def get_metrics_count(self) -> int:
        """Get total count of stored metrics.

        Returns:
            Total number of metrics records
        """
        ...

    def clear_all_metrics(self) -> int:
        """Clear all stored metrics.

        Returns:
            Number of records deleted
        """
        ...


@runtime_checkable
class MetricsServiceProtocol(Protocol):
    """Protocol for metrics service implementations."""

    def record_operation_start(
        self,
        operation_id: str,
        operation_type: "OperationType",
        context: dict[str, Any] | None = None,
    ) -> None:
        """Record the start of an operation.

        Args:
            operation_id: Unique identifier for the operation
            operation_type: Type of operation being started
            context: Additional context information
        """
        ...

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
        ...

    def get_operation_metrics(
        self,
        operation_type: Optional["OperationType"] = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> list["OperationMetrics"]:
        """Retrieve operation metrics with filtering.

        Args:
            operation_type: Filter by operation type
            start_time: Filter operations after this time
            end_time: Filter operations before this time
            limit: Maximum number of records to return

        Returns:
            List of matching operation metrics
        """
        ...

    def generate_summary(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> "MetricsSummary":
        """Generate summary statistics for metrics.

        Args:
            start_time: Start of time range for summary
            end_time: End of time range for summary

        Returns:
            Summary statistics for the specified time range
        """
        ...

    def export_metrics(
        self,
        output_file: Path | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> "MetricsSnapshot":
        """Export metrics data to file or return snapshot.

        Args:
            output_file: File to write exported data to
            start_time: Start of time range to export
            end_time: End of time range to export

        Returns:
            Metrics snapshot containing exported data
        """
        ...

    def clear_metrics(
        self,
        before_time: datetime | None = None,
        operation_type: Optional["OperationType"] = None,
    ) -> int:
        """Clear metrics data with optional filtering.

        Args:
            before_time: Clear metrics before this time
            operation_type: Clear metrics of specific operation type

        Returns:
            Number of records cleared
        """
        ...

    def get_metrics_count(self) -> int:
        """Get total count of stored metrics.

        Returns:
            Total number of metrics records
        """
        ...


@runtime_checkable
class MetricsCollectorProtocol(Protocol):
    """Protocol for metrics collection context managers."""

    def __enter__(self) -> "MetricsCollectorProtocol":
        """Enter the metrics collection context.

        Returns:
            Self for context manager protocol
        """
        ...

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the metrics collection context.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
        """
        ...

    def set_context(self, **context: Any) -> None:
        """Set additional context information for the operation.

        Args:
            **context: Key-value pairs of context information
        """
        ...

    def set_cache_info(self, cache_hit: bool, cache_key: str | None = None) -> None:
        """Set cache-related information for the operation.

        Args:
            cache_hit: Whether the operation used cached results
            cache_key: Cache key used for the operation
        """
        ...

    def record_timing(self, operation_name: str, duration_seconds: float) -> None:
        """Record timing for a sub-operation.

        Args:
            operation_name: Name of the sub-operation (e.g., 'parsing', 'validation')
            duration_seconds: Duration of the sub-operation in seconds
        """
        ...
