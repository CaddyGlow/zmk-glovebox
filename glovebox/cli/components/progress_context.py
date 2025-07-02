"""Progress context implementation that updates the display."""

import time
from typing import Any

from glovebox.cli.components.progress_display import ProgressDisplay
from glovebox.protocols.progress_context_protocol import ProgressContextProtocol


class ProgressContext:
    """Progress context that updates a ProgressDisplay.

    This implementation connects the ProgressContextProtocol interface
    to the actual ProgressDisplay component, translating method calls
    into display updates.
    """

    def __init__(self, display: ProgressDisplay):
        """Initialize progress context with a display.

        Args:
            display: The ProgressDisplay to update
        """
        self.display = display

    def set_total_checkpoints(self, checkpoints: list[str]) -> None:
        """Set the list of checkpoints for this operation.

        Args:
            checkpoints: List of checkpoint names in order
        """
        # This is typically already set via config, but allow dynamic updates
        self.display.config.checkpoints = checkpoints

        # Add any new checkpoints to state
        for checkpoint_name in checkpoints:
            if checkpoint_name not in self.display.state.checkpoints:
                from glovebox.cli.components.progress_config import CheckpointState

                self.display.state.checkpoints[checkpoint_name] = CheckpointState(
                    name=checkpoint_name
                )

        self.display._update_display()

    def start_checkpoint(self, name: str) -> None:
        """Mark a checkpoint as started.

        Args:
            name: Name of the checkpoint to start
        """
        if name in self.display.state.checkpoints:
            checkpoint = self.display.state.checkpoints[name]
            checkpoint.status = "active"
            checkpoint.start_time = time.time()

            # Mark previous active checkpoint as completed if any
            if (
                self.display.state.current_checkpoint
                and self.display.state.current_checkpoint != name
            ):
                prev_checkpoint = self.display.state.checkpoints.get(
                    self.display.state.current_checkpoint
                )
                if prev_checkpoint and prev_checkpoint.status == "active":
                    prev_checkpoint.status = "completed"
                    prev_checkpoint.end_time = time.time()

            self.display.state.current_checkpoint = name
            self.display.state.current_progress = 0
            self.display.state.total_progress = 100
            self.display.state.status_message = f"Starting {name}"

            # Progress tracking is now handled by the panel display

            self.display._update_display()

    def complete_checkpoint(self, name: str) -> None:
        """Mark a checkpoint as completed.

        Args:
            name: Name of the checkpoint to complete
        """
        if name in self.display.state.checkpoints:
            checkpoint = self.display.state.checkpoints[name]
            checkpoint.status = "completed"
            checkpoint.end_time = time.time()

            # Clear current checkpoint if it matches
            if self.display.state.current_checkpoint == name:
                self.display.state.current_checkpoint = None
                self.display.state.status_message = f"Completed {name}"
                
                # Progress tracking is now handled by the panel display

            # Check if all checkpoints are complete
            all_complete = all(
                cp.status == "completed"
                for cp in self.display.state.checkpoints.values()
            )
            if all_complete:
                self.display.state.is_complete = True

            self.display._update_display()

    def fail_checkpoint(self, name: str) -> None:
        """Mark a checkpoint as failed.

        Args:
            name: Name of the checkpoint that failed
        """
        if name in self.display.state.checkpoints:
            checkpoint = self.display.state.checkpoints[name]
            checkpoint.status = "failed"
            checkpoint.end_time = time.time()

            # Clear current checkpoint if it matches
            if self.display.state.current_checkpoint == name:
                self.display.state.current_checkpoint = None
                self.display.state.status_message = f"Failed {name}"

            # Mark overall operation as failed
            self.display.state.is_failed = True

            self.display._update_display()

    def update_progress(self, current: int, total: int, status: str = "") -> None:
        """Update current progress within a checkpoint.

        Args:
            current: Current progress value
            total: Total progress value
            status: Optional status message
        """
        self.display.state.current_progress = current
        self.display.state.total_progress = total

        if status:
            self.display.state.status_message = status

        # Progress tracking is now handled by the panel display

        self.display._update_display()

    def log(self, message: str, level: str = "info") -> None:
        """Log a message to the progress display.

        Args:
            message: Log message
            level: Log level (info, warning, error, debug)
        """
        # Print directly to the display console
        self.display.console.print(message)

    def set_status_info(self, info: dict[str, Any]) -> None:
        """Set status information for display.

        Args:
            info: Dictionary containing status information
        """
        self.display.state.status_info = info
        self.display._update_display()
