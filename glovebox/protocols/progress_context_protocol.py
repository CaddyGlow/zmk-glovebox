"""Protocol for progress context information."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ProgressContextProtocol(Protocol):
    """Protocol for progress context information.

    This protocol defines the interface for progress tracking components,
    allowing services to report progress without depending on specific
    implementation details.
    """

    def set_total_checkpoints(self, checkpoints: list[str]) -> None:
        """Set the list of checkpoints for this operation.

        Args:
            checkpoints: List of checkpoint names in order
        """
        ...

    def start_checkpoint(self, name: str) -> None:
        """Mark a checkpoint as started.

        Args:
            name: Name of the checkpoint to start
        """
        ...

    def complete_checkpoint(self, name: str) -> None:
        """Mark a checkpoint as completed.

        Args:
            name: Name of the checkpoint to complete
        """
        ...

    def fail_checkpoint(self, name: str) -> None:
        """Mark a checkpoint as failed.

        Args:
            name: Name of the checkpoint that failed
        """
        ...

    def update_progress(self, current: int, total: int, status: str = "") -> None:
        """Update current progress within a checkpoint.

        Args:
            current: Current progress value
            total: Total progress value
            status: Optional status message
        """
        ...

    def log(self, message: str, level: str = "info") -> None:
        """Log a message to the progress display.

        Args:
            message: Log message
            level: Log level (info, warning, error, debug)
        """
        ...

    def set_status_info(self, info: dict[str, Any]) -> None:
        """Set status information for display.

        Args:
            info: Dictionary containing status information like:
                - current_file: Current file being processed
                - file_size: Size of current file
                - transfer_speed: Transfer speed in MB/s
                - eta_seconds: Estimated time to completion
                - files_remaining: Number of files remaining
        """
        ...
