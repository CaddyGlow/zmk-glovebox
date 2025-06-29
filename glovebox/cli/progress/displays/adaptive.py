"""Adaptive progress display that automatically handles Rich Live conflicts."""

from __future__ import annotations

from typing import Any

from glovebox.cli.progress.displays.base import ProgressDisplayProtocol
from glovebox.cli.progress.models import ProgressContext


class AdaptiveProgressDisplay:
    """Adaptive display that chooses the best available option."""

    def __init__(self, context: ProgressContext) -> None:
        """Initialize adaptive display."""
        self.context = context
        self._actual_display: Any = None

    def __enter__(self) -> ProgressDisplayProtocol:
        """Enter context manager."""
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager."""
        self.stop()

    def start(self) -> None:
        """Start the display, choosing the best available option."""
        # Try staged with logs first
        try:
            from glovebox.cli.progress.displays.staged_with_logs import StagedProgressWithLogsDisplay
            
            self._actual_display = StagedProgressWithLogsDisplay(self.context)
            self._actual_display.start()
            
        except Exception as e:
            if "live display" in str(e).lower() or "LiveError" in str(type(e)):
                # Rich Live conflict - use fallback
                from glovebox.cli.progress.displays.fallback import FallbackProgressDisplay
                
                self._actual_display = FallbackProgressDisplay(self.context)
                self._actual_display.start()
            else:
                # Unexpected error - use simple fallback
                from glovebox.cli.progress.displays.simple import SimpleProgressDisplay
                
                self._actual_display = SimpleProgressDisplay(self.context)
                self._actual_display.start()

    def stop(self) -> None:
        """Stop the actual display."""
        if self._actual_display:
            self._actual_display.stop()

    def update(self) -> None:
        """Update the actual display."""
        if self._actual_display:
            self._actual_display.update()

    def get_context(self) -> ProgressContext:
        """Get the progress context."""
        return self.context