"""Logging configuration and setup for Glovebox."""

import json
import logging
import logging.handlers
import queue
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.config.models.logging import LoggingConfig, LogHandlerConfig

try:
    import colorlog
    HAS_COLORLOG = True
except ImportError:
    HAS_COLORLOG = False


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
        color_format = format_string.replace("%(levelname)s", "%(log_color)s%(levelname)s%(reset)s")
        return colorlog.ColoredFormatter(
            color_format,
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
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

        if handler:
            # Set level
            handler.setLevel(handler_config.get_log_level_int())

            # Create and set formatter
            # Don't use colored output for file handlers
            use_colors = (handler_config.colored and
                         handler_config.type != LogHandlerType.FILE)
            # Handle both enum and string format values
            format_value = handler_config.format.value if hasattr(handler_config.format, 'value') else handler_config.format
            formatter = _create_formatter(format_value, use_colors)
            handler.setFormatter(formatter)

        return handler

    except Exception as e:
        logger = logging.getLogger("glovebox.core.logging")
        # Handle both enum and string type values
        type_value = handler_config.type.value if hasattr(handler_config.type, 'value') else handler_config.type
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

    return root_logger


# Global queue listener for non-blocking logging
_queue_listener: logging.handlers.QueueListener | None = None
_queue_listener_lock = threading.Lock()


class QueueLoggerManager:
    """Manages queue-based logging for non-blocking operation in TUI applications."""

    def __init__(self) -> None:
        self.log_queue: queue.Queue[logging.LogRecord] = queue.Queue()
        self.queue_listener: logging.handlers.QueueListener | None = None
        self.target_handlers: list[logging.Handler] = []
        self._lock = threading.Lock()

    def add_handler(self, handler: logging.Handler) -> None:
        """Add a target handler for the queue listener."""
        with self._lock:
            self.target_handlers.append(handler)

    def start_listener(self) -> None:
        """Start the queue listener in a background thread."""
        with self._lock:
            if self.queue_listener is None and self.target_handlers:
                self.queue_listener = logging.handlers.QueueListener(
                    self.log_queue,
                    *self.target_handlers,
                    respect_handler_level=True
                )
                self.queue_listener.start()

    def stop_listener(self) -> None:
        """Stop the queue listener."""
        with self._lock:
            if self.queue_listener:
                self.queue_listener.stop()
                self.queue_listener = None

    def get_queue_handler(self) -> logging.handlers.QueueHandler:
        """Get a QueueHandler for this manager."""
        return logging.handlers.QueueHandler(self.log_queue)


def create_queue_handler(handler_config: "LogHandlerConfig") -> tuple[logging.Handler, QueueLoggerManager]:
    """Create a queue-based handler setup for non-blocking logging.

    Args:
        handler_config: Handler configuration

    Returns:
        Tuple of (QueueHandler, QueueLoggerManager)
    """
    # Create the actual target handler
    target_handler = _create_handler_direct(handler_config)
    if not target_handler:
        raise ValueError("Failed to create target handler for queue setup")

    # Create queue manager and add target handler
    queue_manager = QueueLoggerManager()
    queue_manager.add_handler(target_handler)

    # Create queue handler
    queue_handler = queue_manager.get_queue_handler()
    queue_handler.setLevel(handler_config.get_log_level_int())

    return queue_handler, queue_manager


def _create_handler_direct(handler_config: "LogHandlerConfig") -> logging.Handler | None:
    """Create a handler directly without queue wrapper (internal use)."""
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

        if handler:
            # Set level
            handler.setLevel(handler_config.get_log_level_int())

            # Create and set formatter
            # Don't use colored output for file handlers
            use_colors = (handler_config.colored and
                         handler_config.type != LogHandlerType.FILE)
            # Handle both enum and string format values
            format_value = handler_config.format.value if hasattr(handler_config.format, 'value') else handler_config.format
            formatter = _create_formatter(format_value, use_colors)
            handler.setFormatter(formatter)

        return handler

    except Exception as e:
        logger = logging.getLogger("glovebox.core.logging")
        # Handle both enum and string type values
        type_value = handler_config.type.value if hasattr(handler_config.type, 'value') else handler_config.type
        logger.error("Failed to create %s handler: %s", type_value, e)
        return None


def setup_queue_logging_from_config(config: "LoggingConfig") -> tuple[logging.Logger, list[QueueLoggerManager]]:
    """Set up queue-based logging from LoggingConfig object.

    Args:
        config: Logging configuration

    Returns:
        Tuple of (configured logger, list of queue managers to start/stop)
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

    # Create handlers and queue managers
    queue_managers = []
    for handler_config in config.handlers:
        if handler_config.queue_enabled:
            # Create queue-based handler
            try:
                queue_handler, queue_manager = create_queue_handler(handler_config)
                root_logger.addHandler(queue_handler)
                queue_managers.append(queue_manager)
            except Exception as e:
                logger = logging.getLogger("glovebox.core.logging")
                logger.error("Failed to create queue handler: %s", e)
        else:
            # Create regular handler
            handler = _create_handler(handler_config)
            if handler:
                root_logger.addHandler(handler)

    # Prevent propagation to the absolute root logger
    root_logger.propagate = False

    return root_logger, queue_managers


def start_queue_logging(queue_managers: list[QueueLoggerManager]) -> None:
    """Start all queue listeners for non-blocking logging."""
    for manager in queue_managers:
        manager.start_listener()


def stop_queue_logging(queue_managers: list[QueueLoggerManager]) -> None:
    """Stop all queue listeners."""
    for manager in queue_managers:
        manager.stop_listener()

