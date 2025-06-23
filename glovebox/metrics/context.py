"""Thread-local context for metrics session tracking."""

import threading
from typing import Any


class MetricsContext:
    """Thread-local context for storing metrics information."""

    def __init__(self) -> None:
        """Initialize thread-local storage."""
        self._local = threading.local()

    def set_session_id(self, session_id: str | None) -> None:
        """Set the current session ID for this thread.

        Args:
            session_id: Session ID to set
        """
        self._local.session_id = session_id

    def get_session_id(self) -> str | None:
        """Get the current session ID for this thread.

        Returns:
            Current session ID or None if not set
        """
        return getattr(self._local, "session_id", None)

    def clear(self) -> None:
        """Clear all context for this thread."""
        if hasattr(self._local, "session_id"):
            delattr(self._local, "session_id")

    def set_context(self, **context: Any) -> None:
        """Set additional context for this thread.

        Args:
            **context: Key-value pairs to store in context
        """
        for key, value in context.items():
            setattr(self._local, key, value)

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get context value for this thread.

        Args:
            key: Context key to retrieve
            default: Default value if key not found

        Returns:
            Context value or default
        """
        return getattr(self._local, key, default)


# Global instance for metrics context
metrics_context = MetricsContext()


def get_current_session_id() -> str | None:
    """Get the current session ID from thread-local context.

    Returns:
        Current session ID or None if not set
    """
    return metrics_context.get_session_id()


def set_current_session_id(session_id: str | None) -> None:
    """Set the current session ID in thread-local context.

    Args:
        session_id: Session ID to set
    """
    metrics_context.set_session_id(session_id)


def clear_metrics_context() -> None:
    """Clear all metrics context for the current thread."""
    metrics_context.clear()
