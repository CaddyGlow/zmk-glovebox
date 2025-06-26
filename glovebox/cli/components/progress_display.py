"""Reusable TUI progress display component with terminal resizing support."""

import contextlib
import queue
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any, Generic, Protocol, TypeVar

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
    TimeRemainingColumn,
)
from rich.text import Text


# Type variables for generic progress data
T = TypeVar("T")


class ProgressDataProtocol(Protocol):
    """Protocol for progress data objects."""

    def get_status_text(self) -> str:
        """Get the current status text to display."""
        ...

    def get_progress_info(self) -> tuple[int, int, str]:
        """Get progress information as (current, total, description)."""
        ...


ProgressCallback = Callable[[T], None]


class ProgressDisplayManager(Generic[T]):
    """Reusable TUI progress display manager with full terminal support and resizing.

    This component provides a Rich-based terminal interface that automatically
    adapts to terminal size changes and displays progress with optional log streaming.

    Features:
    - Full terminal width/height utilization
    - Automatic terminal resize detection and adaptation
    - Real-time log streaming with intelligent wrapping
    - Customizable progress bar and status display
    - Thread-safe progress updates via queue
    - Clean lifecycle management with proper cleanup
    """

    def __init__(
        self,
        show_logs: bool = True,
        refresh_rate: int = 8,
        max_log_lines: int = 100,
        console: Console | None = None,
    ) -> None:
        """Initialize the progress display manager.

        Args:
            show_logs: Whether to show log panel alongside progress
            refresh_rate: Screen refresh rate in FPS for smooth resizing
            max_log_lines: Maximum number of log lines to keep in memory
            console: Optional Rich console instance (creates new if None)
        """
        self.show_logs = show_logs
        self.refresh_rate = refresh_rate
        self.max_log_lines = max_log_lines
        self.console = console or Console()

        # Progress tracking
        self.progress_queue: queue.Queue[T] = queue.Queue()
        self.stop_event = threading.Event()
        self.recent_logs: deque[tuple[str, str]] = deque(maxlen=max_log_lines)

        # Display state
        self.current_status = "Initializing..."
        self.current_progress = 0
        self.total_progress = 100
        self.progress_description = "Starting..."

        # Threading
        self.worker_thread: threading.Thread | None = None
        self.start_time = time.time()

    def start(self) -> ProgressCallback[T]:
        """Start the progress display and return a callback for updates.

        Returns:
            Callback function to call with progress updates
        """
        if self.worker_thread is not None:
            raise RuntimeError("Progress display is already running")

        self.stop_event.clear()
        self.start_time = time.time()

        # Start the async worker thread
        self.worker_thread = threading.Thread(
            target=self._async_progress_worker, daemon=True
        )
        self.worker_thread.start()

        # Return progress callback
        def progress_callback(progress_data: T) -> None:
            """Progress callback that queues updates for async processing."""
            with contextlib.suppress(queue.Full):
                self.progress_queue.put(progress_data, timeout=1.0)

        # Store cleanup function for later use
        progress_callback.cleanup = self.stop  # type: ignore[attr-defined]

        return progress_callback

    def add_log(self, level: str, message: str) -> None:
        """Add a log message to the TUI display.

        Args:
            level: Log level (debug, info, warning, error, critical)
            message: Log message to display
        """
        # Add log to recent_logs deque (thread-safe)
        self.recent_logs.append((level, message))

    def stop(self) -> None:
        """Stop the progress display and clean up resources."""
        if self.worker_thread is None:
            return

        self.stop_event.set()
        self.worker_thread.join(timeout=2.0)
        self.worker_thread = None

        # Show completion summary
        total_time = time.time() - self.start_time
        self.console.print(
            f"[bold cyan]🎉 Operation completed in {total_time:.1f}s[/bold cyan]"
        )

    def _wrap_text_to_width(self, text: str, width: int) -> list[str]:
        """Wrap text to fit within specified width."""
        if width <= 10:  # Prevent degenerate cases
            return [text[:width] if text else ""]

        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            test_line = f"{current_line} {word}".strip()
            if len(test_line) <= width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                # Handle very long words
                if len(word) > width:
                    lines.append(word[: width - 3] + "...")
                    current_line = ""
                else:
                    current_line = word

        if current_line:
            lines.append(current_line)

        return lines if lines else [""]

    def _create_log_panel(self) -> Panel:
        """Create a responsive panel showing recent logs with proper overflow handling."""
        # Get current terminal dimensions
        terminal_width = self.console.size.width
        terminal_height = self.console.size.height

        # Calculate available space for logs (more conservative height calculation)
        progress_bars_height = 6  # Space for progress bars and status text (increased)
        panel_border_height = 4  # Top/bottom border + title + padding (increased)
        min_log_height = 8  # Minimum height for log panel (increased)

        # More conservative height calculation to prevent overflow
        available_height = terminal_height - progress_bars_height - panel_border_height
        max_log_height = max(
            min_log_height, min(available_height, 20)
        )  # Cap at 20 lines max

        # Content width (accounting for panel borders and padding)
        content_width = max(40, terminal_width - 6)  # More margin for panel borders

        if not self.recent_logs:
            log_content: Group | Text = Text("Waiting for logs...", style="dim")
        else:
            log_lines: list[Text] = []
            # Calculate available lines inside the panel (subtract borders and title)
            available_lines = max_log_height - 3  # Account for borders and title
            lines_used = 0

            # Process logs from most recent, working backwards
            recent_logs_list = list(self.recent_logs)
            if len(recent_logs_list) > 100:  # Limit to most recent 100 logs
                recent_logs_list = recent_logs_list[-100:]

            # Process logs in reverse order to show most recent first
            for level, message in reversed(
                recent_logs_list[-50:]
            ):  # Show last 50 logs max
                if (
                    lines_used >= available_lines - 1
                ):  # Reserve 1 line for overflow indicator
                    break

                # Style logs based on level
                if level == "warning":
                    style = "yellow"
                elif level == "error":
                    style = "red"
                else:
                    style = "white"

                # Wrap long lines to fit panel width
                wrapped_lines = self._wrap_text_to_width(message, content_width)

                # Add wrapped lines, checking available space
                for wrapped_line in wrapped_lines:
                    if lines_used >= available_lines - 1:
                        break
                    log_lines.insert(
                        0, Text(wrapped_line, style=style)
                    )  # Insert at beginning for reverse order
                    lines_used += 1

            # Add overflow indicator if we have more logs
            if (
                len(recent_logs_list) > lines_used or lines_used >= available_lines - 1
            ) and log_lines:
                log_lines.append(Text("... (more logs available)", style="dim italic"))

            log_content = (
                Group(*log_lines)
                if log_lines
                else Text("Waiting for logs...", style="dim")
            )

        return Panel(
            log_content,
            title=f"[bold blue]Logs[/bold blue] ({len(self.recent_logs)} total)",
            border_style="blue",
            height=max_log_height,
            width=terminal_width - 2,  # Full width minus small margin
            padding=(0, 1),  # Add padding inside panel
        )

    def _create_responsive_layout(
        self, progress: Progress, current_file_text: Text
    ) -> Group:
        """Create layout that adapts to current terminal size."""
        terminal_width = self.console.size.width
        terminal_height = self.console.size.height

        # Create status text that fits the terminal width
        status_text = Text(current_file_text.plain, style=current_file_text.style)
        if len(status_text.plain) > terminal_width - 4:
            # Truncate long status messages
            truncated = status_text.plain[: terminal_width - 7] + "..."
            status_text = Text(truncated, style=current_file_text.style)

        if self.show_logs:
            # Ensure we don't try to show logs if terminal is too small
            if terminal_height < 12:
                # Terminal too small for logs, just show progress
                return Group(status_text, progress)
            else:
                log_panel = self._create_log_panel()
                return Group(status_text, progress, log_panel)
        else:
            return Group(status_text, progress)

    def _update_progress_from_data(
        self, progress_data: T, progress: Progress, task_id: Any
    ) -> Text:
        """Update progress from data object. Override this method for custom progress types."""
        # Default implementation assumes progress_data has these methods
        if hasattr(progress_data, "get_status_text"):
            status = progress_data.get_status_text()
            current_file_text = Text(status, style="cyan")
        else:
            current_file_text = Text(str(progress_data), style="cyan")

        if hasattr(progress_data, "get_progress_info"):
            current, total, description = progress_data.get_progress_info()
            progress.update(
                task_id, completed=current, total=total, description=description
            )

        return current_file_text

    def _async_progress_worker(self) -> None:
        """Worker thread for async progress updates with dynamic terminal sizing."""
        # Create Rich progress display with dynamic width
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=None),  # Let Rich auto-size the bar
            MofNCompleteColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("•"),
            TimeRemainingColumn(),
            expand=True,  # Use full width available
        )

        # Create task for progress tracking
        task_id = progress.add_task(
            self.progress_description, total=self.total_progress
        )

        # Initialize display components
        current_file_text = Text(self.current_status, style="cyan")

        progress_group = self._create_responsive_layout(progress, current_file_text)

        with Live(
            progress_group, console=self.console, refresh_per_second=self.refresh_rate
        ) as live:
            last_terminal_size = (self.console.size.width, self.console.size.height)
            last_layout_update = time.time()

            while not self.stop_event.is_set():
                try:
                    # Get progress update with timeout
                    progress_data = self.progress_queue.get(timeout=0.1)

                    # Update display from progress data
                    current_file_text = self._update_progress_from_data(
                        progress_data, progress, task_id
                    )

                    # Note: Logs are now added directly via add_log() method from TUI handler

                    # Always recreate the layout to handle terminal resizing
                    progress_group = self._create_responsive_layout(
                        progress, current_file_text
                    )
                    live.update(progress_group)

                except queue.Empty:
                    # Check for terminal resize even when no progress updates
                    current_terminal_size = (
                        self.console.size.width,
                        self.console.size.height,
                    )
                    current_time = time.time()

                    # Update layout if terminal size changed or every 2 seconds for log updates
                    if (
                        current_terminal_size != last_terminal_size
                        or current_time - last_layout_update > 2.0
                    ):
                        last_terminal_size = current_terminal_size
                        last_layout_update = current_time

                        # Note: Logs are now added directly via add_log() method from TUI handler

                        progress_group = self._create_responsive_layout(
                            progress, current_file_text
                        )
                        live.update(progress_group)
                    continue
                except Exception as e:
                    self.console.print(f"[red]Progress display error: {e}[/red]")
                    break


class WorkspaceProgressDisplayManager(ProgressDisplayManager[Any]):
    """Specialized progress display manager for workspace operations.

    This class extends the base ProgressDisplayManager with workspace-specific
    progress parsing and display logic for file copying operations.
    """

    def _update_progress_from_data(
        self, copy_progress: Any, progress: Progress, task_id: Any
    ) -> Text:
        """Update progress display from CopyProgress data."""
        # Handle workspace copy progress updates
        if hasattr(copy_progress, "current_file"):
            # Format the current file display with component info
            component_info = (
                f" ({copy_progress.component_name})"
                if hasattr(copy_progress, "component_name")
                and copy_progress.component_name
                else ""
            )
            current_file_text = Text(
                f"📄 Copying: {copy_progress.current_file}{component_info}",
                style="cyan",
            )

            # Update progress bar with file and byte information
            if hasattr(copy_progress, "total_bytes") and copy_progress.total_bytes > 0:
                # Use bytes as primary progress metric
                progress.update(
                    task_id,
                    completed=copy_progress.bytes_copied,
                    total=copy_progress.total_bytes,
                    description=f"Copying {copy_progress.files_processed}/{copy_progress.total_files} files",
                )
            else:
                # Fall back to file count if bytes not available
                progress.update(
                    task_id,
                    completed=copy_progress.files_processed,
                    total=copy_progress.total_files,
                    description="Copying files",
                )
        else:
            # Fallback for non-workspace progress
            current_file_text = Text(str(copy_progress), style="cyan")

        return current_file_text


class CompilationProgressDisplayManager(ProgressDisplayManager[Any]):
    """Specialized progress display manager for compilation progress.

    This class extends the base ProgressDisplayManager with compilation-specific
    progress parsing and display logic.
    """

    def _update_progress_from_data(
        self, compilation_progress: Any, progress: Progress, task_id: Any
    ) -> Text:
        """Update progress display from CompilationProgress data."""
        # Handle compilation-specific progress updates
        if hasattr(compilation_progress, "compilation_phase"):
            if compilation_progress.compilation_phase == "initialization":
                current_file_text = Text(
                    f"⚙️ Setup: {compilation_progress.current_repository}",
                    style="blue",
                )
                progress.update(
                    task_id,
                    completed=compilation_progress.repositories_downloaded,
                    total=compilation_progress.total_repositories,
                    description=f"Initializing ({compilation_progress.compilation_phase})",
                )
            elif compilation_progress.compilation_phase == "cache_restoration":
                current_file_text = Text(
                    f"💾 Cache: {compilation_progress.current_repository}",
                    style="green",
                )
                if (
                    hasattr(compilation_progress, "total_bytes")
                    and compilation_progress.total_bytes > 0
                ):
                    # Show bytes progress for cache restoration
                    progress.update(
                        task_id,
                        completed=compilation_progress.bytes_downloaded,
                        total=compilation_progress.total_bytes,
                        description=f"Restoring Cache ({compilation_progress.compilation_phase})",
                    )
                else:
                    # Fallback to percentage progress
                    progress.update(
                        task_id,
                        completed=compilation_progress.repositories_downloaded,
                        total=compilation_progress.total_repositories,
                        description=f"Restoring Cache ({compilation_progress.compilation_phase})",
                    )
            elif compilation_progress.compilation_phase == "workspace_setup":
                current_file_text = Text(
                    f"🗂️ Workspace: {compilation_progress.current_repository}",
                    style="magenta",
                )
                # Use bytes progress if available, otherwise fallback to percentage
                if (
                    hasattr(compilation_progress, "total_bytes")
                    and compilation_progress.total_bytes > 0
                ):
                    progress.update(
                        task_id,
                        completed=compilation_progress.bytes_downloaded or 0,
                        total=compilation_progress.total_bytes,
                        description=f"Setting up Workspace ({compilation_progress.compilation_phase})",
                    )
                else:
                    progress.update(
                        task_id,
                        completed=50,  # Arbitrary progress for workspace setup
                        total=100,
                        description=f"Setting up Workspace ({compilation_progress.compilation_phase})",
                    )
            elif compilation_progress.compilation_phase == "west_update":
                current_file_text = Text(
                    f"📦 Downloading: {compilation_progress.current_repository}",
                    style="cyan",
                )
                progress.update(
                    task_id,
                    completed=compilation_progress.repositories_downloaded,
                    total=compilation_progress.total_repositories,
                    description=f"West Update ({compilation_progress.compilation_phase})",
                )
            elif compilation_progress.compilation_phase == "building":
                # Enhanced building display with board information
                if (
                    hasattr(compilation_progress, "total_boards")
                    and compilation_progress.total_boards > 1
                ):
                    # Multi-board display
                    board_info = f"({compilation_progress.boards_completed + 1}/{compilation_progress.total_boards})"
                    if compilation_progress.current_board:
                        current_file_text = Text(
                            f"🔨 Building: {compilation_progress.current_board} {board_info}",
                            style="yellow",
                        )
                    else:
                        current_file_text = Text(
                            f"🔨 Building: {compilation_progress.current_repository}",
                            style="yellow",
                        )

                    # Use overall progress for multi-board builds
                    progress.update(
                        task_id,
                        completed=compilation_progress.overall_progress_percent,
                        total=100,
                        description=f"Building {board_info}",
                    )
                else:
                    # Single board display (original behavior)
                    current_file_text = Text(
                        f"🔨 Building: {compilation_progress.current_repository}",
                        style="yellow",
                    )
                    progress.update(
                        task_id,
                        description=f"Compiling ({compilation_progress.compilation_phase})",
                    )
            elif compilation_progress.compilation_phase == "collecting":
                current_file_text = Text(
                    f"📁 Collecting: {compilation_progress.current_repository}",
                    style="green",
                )
                progress.update(
                    task_id,
                    description=f"Collecting Artifacts ({compilation_progress.compilation_phase})",
                )
            else:
                # Fallback for unknown phases
                current_file_text = Text(
                    f"⚙️ {compilation_progress.current_repository}", style="white"
                )
        else:
            # Fallback for non-compilation progress
            current_file_text = Text(str(compilation_progress), style="cyan")

        return current_file_text


def create_compilation_progress_display(
    show_logs: bool = True,
) -> Callable[[Any], None]:
    """Factory function to create a compilation progress display (backward compatibility).

    Args:
        show_logs: Whether to show logs alongside progress

    Returns:
        Progress callback function with cleanup method
    """
    manager = CompilationProgressDisplayManager(show_logs=show_logs)
    return manager.start()


def create_workspace_progress_display(show_logs: bool = False) -> Callable[[Any], None]:
    """Factory function to create a workspace progress display.

    Args:
        show_logs: Whether to show logs alongside progress (defaults to False for workspace operations)

    Returns:
        Progress callback function with cleanup method
    """
    manager = WorkspaceProgressDisplayManager(show_logs=show_logs)
    return manager.start()
