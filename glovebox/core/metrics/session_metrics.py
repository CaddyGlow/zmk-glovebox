"""Session-based metrics collection with prometheus_client-compatible API.

This module provides a local JSON-based metrics system that mirrors the prometheus_client
API exactly, allowing for seamless migration to Prometheus in the future while storing
metrics locally during CLI sessions.
"""

import json
import logging
import time
from contextlib import contextmanager
from datetime import datetime
from logging import getLogger
from pathlib import Path
from typing import Any, Optional

from glovebox.core.cache.cache_manager import CacheManager


logger = getLogger(__name__)


class SessionMetricsLabeled:
    """Labeled metric instance that handles label-specific operations."""

    def __init__(self, parent: Any, label_values: tuple[str, ...]) -> None:
        self.parent = parent
        self.label_values = label_values

    def inc(self, amount: float = 1) -> None:
        """Increment counter by amount (Counter only)."""
        self.parent._increment(self.label_values, amount)

    def dec(self, amount: float = 1) -> None:
        """Decrement gauge by amount (Gauge only)."""
        self.parent._decrement(self.label_values, amount)

    def set(self, value: float) -> None:
        """Set gauge to value (Gauge only)."""
        self.parent._set_value(self.label_values, value)

    def set_to_current_time(self) -> None:
        """Set gauge to current unix timestamp (Gauge only)."""
        import time

        self.parent._set_value(self.label_values, time.time())

    def observe(self, value: float) -> None:
        """Observe value (Histogram/Summary only)."""
        self.parent._observe(self.label_values, value)

    @contextmanager
    def time(self) -> Any:
        """Time a block of code (Histogram/Summary only)."""
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self.parent._observe(self.label_values, duration)


class SessionCounter:
    """Counter that increments and stores values locally - prometheus_client compatible."""

    def __init__(
        self,
        name: str,
        description: str,
        labelnames: list[str] | None = None,
        registry: Any = None,
    ) -> None:
        self.name = name
        self.description = description
        self.labelnames = labelnames or []
        self.registry = registry
        self._values: dict[tuple[str, ...], float] = {}

        # Initialize unlabeled metric
        if not self.labelnames:
            self._values[()] = 0

    def inc(self, amount: float = 1) -> None:
        """Increment counter by amount - identical to prometheus_client."""
        if self.labelnames:
            raise ValueError("Counter with labels requires labels() call")
        self._increment((), amount)

    def labels(self, *args: Any, **kwargs: Any) -> SessionMetricsLabeled:
        """Return labeled instance - prometheus_client compatible."""
        if not self.labelnames:
            raise ValueError("Counter was not declared with labels")

        # Handle both positional and keyword arguments
        if args and kwargs:
            raise ValueError("Cannot mix positional and keyword arguments")

        if args:
            if len(args) != len(self.labelnames):
                raise ValueError(
                    f"Expected {len(self.labelnames)} label values, got {len(args)}"
                )
            label_values = tuple(str(v) for v in args)
        else:
            # Keyword arguments - ensure all labels are provided
            missing_labels = set(self.labelnames) - set(kwargs.keys())
            if missing_labels:
                raise ValueError(f"Missing label values: {missing_labels}")
            label_values = tuple(str(kwargs[name]) for name in self.labelnames)

        # Initialize if needed
        if label_values not in self._values:
            self._values[label_values] = 0

        return SessionMetricsLabeled(self, label_values)

    def _increment(self, label_values: tuple[str, ...], amount: float) -> None:
        """Internal method to increment counter value."""
        if label_values not in self._values:
            self._values[label_values] = 0
        self._values[label_values] += amount

        # Notify registry if available
        if self.registry:
            self.registry._record_update(
                self.name, "counter", label_values, self._values[label_values]
            )


class SessionGauge:
    """Gauge that can be set, incremented, or decremented - prometheus_client compatible."""

    def __init__(
        self,
        name: str,
        description: str,
        labelnames: list[str] | None = None,
        registry: Any = None,
    ) -> None:
        self.name = name
        self.description = description
        self.labelnames = labelnames or []
        self.registry = registry
        self._values: dict[tuple[str, ...], float] = {}

        # Initialize unlabeled metric
        if not self.labelnames:
            self._values[()] = 0

    def inc(self, amount: float = 1) -> None:
        """Increment gauge by amount - identical to prometheus_client."""
        if self.labelnames:
            raise ValueError("Gauge with labels requires labels() call")
        self._increment((), amount)

    def dec(self, amount: float = 1) -> None:
        """Decrement gauge by amount - identical to prometheus_client."""
        if self.labelnames:
            raise ValueError("Gauge with labels requires labels() call")
        self._decrement((), amount)

    def set(self, value: float) -> None:
        """Set gauge to value - identical to prometheus_client."""
        if self.labelnames:
            raise ValueError("Gauge with labels requires labels() call")
        self._set_value((), value)

    def set_to_current_time(self) -> None:
        """Set gauge to current unix timestamp - identical to prometheus_client."""
        self.set(time.time())

    def labels(self, *args: Any, **kwargs: Any) -> SessionMetricsLabeled:
        """Return labeled instance - prometheus_client compatible."""
        if not self.labelnames:
            raise ValueError("Gauge was not declared with labels")

        # Handle both positional and keyword arguments
        if args and kwargs:
            raise ValueError("Cannot mix positional and keyword arguments")

        if args:
            if len(args) != len(self.labelnames):
                raise ValueError(
                    f"Expected {len(self.labelnames)} label values, got {len(args)}"
                )
            label_values = tuple(str(v) for v in args)
        else:
            # Keyword arguments - ensure all labels are provided
            missing_labels = set(self.labelnames) - set(kwargs.keys())
            if missing_labels:
                raise ValueError(f"Missing label values: {missing_labels}")
            label_values = tuple(str(kwargs[name]) for name in self.labelnames)

        # Initialize if needed
        if label_values not in self._values:
            self._values[label_values] = 0

        return SessionMetricsLabeled(self, label_values)

    def _increment(self, label_values: tuple[str, ...], amount: float) -> None:
        """Internal method to increment gauge value."""
        if label_values not in self._values:
            self._values[label_values] = 0
        self._values[label_values] += amount

        if self.registry:
            self.registry._record_update(
                self.name, "gauge", label_values, self._values[label_values]
            )

    def _decrement(self, label_values: tuple[str, ...], amount: float) -> None:
        """Internal method to decrement gauge value."""
        if label_values not in self._values:
            self._values[label_values] = 0
        self._values[label_values] -= amount

        if self.registry:
            self.registry._record_update(
                self.name, "gauge", label_values, self._values[label_values]
            )

    def _set_value(self, label_values: tuple[str, ...], value: float) -> None:
        """Internal method to set gauge value."""
        self._values[label_values] = value

        if self.registry:
            self.registry._record_update(self.name, "gauge", label_values, value)


class SessionHistogram:
    """Histogram that observes values and provides timing - prometheus_client compatible."""

    def __init__(
        self,
        name: str,
        description: str,
        buckets: list[float] | None = None,
        registry: Any = None,
    ) -> None:
        self.name = name
        self.description = description
        self.registry = registry
        # Default prometheus buckets
        self.buckets = buckets or [
            0.005,
            0.01,
            0.025,
            0.05,
            0.075,
            0.1,
            0.25,
            0.5,
            0.75,
            1.0,
            2.5,
            5.0,
            7.5,
            10.0,
            float("inf"),
        ]
        self._observations: list[dict[str, Any]] = []

    def observe(self, value: float) -> None:
        """Observe a value - identical to prometheus_client."""
        observation = {"value": value, "timestamp": time.time(), "labels": ()}
        self._observations.append(observation)

        if self.registry:
            self.registry._record_observation(self.name, "histogram", (), value)

    @contextmanager
    def time(self) -> Any:
        """Context manager for timing - identical to prometheus_client."""
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self.observe(duration)

    def _observe(self, label_values: tuple[str, ...], value: float) -> None:
        """Internal method to observe value with labels."""
        observation = {"value": value, "timestamp": time.time(), "labels": label_values}
        self._observations.append(observation)

        if self.registry:
            self.registry._record_observation(
                self.name, "histogram", label_values, value
            )


class SessionSummary:
    """Summary that observes values and provides timing - prometheus_client compatible."""

    def __init__(self, name: str, description: str, registry: Any = None) -> None:
        self.name = name
        self.description = description
        self.registry = registry
        self._observations: list[dict[str, Any]] = []

    def observe(self, value: float) -> None:
        """Observe a value - identical to prometheus_client."""
        observation = {"value": value, "timestamp": time.time(), "labels": ()}
        self._observations.append(observation)

        if self.registry:
            self.registry._record_observation(self.name, "summary", (), value)

    @contextmanager
    def time(self) -> Any:
        """Context manager for timing - identical to prometheus_client."""
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            self.observe(duration)

    def _observe(self, label_values: tuple[str, ...], value: float) -> None:
        """Internal method to observe value with labels."""
        observation = {"value": value, "timestamp": time.time(), "labels": label_values}
        self._observations.append(observation)

        if self.registry:
            self.registry._record_observation(self.name, "summary", label_values, value)


class SessionMetrics:
    """Session-based metrics collection with prometheus_client-compatible API.

    This class provides a local JSON-based metrics registry that mirrors the prometheus_client
    API exactly, allowing for seamless migration to Prometheus in the future.

    Example:
        >>> metrics = SessionMetrics("session_metrics.json")
        >>> counter = metrics.Counter('operations_total', 'Total operations', ['type'])
        >>> counter.labels('layout').inc()
        >>>
        >>> with metrics.Histogram('duration_seconds', 'Operation duration').time():
        ...     do_work()
        >>>
        >>> metrics.save()
    """

    def __init__(
        self, cache_manager: CacheManager, session_uuid: str, ttl_days: int = 7
    ) -> None:
        self.cache_manager = cache_manager
        self.session_uuid = session_uuid
        self.ttl_seconds = ttl_days * 24 * 60 * 60  # Convert days to seconds
        self.session_start = datetime.now()
        self.session_id = f"session_{int(time.time())}"
        self.session_start_perf = time.perf_counter()

        # Metric registries
        self._counters: dict[str, SessionCounter] = {}
        self._gauges: dict[str, SessionGauge] = {}
        self._histograms: dict[str, SessionHistogram] = {}
        self._summaries: dict[str, SessionSummary] = {}

        # Activity log for updates
        self._activity_log: list[dict[str, Any]] = []

        # Session execution information
        self.exit_code: int | None = None
        self.cli_args: list[str] = []

    def Counter(  # noqa: N802
        self, name: str, description: str, labelnames: list[str] | None = None
    ) -> SessionCounter:
        """Create a Counter metric - identical to prometheus_client."""
        if name in self._counters:
            return self._counters[name]

        counter = SessionCounter(name, description, labelnames, registry=self)
        self._counters[name] = counter

        return counter

    def Gauge(  # noqa: N802
        self, name: str, description: str, labelnames: list[str] | None = None
    ) -> SessionGauge:
        """Create a Gauge metric - identical to prometheus_client."""
        if name in self._gauges:
            return self._gauges[name]

        gauge = SessionGauge(name, description, labelnames, registry=self)
        self._gauges[name] = gauge

        return gauge

    def Histogram(  # noqa: N802
        self, name: str, description: str, buckets: list[float] | None = None
    ) -> SessionHistogram:
        """Create a Histogram metric - identical to prometheus_client."""
        if name in self._histograms:
            return self._histograms[name]

        histogram = SessionHistogram(name, description, buckets, registry=self)
        self._histograms[name] = histogram

        return histogram

    def Summary(self, name: str, description: str) -> SessionSummary:  # noqa: N802
        """Create a Summary metric - identical to prometheus_client."""
        if name in self._summaries:
            return self._summaries[name]

        summary = SessionSummary(name, description, registry=self)
        self._summaries[name] = summary

        logger.debug("Created summary: %s", name)
        return summary

    def set_exit_code(self, exit_code: int) -> None:
        """Set the CLI exit code for this session.

        Args:
            exit_code: The exit code (0 for success, non-zero for error)
        """
        self.exit_code = exit_code

    def set_cli_args(self, cli_args: list[str]) -> None:
        """Set the CLI arguments for this session.

        Args:
            cli_args: List of CLI arguments (typically sys.argv)
        """
        self.cli_args = cli_args.copy()  # Make a copy to avoid external mutations

    def _record_update(
        self,
        metric_name: str,
        metric_type: str,
        label_values: tuple[str, ...],
        value: float,
    ) -> None:
        """Record metric update in activity log."""
        self._activity_log.append(
            {
                "timestamp": time.time(),
                "metric_name": metric_name,
                "metric_type": metric_type,
                "label_values": label_values,
                "value": value,
                "operation": "update",
            }
        )

    def _record_observation(
        self,
        metric_name: str,
        metric_type: str,
        label_values: tuple[str, ...],
        value: float,
    ) -> None:
        """Record metric observation in activity log."""
        self._activity_log.append(
            {
                "timestamp": time.time(),
                "metric_name": metric_name,
                "metric_type": metric_type,
                "label_values": label_values,
                "value": value,
                "operation": "observe",
            }
        )

    def record_cache_event(self, cache_type: str, cache_hit: bool) -> None:
        """Record a cache event (hit or miss) for metrics tracking.

        Args:
            cache_type: Type of cache (e.g., 'workspace', 'build', etc.)
            cache_hit: True if cache hit, False if cache miss
        """
        self._activity_log.append(
            {
                "timestamp": time.time(),
                "operation": "cache_event",
                "cache_type": cache_type,
                "cache_hit": cache_hit,
            }
        )

    def save(self) -> None:
        """Save all metrics data to cache."""
        try:
            data = self._serialize_data()

            # Store in cache with TTL (cache.set returns None on success)
            self.cache_manager.set(self.session_uuid, data, ttl=self.ttl_seconds)
            logger.debug(
                "Saved session metrics to cache with key: %s", self.session_uuid
            )

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Failed to save session metrics: %s", e, exc_info=exc_info)

    def checkpoint(self, name: str) -> None:
        histogram = self.Histogram(
            f"start_time_{name}_duration_seconds", f"{name} duration since start"
        )

        histogram.observe(time.perf_counter() - self.session_start_perf)

    def set_context(self, **kwargs: Any) -> None:
        """Set context information for metrics.

        Args:
            **kwargs: Arbitrary context key-value pairs
        """
        # For SessionMetrics, we could store context in activity log
        self._activity_log.append(
            {"timestamp": time.time(), "operation": "set_context", "context": kwargs}
        )

    @contextmanager
    def time_operation(self, operation_name: str) -> Any:
        """Time an operation using a histogram.

        Args:
            operation_name: Name of the operation being timed
        """
        start = time.time()
        try:
            yield
        finally:
            duration = time.time() - start
            # Record specific activity log entry for time_operation
            self._activity_log.append(
                {
                    "timestamp": start,
                    "operation": "time_operation",
                    "operation_name": operation_name,
                    "duration": duration,
                }
            )
            # Also record via histogram for metric collection
            histogram = self.Histogram(
                f"{operation_name}_duration_seconds", f"{operation_name} duration"
            )
            histogram.observe(duration)

    def __enter__(self) -> "SessionMetrics":
        """Enter the context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the context manager."""
        self.save()

    def _serialize_data(self) -> dict[str, Any]:
        """Serialize all metrics data to dictionary."""
        session_end = datetime.now()
        session_duration = (session_end - self.session_start).total_seconds()

        data = {
            "session_info": {
                "session_id": self.session_id,
                "start_time": self.session_start.isoformat(),
                "end_time": session_end.isoformat(),
                "duration_seconds": session_duration,
                "exit_code": self.exit_code,
                "success": self.exit_code == 0 if self.exit_code is not None else None,
                "cli_args": self.cli_args,
            },
            "counters": {},
            "gauges": {},
            "histograms": {},
            "summaries": {},
            "activity_log": self._activity_log[-100:],  # Keep last 100 events
        }

        # Serialize counters
        for name, counter in self._counters.items():
            data["counters"][name] = {  # type: ignore[index]
                "description": counter.description,
                "labelnames": counter.labelnames,
                "values": {
                    str(labels): value for labels, value in counter._values.items()
                },
            }

        # Serialize gauges
        for name, gauge in self._gauges.items():
            data["gauges"][name] = {  # type: ignore[index]
                "description": gauge.description,
                "labelnames": gauge.labelnames,
                "values": {
                    str(labels): value for labels, value in gauge._values.items()
                },
            }

        # Serialize histograms
        for name, histogram in self._histograms.items():
            # Calculate bucket counts and summary stats
            observations = [obs["value"] for obs in histogram._observations]
            bucket_counts = {}
            for bucket in histogram.buckets:
                bucket_counts[str(bucket)] = sum(
                    1 for val in observations if val <= bucket
                )

            data["histograms"][name] = {  # type: ignore[index]
                "description": histogram.description,
                "buckets": histogram.buckets,
                "bucket_counts": bucket_counts,
                "total_count": len(observations),
                "total_sum": sum(observations) if observations else 0,
                "observations": histogram._observations[-50:],  # Keep last 50
            }

        # Serialize summaries
        for name, summary in self._summaries.items():
            observations = [obs["value"] for obs in summary._observations]
            data["summaries"][name] = {  # type: ignore[index]
                "description": summary.description,
                "total_count": len(observations),
                "total_sum": sum(observations) if observations else 0,
                "observations": summary._observations[-50:],  # Keep last 50
            }

        return data


# ============================================================================
# No-Op Metrics Implementation
# ============================================================================


class NoOpMetricsLabeled:
    """No-op labeled metric that does nothing."""

    def inc(self, amount: float = 1) -> None:
        """No-op increment."""
        pass

    def dec(self, amount: float = 1) -> None:
        """No-op decrement."""
        pass

    def set(self, value: float) -> None:
        """No-op set."""
        pass

    def set_to_current_time(self) -> None:
        """No-op set to current time."""
        pass

    def observe(self, value: float) -> None:
        """No-op observe."""
        pass

    @contextmanager
    def time(self) -> Any:
        """No-op time context manager."""
        yield


class NoOpCounter:
    """No-op counter that implements SessionCounter interface."""

    def __init__(
        self, name: str, description: str, labelnames: list[str] | None = None
    ):
        self.name = name
        self.description = description
        self.labelnames = labelnames or []

    def inc(self, amount: float = 1) -> None:
        """No-op increment."""
        if self.labelnames:
            raise ValueError("Counter with labels requires labels() call")

    def labels(self, *args: Any, **kwargs: Any) -> NoOpMetricsLabeled:
        """Return no-op labeled instance."""
        if not self.labelnames:
            raise ValueError("Counter was not declared with labels")

        # Handle both positional and keyword arguments
        if args and kwargs:
            raise ValueError("Cannot mix positional and keyword arguments")

        if args:
            if len(args) != len(self.labelnames):
                raise ValueError(
                    f"Expected {len(self.labelnames)} label values, got {len(args)}"
                )
        elif kwargs:
            # Keyword arguments - ensure all labels are provided
            missing_labels = set(self.labelnames) - set(kwargs.keys())
            if missing_labels:
                raise ValueError(f"Missing label values: {missing_labels}")
        else:
            # No arguments provided - this is like having 0 positional args
            if len(self.labelnames) > 0:
                raise ValueError(f"Expected {len(self.labelnames)} label values, got 0")

        return NoOpMetricsLabeled()


class NoOpGauge:
    """No-op gauge that implements SessionGauge interface."""

    def __init__(
        self, name: str, description: str, labelnames: list[str] | None = None
    ):
        self.name = name
        self.description = description
        self.labelnames = labelnames or []

    def inc(self, amount: float = 1) -> None:
        """No-op increment."""
        pass

    def dec(self, amount: float = 1) -> None:
        """No-op decrement."""
        pass

    def set(self, value: float) -> None:
        """No-op set."""
        pass

    def set_to_current_time(self) -> None:
        """No-op set to current time."""
        pass

    def labels(self, *args: Any, **kwargs: Any) -> NoOpMetricsLabeled:
        """Return no-op labeled instance."""
        if not self.labelnames:
            raise ValueError("Gauge was not declared with labels")

        # Handle both positional and keyword arguments
        if args and kwargs:
            raise ValueError("Cannot mix positional and keyword arguments")

        if args:
            if len(args) != len(self.labelnames):
                raise ValueError(
                    f"Expected {len(self.labelnames)} label values, got {len(args)}"
                )
        elif kwargs:
            # Keyword arguments - ensure all labels are provided
            missing_labels = set(self.labelnames) - set(kwargs.keys())
            if missing_labels:
                raise ValueError(f"Missing label values: {missing_labels}")
        else:
            # No arguments provided - this is like having 0 positional args
            if len(self.labelnames) > 0:
                raise ValueError(f"Expected {len(self.labelnames)} label values, got 0")

        return NoOpMetricsLabeled()


class NoOpHistogram:
    """No-op histogram that implements SessionHistogram interface."""

    def __init__(
        self,
        name: str,
        description: str,
        buckets: list[float] | None = None,
    ):
        self.name = name
        self.description = description
        self.buckets = buckets or []

    def observe(self, value: float) -> None:
        """No-op observe."""
        pass

    @contextmanager
    def time(self) -> Any:
        """No-op time context manager."""
        yield


class NoOpSummary:
    """No-op summary that implements SessionSummary interface."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    def observe(self, value: float) -> None:
        """No-op observe."""
        pass

    @contextmanager
    def time(self) -> Any:
        """No-op time context manager."""
        yield


class NoOpMetrics:
    """No-op metrics that implements SessionMetrics interface."""

    def __init__(self, session_uuid: str):
        self.session_uuid = session_uuid

    def Counter(  # noqa: N802
        self, name: str, description: str, labelnames: list[str] | None = None
    ) -> NoOpCounter:
        """Create a no-op Counter metric."""
        return NoOpCounter(name, description, labelnames)

    def Gauge(  # noqa: N802
        self, name: str, description: str, labelnames: list[str] | None = None
    ) -> NoOpGauge:
        """Create a no-op Gauge metric."""
        return NoOpGauge(name, description, labelnames)

    def Histogram(  # noqa: N802
        self, name: str, description: str, buckets: list[float] | None = None
    ) -> NoOpHistogram:
        """Create a no-op Histogram metric."""
        return NoOpHistogram(name, description, buckets)

    def Summary(self, name: str, description: str) -> NoOpSummary:  # noqa: N802
        """Create a no-op Summary metric."""
        return NoOpSummary(name, description)

    def set_exit_code(self, exit_code: int) -> None:
        """No-op set exit code."""
        pass

    def set_cli_args(self, cli_args: list[str]) -> None:
        """No-op set CLI args."""
        pass

    def save(self) -> None:
        """No-op save."""
        pass

    def record_cache_event(self, cache_type: str, cache_hit: bool) -> None:
        """No-op cache event recording."""
        pass

    def set_context(self, **kwargs: Any) -> None:
        """No-op set context."""
        pass

    @contextmanager
    def time_operation(self, operation_name: str) -> Any:
        """No-op time operation context manager."""
        yield

    def __enter__(self) -> "NoOpMetrics":
        """Enter the context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the context manager."""
        pass


class MetricsContextManager:
    """Context manager for metrics that provides set_context and time_operation methods."""

    def __init__(self, metrics: SessionMetrics | NoOpMetrics):
        self._metrics = metrics

    def set_context(self, **kwargs: Any) -> None:
        """Set context information for metrics (no-op for NoOpMetrics)."""
        pass

    @contextmanager
    def time_operation(self, operation_name: str) -> Any:
        """Time an operation using a histogram (no-op for NoOpMetrics)."""
        if isinstance(self._metrics, SessionMetrics):
            histogram = self._metrics.Histogram(
                f"{operation_name}_duration_seconds", f"{operation_name} duration"
            )
            with histogram.time():
                yield
        else:
            yield

    def __enter__(self) -> "MetricsContextManager":
        """Enter the context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the context manager."""
        if isinstance(self._metrics, SessionMetrics):
            self._metrics.save()


# ============================================================================
# Factory Functions
# ============================================================================


def create_session_metrics(
    session_uuid: str,
    cache_manager: CacheManager | None = None,
    ttl_days: int = 7,
) -> SessionMetrics:
    """Factory function to create SessionMetrics instance.

    Args:
        session_uuid: Unique identifier for this session
        cache_manager: Cache manager instance (if None, creates one with metrics tag)
        ttl_days: Number of days to retain metrics data in cache

    Returns:
        SessionMetrics instance ready for use
    """
    if cache_manager is None:
        # Use shared cache coordination with metrics tag
        from glovebox.core.cache import create_default_cache

        cache_manager = create_default_cache(tag="metrics")

    return SessionMetrics(cache_manager, session_uuid, ttl_days)


def create_noop_session_metrics(session_uuid: str) -> NoOpMetrics:
    """Factory function to create NoOpMetrics instance.

    Args:
        session_uuid: Unique identifier for this session (ignored)

    Returns:
        NoOpMetrics instance that does nothing
    """
    return NoOpMetrics(session_uuid)
