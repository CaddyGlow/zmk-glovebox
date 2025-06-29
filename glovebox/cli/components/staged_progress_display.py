"""Staged progress display component for compilation operations."""

import queue
import threading
import time
from collections.abc import Callable
from typing import Any

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.text import Text

from glovebox.core.file_operations.models import CompilationProgress


class StagedCompilationProgressDisplay:
    """Displays compilation progress with staged build visualization.

    Shows a cool staged progress display like:
    🔧 Setting up build environment... ✓
    📦 Resolving dependencies... ✓
    ⚙️ Compiling firmware... ████████░░ 80%
    🔗 Linking binaries... (pending)
    📱 Generating .uf2 files... (pending)
    """

    def __init__(
        self,
        console: Console | None = None,
        refresh_rate: int = 8,
        show_logs: bool = True,
        max_log_lines: int = 10,
    ) -> None:
        """Initialize the staged progress display.

        Args:
            console: Optional Rich console instance
            refresh_rate: Screen refresh rate in FPS
            show_logs: Whether to show compilation logs above the progress
            max_log_lines: Maximum number of log lines to display
        """
        self.console = console or Console()
        self.refresh_rate = refresh_rate
        self.show_logs = show_logs
        self.max_log_lines = max_log_lines

        # Progress tracking
        self.progress_queue: queue.Queue[CompilationProgress] = queue.Queue()
        self.stop_event = threading.Event()
        self.worker_thread: threading.Thread | None = None
        self.start_time = time.time()

        # Current progress state
        self.current_progress: CompilationProgress | None = None

        # Log storage
        self.log_lines: list[str] = []

    def start(self) -> Callable[[CompilationProgress], None]:
        """Start the staged progress display and return a callback for updates.

        Returns:
            Callback function to call with CompilationProgress updates
        """
        if self.worker_thread is not None:
            raise RuntimeError("Staged progress display is already running")

        self.stop_event.clear()
        self.start_time = time.time()

        # Start the display worker thread
        self.worker_thread = threading.Thread(
            target=self._async_progress_worker, daemon=True
        )
        self.worker_thread.start()

        return self._progress_callback

    def stop(self) -> None:
        """Stop the progress display and clean up resources."""
        if self.worker_thread is None:
            return

        self.stop_event.set()
        self.worker_thread.join(timeout=2.0)
        self.worker_thread = None

    def _progress_callback(self, progress_data: CompilationProgress) -> None:
        """Callback for progress updates."""
        self.progress_queue.put(progress_data)

    def add_log_line(self, line: str) -> None:
        """Add a log line to the display."""
        if self.show_logs:
            # Clean up the line and add timestamp
            clean_line = line.strip()
            if clean_line:
                timestamp = time.strftime("%H:%M:%S")
                formatted_line = f"[dim]{timestamp}[/dim] {clean_line}"
                self.log_lines.append(formatted_line)

                # Keep only the most recent lines
                if len(self.log_lines) > self.max_log_lines:
                    self.log_lines = self.log_lines[-self.max_log_lines :]

    def _create_staged_display(self, progress_data: CompilationProgress) -> Group:
        """Create the staged progress display layout."""
        # Get staged progress display
        staged_lines = progress_data.get_staged_progress_display().split("\n")

        # Create Rich Text objects for each stage
        stage_texts = []
        for line in staged_lines:
            if "✓" in line:
                stage_texts.append(Text(line, style="green"))
            elif "%" in line or "█" in line:
                stage_texts.append(Text(line, style="yellow"))
            else:
                stage_texts.append(Text(line, style="dim"))

        # Create overall progress bar
        overall_progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Overall Progress"),
            BarColumn(bar_width=40),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=self.console,
        )

        overall_task = overall_progress.add_task(
            "Building", completed=int(progress_data.overall_progress_percent), total=100
        )

        # Additional status info for multi-board builds
        status_lines = []
        if progress_data.total_boards > 1:
            status_lines.append(
                Text(
                    f"Building {progress_data.total_boards} boards: "
                    f"{progress_data.boards_completed} completed, "
                    f"{progress_data.boards_remaining} remaining",
                    style="blue",
                )
            )

        if progress_data.current_board:
            status_lines.append(
                Text(f"Current board: {progress_data.current_board}", style="cyan")
            )

        # Combine all elements
        display_elements: list[Any] = []

        # Get terminal width for proper sizing
        terminal_width = min(120, self.console.size.width)  # Cap at 120 chars

        # Add log panel if logs are enabled and we have logs
        if self.show_logs and self.log_lines:
            log_panel = Panel(
                Group(*[Text.from_markup(line) for line in self.log_lines]),
                title="[bold]Build Output",
                border_style="green",
                padding=(0, 1),
                width=terminal_width,
                height=min(self.max_log_lines + 2, len(self.log_lines) + 2),
            )
            display_elements.append(log_panel)

        # Add stage display in a panel
        stage_panel = Panel(
            Group(*stage_texts),
            title="[bold]Build Stages",
            border_style="blue",
            padding=(0, 1),
            width=terminal_width,
        )
        display_elements.append(stage_panel)

        # Add overall progress
        display_elements.append(overall_progress)

        # Add status info if available
        if status_lines:
            display_elements.extend(status_lines)

        return Group(*display_elements)

    def _async_progress_worker(self) -> None:
        """Worker thread for staged progress display updates."""
        last_progress: CompilationProgress | None = None
        last_update_time = 0
        last_display_hash: str | None = None

        with Live(
            Text("Initializing build...", style="cyan"),
            console=self.console,
            refresh_per_second=1,  # Reduce refresh rate further to prevent conflicts
            transient=False,
            auto_refresh=True,
        ) as live:
            while not self.stop_event.is_set():
                try:
                    # Get the latest progress update (non-blocking)
                    progress_data = self.progress_queue.get(timeout=0.5)

                    # Skip duplicate updates based on phase and progress to prevent panel conflicts
                    current_display_hash = f"{progress_data.compilation_phase}_{progress_data.overall_progress_percent}_{progress_data.current_board}_{progress_data.boards_completed}"
                    if current_display_hash == last_display_hash:
                        continue

                    last_progress = progress_data
                    self.current_progress = progress_data
                    last_display_hash = current_display_hash

                    # Throttle updates to prevent display flashing (max 1 update per second)
                    # But allow immediate updates for completion states
                    current_time = time.time()
                    is_completion_state = progress_data.compilation_phase in ["done", "completed", "finished", "success"]

                    if not is_completion_state and current_time - last_update_time < 1.0:
                        continue

                    last_update_time = current_time

                    # Update the display with staged progress
                    display = self._create_staged_display(progress_data)
                    live.update(display)

                except queue.Empty:
                    # No new updates, continue with current display
                    continue
                except Exception as e:
                    # Log error but continue
                    self.console.print(f"[red]Display error: {e}")
                    continue

        # Do not print final display to avoid duplication - the Live display already shows the final state


def create_staged_compilation_progress_display(
    console: Console | None = None,
    refresh_rate: int = 2,  # Reduced default refresh rate
    show_logs: bool = True,
    max_log_lines: int = 8,  # Reduced default log lines
) -> StagedCompilationProgressDisplay:
    """Factory function to create a staged compilation progress display.

    Args:
        console: Optional Rich console instance
        refresh_rate: Screen refresh rate in FPS
        show_logs: Whether to show compilation logs above the progress
        max_log_lines: Maximum number of log lines to display

    Returns:
        Configured StagedCompilationProgressDisplay instance
    """
    return StagedCompilationProgressDisplay(
        console=console,
        refresh_rate=refresh_rate,
        show_logs=show_logs,
        max_log_lines=max_log_lines,
    )
