"""Protocol for metrics collection interfaces."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable


if TYPE_CHECKING:
    from glovebox.core.metrics.session_metrics import (
        NoOpCounter,
        NoOpGauge,
        NoOpHistogram,
        NoOpSummary,
        SessionCounter,
        SessionGauge,
        SessionHistogram,
        SessionSummary,
    )


@runtime_checkable
class MetricsProtocol(Protocol):
    """Protocol for metrics collection that both SessionMetrics and NoOpMetrics implement."""

    def set_context(self, **kwargs: Any) -> None:
        """Set context information for metrics."""
        ...

    @contextmanager
    def time_operation(self, operation_name: str) -> Iterator[None]:
        """Time an operation using a histogram."""
        ...

    def Counter(  # noqa: N802
        self, name: str, description: str, labelnames: list[str] | None = None
    ) -> "SessionCounter | NoOpCounter":
        """Create a Counter metric."""
        ...

    def Gauge(  # noqa: N802
        self, name: str, description: str, labelnames: list[str] | None = None
    ) -> "SessionGauge | NoOpGauge":
        """Create a Gauge metric."""
        ...

    def Histogram(  # noqa: N802
        self, name: str, description: str, buckets: list[float] | None = None
    ) -> "SessionHistogram | NoOpHistogram":
        """Create a Histogram metric."""
        ...

    def Summary(  # noqa: N802
        self, name: str, description: str
    ) -> "SessionSummary | NoOpSummary":
        """Create a Summary metric."""
        ...

    def set_exit_code(self, exit_code: int) -> None:
        """Set the CLI exit code for this session."""
        ...

    def set_cli_args(self, cli_args: list[str]) -> None:
        """Set the CLI arguments for this session."""
        ...

    def record_cache_event(self, cache_type: str, cache_hit: bool) -> None:
        """Record a cache event (hit or miss) for metrics tracking."""
        ...

    def save(self) -> None:
        """Save all metrics data."""
        ...

    def __enter__(self) -> "MetricsProtocol":
        """Enter the context manager."""
        ...

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the context manager."""
        ...
