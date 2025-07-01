"""Simple Rich-based compilation progress display."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table
from rich.text import Text

from glovebox.cli.helpers.theme import Colors, IconMode, Icons, format_status_message


if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class ProgressConfig:
    """Configuration for customizable progress display."""

    operation_name: str = "Operation"
    icon_mode: IconMode = IconMode.TEXT

    @property
    def title_processing(self) -> str:
        """Get processing title with appropriate icon."""
        return Icons.format_with_icon("PROCESSING", "Processing", self.icon_mode)

    @property
    def title_complete(self) -> str:
        """Get completion title with appropriate icon."""
        return Icons.format_with_icon("SUCCESS", "Operation Complete", self.icon_mode)

    @property
    def title_failed(self) -> str:
        """Get failure title with appropriate icon."""
        return Icons.format_with_icon("ERROR", "Operation Failed", self.icon_mode)

    # Fully customizable task list - just task names in order
    tasks: list[str] = field(
        default_factory=lambda: [
            "Cache Setup",
            "Workspace Setup",
            "Dependencies",
            "Building Firmware",
            "Post Processing",
        ]
    )


class SimpleCompilationDisplay:
    """Simple Rich-based compilation progress display with task status indicators."""

    def __init__(
        self,
        console: Console | None = None,
        config: ProgressConfig | None = None,
        icon_mode: IconMode = IconMode.TEXT,
    ) -> None:
        """Initialize the simple compilation display.

        Args:
            console: Rich console for output. If None, creates a new one.
            config: Progress configuration. If None, uses default compilation-focused config.
        """
        self.console = console or Console()
        # If no config provided, create one with the icon_mode
        if config is None:
            config = ProgressConfig(icon_mode=icon_mode)
        else:
            # Update existing config's icon_mode
            config.icon_mode = icon_mode
        self.config = config
        self.icon_mode = icon_mode
        self._live: Live | None = None
        self._progress: Progress | None = None
        self._current_task_id: TaskID | None = None

        # Simple task list with status tracking
        self._tasks = [
            {"name": task_name, "status": "pending"} for task_name in self.config.tasks
        ]
        self._current_task_index = -1

        self._current_description = ""
        self._current_percentage = 0.0  # Track current progress percentage
        self._start_time = time.time()
        self._is_complete = False
        self._is_failed = False

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

    def start_task(
        self, task_index: int, description: str = "", percentage: float = 0.0
    ) -> None:
        """Start a specific task by index."""
        if 0 <= task_index < len(self._tasks):
            # Mark previous tasks as completed
            for i in range(task_index):
                if self._tasks[i]["status"] == "pending":
                    self._tasks[i]["status"] = "completed"

            # Mark current task as active
            self._tasks[task_index]["status"] = "active"
            self._current_task_index = task_index
            self._current_description = description
            self._current_percentage = percentage

            # Update display
            if self._live is not None:
                self._live.update(self._generate_display())

    def start_task_by_name(
        self, task_name: str, description: str = "", percentage: float = 0.0
    ) -> None:
        """Start a task by its name."""
        for i, task in enumerate(self._tasks):
            if task["name"] == task_name:
                self.start_task(i, description, percentage)
                return

    def update_current_task(
        self, description: str = "", percentage: float = 0.0
    ) -> None:
        """Update the current active task."""
        if self._current_task_index >= 0:
            self._current_description = description
            self._current_percentage = percentage

            # Update display
            if self._live is not None:
                self._live.update(self._generate_display())

    def complete_current_task(self) -> None:
        """Mark the current task as completed."""
        if self._current_task_index >= 0:
            self._tasks[self._current_task_index]["status"] = "completed"
            self._current_task_index = -1

            # Update display
            if self._live is not None:
                self._live.update(self._generate_display())

    def fail_current_task(self) -> None:
        """Mark the current task as failed."""
        if self._current_task_index >= 0:
            self._tasks[self._current_task_index]["status"] = "failed"
            self._is_failed = True

            # Update display
            if self._live is not None:
                self._live.update(self._generate_display())

    def complete_all(self) -> None:
        """Mark all tasks as completed."""
        for task in self._tasks:
            if task["status"] in ("pending", "active"):
                task["status"] = "completed"
        self._current_task_index = -1
        self._is_complete = True

        # Update display
        if self._live is not None:
            self._live.update(self._generate_display())

    def fail_all(self) -> None:
        """Mark the operation as failed."""
        if self._current_task_index >= 0:
            self._tasks[self._current_task_index]["status"] = "failed"
        self._is_failed = True

        # Update display
        if self._live is not None:
            self._live.update(self._generate_display())

    def _generate_display(self) -> Panel:
        """Generate the Rich display panel with visual progress bars.

        Returns:
            Rich Panel containing the progress display
        """
        # Create main content table
        table = Table.grid(padding=(0, 1))
        table.add_column(style=Colors.NORMAL, no_wrap=False, width=None)

        # Get current active task info
        active_task_name = "Processing"
        active_percentage = self._current_percentage
        status_info = self._current_description

        # Find the currently active task
        if self._current_task_index >= 0 and self._current_task_index < len(
            self._tasks
        ):
            active_task_name = self._tasks[self._current_task_index]["name"]
        elif self._is_complete:
            active_task_name = "Complete"
            active_percentage = 100.0
        elif self._is_failed:
            active_task_name = "Failed"
            active_percentage = 0.0

        # Create main progress display as a simple text line with inline progress bar
        progress_text = Text()
        progress_text.append(f"{active_task_name}... ", style=Colors.PRIMARY)

        # Create inline progress bar using theme-aware characters
        bar_width = 40
        filled_width = int((active_percentage / 100.0) * bar_width)
        empty_width = bar_width - filled_width

        filled_char = Icons.get_icon("PROGRESS_FULL", self.icon_mode) or "█"
        empty_char = Icons.get_icon("PROGRESS_EMPTY", self.icon_mode) or "░"
        progress_bar = filled_char * filled_width + empty_char * empty_width
        progress_text.append(progress_bar, style=Colors.PROGRESS_BAR)
        progress_text.append(f" {active_percentage:>5.1f}%", style=Colors.HIGHLIGHT)

        # Add main progress line
        table.add_row(progress_text)

        # Add status information if available
        if status_info:
            table.add_row("")  # Spacer

            # Create status text with proper styling
            status_text = Text()
            status_text.append("Status: ", style=Colors.MUTED)

            # Truncate long status info
            display_status = status_info
            if len(display_status) > 80:
                display_status = display_status[:77] + "..."

            status_text.append(display_status, style=Colors.INFO)
            table.add_row(status_text)

        # Add overall progress summary
        table.add_row("")  # Spacer

        # Count completed vs total tasks
        completed_tasks = sum(
            1 for task in self._tasks if task["status"] == "completed"
        )
        total_tasks = len(self._tasks)

        if total_tasks > 0:
            overall_percentage = (completed_tasks / total_tasks) * 100

            # Create simple overall progress line
            overall_text = Text()
            overall_text.append("Overall: ", style=Colors.MUTED)

            # Create smaller inline progress bar for overall using theme-aware characters
            overall_bar_width = 30
            overall_filled_width = int((overall_percentage / 100.0) * overall_bar_width)
            overall_empty_width = overall_bar_width - overall_filled_width

            filled_char = Icons.get_icon("PROGRESS_FULL", self.icon_mode) or "█"
            empty_char = Icons.get_icon("PROGRESS_EMPTY", self.icon_mode) or "░"
            overall_progress_bar = (
                filled_char * overall_filled_width + empty_char * overall_empty_width
            )
            overall_text.append(overall_progress_bar, style=Colors.LOADING_TEXT)
            overall_text.append(
                f" {overall_percentage:>5.1f}% ({completed_tasks}/{total_tasks} tasks)",
                style=Colors.MUTED,
            )

            table.add_row(overall_text)

        # Add task checklist below
        table.add_row("")  # Spacer

        # Show task status list (compact format)
        for task in self._tasks:
            status_icon = self._get_status_icon(task["status"])
            task_name = task["name"]

            # Create task status line
            task_line = Text()
            task_line.append(f" {status_icon} ", style=Colors.NORMAL)

            if task["status"] == "active":
                task_line.append(task_name, style=Colors.RUNNING)
            elif task["status"] == "completed":
                task_line.append(task_name, style=Colors.COMPLETED)
            elif task["status"] == "failed":
                task_line.append(task_name, style=Colors.FAILED)
            else:
                task_line.append(task_name, style=Colors.MUTED)

            table.add_row(task_line)

        # Add elapsed time
        elapsed = time.time() - self._start_time
        elapsed_str = f"Elapsed: {elapsed:.1f}s"

        # Determine title based on state - using config properties
        if self._is_complete:
            title = self.config.title_complete
            border_style = Colors.SUCCESS
        elif self._is_failed:
            title = self.config.title_failed
            border_style = Colors.ERROR
        else:
            title = self.config.title_processing
            border_style = Colors.INFO

        return Panel(
            table,
            title=title,
            subtitle=elapsed_str,
            border_style=border_style,
        )

    def print_log(self, message: str, level: str = "info") -> None:
        """Print a log message through the console, above the progress display.

        Args:
            message: The log message to display
            level: Log level (info, warning, error, debug)
        """
        # Style the message based on level using theme helpers
        if level == "error":
            styled_message = format_status_message(f"ERROR: {message}", "error")
        elif level == "warning":
            styled_message = format_status_message(f"WARNING: {message}", "warning")
        elif level == "debug":
            styled_message = f"[{Colors.MUTED}]DEBUG:[/] {message}"
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
        icon_map = {
            "pending": "BULLET",
            "active": "RUNNING",
            "completed": "SUCCESS",
            "failed": "ERROR",
        }
        icon_name = icon_map.get(status, "BULLET")
        return Icons.get_icon(icon_name, self.icon_mode)


class SimpleProgressCoordinator:
    """Simple progress coordinator with task-based interface."""

    def __init__(self, display: SimpleCompilationDisplay) -> None:
        """Initialize the coordinator.

        Args:
            display: The simple display to update
        """
        self.display = display
        self.config = display.config  # Use the same config as the display

    def start_task_by_name(
        self, task_name: str, description: str = "", percentage: float = 0.0
    ) -> None:
        """Start a task by its name.

        Args:
            task_name: Name of the task to start
            description: Optional description for the task
            percentage: Initial progress percentage (0-100)
        """
        self.display.start_task_by_name(task_name, description, percentage)

    def update_current_task(
        self, description: str = "", percentage: float = 0.0
    ) -> None:
        """Update the current active task.

        Args:
            description: Updated description for the task
            percentage: Updated progress percentage (0-100)
        """
        self.display.update_current_task(description, percentage)

    def complete_current_task(self) -> None:
        """Mark the current task as completed."""
        self.display.complete_current_task()

    def fail_current_task(self) -> None:
        """Mark the current task as failed."""
        self.display.fail_current_task()

    def complete_all_tasks(self) -> None:
        """Mark all tasks as completed."""
        self.display.complete_all()

    def fail_all_tasks(self) -> None:
        """Mark the operation as failed."""
        self.display.fail_all()

    def print_log(self, message: str, level: str = "info") -> None:
        """Print a log message through the display console.

        Args:
            message: The log message to display
            level: Log level (info, warning, error, debug)
        """
        self.display.print_log(message, level)

    def transition_to_phase(self, phase: str, description: str = "") -> None:
        """Transition to a new phase - maps to task-based system.

        For backward compatibility, this maps common phase names to tasks.
        If the phase matches a task name, it will start that task.

        Args:
            phase: Phase name (e.g., "cache_setup", "workspace_setup")
            description: Description for the phase/task
        """
        # Try to find a matching task name for this phase
        phase_to_task_mapping = {
            "cache": "Cache Setup",
            "cache_setup": "Cache Setup",
            "workspace": "Workspace Setup",
            "workspace_setup": "Workspace Setup",
            "dependencies": "Dependencies",
            "dependency_fetch": "Dependencies",
            "building": "Building Firmware",
            "post_processing": "Post Processing",
            "finalizing": "Post Processing",
        }

        # Find matching task name
        task_name = phase_to_task_mapping.get(phase.lower())
        if task_name:
            self.start_task_by_name(task_name, description)
        else:
            # If no mapping found, try to find a task with similar name
            for task in self.config.tasks:
                if phase.lower() in task.lower() or task.lower() in phase.lower():
                    self.start_task_by_name(task, description)
                    return

            # If still no match, just update current task with description
            if description:
                self.update_current_task(description)

    def set_enhanced_task_status(
        self, task_name: str, status: str, description: str = ""
    ) -> None:
        """Set status for enhanced tasks - compatibility method.

        This method provides backward compatibility for callers that expect
        enhanced task status functionality. In the simplified system, this
        maps to basic task operations.

        Args:
            task_name: Name of the enhanced task
            status: Task status (pending, active, completed, failed)
            description: Optional description for the task
        """
        if status == "active":
            # Find the closest matching task name or use description
            display_name = description or task_name.replace("_", " ").title()

            # Try to find matching task in our config
            matching_task = None
            for task in self.config.tasks:
                if (
                    task_name.lower() in task.lower()
                    or task.lower() in task_name.lower()
                ):
                    matching_task = task
                    break

            if matching_task:
                self.start_task_by_name(matching_task, description)
            else:
                # Update current task with the description
                self.update_current_task(display_name)
        elif status == "completed":
            self.complete_current_task()
        elif status == "failed":
            self.fail_current_task()

    def set_compilation_strategy(self, strategy: str, docker_image: str = "") -> None:
        """Set compilation strategy metadata."""
        self.compilation_strategy = strategy
        self.docker_image_name = docker_image

    def update_workspace_progress(
        self,
        files_copied: int = 0,
        total_files: int = 0,
        bytes_copied: int = 0,
        total_bytes: int = 0,
        current_file: str = "",
        component: str = "",
        transfer_speed_mb_s: float = 0.0,
        eta_seconds: float = 0.0,
    ) -> None:
        """Update workspace setup progress.

        Args:
            files_copied: Number of files copied so far
            total_files: Total number of files to copy
            bytes_copied: Number of bytes copied so far
            total_bytes: Total number of bytes to copy
            current_file: Current file being copied
            component: Current component being processed
            transfer_speed_mb_s: Transfer speed in MB/s
            eta_seconds: Estimated time to completion in seconds
        """
        if total_files > 0:
            progress_percentage = (files_copied / total_files) * 100
        elif total_bytes > 0:
            progress_percentage = (bytes_copied / total_bytes) * 100
        else:
            progress_percentage = 0.0

        # Create descriptive status message
        if component and current_file:
            status = f"Copying {component}: {current_file}"
        elif component:
            status = f"Processing {component} ({files_copied}/{total_files} files)"
        elif current_file:
            status = f"Copying: {current_file}"
        else:
            status = f"Copying files ({files_copied}/{total_files})"

        # Add transfer speed and ETA if available
        if transfer_speed_mb_s > 0:
            status += f" @ {transfer_speed_mb_s:.1f} MB/s"
        if eta_seconds > 0:
            eta_minutes = eta_seconds / 60
            if eta_minutes >= 1:
                status += f" (ETA: {eta_minutes:.1f}m)"
            else:
                status += f" (ETA: {eta_seconds:.0f}s)"

        self.update_current_task(status, progress_percentage)

    def update_cache_extraction_progress(
        self,
        operation: str = "",
        files_extracted: int = 0,
        total_files: int = 0,
        bytes_extracted: int = 0,
        total_bytes: int = 0,
        current_file: str = "",
        archive_name: str = "",
        extraction_speed_mb_s: float = 0.0,
        eta_seconds: float = 0.0,
    ) -> None:
        """Update cache extraction progress.

        Args:
            operation: Type of operation being performed
            files_extracted: Number of files extracted so far
            total_files: Total number of files to extract
            bytes_extracted: Number of bytes extracted so far
            total_bytes: Total number of bytes to extract
            current_file: Current file being extracted
            archive_name: Name of the archive being extracted
            extraction_speed_mb_s: Extraction speed in MB/s
            eta_seconds: Estimated time to completion in seconds
        """
        if total_files > 0:
            progress_percentage = (files_extracted / total_files) * 100
        elif total_bytes > 0:
            progress_percentage = (bytes_extracted / total_bytes) * 100
        else:
            progress_percentage = 0.0

        # Create descriptive status message
        if current_file and archive_name:
            # Show just the filename if it's very long
            display_file = (
                current_file.split("/")[-1] if "/" in current_file else current_file
            )
            if len(display_file) > 40:
                display_file = display_file[:37] + "..."
            status = f"Extracting {archive_name}: {display_file}"
        elif archive_name:
            status = (
                f"Extracting {archive_name} ({files_extracted}/{total_files} files)"
            )
        else:
            status = f"Extracting files ({files_extracted}/{total_files})"

        # Add extraction speed and ETA if available
        if extraction_speed_mb_s > 0:
            status += f" @ {extraction_speed_mb_s:.1f} MB/s"
        if eta_seconds > 0:
            eta_minutes = eta_seconds / 60
            if eta_minutes >= 1:
                status += f" (ETA: {eta_minutes:.1f}m)"
            else:
                status += f" (ETA: {eta_seconds:.0f}s)"

        self.update_current_task(status, progress_percentage)


def create_simple_compilation_display(
    console: Console | None = None,
    config: ProgressConfig | None = None,
    icon_mode: IconMode = IconMode.TEXT,
) -> SimpleCompilationDisplay:
    """Factory function to create a simple compilation display.

    Args:
        console: Rich console for output. If None, creates a new one.
        config: Progress configuration. If None, uses default compilation-focused config.
        icon_mode: Icon mode for symbols and progress indicators.

    Returns:
        SimpleCompilationDisplay instance
    """
    return SimpleCompilationDisplay(console, config, icon_mode)


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
