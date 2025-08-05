"""Logging configuration and setup for Glovebox."""

import json
import logging
import logging.handlers
import queue
import sys
import threading
from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from glovebox.config.models.logging import LoggingConfig, LogHandlerConfig

try:
    import colorlog

    HAS_COLORLOG = True
except ImportError:
    HAS_COLORLOG = False

# Import structlog setup functions
try:
    from glovebox.core.structlog_config import (
        setup_structlog_from_config,
        setup_structlog_simple,
    )

    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False


class TUIProgressProtocol(Protocol):
    """Protocol for TUI progress managers (simplified - no log display)."""

    pass


class TUILogHandler(logging.Handler):
    """Simplified TUI log handler that consumes logs without display.

    This handler maintains compatibility with existing TUI logging configuration
    but doesn't forward logs to display since we simplified the TUI to show only
    progress. Logs still go to their other configured handlers (file, console, etc.).
    """

    def __init__(
        self,
        progress_manager: TUIProgressProtocol | None = None,  # Kept for compatibility
        level: int = logging.NOTSET,
    ) -> None:
        """Initialize TUI log handler.

        Args:
            progress_manager: Progress manager (kept for compatibility, not used)
            level: Minimum log level to handle
        """
        super().__init__(level)
        self.log_queue: queue.Queue[tuple[str, str]] = queue.Queue(maxsize=1000)
        self.stop_event = threading.Event()
        self.worker_thread: threading.Thread | None = None
        self._setup_worker()

    def set_progress_manager(self, progress_manager: TUIProgressProtocol) -> None:
        """Set or update the progress manager (kept for compatibility, not used).

        Args:
            progress_manager: Progress manager (ignored in simplified implementation)
        """
        pass  # No-op since we don't use progress manager anymore

    def _setup_worker(self) -> None:
        """Set up the background worker thread for async log processing."""
        if self.worker_thread is not None:
            return

        self.stop_event.clear()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def _worker_loop(self) -> None:
        """Background worker loop that processes queued log messages."""
        while not self.stop_event.is_set():
            try:
                # Get log message with timeout
                level, message = self.log_queue.get(timeout=0.1)

                # Since we simplified the TUI to not show logs, just consume the queue
                # The logs will still go to their other configured handlers (file, console, etc.)
                # No need to forward to progress manager anymore

                # Mark task as done
                self.log_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                # Log worker errors to stderr to avoid infinite loops
                print(f"TUILogHandler worker error: {e}", file=sys.stderr)

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record by queuing it for async processing.

        Args:
            record: Log record to emit
        """
        try:
            # Format the message
            message = self.format(record)
            level = record.levelname.lower()

            # Queue the log message (non-blocking)
            self.log_queue.put((level, message), block=False)

        except queue.Full:
            # Queue is full, drop the message (prevents blocking)
            pass
        except Exception:
            # Handle any other errors silently to prevent logging loops
            pass

    def close(self) -> None:
        """Close the handler and clean up resources."""
        # Signal worker to stop
        self.stop_event.set()

        # Wait for worker to finish
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1.0)

        # Clean up
        self.worker_thread = None
        super().close()


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter using built-in json module."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info and record.exc_info != (None, None, None):
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "extra"):
            log_entry.update(record.extra)

        return json.dumps(log_entry)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    Args:
        name: The logger name, usually __name__

    Returns:
        A logger instance

    Note: For exception logging with debug stack traces, use this pattern:
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Operation failed: %s", e, exc_info=exc_info)
    """
    return logging.getLogger(name)


def _create_formatter(format_type: str, colored: bool = False) -> logging.Formatter:
    """Create a formatter based on format type and color preference.

    Args:
        format_type: Format type (simple, detailed, json)
        colored: Whether to use colored output (ignored for json format)

    Returns:
        Appropriate formatter instance
    """
    # Format templates
    formats = {
        "simple": "%(levelname)s: %(message)s",
        "detailed": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    }

    if format_type == "json":
        return JSONFormatter()

    format_string = formats.get(format_type, formats["simple"])

    # Use colored formatter if requested and available
    if colored and HAS_COLORLOG and format_type != "json":
        # Colorlog format with colors
        color_format = format_string.replace(
            "%(levelname)s", "%(log_color)s%(levelname)s%(reset)s"
        )
        return colorlog.ColoredFormatter(
            color_format,
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
            },
        )

    return logging.Formatter(format_string)


def _create_handler(handler_config: "LogHandlerConfig") -> logging.Handler | None:
    """Create a logging handler from configuration.

    Args:
        handler_config: Handler configuration

    Returns:
        Configured handler or None if creation failed
    """
    from glovebox.config.models.logging import LogHandlerType

    handler: logging.Handler | None = None

    try:
        if handler_config.type == LogHandlerType.CONSOLE:
            handler = logging.StreamHandler(sys.stdout)
        elif handler_config.type == LogHandlerType.STDERR:
            handler = logging.StreamHandler(sys.stderr)
        elif handler_config.type == LogHandlerType.FILE:
            if not handler_config.file_path:
                logging.getLogger("glovebox.core.logging").error(
                    "File path required for file handler"
                )
                return None

            # Ensure parent directory exists
            handler_config.file_path.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(handler_config.file_path)
        elif handler_config.type == LogHandlerType.TUI:
            # Create TUI handler without progress manager (set later)
            handler = TUILogHandler()

        if handler:
            # Set level
            handler.setLevel(handler_config.get_log_level_int())

            # Create and set formatter
            # Don't use colored output for file handlers
            use_colors = (
                handler_config.colored and handler_config.type != LogHandlerType.FILE
            )
            # Handle both enum and string format values
            format_value = (
                handler_config.format.value
                if hasattr(handler_config.format, "value")
                else handler_config.format
            )
            formatter = _create_formatter(format_value, use_colors)
            handler.setFormatter(formatter)

        return handler

    except Exception as e:
        logger = logging.getLogger("glovebox.core.logging")
        # Handle both enum and string type values
        type_value = (
            handler_config.type.value
            if hasattr(handler_config.type, "value")
            else handler_config.type
        )
        logger.error("Failed to create %s handler: %s", type_value, e)
        return None


def setup_logging_from_config(config: "LoggingConfig") -> logging.Logger:
    """Set up logging from LoggingConfig object.

    Args:
        config: Logging configuration

    Returns:
        The configured root logger
    """
    # Get the root logger for the glovebox package
    root_logger = logging.getLogger("glovebox")

    # Clear any existing handlers to avoid duplicate logs
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Find the most restrictive log level across all handlers
    min_level = logging.CRITICAL
    for handler_config in config.handlers:
        handler_level = handler_config.get_log_level_int()
        if handler_level < min_level:
            min_level = handler_level

    root_logger.setLevel(min_level)

    # Create and add handlers
    for handler_config in config.handlers:
        handler = _create_handler(handler_config)
        if handler:
            root_logger.addHandler(handler)

    # Prevent propagation to the absolute root logger
    root_logger.propagate = False

    # Initialize structlog with the same configuration
    if HAS_STRUCTLOG:
        try:
            setup_structlog_from_config(config)
        except Exception as e:
            # Log error but don't fail - structlog is optional
            logger = logging.getLogger("glovebox.core.logging")
            logger.warning("Failed to setup structlog: %s", e)

    return root_logger


def setup_logging(
    level: int | str = logging.INFO,
    log_file: str | None = None,
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
) -> logging.Logger:
    """Set up logging configuration for Glovebox (backward compatibility).

    Args:
        level: Logging level (default: INFO)
        log_file: Optional file to write logs to
        log_format: Format string for log messages

    Returns:
        The configured root logger
    """
    # Get the root logger for the glovebox package
    root_logger = logging.getLogger("glovebox")
    root_logger.setLevel(level)

    # Clear any existing handlers to avoid duplicate logs if called multiple times
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(log_format)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler if requested
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except OSError as e:
            # Log error about file handler creation to console, but don't crash
            console_logger = logging.getLogger("glovebox.core.logging")
            console_logger.error(
                "Failed to create log file handler for %s: %s", log_file, e
            )

    # Prevent propagation to the absolute root logger
    root_logger.propagate = False

    # Initialize structlog with simple configuration
    if HAS_STRUCTLOG:
        try:
            # Determine format based on log_format parameter
            format_type = "console"  # Default
            if "json" in log_format.lower():
                format_type = "json"
            elif "simple" in log_format.lower():
                format_type = "simple"

            setup_structlog_simple(
                level=level,
                log_format=format_type,
                colored=True,  # Default to colored for console output
            )
        except Exception as e:
            # Log error but don't fail - structlog is optional
            console_logger = logging.getLogger("glovebox.core.logging")
            console_logger.warning("Failed to setup structlog: %s", e)

    return root_logger
