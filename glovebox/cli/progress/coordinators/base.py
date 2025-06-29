"""Base progress coordinator with workspace integration."""

from __future__ import annotations

import logging
import time
from typing import Any

from glovebox.cli.progress.models import (
    ProgressContext,
    ProgressCoordinatorProtocol,
    WorkspaceOperation,
)
from glovebox.compilation.models import CompilationProgress, CompilationState


class BaseProgressCoordinator:
    """Base progress coordinator with workspace-aware capabilities.

    This replaces the old BaseCompilationProgressCoordinator while maintaining
    the same interface but adding workspace operation support.
    """

    def __init__(self, context: ProgressContext) -> None:
        """Initialize with progress context."""
        self.context = context
        self.logger = logging.getLogger(self.__class__.__name__)
        self._last_update_time = 0.0

    def update_progress(self, progress: CompilationProgress) -> None:
        """Update compilation progress and trigger callbacks."""
        old_state = self.context.progress.state
        self.context.progress = progress

        # Trigger callbacks
        if self.context.callbacks.on_progress_update:
            self.context.callbacks.on_progress_update(progress)

        # Handle state transitions
        if old_state != progress.state:
            self._handle_state_transition(old_state, progress.state)

    def update_workspace(
        self, operation: WorkspaceOperation, component: str | None = None, **kwargs: Any
    ) -> None:
        """Update workspace operation progress."""
        self.context.update_workspace(operation, component, **kwargs)

        # Log workspace updates at debug level
        if component:
            self.logger.debug(
                "Workspace operation %s on component %s: %s",
                operation.value,
                component,
                kwargs,
            )
        else:
            self.logger.debug("Workspace operation %s: %s", operation.value, kwargs)

    def get_context(self) -> ProgressContext:
        """Get the current progress context."""
        return self.context

    def handle_phase_change(self, old_phase: str, new_phase: str) -> None:
        """Handle phase transitions with workspace awareness."""
        self.logger.debug("Phase transition: %s -> %s", old_phase, new_phase)

        # Update progress description
        self.context.progress.description = self._get_phase_description(new_phase)

        # Trigger callback
        if self.context.callbacks.on_phase_change:
            self.context.callbacks.on_phase_change(old_phase, new_phase)

    def start_operation(self) -> None:
        """Mark operation as started."""
        self.context.is_active = True
        self.context.start_time = time.time()
        self.logger.debug("Started %s operation", self.context.operation_type)

    def complete_operation(self, result: Any = None) -> None:
        """Mark operation as completed."""
        self.context.is_active = False
        self.context.end_time = time.time()

        if self.context.callbacks.on_complete:
            self.context.callbacks.on_complete(result)

        duration = self.get_operation_duration()
        self.logger.debug(
            "Completed %s operation in %.2fs", self.context.operation_type, duration
        )

    def handle_error(self, error: Exception, phase: str = "unknown") -> None:
        """Handle errors with proper logging."""
        exc_info = self.logger.isEnabledFor(logging.DEBUG)
        self.logger.error("Error in %s phase: %s", phase, error, exc_info=exc_info)

        if self.context.callbacks.on_error:
            self.context.callbacks.on_error(phase, error)

    def get_operation_duration(self) -> float:
        """Get operation duration in seconds."""
        if not self.context.start_time:
            return 0.0
        end_time = self.context.end_time or time.time()
        return end_time - self.context.start_time

    def should_throttle_updates(self) -> bool:
        """Check if updates should be throttled to avoid spam."""
        current_time = time.time()
        min_interval = self.context.display_config.update_interval

        if current_time - self._last_update_time < min_interval:
            return True

        self._last_update_time = current_time
        return False

    def _handle_state_transition(
        self, old_state: CompilationState, new_state: CompilationState
    ) -> None:
        """Handle compilation state transitions."""
        self.logger.debug("State transition: %s -> %s", old_state, new_state)

        # Update workspace operations based on state
        if new_state == CompilationState.WORKSPACE_SETUP:
            self.update_workspace(WorkspaceOperation.WORKSPACE_INIT)
        elif new_state == CompilationState.CACHE_SETUP:
            self.update_workspace(WorkspaceOperation.CACHE_CHECK)

    def _get_phase_description(self, phase: str) -> str:
        """Get human-readable description for a phase."""
        phase_descriptions = {
            "workspace_setup": "Setting up workspace...",
            "cache_check": "Checking cache...",
            "cache_restore": "Restoring from cache...",
            "west_init": "Initializing West workspace...",
            "west_update": "Updating dependencies...",
            "compilation": "Compiling firmware...",
            "post_processing": "Processing output...",
            "cleanup": "Cleaning up...",
        }
        return phase_descriptions.get(phase, f"Processing {phase}...")

    def create_workspace_callback(self) -> Any:
        """Create a callback for workspace services to use."""

        def callback(
            operation: str, component: str | None = None, **progress_data: Any
        ) -> None:
            """Workspace operation callback."""
            # Map string to enum
            op_map = {
                "cache_check": WorkspaceOperation.CACHE_CHECK,
                "cache_restore": WorkspaceOperation.CACHE_RESTORE,
                "workspace_init": WorkspaceOperation.WORKSPACE_INIT,
                "component_copy": WorkspaceOperation.COMPONENT_COPY,
                "west_init": WorkspaceOperation.WEST_INIT,
                "west_update": WorkspaceOperation.WEST_UPDATE,
                "manifest_setup": WorkspaceOperation.MANIFEST_SETUP,
            }

            workspace_op = op_map.get(operation, WorkspaceOperation.WORKSPACE_INIT)

            # Don't spam updates
            if not self.should_throttle_updates():
                self.update_workspace(workspace_op, component, **progress_data)

        return callback
