"""Progress display component with Rich and logging integration."""

import time
from typing import Any

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

from glovebox.cli.components.progress_config import (
    CheckpointState,
    ProgressConfig,
    ProgressState,
)
from glovebox.cli.helpers.theme import Colors, Icons


class ProgressDisplay:
    """Reusable progress display with Rich and logging integration.

    This component provides a live-updating panel showing:
    - Scrollable log entries at the top
    - Current task progress bar
    - Status information line
    - Checkpoint list with visual indicators
    - Overall progress bar at the bottom
    """

    def __init__(self, config: ProgressConfig):
        """Initialize progress display.

        Args:
            config: Progress display configuration
        """
        self.config = config
        # Use base Console for Rich components, themed console is for CLI output
        self.console = Console()
        self.state = ProgressState()


        # Rich components
        self._live: Live | None = None
        self._progress: Progress | None = None

        # Initialize checkpoints
        for checkpoint_name in config.checkpoints:
            self.state.checkpoints[checkpoint_name] = CheckpointState(
                name=checkpoint_name
            )


    def start(self) -> None:
        """Start the live display."""
        if self._live is not None:
            return

        # Initialize progress tracking
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
            transient=False,
        )

        # Add a main task for current checkpoint progress
        self._main_task_id = self._progress.add_task("Starting...", total=100)

        # Start live display with combined progress and checkpoint panel
        self._live = Live(
            self._generate_combined_display(),
            console=self.console,
            refresh_per_second=self.config.refresh_rate,
            transient=False,
        )
        self._live.start()

        # Record start time
        self.state.start_time = time.time()

    def stop(self) -> None:
        """Stop the live display."""
        # Stop live display
        if self._live is not None:
            self._live.stop()
            self._live = None

        self._progress = None

    def _update_display(self) -> None:
        """Update the live display."""
        if self._live is not None:
            self._live.update(self._generate_combined_display())

    def _generate_combined_display(self) -> Panel:
        """Generate combined display with progress and checkpoint panel."""
        # Just return the checkpoint panel - it now includes the progress bar inside
        return self._generate_checkpoint_panel()

    def _generate_checkpoint_panel(self) -> Panel:
        """Generate checkpoint status panel.

        Returns:
            Panel containing checkpoint status and overall progress
        """
        table = Table.grid(padding=(0, 1))
        table.add_column(style=Colors.NORMAL, no_wrap=False, width=None)

        # Current task progress bar (if active)
        if self._progress and self.state.current_checkpoint:
            # Create a custom progress bar representation
            current_percentage = (self.state.current_progress / self.state.total_progress * 100) if self.state.total_progress > 0 else 0

            progress_text = Text()
            progress_text.append("Current: ", style=Colors.MUTED)
            progress_text.append(f"{self.state.current_checkpoint} ", style=Colors.RUNNING)

            # Create progress bar
            bar_width = 25
            filled_width = int((current_percentage / 100.0) * bar_width)
            empty_width = bar_width - filled_width

            filled_char = Icons.get_icon("PROGRESS_FULL", self.config.icon_mode) or "█"
            empty_char = Icons.get_icon("PROGRESS_EMPTY", self.config.icon_mode) or "░"
            progress_bar = filled_char * filled_width + empty_char * empty_width

            progress_text.append(progress_bar, style=Colors.LOADING_TEXT)
            progress_text.append(f" {current_percentage:>5.1f}%", style=Colors.MUTED)

            table.add_row(progress_text)
            table.add_row("")  # Spacer

        # Status lines
        if self.config.show_status_line and (
            self.state.status_message or self.state.status_info
        ):
            status_lines = self._format_status_line()
            if status_lines:
                for status_line in status_lines:
                    table.add_row(status_line)
                table.add_row("")  # Spacer

        # Checkpoint list
        if self.state.checkpoints:
            for checkpoint_name in self.config.checkpoints:
                if checkpoint_name in self.state.checkpoints:
                    checkpoint = self.state.checkpoints[checkpoint_name]
                    icon = self._get_checkpoint_icon(checkpoint.status)
                    style = self._get_checkpoint_style(checkpoint.status)

                    checkpoint_text = Text()
                    checkpoint_text.append(f" {icon} ", style=style)
                    checkpoint_text.append(checkpoint.name, style=style)

                    # Add duration for completed checkpoints
                    if checkpoint.duration is not None:
                        checkpoint_text.append(
                            f" ({checkpoint.duration:.1f}s)", style=Colors.MUTED
                        )

                    table.add_row(checkpoint_text)

        # Overall progress bar
        if self.config.show_overall_progress and self.state.total_checkpoints > 0:
            table.add_row("")  # Spacer

            overall_text = Text()
            overall_text.append("Overall: ", style=Colors.MUTED)

            overall_percentage = self.state.overall_progress_percentage
            overall_bar_width = 30
            overall_filled_width = int((overall_percentage / 100.0) * overall_bar_width)
            overall_empty_width = overall_bar_width - overall_filled_width

            filled_char = Icons.get_icon("PROGRESS_FULL", self.config.icon_mode) or "█"
            empty_char = Icons.get_icon("PROGRESS_EMPTY", self.config.icon_mode) or "░"
            overall_progress_bar = (
                filled_char * overall_filled_width + empty_char * overall_empty_width
            )
            overall_text.append(overall_progress_bar, style=Colors.LOADING_TEXT)
            overall_text.append(
                f" {overall_percentage:>5.1f}% ({self.state.completed_checkpoints}/{self.state.total_checkpoints} tasks)",
                style=Colors.MUTED,
            )

            table.add_row(overall_text)

        # Determine panel styling based on state
        if self.state.is_complete:
            title = Icons.format_with_icon(
                "SUCCESS",
                "Status",
                self.config.icon_mode,
            )
            border_style = Colors.SUCCESS
        elif self.state.is_failed:
            title = Icons.format_with_icon(
                "ERROR",
                "Status",
                self.config.icon_mode,
            )
            border_style = Colors.ERROR
        else:
            title = Icons.format_with_icon(
                "PROCESSING", "Status", self.config.icon_mode
            )
            border_style = Colors.INFO

        return Panel(
            table,
            title=title,
            border_style=border_style,
        )


    def _format_status_line(self) -> list[Text]:
        """Format the status line with current information.

        Returns:
            List of formatted status Text objects, one per line
        """
        if not self.state.status_message and not self.state.status_info:
            return []

        status_lines = []

        # Add status message if present
        if self.state.status_message:
            status_text = Text()
            status_text.append("Status: ", style=Colors.MUTED)
            # Truncate long status messages
            display_status = self.state.status_message
            if len(display_status) > 70:
                display_status = display_status[:67] + "..."
            status_text.append(display_status, style=Colors.INFO)
            status_lines.append(status_text)

        # Add status info if present
        if self.state.status_info:
            # Current file
            if "current_file" in self.state.status_info:
                file_text = Text()
                file_text.append("File: ", style=Colors.MUTED)
                filename = self.state.status_info['current_file']
                # Truncate long filenames
                if len(filename) > 60:
                    filename = "..." + filename[-57:]
                file_text.append(filename, style=Colors.NORMAL)
                status_lines.append(file_text)

            # Component
            if "component" in self.state.status_info:
                component_text = Text()
                component_text.append("Component: ", style=Colors.MUTED)
                component_text.append(self.state.status_info['component'], style=Colors.INFO)
                status_lines.append(component_text)

            # Files remaining and data progress on same line
            progress_parts = []
            if "files_remaining" in self.state.status_info:
                remaining = self.state.status_info["files_remaining"]
                progress_parts.append(f"Files remaining: {remaining:,}")

            if "bytes_copied" in self.state.status_info and "total_bytes" in self.state.status_info:
                bytes_copied = self.state.status_info["bytes_copied"]
                total_bytes = self.state.status_info["total_bytes"]
                if total_bytes > 0:
                    progress_mb = bytes_copied / (1024 * 1024)
                    total_mb = total_bytes / (1024 * 1024)
                    if total_mb >= 1024:
                        progress_gb = progress_mb / 1024
                        total_gb = total_mb / 1024
                        progress_parts.append(f"Data: {progress_gb:.1f}/{total_gb:.1f} GB")
                    else:
                        progress_parts.append(f"Data: {progress_mb:.1f}/{total_mb:.1f} MB")

            if progress_parts:
                progress_text = Text()
                progress_text.append(" | ".join(progress_parts), style=Colors.MUTED)
                status_lines.append(progress_text)

            # Speed and ETA on same line
            speed_parts = []
            if "transfer_speed" in self.state.status_info:
                speed = self.state.status_info["transfer_speed"]
                speed_parts.append(f"Speed: {speed:.1f} MB/s")

            if "eta_seconds" in self.state.status_info:
                eta = self.state.status_info["eta_seconds"]
                if eta >= 60:
                    speed_parts.append(f"ETA: {eta / 60:.1f}m")
                else:
                    speed_parts.append(f"ETA: {eta:.0f}s")

            if speed_parts:
                speed_text = Text()
                speed_text.append(" | ".join(speed_parts), style=Colors.MUTED)
                status_lines.append(speed_text)

        return status_lines

    def _get_checkpoint_icon(self, status: str) -> str:
        """Get icon for checkpoint status.

        Args:
            status: Checkpoint status

        Returns:
            Icon string
        """
        icon_map = {
            "pending": "BULLET",
            "active": "RUNNING",
            "completed": "SUCCESS",
            "failed": "ERROR",
        }
        icon_name = icon_map.get(status, "BULLET")
        return Icons.get_icon(icon_name, self.config.icon_mode)

    def _get_checkpoint_style(self, status: str) -> str:
        """Get style for checkpoint status.

        Args:
            status: Checkpoint status

        Returns:
            Style string
        """
        style_map = {
            "pending": Colors.MUTED,
            "active": Colors.RUNNING,
            "completed": Colors.COMPLETED,
            "failed": Colors.FAILED,
        }
        return style_map.get(status, Colors.NORMAL)

    def _get_log_level_style(self, level: str) -> str:
        """Get style for log level.

        Args:
            level: Log level name

        Returns:
            Style string
        """
        style_map = {
            "DEBUG": Colors.MUTED,
            "INFO": Colors.INFO,
            "WARNING": Colors.WARNING,
            "ERROR": Colors.ERROR,
            "CRITICAL": Colors.ERROR,
        }
        return style_map.get(level, Colors.NORMAL)
