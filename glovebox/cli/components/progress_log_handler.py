"""Custom logging handler for staged progress display."""

import logging
from typing import Any


class ProgressLogHandler(logging.Handler):
    """Custom logging handler that forwards log messages to progress display."""

    def __init__(self, progress_callback: Any, level: int = logging.INFO) -> None:
        """Initialize the progress log handler.

        Args:
            progress_callback: The progress callback with add_log_line method
            level: Minimum logging level to handle
        """
        super().__init__(level)
        self.progress_callback = progress_callback

        # Set a formatter for clean log output
        formatter = logging.Formatter("%(name)s: %(message)s")
        self.setFormatter(formatter)

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to the progress display."""
        try:
            if hasattr(self.progress_callback, "add_log_line"):
                # Format the log message
                msg = self.format(record)

                # Filter out some noisy loggers
                if self._should_display_record(record):
                    self.progress_callback.add_log_line(msg)
        except Exception:
            # Don't let logging errors break the compilation
            self.handleError(record)

    def _should_display_record(self, record: logging.LogRecord) -> bool:
        """Check if a log record should be displayed."""
        # Filter out some noisy loggers
        noisy_loggers = [
            "urllib3",
            "requests",
            "docker",
            "paramiko",
            "asyncio",
        ]

        # Only show compilation-related logs
        if any(noisy in record.name for noisy in noisy_loggers):
            return False

        # Show warnings and errors from any logger
        if record.levelno >= logging.WARNING:
            return True

        # Show info and debug from glovebox loggers
        return record.name.startswith("glovebox")


def create_progress_log_handler(
    progress_callback: Any, level: int = logging.INFO
) -> ProgressLogHandler:
    """Factory function to create a progress log handler.

    Args:
        progress_callback: The progress callback with add_log_line method
        level: Minimum logging level to handle

    Returns:
        Configured ProgressLogHandler instance
    """
    return ProgressLogHandler(progress_callback, level)
