"""Base protocol for progress displays."""

from __future__ import annotations

from typing import Any, Protocol

from glovebox.cli.progress.models import ProgressContext


class ProgressDisplayProtocol(Protocol):
    """Protocol for progress display components."""

    def __enter__(self) -> ProgressDisplayProtocol:
        """Enter context manager."""
        ...

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager."""
        ...

    def start(self) -> None:
        """Start the display."""
        ...

    def stop(self) -> None:
        """Stop the display."""
        ...

    def update(self) -> None:
        """Update the display with current context state."""
        ...

    def get_context(self) -> ProgressContext:
        """Get the progress context."""
        ...
