"""Custom log handler for progress display integration."""

from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Any


class LogPanelHandler(logging.Handler):
    """Custom log handler that feeds logs to the display panel."""

    def __init__(
        self,
        log_buffer: deque[str],
        lock: threading.Lock,
        max_line_length: int = 120,
    ) -> None:
        """Initialize log panel handler.

        Args:
            log_buffer: Deque to store log messages
            lock: Thread lock for safe buffer access
            max_line_length: Maximum length of log lines before truncation
        """
        super().__init__()
        self.log_buffer = log_buffer
        self.lock = lock
        self.max_line_length = max_line_length

        # Setup formatter for clean log display
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"
        )
        self.setFormatter(formatter)

    def emit(self, record: logging.LogRecord) -> None:
        """Add log record to buffer for display."""
        try:
            msg = self.format(record)

            # Truncate long lines to prevent display issues
            if len(msg) > self.max_line_length:
                msg = msg[: self.max_line_length - 3] + "..."

            # Add to buffer with thread safety
            assert self.lock is not None
            with self.lock:
                self.log_buffer.append(msg)

        except Exception:
            # Don't let logging errors break the display
            self.handleError(record)

    def get_log_style(self, log_line: str) -> str:
        """Get Rich style for log line based on level."""
        if "[ERROR]" in log_line:
            return "red"
        elif "[WARNING]" in log_line:
            return "yellow"
        elif "[INFO]" in log_line:
            return "white"
        elif "[DEBUG]" in log_line:
            return "dim cyan"
        else:
            return "white"


class LogBuffer:
    """Thread-safe log buffer for display components."""

    def __init__(self, max_lines: int = 100) -> None:
        """Initialize log buffer.

        Args:
            max_lines: Maximum number of log lines to retain
        """
        self.buffer: deque[str] = deque(maxlen=max_lines)
        self.lock: threading.Lock = threading.Lock()
        self.handler: LogPanelHandler | None = None

    def setup_handler(self, logger_name: str = "") -> LogPanelHandler:
        """Setup and attach log handler to capture logs.

        Args:
            logger_name: Name of logger to attach to (empty for root logger)

        Returns:
            The created log handler
        """
        if self.handler:
            return self.handler

        self.handler = LogPanelHandler(self.buffer, self.lock)

        # Attach to specified logger
        logger = logging.getLogger(logger_name)
        logger.addHandler(self.handler)

        # Set level to capture all logs that might be interesting
        if not logger_name:  # Root logger
            self.handler.setLevel(logging.INFO)
        else:
            self.handler.setLevel(logging.DEBUG)

        return self.handler

    def get_recent_logs(self, count: int = 20) -> list[str]:
        """Get recent log lines for display.

        Args:
            count: Number of recent lines to return

        Returns:
            List of recent log lines
        """
        with self.lock:
            lines = list(self.buffer)
            return lines[-count:] if len(lines) > count else lines

    def get_log_style(self, log_line: str) -> str:
        """Get Rich style for log line based on level."""
        if self.handler:
            return self.handler.get_log_style(log_line)
        return "white"

    def clear(self) -> None:
        """Clear the log buffer."""
        with self.lock:
            self.buffer.clear()

    def cleanup(self) -> None:
        """Remove log handler when done."""
        if self.handler:
            # Remove from all loggers that might have it
            for logger_name in ["", "glovebox"]:
                logger = logging.getLogger(logger_name)
                if self.handler in logger.handlers:
                    logger.removeHandler(self.handler)
            self.handler = None
