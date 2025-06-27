"""Workspace progress widget for file copying and workspace operations."""

import time
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from .progress_widget import ProgressWidget


class WorkspaceProgressWidget(ProgressWidget[Any]):
    """Specialized progress widget for workspace operations.

    This widget extends ProgressWidget with workspace-specific display elements
    for file copying operations, including:
    - Current file being copied with component information
    - Transfer speed and ETA calculations
    - File and byte progress metrics
    - Visual indicators for different workspace components
    """

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        """Initialize the workspace progress widget.

        Args:
            name: The name of the widget
            id: The ID of the widget
            classes: CSS classes for styling
            disabled: Whether the widget is disabled
        """
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)

        # Workspace-specific state
        self.current_file = ""
        self.component_name = ""
        self.files_processed = 0
        self.total_files = 0
        self.bytes_copied = 0
        self.total_bytes = 0
        self.transfer_speed = 0.0
        self.last_update_time = 0.0

    def compose(self) -> ComposeResult:
        """Compose the workspace progress widget layout."""
        with Vertical():
            # Status and current file information
            yield Static(self.status_text, id="status-text", classes="status")

            # Current file and component info
            with Horizontal(classes="file-info"):
                yield Static("📄", id="file-icon", classes="icon")
                yield Static("", id="current-file", classes="current-file")
                yield Static("", id="component-info", classes="component")

            # Progress bars
            yield Static("", id="progress-info", classes="progress-info")
            from textual.widgets import ProgressBar

            yield ProgressBar(
                total=self.progress_total,
                show_eta=True,
                show_percentage=True,
                id="progress-bar",
            )

            # Transfer statistics
            with Horizontal(classes="transfer-stats"):
                yield Static("", id="file-stats", classes="stats")
                yield Static("", id="speed-stats", classes="stats")

            # Description and additional info
            yield Static(self.description, id="description", classes="description")

    def on_mount(self) -> None:
        """Initialize the workspace progress widget when mounted."""
        super().on_mount()

        # Get references to workspace-specific widgets
        self.file_icon = self.query_one("#file-icon", Static)
        self.current_file_widget = self.query_one("#current-file", Static)
        self.component_info_widget = self.query_one("#component-info", Static)
        self.progress_info_widget = self.query_one("#progress-info", Static)
        self.file_stats_widget = self.query_one("#file-stats", Static)
        self.speed_stats_widget = self.query_one("#speed-stats", Static)

    def _update_from_progress_data(self, progress_data: Any) -> None:
        """Update widget state from workspace copy progress data.

        Args:
            progress_data: Workspace copy progress data object
        """
        current_time = time.time()

        # Handle workspace copy progress updates
        if hasattr(progress_data, "current_file"):
            self.current_file = progress_data.current_file
            self._update_current_file_display()

            # Update component information
            if (
                hasattr(progress_data, "component_name")
                and progress_data.component_name
            ):
                self.component_name = progress_data.component_name
                self.component_info_widget.update(f"({self.component_name})")
            else:
                self.component_info_widget.update("")

            # Update file statistics
            if hasattr(progress_data, "files_processed") and hasattr(
                progress_data, "total_files"
            ):
                self.files_processed = progress_data.files_processed
                self.total_files = progress_data.total_files
                self._update_file_stats()

            # Update byte statistics and calculate transfer speed
            if hasattr(progress_data, "bytes_copied") and hasattr(
                progress_data, "total_bytes"
            ):
                previous_bytes = self.bytes_copied
                self.bytes_copied = progress_data.bytes_copied
                self.total_bytes = progress_data.total_bytes

                # Calculate transfer speed
                if self.last_update_time > 0 and current_time > self.last_update_time:
                    time_diff = current_time - self.last_update_time
                    bytes_diff = self.bytes_copied - previous_bytes
                    if time_diff > 0:
                        # Speed in MB/s
                        self.transfer_speed = (bytes_diff / (1024 * 1024)) / time_diff

                self.last_update_time = current_time
                self._update_speed_stats()

                # Use bytes as primary progress metric if available
                if self.total_bytes > 0:
                    self.progress_current = self.bytes_copied
                    self.progress_total = self.total_bytes
                    self.description = (
                        f"Copying {self.files_processed}/{self.total_files} files"
                    )
                else:
                    # Fall back to file count
                    self.progress_current = self.files_processed
                    self.progress_total = (
                        self.total_files if self.total_files > 0 else 100
                    )
                    self.description = "Copying files"
            else:
                # Fallback for basic progress without detailed metrics
                if hasattr(progress_data, "files_processed") and hasattr(
                    progress_data, "total_files"
                ):
                    self.progress_current = self.files_processed
                    self.progress_total = (
                        self.total_files if self.total_files > 0 else 100
                    )
                    self.description = "Copying files"

            # Update main status
            if self.current_file:
                file_name = (
                    self.current_file.split("/")[-1]
                    if "/" in self.current_file
                    else self.current_file
                )
                self.status_text = f"📄 Copying: {file_name}"
            else:
                self.status_text = "📄 Copying workspace files..."

        else:
            # Fallback for non-workspace progress data
            super()._update_from_progress_data(progress_data)

    def _update_current_file_display(self) -> None:
        """Update the current file display with proper truncation."""
        if not self.current_file:
            self.current_file_widget.update("")
            return

        # Get file name from path
        file_name = (
            self.current_file.split("/")[-1]
            if "/" in self.current_file
            else self.current_file
        )

        # Truncate long file names for display
        max_length = 50
        if len(file_name) > max_length:
            file_name = f"{file_name[: max_length - 3]}..."

        self.current_file_widget.update(file_name)

    def _update_file_stats(self) -> None:
        """Update file statistics display."""
        if self.total_files > 0:
            self.file_stats_widget.update(
                f"Files: {self.files_processed}/{self.total_files}"
            )
        else:
            self.file_stats_widget.update("")

    def _update_speed_stats(self) -> None:
        """Update transfer speed statistics display."""
        if self.total_bytes > 0:
            # Format bytes in human-readable format
            def format_bytes(bytes_val: int) -> str:
                for unit in ["B", "KB", "MB", "GB"]:
                    if bytes_val < 1024:
                        return f"{bytes_val:.1f} {unit}"
                    bytes_val /= 1024
                return f"{bytes_val:.1f} TB"

            copied_str = format_bytes(self.bytes_copied)
            total_str = format_bytes(self.total_bytes)

            # Include transfer speed if available
            if self.transfer_speed > 0:
                speed_str = f" @ {self.transfer_speed:.1f} MB/s"
            else:
                speed_str = ""

            self.speed_stats_widget.update(f"{copied_str}/{total_str}{speed_str}")
        else:
            self.speed_stats_widget.update("")

    def _update_progress_info(self) -> None:
        """Update the progress information display."""
        if self.total_bytes > 0:
            # Show byte-based progress
            percentage = (self.bytes_copied / self.total_bytes) * 100
            self.progress_info_widget.update(f"Progress: {percentage:.1f}%")
        elif self.total_files > 0:
            # Show file-based progress
            percentage = (self.files_processed / self.total_files) * 100
            self.progress_info_widget.update(f"Progress: {percentage:.1f}%")
        else:
            self.progress_info_widget.update("")

    # Override reactive watchers to update workspace-specific displays
    def watch_progress_current(self, progress_current: int) -> None:
        """React to progress current changes."""
        super().watch_progress_current(progress_current)
        self._update_progress_info()

    def watch_progress_total(self, progress_total: int) -> None:
        """React to progress total changes."""
        super().watch_progress_total(progress_total)
        self._update_progress_info()

    def complete_progress(self, result: Any = None) -> None:
        """Mark the workspace operation as completed.

        Args:
            result: Optional result data to store
        """
        super().complete_progress(result)

        # Update workspace-specific completion display
        if self.total_files > 0:
            self.file_stats_widget.update(f"✅ Completed: {self.total_files} files")

        if self.total_bytes > 0:

            def format_bytes(bytes_val: int) -> str:
                for unit in ["B", "KB", "MB", "GB"]:
                    if bytes_val < 1024:
                        return f"{bytes_val:.1f} {unit}"
                    bytes_val /= 1024
                return f"{bytes_val:.1f} TB"

            total_str = format_bytes(self.total_bytes)
            total_time = time.time() - self.start_time
            avg_speed = (
                (self.total_bytes / (1024 * 1024)) / total_time if total_time > 0 else 0
            )
            self.speed_stats_widget.update(f"✅ {total_str} @ {avg_speed:.1f} MB/s avg")

        # Clear current file display
        self.current_file_widget.update("Operation completed")
        self.component_info_widget.update("")


def create_workspace_progress_widget(**kwargs: Any) -> WorkspaceProgressWidget:
    """Factory function to create a workspace progress widget.

    Args:
        **kwargs: Keyword arguments for the widget

    Returns:
        A new WorkspaceProgressWidget instance
    """
    return WorkspaceProgressWidget(**kwargs)
