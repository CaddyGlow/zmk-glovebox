"""Configuration models for progress display components."""

from typing import Any

from pydantic import Field

from glovebox.cli.helpers.theme import IconMode
from glovebox.models.base import GloveboxBaseModel


class ProgressConfig(GloveboxBaseModel):
    """Configuration for progress display following CLAUDE.md guidelines.

    This model configures all aspects of the progress display including
    visual appearance, logging capture, and operational parameters.
    """

    operation_name: str = "Operation"
    """Name of the operation being tracked"""

    checkpoints: list[str] = Field(default_factory=list)
    """List of checkpoint names in order of execution"""

    icon_mode: IconMode = IconMode.TEXT
    """Icon mode for visual indicators (default: ASCII per CLAUDE.md)"""


    show_overall_progress: bool = True
    """Whether to show overall progress bar at bottom"""

    show_status_line: bool = True
    """Whether to show status line with file/speed information"""

    refresh_rate: int = 10
    """Display refresh rate per second"""

    panel_title_prefix: str = ""
    """Optional prefix for panel title"""

    panel_title_suffix: str = ""
    """Optional suffix for panel title"""

    @property
    def full_operation_name(self) -> str:
        """Get full operation name with prefix/suffix."""
        parts = [self.panel_title_prefix, self.operation_name, self.panel_title_suffix]
        return " ".join(part for part in parts if part.strip())


class CheckpointState(GloveboxBaseModel):
    """State information for a progress checkpoint."""

    name: str
    """Name of the checkpoint"""

    status: str = "pending"
    """Current status: pending, active, completed, failed"""

    start_time: float | None = None
    """Timestamp when checkpoint was started"""

    end_time: float | None = None
    """Timestamp when checkpoint completed/failed"""

    error_message: str | None = None
    """Error message if checkpoint failed"""

    @property
    def duration(self) -> float | None:
        """Get duration in seconds if both start and end times are set."""
        if self.start_time is not None and self.end_time is not None:
            return self.end_time - self.start_time
        return None


class ProgressState(GloveboxBaseModel):
    """Current state of progress tracking."""

    checkpoints: dict[str, CheckpointState] = Field(default_factory=dict)
    """Dictionary of checkpoint states by name"""

    current_checkpoint: str | None = None
    """Name of currently active checkpoint"""

    current_progress: int = 0
    """Current progress value within checkpoint"""

    total_progress: int = 100
    """Total progress value for current checkpoint"""

    status_message: str = ""
    """Current status message"""

    status_info: dict[str, Any] = Field(default_factory=dict)
    """Additional status information for display"""

    log_entries: list[dict[str, Any]] = Field(default_factory=list)
    """List of captured log entries"""

    start_time: float | None = None
    """Overall operation start time"""

    is_complete: bool = False
    """Whether the operation is complete"""

    is_failed: bool = False
    """Whether the operation has failed"""

    @property
    def completed_checkpoints(self) -> int:
        """Get number of completed checkpoints."""
        return sum(
            1
            for checkpoint in self.checkpoints.values()
            if checkpoint.status == "completed"
        )

    @property
    def total_checkpoints(self) -> int:
        """Get total number of checkpoints."""
        return len(self.checkpoints)

    @property
    def overall_progress_percentage(self) -> float:
        """Get overall progress as percentage."""
        if self.total_checkpoints == 0:
            return 0.0
        return (self.completed_checkpoints / self.total_checkpoints) * 100
