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

        # Additional task states for enhanced operations
        self._enhanced_tasks = {
            "download": {"name": "Download", "status": "pending"},
            "zip_extraction": {"name": "ZIP Extraction", "status": "pending"},
            "cache_restoration": {"name": "Cache Restoration", "status": "pending"},
            "cache_analysis": {"name": "Cache Analysis", "status": "pending"},
            "workspace_injection": {"name": "Workspace Injection", "status": "pending"},
            "workspace_export": {"name": "Workspace Export", "status": "pending"},
        }

        self._current_state = CompilationState.IDLE
        self._current_description = ""
        self._current_enhanced_task = None  # Track which enhanced task is active
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
            for task in self._enhanced_tasks.values():
                if task["status"] == "active":
                    task["status"] = "completed"
        elif compilation_progress.state == CompilationState.FAILED:
            for task in self._tasks.values():
                if task["status"] == "active":
                    task["status"] = "failed"
            for task in self._enhanced_tasks.values():
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

        # Add task status rows - combine regular and enhanced tasks
        all_tasks = []

        # Add regular compilation tasks
        for state, task_info in self._tasks.items():
            all_tasks.append((state, task_info, "regular"))

        # Add enhanced tasks that are active or completed
        for enhanced_state, task_info in self._enhanced_tasks.items():
            if task_info["status"] != "pending":
                all_tasks.append((enhanced_state, task_info, "enhanced"))

        for state, task_info, task_type in all_tasks:
            status_icon = self._get_status_icon(task_info["status"])
            task_name = task_info["name"]

            # Add extra info for active tasks
            extra_info = ""
            if task_info["status"] == "active" and self._current_description:
                if task_type == "regular" and state == self._current_state:
                    # Only show description for regular tasks if no enhanced task is active
                    if self._current_enhanced_task is None:
                        extra_info = f" - {self._current_description}"
                elif task_type == "enhanced" and state == self._current_enhanced_task:
                    # Only show description for the currently active enhanced task
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

    def set_enhanced_task_status(self, task_name: str, status: str, description: str = "") -> None:
        """Set status for enhanced tasks like download, zip_extraction, cache_restoration.

        Args:
            task_name: Name of the enhanced task (download, zip_extraction, cache_restoration, etc.)
            status: Task status (pending, active, completed, failed)
            description: Optional description for the task
        """
        if task_name in self.display._enhanced_tasks:
            self.display._enhanced_tasks[task_name]["status"] = status
            if status == "active":
                # Set this as the current active enhanced task
                self.display._current_enhanced_task = task_name
                if description:
                    self._progress.description = description
            elif status in ("completed", "failed"):
                # Clear current enhanced task if this was the active one
                if self.display._current_enhanced_task == task_name:
                    self.display._current_enhanced_task = None
            self.display.update(self._progress)

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
        transfer_speed_mb_s: float = 0.0,
        eta_seconds: float = 0.0,
    ) -> None:
        """Update workspace setup progress with enhanced file-level details.

        Args:
            files_copied: Number of files copied so far
            total_files: Total number of files to copy
            bytes_copied: Number of bytes copied so far
            total_bytes: Total number of bytes to copy
            current_file: Name of the current file being copied
            component: Name of the current component (zmk, zephyr, modules, etc.)
            transfer_speed_mb_s: Current transfer speed in MB/s
            eta_seconds: Estimated time remaining in seconds
        """
        # Use bytes for more accurate progress if available
        if total_bytes > 0:
            self._progress.percentage = (bytes_copied / total_bytes) * 100
        elif total_files > 0:
            self._progress.percentage = (files_copied / total_files) * 100

        desc_parts = []
        if component:
            desc_parts.append(component)

        # Add file info if available
        if files_copied > 0 and total_files > 0:
            desc_parts.append(f"({files_copied}/{total_files} files)")

        # Add size info if available
        if bytes_copied > 0 and total_bytes > 0:
            mb_copied = bytes_copied / (1024 * 1024)
            mb_total = total_bytes / (1024 * 1024)
            desc_parts.append(f"{mb_copied:.1f}/{mb_total:.1f} MB")

        # Add transfer speed if available
        if transfer_speed_mb_s > 0:
            desc_parts.append(f"{transfer_speed_mb_s:.1f} MB/s")

        # Add ETA if available
        if eta_seconds > 0:
            if eta_seconds < 60:
                desc_parts.append(f"ETA: {eta_seconds:.0f}s")
            else:
                minutes = eta_seconds / 60
                desc_parts.append(f"ETA: {minutes:.1f}m")

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

    def update_git_clone_progress(
        self,
        repository_name: str,
        objects_received: int = 0,
        total_objects: int = 0,
        deltas_resolved: int = 0,
        total_deltas: int = 0,
        transfer_speed_kb_s: float = 0.0,
    ) -> None:
        """Update detailed git clone progress during repository downloads.

        Args:
            repository_name: Name of the repository being cloned
            objects_received: Number of objects received
            total_objects: Total number of objects to receive
            deltas_resolved: Number of deltas resolved
            total_deltas: Total number of deltas to resolve
            transfer_speed_kb_s: Current transfer speed in KB/s
        """
        # Calculate progress based on objects and deltas
        objects_percent = (
            (objects_received / total_objects * 100) if total_objects > 0 else 0
        )
        deltas_percent = (
            (deltas_resolved / total_deltas * 100) if total_deltas > 0 else 0
        )

        # Average the two phases (receiving objects + resolving deltas)
        if deltas_resolved > 0:
            # If we're resolving deltas, we're in phase 2
            self._progress.percentage = 50 + (deltas_percent / 2)
            phase = f"Resolving deltas: {deltas_resolved}/{total_deltas}"
        else:
            # Still receiving objects, phase 1
            self._progress.percentage = objects_percent / 2
            phase = f"Receiving objects: {objects_received}/{total_objects}"

        desc_parts = [f"Cloning {repository_name}", phase]

        if transfer_speed_kb_s > 0:
            if transfer_speed_kb_s > 1024:
                desc_parts.append(f"{transfer_speed_kb_s / 1024:.1f} MB/s")
            else:
                desc_parts.append(f"{transfer_speed_kb_s:.0f} KB/s")

        self._progress.description = " | ".join(desc_parts)
        self.display.update(self._progress)

    def update_cache_extraction_progress(
        self,
        operation: str,
        files_extracted: int = 0,
        total_files: int = 0,
        bytes_extracted: int = 0,
        total_bytes: int = 0,
        current_file: str = "",
        archive_name: str = "",
        extraction_speed_mb_s: float = 0.0,
        eta_seconds: float = 0.0,
    ) -> None:
        """Update progress for cache extraction operations with enhanced details.

        Args:
            operation: Type of extraction operation
            files_extracted: Number of files extracted so far
            total_files: Total number of files to extract
            bytes_extracted: Number of bytes extracted so far
            total_bytes: Total number of bytes to extract
            current_file: Current file being extracted
            archive_name: Name of the archive being extracted
            extraction_speed_mb_s: Current extraction speed in MB/s
            eta_seconds: Estimated time remaining in seconds
        """
        # Set ZIP extraction task as active
        self.set_enhanced_task_status("zip_extraction", "active")

        # Use bytes for more accurate progress if available
        if total_bytes > 0:
            self._progress.percentage = (bytes_extracted / total_bytes) * 100
        elif total_files > 0:
            self._progress.percentage = (files_extracted / total_files) * 100

        desc_parts = [f"Extracting {operation}"]

        if archive_name:
            desc_parts.append(f"from {archive_name}")

        # Add file count info
        if files_extracted > 0 and total_files > 0:
            desc_parts.append(f"({files_extracted}/{total_files} files)")

        # Add size info if available
        if bytes_extracted > 0 and total_bytes > 0:
            mb_extracted = bytes_extracted / (1024 * 1024)
            mb_total = total_bytes / (1024 * 1024)
            desc_parts.append(f"{mb_extracted:.1f}/{mb_total:.1f} MB")

        # Add extraction speed if available
        if extraction_speed_mb_s > 0:
            desc_parts.append(f"{extraction_speed_mb_s:.1f} MB/s")

        # Add ETA if available
        if eta_seconds > 0:
            if eta_seconds < 60:
                desc_parts.append(f"ETA: {eta_seconds:.0f}s")
            else:
                minutes = eta_seconds / 60
                desc_parts.append(f"ETA: {minutes:.1f}m")

        # Add current file info if available
        if current_file:
            # Truncate long file paths
            display_file = current_file
            if len(display_file) > 30:
                display_file = "..." + display_file[-27:]
            desc_parts.append(f"[{display_file}]")

        self._progress.description = " ".join(desc_parts)
        self.display.update(self._progress)

    def update_folder_scan_progress(
        self,
        operation: str,
        directories_scanned: int = 0,
        total_directories: int = 0,
        files_found: int = 0,
        current_directory: str = "",
    ) -> None:
        """Update progress for folder scanning operations before copying.

        Args:
            operation: Type of scan operation (e.g., "workspace analysis", "cache preparation")
            directories_scanned: Number of directories scanned so far
            total_directories: Total number of directories to scan
            files_found: Total number of files found so far
            current_directory: Current directory being scanned
        """
        if total_directories > 0:
            self._progress.percentage = (directories_scanned / total_directories) * 100

        desc_parts = [f"Scanning {operation}"]

        if directories_scanned > 0 and total_directories > 0:
            desc_parts.append(f"({directories_scanned}/{total_directories} dirs)")

        if files_found > 0:
            desc_parts.append(f"{files_found} files found")

        if current_directory:
            # Truncate long directory paths
            display_dir = current_directory
            if len(display_dir) > 25:
                display_dir = "..." + display_dir[-22:]
            desc_parts.append(f"[{display_dir}]")

        self._progress.description = " ".join(desc_parts)
        self.display.update(self._progress)

    def update_cache_restoration_progress(
        self,
        operation: str,
        component: str = "",
        files_copied: int = 0,
        total_files: int = 0,
        bytes_copied: int = 0,
        total_bytes: int = 0,
        current_file: str = "",
        transfer_speed_mb_s: float = 0.0,
        eta_seconds: float = 0.0,
    ) -> None:
        """Update progress for cache restoration operations with detailed tracking.

        Args:
            operation: Type of restoration operation (restoring, validating, verifying)
            component: Current component being restored (zmk, zephyr, modules, .west)
            files_copied: Number of files restored so far
            total_files: Total number of files to restore
            bytes_copied: Number of bytes restored so far
            total_bytes: Total number of bytes to restore
            current_file: Current file being restored
            transfer_speed_mb_s: Current restoration speed in MB/s
            eta_seconds: Estimated time remaining in seconds
        """
        # Set appropriate enhanced task status
        if operation == "restoring":
            self.set_enhanced_task_status("cache_restoration", "active")
        elif operation in ("validating", "verifying"):
            # Mark restoration as completed and show validation
            self.set_enhanced_task_status("cache_restoration", "completed")

        # Use bytes for more accurate progress if available
        if total_bytes > 0:
            self._progress.percentage = (bytes_copied / total_bytes) * 100
        elif total_files > 0:
            self._progress.percentage = (files_copied / total_files) * 100

        desc_parts = [f"Cache {operation}"]

        # Add component info if available
        if component:
            desc_parts.append(f"({component})")

        # Add file count info
        if files_copied > 0 and total_files > 0:
            desc_parts.append(f"{files_copied}/{total_files} files")

        # Add size info if available
        if bytes_copied > 0 and total_bytes > 0:
            mb_copied = bytes_copied / (1024 * 1024)
            mb_total = total_bytes / (1024 * 1024)
            desc_parts.append(f"{mb_copied:.1f}/{mb_total:.1f} MB")

        # Add transfer speed if available
        if transfer_speed_mb_s > 0:
            desc_parts.append(f"{transfer_speed_mb_s:.1f} MB/s")

        # Add ETA if available
        if eta_seconds > 0:
            if eta_seconds < 60:
                desc_parts.append(f"ETA: {eta_seconds:.0f}s")
            else:
                minutes = eta_seconds / 60
                desc_parts.append(f"ETA: {minutes:.1f}m")

        # Add current file info if available
        if current_file:
            # Truncate long file paths
            display_file = current_file
            if len(display_file) > 25:
                display_file = "..." + display_file[-22:]
            desc_parts.append(f"[{display_file}]")

        self._progress.description = " ".join(desc_parts)
        self.display.update(self._progress)

        # Also log cache operations for visibility
        if operation in ("restoring", "validating"):
            log_msg = f"Cache {operation}"
            if component:
                log_msg += f": {component}"
            if transfer_speed_mb_s > 0:
                log_msg += f" ({transfer_speed_mb_s:.1f} MB/s)"
            self.display.print_log(log_msg, "info")

    def update_export_progress(
        self,
        files_processed: int = 0,
        total_files: int = 0,
        current_file: str = "",
        archive_format: str = "",
        compression_level: int = 0,
        speed_mb_s: float = 0.0,
        eta_seconds: float = 0.0,
    ) -> None:
        """Update workspace export progress with detailed tracking.

        Args:
            files_processed: Number of files processed so far
            total_files: Total number of files to process
            current_file: Current file being processed
            archive_format: Archive format being created
            compression_level: Compression level being used
            speed_mb_s: Current processing speed in MB/s
            eta_seconds: Estimated time remaining in seconds
        """
        # Set workspace export task as active
        self.set_enhanced_task_status("workspace_export", "active")
        
        # Use files for progress tracking
        if total_files > 0:
            self._progress.percentage = (files_processed / total_files) * 100

        desc_parts = [f"Exporting to {archive_format}"]

        # Add file count info
        if files_processed > 0 and total_files > 0:
            desc_parts.append(f"({files_processed}/{total_files} files)")

        # Add compression level info
        if compression_level > 0:
            desc_parts.append(f"level {compression_level}")

        # Add processing speed if available
        if speed_mb_s > 0:
            desc_parts.append(f"{speed_mb_s:.1f} MB/s")

        # Add ETA if available
        if eta_seconds > 0:
            if eta_seconds < 60:
                desc_parts.append(f"ETA: {eta_seconds:.0f}s")
            else:
                minutes = eta_seconds / 60
                desc_parts.append(f"ETA: {minutes:.1f}m")

        # Add current file info if available
        if current_file:
            # Truncate long file paths
            display_file = current_file
            if len(display_file) > 25:
                display_file = "..." + display_file[-22:]
            desc_parts.append(f"[{display_file}]")

        self._progress.description = " ".join(desc_parts)
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
