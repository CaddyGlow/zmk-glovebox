"""Metrics collector context manager for automatic operation tracking."""

import logging
import time
from typing import Any, Optional

from glovebox.core.logging import get_logger
from glovebox.metrics.context import get_current_session_id
from glovebox.metrics.models import OperationType
from glovebox.metrics.protocols import MetricsServiceProtocol
from glovebox.metrics.service import create_metrics_service, generate_operation_id


class MetricsCollector:
    """Context manager for automatic metrics collection during operations."""

    def __init__(
        self,
        operation_type: OperationType,
        metrics_service: MetricsServiceProtocol | None = None,
        operation_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """Initialize metrics collector.

        Args:
            operation_type: Type of operation to track
            metrics_service: Metrics service instance (creates default if None)
            operation_id: Operation ID (generates one if None)
            session_id: Session ID to associate with this operation
        """
        self.operation_type = operation_type
        self.metrics_service = metrics_service or create_metrics_service()
        self.operation_id = operation_id or generate_operation_id()
        self.logger = get_logger(__name__)

        # Track operation state
        self._context: dict[str, Any] = {}
        self._timings: dict[str, float] = {}
        self._cache_hit: bool | None = None
        self._cache_key: str | None = None
        self._cache_details: dict[str, Any] = {}
        self._exception_occurred = False
        self._start_time: float | None = None

        # Set session_id in context if provided
        if session_id:
            self._context["session_id"] = session_id

    def __enter__(self) -> "MetricsCollector":
        """Enter the metrics collection context.

        Returns:
            Self for context manager protocol
        """
        try:
            self._start_time = time.time()

            # Record operation start with initial context
            self.metrics_service.record_operation_start(
                operation_id=self.operation_id,
                operation_type=self.operation_type,
                context=self._context,
            )

            self.logger.debug(
                "Started metrics collection for operation %s (%s)",
                self.operation_id,
                self.operation_type,
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to start metrics collection: %s", e, exc_info=exc_info
            )

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the metrics collection context.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
        """
        try:
            success = exc_type is None
            error_message = None
            error_details = None

            if not success:
                self._exception_occurred = True
                error_message = str(exc_val) if exc_val else "Unknown error"
                error_details = {
                    "exception_type": exc_type.__name__ if exc_type else "Unknown",
                }

            # Prepare results with timing and cache information
            results: dict[str, Any] = {}

            # Add cache information
            if self._cache_hit is not None:
                results["cache_hit"] = self._cache_hit
            if self._cache_key is not None:
                results["cache_key"] = self._cache_key
            if self._cache_details:
                results["cache_details"] = self._cache_details

            # Add sub-operation timings
            for timing_name, duration in self._timings.items():
                field_name = f"{timing_name}_time_seconds"
                results[field_name] = duration

            # Add any additional context as results
            results.update(self._context)

            # Record operation completion
            self.metrics_service.record_operation_end(
                operation_id=self.operation_id,
                success=success,
                error_message=error_message,
                error_details=error_details,
                results=results,
            )

            self.logger.debug(
                "Completed metrics collection for operation %s (success: %s)",
                self.operation_id,
                success,
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to complete metrics collection: %s", e, exc_info=exc_info
            )

    def set_context(self, **context: Any) -> None:
        """Set additional context information for the operation.

        Args:
            **context: Key-value pairs of context information
        """
        try:
            self._context.update(context)
            self.logger.debug("Updated operation context: %s", context)
        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Failed to set context: %s", e, exc_info=exc_info)

    def set_cache_info(self, cache_hit: bool, cache_key: str | None = None) -> None:
        """Set cache-related information for the operation.

        Args:
            cache_hit: Whether the operation used cached results
            cache_key: Cache key used for the operation
        """
        try:
            self._cache_hit = cache_hit
            self._cache_key = cache_key
            self.logger.debug("Set cache info: hit=%s, key=%s", cache_hit, cache_key)
        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Failed to set cache info: %s", e, exc_info=exc_info)

    def record_cache_event(
        self, cache_type: str, cache_hit: bool, cache_key: str | None = None
    ) -> None:
        """Record a cache event for detailed cache tracking.

        Args:
            cache_type: Type of cache (e.g., 'build_result', 'workspace', 'docker_image')
            cache_hit: Whether this cache was hit or missed
            cache_key: Optional cache key used
        """
        try:
            self._cache_details[cache_type] = {
                "hit": cache_hit,
                "key": cache_key,
            }

            # Update overall cache hit if this is the primary cache
            if cache_type in ["build_result", "compilation_result"]:
                self._cache_hit = cache_hit
                if cache_key:
                    self._cache_key = cache_key

            self.logger.debug(
                "Recorded cache event: type=%s, hit=%s, key=%s",
                cache_type,
                cache_hit,
                cache_key,
            )
        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Failed to record cache event: %s", e, exc_info=exc_info)

    def record_timing(self, operation_name: str, duration_seconds: float) -> None:
        """Record timing for a sub-operation.

        Args:
            operation_name: Name of the sub-operation (e.g., 'parsing', 'validation')
            duration_seconds: Duration of the sub-operation in seconds
        """
        try:
            self._timings[operation_name] = duration_seconds
            self.logger.debug(
                "Recorded timing for %s: %.3fs", operation_name, duration_seconds
            )
        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Failed to record timing: %s", e, exc_info=exc_info)

    def time_operation(self, operation_name: str) -> "TimingContext":
        """Create a timing context for a sub-operation.

        Args:
            operation_name: Name of the sub-operation to time

        Returns:
            Timing context manager that automatically records duration
        """
        return TimingContext(self, operation_name)

    @property
    def is_exception_occurred(self) -> bool:
        """Check if an exception occurred during the operation.

        Returns:
            True if an exception was recorded
        """
        return self._exception_occurred

    @property
    def elapsed_time(self) -> float | None:
        """Get elapsed time since operation start.

        Returns:
            Elapsed time in seconds or None if not started
        """
        if self._start_time is None:
            return None
        return time.time() - self._start_time


class TimingContext:
    """Context manager for timing sub-operations within a metrics collector."""

    def __init__(self, collector: MetricsCollector, operation_name: str) -> None:
        """Initialize timing context.

        Args:
            collector: Parent metrics collector
            operation_name: Name of the operation being timed
        """
        self.collector = collector
        self.operation_name = operation_name
        self._start_time: float | None = None

    def __enter__(self) -> "TimingContext":
        """Start timing the operation.

        Returns:
            Self for context manager protocol
        """
        self._start_time = time.time()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop timing and record the duration.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
        """
        if self._start_time is not None:
            duration = time.time() - self._start_time
            self.collector.record_timing(self.operation_name, duration)


def create_metrics_collector(
    operation_type: OperationType,
    operation_id: str | None = None,
    metrics_service: MetricsServiceProtocol | None = None,
    session_id: str | None = None,
) -> MetricsCollector:
    """Create a metrics collector for automatic operation tracking with dependency injection.

    Args:
        operation_type: Type of operation to track
        operation_id: Operation ID (generates one if None)
        metrics_service: Optional metrics service instance. If None, creates default service.
        session_id: Session ID to associate with this operation

    Returns:
        MetricsCollector: Configured metrics collector
    """
    return MetricsCollector(
        operation_type=operation_type,
        operation_id=operation_id,
        metrics_service=metrics_service,
        session_id=session_id,
    )


def layout_metrics(
    operation_id: str | None = None, session_id: str | None = None
) -> MetricsCollector:
    """Create a metrics collector for layout operations.

    Args:
        operation_id: Operation ID (generates one if None)
        session_id: Session ID to associate with this operation (uses thread-local if None)

    Returns:
        MetricsCollector configured for layout operations
    """
    return create_metrics_collector(
        operation_type=OperationType.LAYOUT_COMPILATION,
        operation_id=operation_id,
        session_id=session_id or get_current_session_id(),
    )


def firmware_metrics(
    operation_id: str | None = None, session_id: str | None = None
) -> MetricsCollector:
    """Create a metrics collector for firmware operations.

    Args:
        operation_id: Operation ID (generates one if None)
        session_id: Session ID to associate with this operation (uses thread-local if None)

    Returns:
        MetricsCollector configured for firmware operations
    """
    return create_metrics_collector(
        operation_type=OperationType.FIRMWARE_COMPILATION,
        operation_id=operation_id,
        session_id=session_id or get_current_session_id(),
    )


def flash_metrics(
    operation_id: str | None = None, session_id: str | None = None
) -> MetricsCollector:
    """Create a metrics collector for flash operations.

    Args:
        operation_id: Operation ID (generates one if None)
        session_id: Session ID to associate with this operation (uses thread-local if None)

    Returns:
        MetricsCollector configured for flash operations
    """
    return create_metrics_collector(
        operation_type=OperationType.FIRMWARE_FLASH,
        operation_id=operation_id,
        session_id=session_id or get_current_session_id(),
    )


def compilation_metrics(
    operation_id: str | None = None, session_id: str | None = None
) -> MetricsCollector:
    """Create a metrics collector for compilation operations.

    Args:
        operation_id: Operation ID (generates one if None)
        session_id: Session ID to associate with this operation (uses thread-local if None)

    Returns:
        MetricsCollector configured for compilation operations
    """
    return create_metrics_collector(
        operation_type=OperationType.FIRMWARE_COMPILATION,
        operation_id=operation_id,
        session_id=session_id or get_current_session_id(),
    )
