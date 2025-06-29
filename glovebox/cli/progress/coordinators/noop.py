"""No-op progress coordinator for silent operations."""

from __future__ import annotations

from typing import Any

from glovebox.cli.progress.coordinators.base import BaseProgressCoordinator
from glovebox.cli.progress.models import ProgressContext, WorkspaceOperation
from glovebox.compilation.models import CompilationProgress


class NoOpProgressCoordinator(BaseProgressCoordinator):
    """No-op progress coordinator that doesn't display anything."""

    def __init__(self, context: ProgressContext) -> None:
        """Initialize no-op coordinator."""
        super().__init__(context)

    def update_progress(self, progress: CompilationProgress) -> None:
        """Update progress silently."""
        # Just update the context without any display
        self.context.progress = progress

    def update_workspace(
        self, operation: WorkspaceOperation, component: str | None = None, **kwargs: Any
    ) -> None:
        """Update workspace silently."""
        # Update context without any output
        self.context.update_workspace(operation, component, **kwargs)

    def handle_phase_change(self, old_phase: str, new_phase: str) -> None:
        """Handle phase changes silently."""
        # Just log at debug level
        self.logger.debug("Silent phase transition: %s -> %s", old_phase, new_phase)

    def start_operation(self) -> None:
        """Start operation silently."""
        super().start_operation()

    def complete_operation(self, result: Any = None) -> None:
        """Complete operation silently."""
        super().complete_operation(result)
