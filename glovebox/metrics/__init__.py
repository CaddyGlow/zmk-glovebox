"""Metrics domain for application performance and usage tracking.

This domain provides comprehensive metrics collection and reporting for:
- Layout compilation performance and success rates
- Firmware compilation performance and success rates
- Operation timing and caching statistics
- Error categorization and frequency analysis
"""

from typing import TYPE_CHECKING

# Import and re-export models and enums for CLI usage
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

# Import and re-export SessionMetrics for prometheus_client-compatible API
from glovebox.metrics.session_metrics import (
    SessionCounter,
    SessionGauge,
    SessionHistogram,
    SessionMetrics,
    SessionSummary,
    create_session_metrics,
)


if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from glovebox.core.cache_v2.cache_manager import CacheManager
    from glovebox.metrics.collector import MetricsCollector
    from glovebox.metrics.protocols import (
        MetricsServiceProtocol,
        MetricsStorageProtocol,
    )
    from glovebox.metrics.service import MetricsService
    from glovebox.metrics.storage import MetricsStorage

    # Context extractor type definition
    ContextExtractor = Callable[
        [Callable[..., Any], tuple[Any, ...], dict[str, Any]], dict[str, Any]
    ]


def create_metrics_service(
    storage: "MetricsStorageProtocol | None" = None,
) -> "MetricsServiceProtocol":
    """Create metrics service with optional storage backend dependency injection.

    Args:
        storage: Optional storage backend instance. If None, creates default storage.

    Returns:
        MetricsServiceProtocol: Configured metrics service
    """
    from glovebox.metrics.service import create_metrics_service

    return create_metrics_service(storage=storage)


def create_metrics_storage(
    cache: "CacheManager | None" = None,
) -> "MetricsStorageProtocol":
    """Create metrics storage adapter with optional cache dependency injection.

    Args:
        cache: Optional cache manager instance. If None, creates default cache.

    Returns:
        MetricsStorageProtocol: Configured metrics storage
    """
    from glovebox.metrics.storage import create_metrics_storage

    return create_metrics_storage(cache=cache)


def create_metrics_collector(
    operation_type: OperationType,
    operation_id: str | None = None,
    metrics_service: "MetricsServiceProtocol | None" = None,
) -> "MetricsCollector":
    """Create metrics collector with optional service dependency injection.

    Args:
        operation_type: Type of operation to track
        operation_id: Operation ID (generates one if None)
        metrics_service: Optional metrics service instance. If None, creates default service.

    Returns:
        MetricsCollector: Configured metrics collector
    """
    from glovebox.metrics.collector import create_metrics_collector

    return create_metrics_collector(
        operation_type=operation_type,
        operation_id=operation_id,
        metrics_service=metrics_service,
    )


def create_operation_tracker(
    operation_type: OperationType,
    extract_context: "ContextExtractor | None" = None,
    metrics_service: "MetricsServiceProtocol | None" = None,
) -> "Callable[..., Any]":
    """Create operation tracking decorator with dependency injection support.

    This factory function creates decorators for automatic metrics collection
    following the CLAUDE.md dependency injection pattern.

    Args:
        operation_type: Type of operation being tracked
        extract_context: Optional function to extract context from args/kwargs
        metrics_service: Optional metrics service instance for dependency injection

    Returns:
        Decorator function that can be applied to functions for metrics tracking

    Example:
        >>> tracker = create_operation_tracker(
        ...     OperationType.LAYOUT_COMPILATION,
        ...     extract_context=extract_cli_context
        ... )
        >>> @tracker
        ... def my_function():
        ...     pass
    """
    from glovebox.metrics.decorators import create_operation_tracker

    return create_operation_tracker(
        operation_type=operation_type,
        extract_context=extract_context,
        metrics_service=metrics_service,
    )


__all__ = [
    # Models and enums
    "OperationType",
    "OperationStatus",
    "ErrorCategory",
    "OperationMetrics",
    "LayoutMetrics",
    "FirmwareMetrics",
    "FlashMetrics",
    "MetricsSummary",
    "MetricsSnapshot",
    # Factory functions
    "create_metrics_service",
    "create_metrics_storage",
    "create_metrics_collector",
    "create_operation_tracker",
    # SessionMetrics (prometheus_client-compatible)
    "SessionMetrics",
    "SessionCounter",
    "SessionGauge",
    "SessionHistogram",
    "SessionSummary",
    "create_session_metrics",
]
