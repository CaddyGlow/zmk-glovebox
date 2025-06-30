"""Simple Rich-based compilation progress display."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table
from rich.text import Text

from glovebox.compilation.models.progress import CompilationProgress, CompilationState
from glovebox.protocols.progress_coordinator_protocol import ProgressCoordinatorProtocol


if TYPE_CHECKING:
    from glovebox.adapters.compilation_progress_middleware import (
        CompilationProgressMiddleware,
    )

logger = logging.getLogger(__name__)


class SimpleCompilationDisplay:
    """Simple Rich-based compilation progress display with task status indicators."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize the simple compilation display.

        Args:
            console: Rich console for output. If None, creates a new one.
        """
        self.console = console or Console()
        self._live: Live | None = None
        self._progress: Progress | None = None
        self._current_task_id: int | None = None

        # Task states
        self._tasks = {
            CompilationState.CACHE_SETUP: {"name": "Cache Setup", "status": "pending"},
            CompilationState.WORKSPACE_SETUP: {
                "name": "Workspace Setup",
                "status": "pending",
            },
            CompilationState.DEPENDENCY_FETCH: {
                "name": "Dependencies",
                "status": "pending",
            },
            CompilationState.BUILDING: {
                "name": "Building Firmware",
                "status": "pending",
            },
            CompilationState.POST_PROCESSING: {
                "name": "Post Processing",
                "status": "pending",
            },
        }

        self._current_state = CompilationState.IDLE
        self._current_description = ""
        self._start_time = time.time()

    def start(self) -> None:
        """Start the live display."""
        if self._live is not None:
            return

        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
            transient=False,
        )

        self._live = Live(
            self._generate_display(),
            console=self.console,
            refresh_per_second=10,
            transient=False,
        )
        self._live.start()

    def stop(self) -> None:
        """Stop the live display."""
        if self._live is not None:
            self._live.stop()
            self._live = None
        self._progress = None

    def update(self, compilation_progress: CompilationProgress) -> None:
        """Update the display with new progress information.

        Args:
            compilation_progress: Current compilation progress state
        """
        self._current_state = compilation_progress.state
        self._current_description = compilation_progress.description or ""

        # Update task statuses
        if compilation_progress.state in self._tasks:
            # Mark current state as active
            self._tasks[compilation_progress.state]["status"] = "active"

            # Mark previous states as completed
            task_order = list(self._tasks.keys())
            current_index = task_order.index(compilation_progress.state)
            for i in range(current_index):
                prev_state = task_order[i]
                if self._tasks[prev_state]["status"] not in ("completed", "failed"):
                    self._tasks[prev_state]["status"] = "completed"

        # Handle completion/failure
        if compilation_progress.state == CompilationState.COMPLETED:
            for task in self._tasks.values():
                if task["status"] == "active":
                    task["status"] = "completed"
        elif compilation_progress.state == CompilationState.FAILED:
            for task in self._tasks.values():
                if task["status"] == "active":
                    task["status"] = "failed"

        # Update progress bar for active task
        if self._progress is not None and compilation_progress.is_active():
            if self._current_task_id is None:
                self._current_task_id = self._progress.add_task(
                    self._current_description,
                    total=100,
                )
            else:
                self._progress.update(
                    self._current_task_id,
                    description=self._current_description,
                    completed=compilation_progress.get_percentage(),
                )

        # Update display
        if self._live is not None:
            self._live.update(self._generate_display())

    def _generate_display(self) -> Panel:
        """Generate the Rich display panel.

        Returns:
            Rich Panel containing the progress display
        """
        table = Table.grid(padding=(0, 2))
        table.add_column(style="white", no_wrap=True)
        table.add_column(style="white")

        # Add task status rows
        for state, task_info in self._tasks.items():
            status_icon = self._get_status_icon(task_info["status"])
            task_name = task_info["name"]

            # Add extra info for active tasks
            extra_info = ""
            if (
                task_info["status"] == "active"
                and state == self._current_state
                and self._current_description
            ):
                extra_info = f" - {self._current_description}"

            table.add_row(status_icon, f"{task_name}{extra_info}")

        # Add progress bar for active task if available
        if (
            self._progress is not None
            and self._current_task_id is not None
            and self._current_state
            in (
                CompilationState.BUILDING,
                CompilationState.DEPENDENCY_FETCH,
            )
        ):
            table.add_row("", "")  # Spacer
            # Get the progress renderable
            progress_renderable = self._progress
            table.add_row("  └─", progress_renderable)

        # Add elapsed time
        elapsed = time.time() - self._start_time
        elapsed_str = f"Elapsed: {elapsed:.1f}s"

        title = "Compilation Progress"
        if self._current_state == CompilationState.COMPLETED:
            title = "✓ Compilation Complete"
        elif self._current_state == CompilationState.FAILED:
            title = "✗ Compilation Failed"

        return Panel(
            table,
            title=title,
            subtitle=elapsed_str,
            border_style="blue",
        )

    def print_log(self, message: str, level: str = "info") -> None:
        """Print a log message through the console, above the progress display.

        Args:
            message: The log message to display
            level: Log level (info, warning, error, debug)
        """
        # Style the message based on level
        if level == "error":
            styled_message = f"[red]ERROR:[/red] {message}"
        elif level == "warning":
            styled_message = f"[yellow]WARNING:[/yellow] {message}"
        elif level == "debug":
            styled_message = f"[dim]DEBUG:[/dim] {message}"
        else:
            styled_message = message

        # Print through the console so it appears above the live display
        self.console.print(styled_message)

    def _get_status_icon(self, status: str) -> str:
        """Get the status icon for a task.

        Args:
            status: Task status (pending, active, completed, failed)

        Returns:
            Status icon string
        """
        icons = {
            "pending": "□",
            "active": "⚙",
            "completed": "✓",
            "failed": "✗",
        }
        return icons.get(status, "□")


class SimpleProgressCoordinator:
    """Simple progress coordinator that implements the protocol interface."""

    def __init__(self, display: SimpleCompilationDisplay) -> None:
        """Initialize the coordinator.

        Args:
            display: The simple display to update
        """
        self.display = display
        self.current_phase = "idle"
        self.docker_image_name = ""
        self._progress = CompilationProgress()
        self.compilation_strategy = "unknown"

        # Tracking for complex operations
        self.total_repositories = 0
        self.downloaded_repositories = 0
        self.total_boards = 2  # Default for glove80
        self.boards_completed = 0

    @property
    def compilation_strategy(self) -> str:
        """Get the compilation strategy name."""
        return self._compilation_strategy

    @compilation_strategy.setter
    def compilation_strategy(self, value: str) -> None:
        """Set the compilation strategy name."""
        self._compilation_strategy = value

    def transition_to_phase(self, phase: str, description: str = "") -> None:
        """Transition to a new compilation phase."""
        self.current_phase = phase

        # Map phases to states
        phase_mapping = {
            "initialization": CompilationState.INITIALIZING,
            "cache_restoration": CompilationState.CACHE_SETUP,
            "cache_setup": CompilationState.CACHE_SETUP,
            "workspace_setup": CompilationState.WORKSPACE_SETUP,
            "west_update": CompilationState.DEPENDENCY_FETCH,
            "building": CompilationState.BUILDING,
            "collecting": CompilationState.POST_PROCESSING,
            "cache_saving": CompilationState.POST_PROCESSING,
            "complete": CompilationState.COMPLETED,
            "failed": CompilationState.FAILED,
        }

        new_state = phase_mapping.get(phase, CompilationState.INITIALIZING)
        self._progress.state = new_state
        self._progress.description = description

        self.display.update(self._progress)

    def set_compilation_strategy(self, strategy: str, docker_image: str = "") -> None:
        """Set compilation strategy metadata."""
        self.compilation_strategy = strategy
        self.docker_image_name = docker_image

    def update_cache_progress(
        self,
        operation: str,
        current: int = 0,
        total: int = 100,
        description: str = "",
        status: str = "in_progress",
    ) -> None:
        """Update cache restoration progress."""
        if total > 0:
            self._progress.percentage = (current / total) * 100
        self._progress.description = description or f"Cache {operation}"
        self.display.update(self._progress)

    def update_workspace_progress(
        self,
        files_copied: int = 0,
        total_files: int = 0,
        bytes_copied: int = 0,
        total_bytes: int = 0,
        current_file: str = "",
        component: str = "",
    ) -> None:
        """Update workspace setup progress."""
        if total_files > 0:
            self._progress.percentage = (files_copied / total_files) * 100

        desc_parts = []
        if component:
            desc_parts.append(component)
        if current_file:
            desc_parts.append(f"({current_file})")

        self._progress.description = " ".join(desc_parts) or "Setting up workspace"
        self.display.update(self._progress)

    def update_repository_progress(self, repository_name: str) -> None:
        """Update repository download progress during west update."""
        self.downloaded_repositories += 1

        if self.total_repositories > 0:
            self._progress.percentage = (
                self.downloaded_repositories / self.total_repositories
            ) * 100

        self._progress.description = f"Downloading {repository_name} ({self.downloaded_repositories}/{self.total_repositories})"
        self.display.update(self._progress)

    def update_board_progress(
        self,
        board_name: str = "",
        current_step: int = 0,
        total_steps: int = 0,
        completed: bool = False,
    ) -> None:
        """Update board compilation progress."""
        if completed:
            self.boards_completed += 1

        if total_steps > 0:
            self._progress.percentage = (current_step / total_steps) * 100

        desc_parts = []
        if board_name:
            desc_parts.append(f"Board: {board_name}")
        if current_step > 0 and total_steps > 0:
            desc_parts.append(f"({current_step}/{total_steps})")

        self._progress.description = " ".join(desc_parts) or "Building firmware"
        self.display.update(self._progress)

    def complete_all_builds(self) -> None:
        """Mark all builds as complete and transition to done phase."""
        self.transition_to_phase("collecting", "Collecting artifacts")

    def complete_build_success(
        self, reason: str = "Build completed successfully"
    ) -> None:
        """Mark build as complete regardless of current phase (for cached builds)."""
        self.transition_to_phase("complete", reason)

    def update_cache_saving(self, operation: str = "", progress_info: str = "") -> None:
        """Update cache saving progress."""
        desc = f"Saving cache: {operation}" if operation else "Saving cache"
        if progress_info:
            desc += f" ({progress_info})"
        self._progress.description = desc
        self.display.update(self._progress)

        # Also print the cache operation as a log message
        self.display.print_log(f"Cache: {desc}", "info")

    def update_docker_verification(
        self, image_name: str, status: str = "verifying"
    ) -> None:
        """Update Docker image verification progress (MoErgo specific)."""
        self._progress.description = f"Verifying Docker image: {image_name}"
        self.display.update(self._progress)

    def update_nix_build_progress(
        self, operation: str, status: str = "building"
    ) -> None:
        """Update Nix environment build progress (MoErgo specific)."""
        self._progress.description = f"Nix build: {operation}"
        self.display.update(self._progress)

    def print_docker_log(self, message: str, level: str = "info") -> None:
        """Print a Docker log message through the display console.

        Args:
            message: The log message from Docker
            level: Log level (info, warning, error, debug)
        """
        self.display.print_log(message, level)

    def get_current_progress(self) -> CompilationProgress:
        """Get the current unified progress state."""
        return self._progress


def create_simple_compilation_display(
    console: Console | None = None,
) -> SimpleCompilationDisplay:
    """Factory function to create a simple compilation display.

    Args:
        console: Rich console for output. If None, creates a new one.

    Returns:
        SimpleCompilationDisplay instance
    """
    return SimpleCompilationDisplay(console)


def create_simple_progress_coordinator(
    display: SimpleCompilationDisplay,
) -> SimpleProgressCoordinator:
    """Factory function to create a simple progress coordinator.

    Args:
        display: The simple display to update

    Returns:
        SimpleProgressCoordinator instance
    """
    return SimpleProgressCoordinator(display)
