"""Staged progress display with Rich console output."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)

from glovebox.cli.progress.displays.base import ProgressDisplayProtocol
from glovebox.cli.progress.models import ProgressContext


class StagedProgressDisplay:
    """Staged progress display using Rich progress bars."""

    def __init__(self, context: ProgressContext) -> None:
        """Initialize staged display."""
        self.context = context
        self.console = Console()
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
        """Start the staged display."""
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

        # Setup callbacks
        self._setup_callbacks()

    def stop(self) -> None:
        """Stop the staged display."""
        if self.progress:
            self.progress.stop()

    def update(self) -> None:
        """Update the display with current progress."""
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

    def get_context(self) -> ProgressContext:
        """Get the progress context."""
        return self.context

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
