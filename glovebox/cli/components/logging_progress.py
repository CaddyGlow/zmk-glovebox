"""Enhanced progress display with integrated queue-based logging for TUI applications."""

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Generic, TypeVar

from glovebox.cli.components.progress_display import ProgressDisplayManager
from glovebox.config.models.logging import create_tui_logging_config
from glovebox.core.logging import (
    QueueLoggerManager,
    get_logger,
    setup_queue_logging_from_config,
    start_queue_logging,
    stop_queue_logging,
)


# Type variable for progress data
T = TypeVar("T")


class LogCapturingHandler(logging.Handler):
    """Handler that captures logs for progress display with thread safety.
    
    This handler implements the LogProviderProtocol expected by ProgressDisplayManager.
    """

    def __init__(self) -> None:
        super().__init__()
        self._logs: list[tuple[str, str]] = []
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record by capturing it for progress display."""
        try:
            msg = self.format(record)
            level = record.levelname.lower()
            with self._lock:
                self._logs.append((level, msg))
                # Keep only the most recent 200 logs to prevent memory growth
                if len(self._logs) > 200:
                    self._logs = self._logs[-200:]
        except Exception:
            self.handleError(record)

    @property
    def captured_logs(self) -> list[tuple[str, str]]:
        """Thread-safe access to captured logs (LogProviderProtocol compatibility)."""
        with self._lock:
            return self._logs.copy()

    @captured_logs.setter
    def captured_logs(self, value: list[tuple[str, str]]) -> None:
        """Set captured logs (LogProviderProtocol compatibility)."""
        with self._lock:
            self._logs = value.copy()


class LoggingProgressManager(Generic[T]):
    """Combines queue-based logging with progress display for TUI applications.

    This manager provides a unified interface for operations that need both
    progress visualization and logging output in TUI environments. It uses
    queue-based logging to ensure non-blocking operation and captures logs
    for display alongside the progress bars.

    Features:
    - Non-blocking queue-based logging
    - Real-time log capture and display
    - File and console logging
    - Thread-safe log handling
    - Clean lifecycle management
    """

    def __init__(self, debug_file: Path | None = None, show_logs: bool = True) -> None:
        """Initialize the logging progress manager.

        Args:
            debug_file: Optional path for debug log file
            show_logs: Whether to show logs in progress display
        """
        self.debug_file = debug_file
        self.show_logs = show_logs
        self.log_capture_handler = LogCapturingHandler()
        self.progress_manager: ProgressDisplayManager[T] | None = None
        self.queue_managers: list[QueueLoggerManager] = []
        self.logger: logging.Logger | None = None

    def start(self) -> Callable[[T], None]:
        """Start combined logging and progress display.

        Returns:
            Progress callback function for sending progress updates
        """
        # Setup TUI logging configuration with queue-based handlers
        config = create_tui_logging_config(self.debug_file)
        self.logger, self.queue_managers = setup_queue_logging_from_config(config)

        # Add our log capture handler for progress display integration
        # Set it to capture all levels since we want to show logs in progress display
        self.log_capture_handler.setLevel(logging.DEBUG)
        self.log_capture_handler.setFormatter(
            logging.Formatter('%(message)s')  # Simple format for progress display
        )

        # Add the handler to the glovebox root logger so it captures all glovebox logs
        glovebox_root = logging.getLogger("glovebox")
        glovebox_root.addHandler(self.log_capture_handler)

        # Start queue logging for non-blocking operation
        start_queue_logging(self.queue_managers)

        # Setup progress display
        self.progress_manager = ProgressDisplayManager[T](
            show_logs=self.show_logs,
            refresh_rate=10,  # Higher refresh rate for better responsiveness
            max_log_lines=100,
        )
        self.progress_manager.set_log_provider(self.log_capture_handler)

        return self.progress_manager.start()

    def stop(self) -> None:
        """Stop logging and progress display with proper cleanup."""
        if self.progress_manager:
            self.progress_manager.stop()

        if self.queue_managers:
            stop_queue_logging(self.queue_managers)

        # Remove our custom handler from the glovebox root logger to prevent memory leaks
        glovebox_root = logging.getLogger("glovebox")
        if self.log_capture_handler in glovebox_root.handlers:
            glovebox_root.removeHandler(self.log_capture_handler)

    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger for the application.

        Args:
            name: Logger name, typically __name__

        Returns:
            Logger instance that will feed into the progress display
        """
        return get_logger(name)


class WorkspaceLoggingProgressManager(LoggingProgressManager[object]):
    """Specialized logging progress manager for workspace operations."""

    def start(self) -> Callable[..., None]:
        """Start progress display optimized for workspace operations."""
        # Use WorkspaceProgressDisplayManager for better workspace progress handling
        from glovebox.cli.components.progress_display import (
            WorkspaceProgressDisplayManager,
        )

        # Setup logging first
        config = create_tui_logging_config(self.debug_file)
        self.logger, self.queue_managers = setup_queue_logging_from_config(config)

        # Add log capture handler to glovebox root logger
        self.log_capture_handler.setLevel(logging.DEBUG)
        self.log_capture_handler.setFormatter(logging.Formatter('%(message)s'))
        glovebox_root = logging.getLogger("glovebox")
        glovebox_root.addHandler(self.log_capture_handler)

        # Start queue logging
        start_queue_logging(self.queue_managers)

        # Setup workspace-specific progress display
        self.progress_manager = WorkspaceProgressDisplayManager(
            show_logs=self.show_logs,
            refresh_rate=10,
            max_log_lines=100,
        )
        self.progress_manager.set_log_provider(self.log_capture_handler)

        return self.progress_manager.start()


class CompilationLoggingProgressManager(LoggingProgressManager[object]):
    """Specialized logging progress manager for compilation operations."""

    def start(self) -> Callable[..., None]:
        """Start progress display optimized for compilation operations."""
        # Use CompilationProgressDisplayManager for better compilation progress handling
        from glovebox.cli.components.progress_display import (
            CompilationProgressDisplayManager,
        )

        # Setup logging first
        config = create_tui_logging_config(self.debug_file)
        self.logger, self.queue_managers = setup_queue_logging_from_config(config)

        # Add log capture handler to glovebox root logger
        self.log_capture_handler.setLevel(logging.DEBUG)
        self.log_capture_handler.setFormatter(logging.Formatter('%(message)s'))
        glovebox_root = logging.getLogger("glovebox")
        glovebox_root.addHandler(self.log_capture_handler)

        # Start queue logging
        start_queue_logging(self.queue_managers)

        # Setup compilation-specific progress display
        self.progress_manager = CompilationProgressDisplayManager(
            show_logs=self.show_logs,
            refresh_rate=10,
            max_log_lines=100,
        )
        self.progress_manager.set_log_provider(self.log_capture_handler)

        return self.progress_manager.start()


# Factory functions for convenience
def create_logging_progress_manager(
    debug_file: Path | None = None,
    show_logs: bool = True
) -> LoggingProgressManager[object]:
    """Create a general-purpose logging progress manager.

    Args:
        debug_file: Optional path for debug log file
        show_logs: Whether to show logs in progress display

    Returns:
        Configured LoggingProgressManager instance
    """
    return LoggingProgressManager[object](debug_file=debug_file, show_logs=show_logs)


def create_workspace_logging_progress_manager(
    debug_file: Path | None = None,
    show_logs: bool = True
) -> WorkspaceLoggingProgressManager:
    """Create a workspace-optimized logging progress manager.

    Args:
        debug_file: Optional path for debug log file
        show_logs: Whether to show logs in progress display

    Returns:
        Configured WorkspaceLoggingProgressManager instance
    """
    return WorkspaceLoggingProgressManager(debug_file=debug_file, show_logs=show_logs)


def create_compilation_logging_progress_manager(
    debug_file: Path | None = None,
    show_logs: bool = True
) -> CompilationLoggingProgressManager:
    """Create a compilation-optimized logging progress manager.

    Args:
        debug_file: Optional path for debug log file
        show_logs: Whether to show logs in progress display

    Returns:
        Configured CompilationLoggingProgressManager instance
    """
    return CompilationLoggingProgressManager(debug_file=debug_file, show_logs=show_logs)
