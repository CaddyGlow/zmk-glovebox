"""System information widget with live metrics."""

import os
import platform
from datetime import datetime

import psutil
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import ProgressBar, Static


class SystemInfo(Vertical):
    """Widget for displaying system information and metrics."""

    cpu_percent: reactive[float] = reactive(0.0)
    memory_percent: reactive[float] = reactive(0.0)

    def compose(self) -> ComposeResult:
        """Compose the system info layout."""
        yield Static("[bold cyan]System Information[/bold cyan]")
        yield Static("")  # spacer

        # Static system information
        yield Static(f"OS: {platform.system()} {platform.release()}")
        yield Static(f"Python: {platform.python_version()}")
        yield Static(f"Architecture: {platform.machine()}")

        try:
            term_size = os.get_terminal_size()
            terminal_info = f"Terminal: {term_size.columns}x{term_size.lines}"
        except (OSError, AttributeError):
            terminal_info = "Terminal: N/A"
        yield Static(terminal_info)
        yield Static(f"TMUX: {'Yes' if os.environ.get('TMUX') else 'No'}")

        yield Static("")  # spacer
        yield Static("[bold yellow]Live Metrics[/bold yellow]")

        # Live metrics
        yield Static("CPU Usage:")
        yield ProgressBar(
            total=100, show_eta=False, show_percentage=True, id="cpu-progress"
        )
        yield Static("Memory Usage:")
        yield ProgressBar(
            total=100, show_eta=False, show_percentage=True, id="memory-progress"
        )
        yield Static("", id="uptime-info")

    def on_mount(self) -> None:
        """Initialize system monitoring when mounted."""
        self.cpu_progress = self.query_one("#cpu-progress", ProgressBar)
        self.memory_progress = self.query_one("#memory-progress", ProgressBar)
        self.uptime_info = self.query_one("#uptime-info", Static)

        # Start periodic updates
        self.update_timer = self.set_interval(2.0, self.update_metrics)
        self.update_metrics()

    def update_metrics(self) -> None:
        """Update system metrics."""
        try:
            # Update CPU usage
            self.cpu_percent = psutil.cpu_percent(interval=None)
            self.cpu_progress.advance(self.cpu_percent - self.cpu_progress.progress)

            # Update memory usage
            memory = psutil.virtual_memory()
            self.memory_percent = memory.percent
            self.memory_progress.advance(
                self.memory_percent - self.memory_progress.progress
            )

            # Update uptime
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            days = uptime.days
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            self.uptime_info.update(f"Uptime: {days}d {hours}h {minutes}m")

        except Exception as e:
            # Handle any errors gracefully
            pass

    def watch_cpu_percent(self, cpu_percent: float) -> None:
        """React to CPU percentage changes."""
        if hasattr(self, "cpu_progress"):
            self.cpu_progress.progress = cpu_percent

    def watch_memory_percent(self, memory_percent: float) -> None:
        """React to memory percentage changes."""
        if hasattr(self, "memory_progress"):
            self.memory_progress.progress = memory_percent
