"""Compilation progress models for tracking build status."""

from __future__ import annotations

from enum import Enum

from glovebox.models.base import GloveboxBaseModel


class CompilationState(str, Enum):
    """States of compilation process."""

    IDLE = "idle"
    INITIALIZING = "initializing"
    CACHE_SETUP = "cache_setup"
    WORKSPACE_SETUP = "workspace_setup"
    DEPENDENCY_FETCH = "dependency_fetch"
    BUILDING = "building"
    POST_PROCESSING = "post_processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CompilationProgress(GloveboxBaseModel):
    """Progress tracking for compilation operations."""

    state: CompilationState = CompilationState.IDLE
    description: str | None = None
    current_stage: int = 0
    total_stages: int = 0
    percentage: float = 0.0
    start_time: float | None = None
    end_time: float | None = None
    error_message: str | None = None

    def get_percentage(self) -> float:
        """Calculate percentage based on stages if not explicitly set."""
        if self.percentage > 0:
            return self.percentage

        if self.total_stages > 0:
            return min((self.current_stage / self.total_stages) * 100, 100.0)

        return 0.0

    def is_complete(self) -> bool:
        """Check if compilation is complete."""
        return self.state in (CompilationState.COMPLETED, CompilationState.FAILED)

    def is_active(self) -> bool:
        """Check if compilation is actively running."""
        return self.state not in (
            CompilationState.IDLE,
            CompilationState.COMPLETED,
            CompilationState.FAILED,
        )
