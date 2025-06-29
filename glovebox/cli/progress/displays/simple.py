"""Simple progress display using basic console output."""

from __future__ import annotations

import sys
from typing import Any

from glovebox.cli.progress.displays.base import ProgressDisplayProtocol
from glovebox.cli.progress.models import ProgressContext


class SimpleProgressDisplay:
    """Simple progress display using console output."""

    def __init__(self, context: ProgressContext) -> None:
        """Initialize simple display."""
        self.context = context
        self._last_status = ""

    def __enter__(self) -> ProgressDisplayProtocol:
        """Enter context manager."""
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager."""
        self.stop()

    def start(self) -> None:
        """Start the display."""
        # Setup callbacks to update on progress changes
        original_on_progress = self.context.callbacks.on_progress_update
        original_on_workspace = self.context.callbacks.on_workspace_update

        def update_callback(*args: Any) -> None:
            self.update()
            if original_on_progress:
                original_on_progress(*args)

        def workspace_callback(*args: Any) -> None:
            self.update()
            if original_on_workspace:
                original_on_workspace(*args)

        self.context.callbacks.on_progress_update = update_callback
        self.context.callbacks.on_workspace_update = workspace_callback

    def stop(self) -> None:
        """Stop the display."""
        if self._last_status:
            print()  # Add final newline

    def update(self) -> None:
        """Update the display with current status."""
        current_status = self.context.get_current_status()

        if current_status != self._last_status:
            # Clear previous line and print new status
            if self._last_status:
                print(f"\r{' ' * len(self._last_status)}\r", end="")

            print(f"{current_status}", end="", flush=True)
            self._last_status = current_status

    def get_context(self) -> ProgressContext:
        """Get the progress context."""
        return self.context
