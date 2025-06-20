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


if TYPE_CHECKING:
    from glovebox.metrics.collector import MetricsCollector
    from glovebox.metrics.protocols import (
        MetricsServiceProtocol,
        MetricsStorageProtocol,
    )
    from glovebox.metrics.service import MetricsService
    from glovebox.metrics.storage import MetricsStorage


def create_metrics_service() -> "MetricsServiceProtocol":
    """Create metrics service with default storage backend.

    Returns:
        MetricsServiceProtocol: Configured metrics service
    """
    from glovebox.metrics.service import create_metrics_service

    return create_metrics_service()


def create_metrics_storage() -> "MetricsStorageProtocol":
    """Create metrics storage adapter using cache system.

    Returns:
        MetricsStorageProtocol: Configured metrics storage
    """
    from glovebox.metrics.storage import create_metrics_storage

    return create_metrics_storage()


def create_metrics_collector(
    operation_type: OperationType,
    operation_id: str | None = None,
) -> "MetricsCollector":
    """Create metrics collector for capturing operation events.

    Args:
        operation_type: Type of operation to track
        operation_id: Operation ID (generates one if None)

    Returns:
        MetricsCollector: Configured metrics collector
    """
    from glovebox.metrics.collector import create_metrics_collector

    return create_metrics_collector(
        operation_type=operation_type, operation_id=operation_id
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
]
