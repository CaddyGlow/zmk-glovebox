import logging
import sys
from typing import Optional, Union


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    Args:
        name: The logger name, usually __name__

    Returns:
        A logger instance
    """
    return logging.getLogger(name)


def setup_logging(
    level: int | str = logging.INFO,
    log_file: str | None = None,
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
) -> logging.Logger:
    """Set up logging configuration for Glovebox.

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
                f"Failed to create log file handler for {log_file}: {e}"
            )

    # Prevent propagation to the absolute root logger
    root_logger.propagate = False

    return root_logger
