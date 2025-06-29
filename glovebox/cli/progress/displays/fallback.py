"""Fallback progress display for when Rich Live is already in use."""

from __future__ import annotations

import threading
import time
from typing import Any

from rich.console import Console

from glovebox.cli.progress.displays.base import ProgressDisplayProtocol
from glovebox.cli.progress.log_handler import LogBuffer
from glovebox.cli.progress.models import ProgressContext


class FallbackProgressDisplay:
    """Fallback progress display that works when Rich Live is already active."""

    def __init__(self, context: ProgressContext) -> None:
        """Initialize fallback display."""
        self.context = context
        self.console = Console()
        self.log_buffer = LogBuffer(max_lines=context.display_config.max_log_lines)
        self._stop_event = threading.Event()
        self._update_thread: threading.Thread | None = None
        self._last_log_count = 0

    def __enter__(self) -> ProgressDisplayProtocol:
        """Enter context manager."""
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager."""
        self.stop()

    def start(self) -> None:
        """Start the fallback display."""
        # Setup log capture
        self.log_buffer.setup_handler("glovebox")
        
        # Print initial header
        self.console.print("📋 [bold blue]Compilation Progress[/bold blue] (Live logs below)")
        self.console.print("─" * 60)
        
        # Start background thread to print new logs
        self._stop_event.clear()
        self._update_thread = threading.Thread(target=self._update_logs_continuously, daemon=True)
        self._update_thread.start()

        # Setup callbacks
        self._setup_callbacks()

    def stop(self) -> None:
        """Stop the fallback display."""
        # Stop the update thread
        if self._update_thread:
            self._stop_event.set()
            self._update_thread.join(timeout=1.0)
        
        # Print final logs
        self._print_new_logs()
        
        # Print completion
        self.console.print("─" * 60)
        self.console.print("✅ [bold green]Operation completed[/bold green]")
        
        # Cleanup log handler
        self.log_buffer.cleanup()

    def update(self) -> None:
        """Update the display (no-op for fallback)."""
        pass

    def get_context(self) -> ProgressContext:
        """Get the progress context."""
        return self.context

    def _update_logs_continuously(self) -> None:
        """Continuously print new logs in background thread."""
        while not self._stop_event.is_set():
            self._print_new_logs()
            time.sleep(0.5)  # Check for new logs every 500ms

    def _print_new_logs(self) -> None:
        """Print any new logs that have appeared."""
        current_logs = self.log_buffer.get_recent_logs(count=1000)
        new_log_count = len(current_logs)
        
        if new_log_count > self._last_log_count:
            # Print only the new logs
            new_logs = current_logs[self._last_log_count:]
            for log_line in new_logs:
                style = self.log_buffer.get_log_style(log_line)
                self.console.print(f"  {log_line}", style=style)
            
            self._last_log_count = new_log_count

    def _setup_callbacks(self) -> None:
        """Setup callbacks to update display on progress changes."""
        original_on_progress = self.context.callbacks.on_progress_update
        original_on_workspace = self.context.callbacks.on_workspace_update

        def update_callback(*args: Any) -> None:
            # For fallback display, just trigger log check
            if original_on_progress:
                original_on_progress(*args)

        def workspace_callback(*args: Any) -> None:
            # For fallback display, just trigger log check  
            if original_on_workspace:
                original_on_workspace(*args)

        self.context.callbacks.on_progress_update = update_callback
        self.context.callbacks.on_workspace_update = workspace_callback