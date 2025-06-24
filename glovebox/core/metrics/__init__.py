"""Metrics domain for application performance and usage tracking.

This domain provides comprehensive metrics collection with prometheus_client-compatible API:
- Performance monitoring via SessionMetrics
- CLI arguments and exit code tracking
- Local JSON storage with automatic TTL cleanup
- Thread-safe cache-based metrics storage
- Easy migration path to real prometheus_client
"""

# Import and re-export SessionMetrics for prometheus_client-compatible API
from glovebox.core.metrics.session_metrics import (
    MetricsContextManager,
    NoOpCounter,
    NoOpGauge,
    NoOpHistogram,
    NoOpMetrics,
    NoOpMetricsLabeled,
    NoOpSummary,
    SessionCounter,
    SessionGauge,
    SessionHistogram,
    SessionMetrics,
    SessionMetricsLabeled,
    SessionSummary,
    create_noop_session_metrics,
    create_session_metrics,
)


__all__ = [
    # SessionMetrics (prometheus_client-compatible API)
    "SessionMetrics",
    "SessionCounter",
    "SessionGauge",
    "SessionHistogram",
    "SessionSummary",
    "SessionMetricsLabeled",
    "create_session_metrics",
    # NoOp Metrics (for when metrics are disabled)
    "NoOpMetrics",
    "NoOpCounter",
    "NoOpGauge",
    "NoOpHistogram",
    "NoOpSummary",
    "NoOpMetricsLabeled",
    "create_noop_session_metrics",
    # Context Manager
    "MetricsContextManager",
]
