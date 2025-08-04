"""Modern table-based progress display component with Rich integration."""

import threading
import time
from datetime import datetime

from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

from glovebox.cli.components.progress_config import (
    CheckpointState,
    ProgressConfig,
    ProgressState,
)
from glovebox.cli.helpers.theme import Colors, Icons


class ProgressDisplay:
    """Modern table-based progress display with Rich integration.

    This component provides a live-updating interface showing:
    - Header panel with overall statistics
    - Task status table with embedded progress bars
    - Footer panel with overall progress
    - Real-time status updates with better visual hierarchy
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

        # Logging
        self._log_lock = threading.Lock()

        # Initialize checkpoints as tasks
        for checkpoint_name in config.checkpoints:
            self.state.checkpoints[checkpoint_name] = CheckpointState(
                name=checkpoint_name
            )

    def start(self) -> None:
        """Start the live display."""
        if self._live is not None:
            return

        # Start live display with complete interface
        self._live = Live(
            self._generate_complete_display(),
            console=self.console,
            refresh_per_second=self.config.refresh_rate,
            transient=False,
        )
        self._live.start()

        # Record start time
        self.state.start_time = time.time()

    def stop(self) -> None:
        """Stop the live display."""
        if self._live is not None:
            self._live.stop()
            self._live = None

    def add_log(self, message: str, checkpoint_name: str | None = None) -> None:
        """Add a log message using console.print.

        Args:
            message: Log message to display
            checkpoint_name: Optional checkpoint to associate the log with
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[dim][{timestamp}][/dim] {message}"

        with self._log_lock:
            # Add to checkpoint-specific logs if specified
            if checkpoint_name and checkpoint_name in self.state.checkpoints:
                # Store in state for potential display in UI
                if "log_lines" not in self.state.status_info:
                    self.state.status_info["log_lines"] = []
                self.state.status_info["log_lines"].append(log_entry)

                # Keep only recent logs (last 50)
                if len(self.state.status_info["log_lines"]) > 50:
                    self.state.status_info["log_lines"] = self.state.status_info[
                        "log_lines"
                    ][-50:]

            # Print directly to console (outside Live display to avoid conflicts)
            self.console.print(log_entry)

    def _update_display(self) -> None:
        """Update the live display."""
        if self._live is not None:
            self._live.update(self._generate_complete_display())

    def _generate_combined_display(self) -> Panel:
        """Generate combined display for backward compatibility.

        Returns:
            Panel containing the complete interface
        """
        return Panel(
            self._generate_complete_display(),
            title="Status",
            border_style=self._get_border_style(),
        )

    def _generate_complete_display(self) -> Group:
        """Generate complete display with header, table, and footer."""
        # Build components list with proper typing
        header = self._create_header()
        task_table = Panel(
            self._create_task_status_table(),
            title=self._get_table_title(),
            border_style=self._get_border_style(),
        )
        footer = self._create_footer()

        # Check if we should show detailed status
        show_details = (
            self.state.current_checkpoint
            and self.state.current_checkpoint in self.state.checkpoints
            and self.state.checkpoints[self.state.current_checkpoint].status == "active"
        )

        components = [
            header,
            "",  # Empty line
            task_table,
        ]

        if show_details:
            details_panel = self._create_active_task_details()
            components.extend(
                [
                    "",  # Empty line
                    details_panel,
                ]
            )

        components.extend(
            [
                "",  # Empty line
                footer,
            ]
        )

        return Group(*components)

    def _create_header(self) -> Panel:
        """Create header panel with operation statistics."""
        completed_tasks = sum(
            1
            for checkpoint in self.state.checkpoints.values()
            if checkpoint.status == "completed"
        )
        failed_tasks = sum(
            1
            for checkpoint in self.state.checkpoints.values()
            if checkpoint.status == "failed"
        )
        total_tasks = len(self.state.checkpoints)

        # Get icon and title based on state
        if self.state.is_complete:
            icon = Icons.get_icon("SUCCESS", self.config.icon_mode)
        elif self.state.is_failed:
            icon = Icons.get_icon("ERROR", self.config.icon_mode)
        else:
            icon = Icons.get_icon("PROCESSING", self.config.icon_mode)

        title = Text(f"{icon} {self.config.full_operation_name}", style="bold blue")

        status_text = f"Tasks: {completed_tasks}/{total_tasks} completed"
        if failed_tasks > 0:
            status_text += f", {failed_tasks} failed"

        header_content = Group(
            Align.center(title), Align.center(Text(status_text, style="dim"))
        )

        return Panel(header_content, style=Colors.SECONDARY)

    def _create_task_status_table(self) -> Table:
        """Create table showing checkpoint statuses with embedded progress bars."""
        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("Task", style=Colors.PRIMARY, no_wrap=True, width=20)
        table.add_column("Status", justify="center", width=10)
        table.add_column("Progress", justify="left", width=30)
        table.add_column("%", justify="center", width=8)
        table.add_column("Details", style="dim", width=30)

        for checkpoint_name in self.config.checkpoints:
            if checkpoint_name not in self.state.checkpoints:
                continue

            checkpoint = self.state.checkpoints[checkpoint_name]

            # Status with color
            status_text = self._get_status_display(checkpoint.status)

            # Progress bar
            progress_bar = self._create_checkpoint_progress_bar(checkpoint_name)

            # Completion percentage
            completion_text, completion_style = self._get_completion_display(
                checkpoint_name
            )
            completion = Text(completion_text, style=completion_style)

            # Details from status info
            details_text = self._get_checkpoint_details(checkpoint_name)

            table.add_row(
                checkpoint.name, status_text, progress_bar, completion, details_text
            )

        return table

    def _create_footer(self) -> Panel:
        """Create footer with overall progress."""
        completed = self.state.completed_checkpoints
        total = self.state.total_checkpoints

        if total > 0:
            overall_pct = self.state.overall_progress_percentage

            # Create overall progress bar
            overall_bar = ProgressBar(
                total=total,
                completed=completed,
                width=30,
                pulse=False,
                animation_time=time.time(),
                style="bar.back",
                complete_style="bar.complete",
                finished_style="bar.finished",
            )

            footer_content = Group(
                Align.center(
                    Text(
                        f"Overall: {completed}/{total} ({overall_pct:.0f}%)",
                        style="bold",
                    )
                ),
                Align.center(overall_bar),
            )
        else:
            footer_content = Group(
                Align.center(
                    Text(f"Ready for {self.config.operation_name}...", style="bold")
                )
            )

        return Panel(footer_content, style=Colors.SUCCESS)

    def _create_active_task_details(self) -> Panel:
        """Create detailed status panel for the currently active task."""
        if not self.state.current_checkpoint:
            return Panel(Text("No active task", style="dim"), title="Task Details")

        details_table = Table.grid(padding=(0, 2))
        details_table.add_column("Label", style="cyan", width=12)
        details_table.add_column("Value", style="white")

        # Current file being processed
        if "current_file" in self.state.status_info:
            current_file = str(self.state.status_info["current_file"])
            details_table.add_row("File:", current_file)

        # Processing speed
        if "speed" in self.state.status_info:
            speed = self.state.status_info["speed"]
            details_table.add_row("Speed:", f"{speed} files/sec")

        # Files processed vs total
        if "files_copied" in self.state.status_info:
            files_copied = self.state.status_info["files_copied"]
            details_table.add_row("Processed:", f"{files_copied} files")

        # Remaining files
        if "files_remaining" in self.state.status_info:
            files_remaining = self.state.status_info["files_remaining"]
            details_table.add_row("Remaining:", f"{files_remaining} files")

        # Component info
        if "component" in self.state.status_info:
            component = self.state.status_info["component"]
            details_table.add_row("Component:", component)

        # Docker status
        if "docker_status" in self.state.status_info:
            docker_status = self.state.status_info["docker_status"]
            details_table.add_row("Docker:", docker_status)

        # Time elapsed for current task
        checkpoint = self.state.checkpoints[self.state.current_checkpoint]
        if checkpoint.start_time:
            elapsed = time.time() - checkpoint.start_time
            details_table.add_row("Elapsed:", f"{elapsed:.1f}s")

        return Panel(
            details_table,
            title=f"{self.state.current_checkpoint} Details",
            border_style=Colors.INFO,
            style="dim",
        )

    def _create_recent_logs_panel(self) -> Panel:
        """Create panel showing recent log entries."""
        if "log_lines" not in self.state.status_info:
            return Panel(
                Text("No logs available", style="dim"), title="Recent Logs", style="dim"
            )

        log_lines = self.state.status_info["log_lines"]

        # Show last 5 log entries to keep display compact
        recent_logs = log_lines[-5:] if len(log_lines) > 5 else log_lines

        log_table = Table.grid(padding=(0, 1))
        log_table.add_column(style=Colors.NORMAL, no_wrap=False)

        for log_line in recent_logs:
            log_table.add_row(Text.from_markup(log_line))

        # If there are more logs, show indicator
        if len(log_lines) > 5:
            log_table.add_row(
                Text(f"... and {len(log_lines) - 5} more entries", style="dim italic")
            )

        return Panel(
            log_table,
            title=f"Recent Logs ({len(log_lines)} total)",
            border_style=Colors.INFO,
            style="dim",
        )

    def _get_status_display(self, status: str) -> Text:
        """Get formatted status display."""
        if status == "active":
            return Text("↻ Run", style=Colors.WARNING)
        elif status == "completed":
            return Text("✓ Done", style=Colors.SUCCESS)
        elif status == "failed":
            return Text("✗ Fail", style=Colors.ERROR)
        else:
            return Text("○ Wait", style="dim")

    def _create_checkpoint_progress_bar(self, checkpoint_name: str) -> ProgressBar:
        """Create progress bar for a checkpoint."""
        # Calculate progress for current checkpoint
        if checkpoint_name == self.state.current_checkpoint:
            if self.state.total_progress > 0:
                progress = self.state.current_progress
                total = self.state.total_progress
            else:
                progress = 0
                total = None
        else:
            checkpoint = self.state.checkpoints[checkpoint_name]
            if checkpoint.status == "completed":
                progress = 100
                total = 100
            elif checkpoint.status == "active":
                progress = 0
                total = None  # Indeterminate
            else:
                progress = 0
                total = 100

        return ProgressBar(
            total=total,
            completed=progress,
            width=25,
            pulse=checkpoint_name == self.state.current_checkpoint and total is None,
            animation_time=time.time(),
            style="bar.back",
            complete_style="bar.complete",
            finished_style="bar.finished",
            pulse_style="bar.pulse",
        )

    def _get_completion_display(self, checkpoint_name: str) -> tuple[str, str]:
        """Get completion percentage display."""
        checkpoint = self.state.checkpoints[checkpoint_name]

        if (
            checkpoint_name == self.state.current_checkpoint
            and self.state.total_progress > 0
        ):
            progress_pct = (
                self.state.current_progress / self.state.total_progress
            ) * 100
            completion_text = f"{progress_pct:.0f}%"
            completion_style = "yellow"
        elif checkpoint.status == "completed":
            completion_text = "100%"
            completion_style = "green"
        elif checkpoint.status == "active":
            completion_text = "..."
            completion_style = "yellow"
        else:
            completion_text = "-"
            completion_style = "dim"

        return completion_text, completion_style

    def _get_checkpoint_details(self, checkpoint_name: str) -> str:
        """Get brief details text for checkpoint in table."""
        details_list = []
        checkpoint = self.state.checkpoints[checkpoint_name]

        # For active checkpoint, show brief progress info
        if checkpoint_name == self.state.current_checkpoint:
            if "files_remaining" in self.state.status_info:
                remaining = self.state.status_info["files_remaining"]
                details_list.append(f"Remaining: {remaining}")
            elif "files_copied" in self.state.status_info:
                copied = self.state.status_info["files_copied"]
                details_list.append(f"Processed: {copied}")

        # Show duration for completed checkpoints
        if checkpoint.duration is not None:
            details_list.append(f"({checkpoint.duration:.1f}s)")

        return " | ".join(details_list) if details_list else ""

    def _get_table_title(self) -> str:
        """Get table title with icon."""
        icon = Icons.get_icon("BULLET", self.config.icon_mode)
        return f"{icon} {self.config.operation_name} Tasks"

    def _get_border_style(self) -> str:
        """Get border style based on current state."""
        if self.state.is_complete:
            return Colors.SUCCESS
        elif self.state.is_failed:
            return Colors.ERROR
        else:
            return Colors.INFO
