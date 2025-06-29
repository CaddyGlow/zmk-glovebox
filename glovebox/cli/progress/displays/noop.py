"""No-op progress display for silent operations."""

from __future__ import annotations

from typing import Any

from glovebox.cli.progress.displays.base import ProgressDisplayProtocol
from glovebox.cli.progress.models import ProgressContext


class NoOpProgressDisplay:
    """No-op progress display that doesn't show anything."""

    def __init__(self, context: ProgressContext) -> None:
        """Initialize no-op display."""
        self.context = context

    def __enter__(self) -> ProgressDisplayProtocol:
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager."""
        pass

    def start(self) -> None:
        """Start display (no-op)."""
        pass

    def stop(self) -> None:
        """Stop display (no-op)."""
        pass

    def update(self) -> None:
        """Update display (no-op)."""
        pass

    def get_context(self) -> ProgressContext:
        """Get the progress context."""
        return self.context
