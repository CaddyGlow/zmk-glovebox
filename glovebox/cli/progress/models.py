"""Progress context models for unified multi-phase command execution.

This module provides a unified context object that carries all progress-related
state through multiple phases of command execution, including workspace operations.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from pydantic import ConfigDict

from glovebox.compilation.models import CompilationProgress
from glovebox.models.base import GloveboxBaseModel


class ProgressDisplayType(str, Enum):
    """Types of progress displays available."""

    STAGED = "staged"
    SIMPLE = "simple"
    NONE = "none"


class WorkspaceOperation(str, Enum):
    """Types of workspace operations for progress tracking."""

    CACHE_CHECK = "cache_check"
    CACHE_RESTORE = "cache_restore"
    WORKSPACE_INIT = "workspace_init"
    COMPONENT_COPY = "component_copy"
    WEST_INIT = "west_init"
    WEST_UPDATE = "west_update"
    MANIFEST_SETUP = "manifest_setup"


class WorkspaceComponentProgress(GloveboxBaseModel):
    """Progress tracking for individual workspace components."""

    name: str
    operation: WorkspaceOperation
    source_path: Path | None = None
    target_path: Path | None = None
    bytes_copied: int = 0
    total_bytes: int = 0
    files_copied: int = 0
    total_files: int = 0
    status: str = ""
    is_complete: bool = False


class WorkspaceProgress(GloveboxBaseModel):
    """Workspace-specific progress tracking."""

    current_operation: WorkspaceOperation | None = None
    current_component: str | None = None
    components: dict[str, WorkspaceComponentProgress] = {}
    workspace_path: Path | None = None
    cache_hit: bool = False
    total_components: int = 0
    completed_components: int = 0

    def get_status_text(self) -> str:
        """Generate human-readable status for workspace operations."""
        if not self.current_operation:
            return "Initializing workspace..."

        if self.current_operation == WorkspaceOperation.CACHE_CHECK:
            return "Checking workspace cache..."
        elif self.current_operation == WorkspaceOperation.CACHE_RESTORE:
            if self.current_component:
                comp = self.components.get(self.current_component)
                if comp and comp.total_bytes > 0:
                    pct = (comp.bytes_copied / comp.total_bytes) * 100
                    return f"Restoring {comp.name}: {pct:.0f}%"
                return f"Restoring {self.current_component}..."
            return "Restoring workspace from cache..."
        elif self.current_operation == WorkspaceOperation.COMPONENT_COPY:
            if self.current_component:
                return f"Copying {self.current_component}..."
            return "Copying workspace components..."
        elif self.current_operation == WorkspaceOperation.WEST_UPDATE:
            return "Updating West workspace..."
        else:
            return f"Workspace: {self.current_operation.value}"


class ProgressDisplayConfig(GloveboxBaseModel):
    """Configuration for progress display."""

    display_type: ProgressDisplayType = ProgressDisplayType.STAGED
    show_logs: bool = True
    show_workspace_details: bool = True
    show_cache_operations: bool = True
    update_interval: float = 0.1
    custom_stages: list[str] | None = None


class ProgressCallbacks(GloveboxBaseModel):
    """Callbacks for progress events."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    on_phase_change: Callable[[str, str], None] | None = None
    on_progress_update: Callable[[CompilationProgress], None] | None = None
    on_workspace_update: Callable[[WorkspaceProgress], None] | None = None
    on_error: Callable[[str, Exception], None] | None = None
    on_complete: Callable[[Any], None] | None = None


class ProgressContext(GloveboxBaseModel):
    """Unified context for multi-phase command execution with workspace integration."""

    # Core progress tracking
    progress: CompilationProgress
    workspace_progress: WorkspaceProgress = field(default_factory=WorkspaceProgress)

    # Display configuration
    display_config: ProgressDisplayConfig = field(default_factory=ProgressDisplayConfig)

    # Strategy and operation info
    strategy: str
    operation_type: str = "compilation"

    # Workspace and cache integration
    workspace_path: Path | None = None
    cache_enabled: bool = True
    cache_key: str | None = None

    # Strategy-specific data
    strategy_data: dict[str, Any] = {}

    # Callbacks for different events
    callbacks: ProgressCallbacks = field(default_factory=ProgressCallbacks)

    # Runtime state
    is_active: bool = False
    start_time: float | None = None
    end_time: float | None = None

    def update_workspace(
        self,
        operation: WorkspaceOperation,
        component: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Update workspace progress state."""
        self.workspace_progress.current_operation = operation
        if component:
            self.workspace_progress.current_component = component
            if component not in self.workspace_progress.components:
                self.workspace_progress.components[component] = (
                    WorkspaceComponentProgress(name=component, operation=operation)
                )
            comp_progress = self.workspace_progress.components[component]
            for key, value in kwargs.items():
                if hasattr(comp_progress, key):
                    setattr(comp_progress, key, value)

        # Trigger callback if set
        if self.callbacks.on_workspace_update:
            self.callbacks.on_workspace_update(self.workspace_progress)

    def get_current_status(self) -> str:
        """Get current status text combining compilation and workspace progress."""
        if self.workspace_progress.current_operation:
            return self.workspace_progress.get_status_text()
        return self.progress.description or "Processing..."


class ProgressCoordinatorProtocol(Protocol):
    """Protocol for progress coordinators with workspace support."""

    def update_progress(self, progress: CompilationProgress) -> None:
        """Update compilation progress."""
        ...

    def update_workspace(
        self, operation: WorkspaceOperation, component: str | None = None, **kwargs: Any
    ) -> None:
        """Update workspace operation progress."""
        ...

    def get_context(self) -> ProgressContext:
        """Get the current progress context."""
        ...

    def handle_phase_change(self, old_phase: str, new_phase: str) -> None:
        """Handle phase transitions."""
        ...
