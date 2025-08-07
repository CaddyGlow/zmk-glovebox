"""Logging configuration and setup for Glovebox."""

import logging
import queue
import shutil
import sys
import threading
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, TextIO

import structlog
from rich.console import Console
from rich.traceback import Traceback
from structlog.stdlib import BoundLogger
from structlog.typing import ExcInfo, Processor

from glovebox.config.models.logging import LoggingConfig


def setup_logging_from_config(config: "LoggingConfig") -> BoundLogger:
    return setup_logging()  # json_logs=False, log_level_name="DEBUG", log_file=None)


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


suppress_debug = [
    "ccproxy.scheduler",
    "ccproxy.observability.context",
    "ccproxy.utils.simple_request_logger",
]


def configure_structlog(log_level: int = logging.INFO) -> None:
    """Configure structlog with shared processors following canonical pattern."""
    # Shared processors for all structlog loggers
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,  # For request context in web apps
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
    ]

    # Add debug-specific processors
    if log_level < logging.INFO:
        # Dev mode (DEBUG): add callsite information
        processors.append(
            structlog.processors.CallsiteParameterAdder(
                parameters=[
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ]
            )
        )

    # Common processors for all log levels
    # First add timestamp with microseconds
    processors.append(
        structlog.processors.TimeStamper(
            fmt="%H:%M:%S.%f" if log_level < logging.INFO else "%Y-%m-%d %H:%M:%S.%f",
            key="timestamp_raw",
        )
    )

    # Then add processor to convert microseconds to milliseconds
    def format_timestamp_ms(
        logger: Any, log_method: str, event_dict: MutableMapping[str, Any]
    ) -> MutableMapping[str, Any]:
        """Format timestamp with milliseconds instead of microseconds."""
        if "timestamp_raw" in event_dict:
            # Truncate microseconds to milliseconds (6 digits to 3)
            timestamp_raw = event_dict.pop("timestamp_raw")
            event_dict["timestamp"] = timestamp_raw[:-3]
        return event_dict

    processors.extend(
        [
            format_timestamp_ms,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,  # Handle exceptions properly
            # This MUST be the last processor - allows different renderers per handler
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ]
    )

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def rich_traceback(sio: TextIO, exc_info: ExcInfo) -> None:
    """Pretty-print *exc_info* to *sio* using the *Rich* package.

    Based on:
    https://github.com/hynek/structlog/blob/74cdff93af217519d4ebea05184f5e0db2972556/src/structlog/dev.py#L179-L192

    """
    term_width, _height = shutil.get_terminal_size((80, 123))
    sio.write("\n")
    # Rich docs: https://rich.readthedocs.io/en/stable/reference/traceback.html
    Console(file=sio, color_system="truecolor").print(
        Traceback.from_exception(
            *exc_info,
            # show_locals=True,  # Takes up too much vertical space
            extra_lines=1,  # Reduce amount of source code displayed
            width=term_width,  # Maximize width
            max_frames=5,  # Default is 10
            suppress=[
                "click",
                "typer",
                "uvicorn",
                "fastapi",
                "starlette",
            ],  # Suppress noise from these libraries
        ),
    )


def setup_logging(
    json_logs: bool = False,
    log_level_name: str = "DEBUG",
    log_file: str | None = None,
) -> BoundLogger:
    """
    Setup logging for the entire application using canonical structlog pattern.
    Returns a structlog logger instance.
    """
    log_level = getattr(logging, log_level_name.upper(), logging.INFO)

    # Install rich traceback handler globally with frame limit
    # install_rich_traceback(
    #     show_locals=log_level <= logging.DEBUG,  # Only show locals in debug mode
    #     max_frames=max_traceback_frames,
    #     width=120,
    #     word_wrap=True,
    #     suppress=[
    #         "click",
    #         "typer",
    #         "uvicorn",
    #         "fastapi",
    #         "starlette",
    #     ],  # Suppress noise from these libraries
    # )

    # Get root logger and set level BEFORE configuring structlog
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 1. Configure structlog with shared processors
    configure_structlog(log_level=log_level)

    # 2. Setup root logger handlers
    root_logger.handlers = []  # Clear any existing handlers

    # 3. Create shared processors for foreign (stdlib) logs
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.dev.set_exc_info,
    ]

    # Add debug processors if needed
    if log_level < logging.INFO:
        shared_processors.append(
            structlog.processors.CallsiteParameterAdder(  # type: ignore[arg-type]
                parameters=[
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ]
            )
        )

    # Add appropriate timestamper for console vs file
    # Using custom lambda to truncate microseconds to milliseconds
    console_timestamper = (
        structlog.processors.TimeStamper(fmt="%H:%M:%S.%f", key="timestamp_raw")
        if log_level < logging.INFO
        else structlog.processors.TimeStamper(
            fmt="%Y-%m-%d %H:%M:%S.%f", key="timestamp_raw"
        )
    )

    # Processor to convert microseconds to milliseconds
    def format_timestamp_ms(
        logger: Any, log_method: str, event_dict: MutableMapping[str, Any]
    ) -> MutableMapping[str, Any]:
        """Format timestamp with milliseconds instead of microseconds."""
        if "timestamp_raw" in event_dict:
            # Truncate microseconds to milliseconds (6 digits to 3)
            timestamp_raw = event_dict.pop("timestamp_raw")
            event_dict["timestamp"] = timestamp_raw[:-3]
        return event_dict

    file_timestamper = structlog.processors.TimeStamper(fmt="iso")

    # 4. Setup console handler with ConsoleRenderer
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_renderer = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(
            exception_formatter=rich_traceback  # structlog.dev.rich_traceback,  # Use rich for better formatting
        )
    )

    # Console gets human-readable timestamps for both structlog and stdlib logs
    console_processors = shared_processors + [console_timestamper, format_timestamp_ms]
    console_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=console_processors,  # type: ignore[arg-type]
            processor=console_renderer,
        )
    )
    root_logger.addHandler(console_handler)

    # 5. Setup file handler with JSONRenderer (if log_file provided)
    if log_file:
        # Ensure parent directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8", delay=True)
        file_handler.setLevel(log_level)

        # File gets ISO timestamps for both structlog and stdlib logs
        file_processors = shared_processors + [file_timestamper]
        file_handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                foreign_pre_chain=file_processors,
                processor=structlog.processors.JSONRenderer(),
            )
        )
        root_logger.addHandler(file_handler)

    # 6. Configure stdlib loggers to propagate to our handlers
    for logger_name in [
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "ccproxy",
    ]:
        logger = logging.getLogger(logger_name)
        logger.handlers = []  # Remove default handlers
        logger.propagate = True  # Use root logger's handlers

        # In DEBUG mode, let all logs through at DEBUG level
        # Otherwise, reduce uvicorn noise by setting to WARNING
        if log_level == logging.DEBUG:
            logger.setLevel(logging.DEBUG)
        elif logger_name.startswith("uvicorn"):
            logger.setLevel(logging.WARNING)
        else:
            logger.setLevel(log_level)

    # Configure httpx logger separately - INFO when app is DEBUG, WARNING otherwise
    httpx_logger = logging.getLogger("httpx")
    httpx_logger.handlers = []
    httpx_logger.propagate = True
    httpx_logger.setLevel(logging.INFO if log_level < logging.INFO else logging.WARNING)

    # Set noisy HTTP-related loggers to WARNING
    noisy_log_level = logging.WARNING if log_level <= logging.WARNING else log_level
    for noisy_logger_name in [
        "urllib3",
        "urllib3.connectionpool",
        "requests",
        "aiohttp",
        "httpcore",
        "httpcore.http11",
        "fastapi_mcp",
        "sse_starlette",
        "mcp",
    ]:
        noisy_logger = logging.getLogger(noisy_logger_name)
        noisy_logger.handlers = []
        noisy_logger.propagate = True
        noisy_logger.setLevel(noisy_log_level)

    [
        logging.getLogger(logger_name).setLevel(
            logging.INFO if log_level <= logging.DEBUG else log_level
        )  # type: ignore[func-returns-value]
        for logger_name in suppress_debug
    ]

    return structlog.get_logger()  # type: ignore[no-any-return]


# Create a convenience function for getting loggers
def get_logger(name: str | None = None) -> BoundLogger:
    """Get a structlog logger instance."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]
