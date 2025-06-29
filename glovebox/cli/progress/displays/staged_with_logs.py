"""Staged progress display with scrollable log panel on top."""

from __future__ import annotations

from typing import Any, Union

from rich.console import Console, Group, RenderableType
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.text import Text

from glovebox.cli.progress.displays.base import ProgressDisplayProtocol
from glovebox.cli.progress.log_handler import LogBuffer
from glovebox.cli.progress.models import ProgressContext


class StagedProgressWithLogsDisplay:
    """Staged progress display with scrollable log panel on top."""

    def __init__(self, context: ProgressContext) -> None:
        """Initialize staged display with logs."""
        self.context = context
        self.console = Console(force_terminal=True, width=None)  # Use dedicated console
        self.log_buffer = LogBuffer(max_lines=context.display_config.max_log_lines)

        # Rich components
        self.layout: Layout | None = None
        self.live: Live | None = None
        self.progress: Progress | None = None
        self.main_task: TaskID | None = None
        self.workspace_task: TaskID | None = None

    def __enter__(self) -> ProgressDisplayProtocol:
        """Enter context manager."""
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager."""
        self.stop()

    def start(self) -> None:
        """Start the display with logs and progress panels."""
        # Setup log capture
        self.log_buffer.setup_handler("glovebox")

        # Create layout with log panel on top, progress on bottom
        self.layout = Layout(name="root")

        log_height = self.context.display_config.log_panel_height
        progress_height = 10

        self.layout.split(
            Layout(name="logs", size=log_height),
            Layout(name="progress", size=progress_height),
        )

        # Create Rich progress with multiple columns
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=self.console,
        )

        # Start the progress display
        self.progress.start()

        # Create main compilation task
        total_stages = self.context.progress.total_stages or 1
        self.main_task = self.progress.add_task(
            description="Compilation",
            total=total_stages,
        )

        # Create workspace task if workspace details are enabled
        if self.context.display_config.show_workspace_details:
            self.workspace_task = self.progress.add_task(
                description="Workspace setup",
                total=100,  # Percentage-based for workspace operations
            )

        # Initialize layout content
        self._update_layout()

        # Start Live display
        self.live = Live(
            self.layout,
            console=self.console,
            auto_refresh=True,
            refresh_per_second=2,  # Moderate refresh rate
        )
        self.live.start()

        # Setup callbacks
        self._setup_callbacks()

    def stop(self) -> None:
        """Stop the display and cleanup."""
        if self.live:
            self.live.stop()
        if self.progress:
            self.progress.stop()

        # Cleanup log handler
        self.log_buffer.cleanup()

    def update(self) -> None:
        """Update the display with current progress and logs."""
        if not self.layout or not self.progress:
            return

        self._update_progress_tasks()
        self._update_layout()

    def get_context(self) -> ProgressContext:
        """Get the progress context."""
        return self.context

    def _update_progress_tasks(self) -> None:
        """Update Rich progress tasks with current data."""
        if not self.progress or not self.main_task:
            return

        # Update main compilation progress
        compilation_progress = self.context.progress
        self.progress.update(
            self.main_task,
            completed=compilation_progress.current_stage,
            description=compilation_progress.description or "Processing...",
        )

        # Update workspace progress if enabled
        if self.workspace_task and self.context.display_config.show_workspace_details:
            workspace_progress = self.context.workspace_progress
            workspace_status = workspace_progress.get_status_text()

            # Calculate overall workspace completion
            if workspace_progress.total_components > 0:
                workspace_completion = (
                    workspace_progress.completed_components
                    / workspace_progress.total_components
                ) * 100
            else:
                workspace_completion = 0

            self.progress.update(
                self.workspace_task,
                completed=workspace_completion,
                description=workspace_status,
            )

    def _update_layout(self) -> None:
        """Update the layout with current logs and progress."""
        if not self.layout:
            return

        # Update log panel
        log_panel = self._create_log_panel()
        self.layout["logs"].update(log_panel)

        # Update progress panel
        progress_panel = self._create_progress_panel()
        self.layout["progress"].update(progress_panel)

    def _create_log_panel(self) -> Panel:
        """Create scrollable log panel."""
        log_lines = self.log_buffer.get_recent_logs(
            count=self.context.display_config.log_panel_height - 2
        )

        content: RenderableType
        if not log_lines:
            content = Text("Waiting for logs...", style="dim")
        else:
            # Create text objects with appropriate styling
            styled_lines = []
            for line in log_lines:
                style = self.log_buffer.get_log_style(line)
                styled_lines.append(Text(line, style=style))

            content = Group(*styled_lines)

        return Panel(
            content,
            title="📋 Logs",
            border_style="blue",
            height=self.context.display_config.log_panel_height,
        )

    def _create_progress_panel(self) -> Panel:
        """Create progress panel."""
        content: RenderableType
        if not self.progress:
            content = Text("No progress data", style="dim")
        else:
            content = self.progress

        return Panel(content, title="⚡ Progress", border_style="green", height=10)

    def _setup_callbacks(self) -> None:
        """Setup callbacks to update display on progress changes."""
        original_on_progress = self.context.callbacks.on_progress_update
        original_on_workspace = self.context.callbacks.on_workspace_update

        def update_callback(*args: Any) -> None:
            self.update()
            if original_on_progress:
                original_on_progress(*args)

        def workspace_callback(*args: Any) -> None:
            self.update()
            if original_on_workspace:
                original_on_workspace(*args)

        self.context.callbacks.on_progress_update = update_callback
        self.context.callbacks.on_workspace_update = workspace_callback
