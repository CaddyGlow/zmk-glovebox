"""Structlog configuration and setup for Glovebox."""

import logging
import sys
from typing import TYPE_CHECKING, Any

import structlog
from structlog.processors import JSONRenderer


if TYPE_CHECKING:
    from glovebox.config.models.logging import LoggingConfig


try:
    import colorlog

    HAS_COLORLOG = True
except ImportError:
    HAS_COLORLOG = False


class StructlogColorRenderer:
    """Custom colored console renderer for structlog that integrates with colorlog."""

    def __init__(self) -> None:
        """Initialize the colored renderer."""
        if HAS_COLORLOG:
            self.color_map = {
                "debug": "cyan",
                "info": "green",
                "warning": "yellow",
                "error": "red",
                "critical": "red,bg_white",
            }
        else:
            self.color_map = {}

    def __call__(
        self, logger: Any, method_name: str, event_dict: dict[str, Any]
    ) -> str:
        """Render log event with colors."""
        level = event_dict.get("level", "info").lower()
        timestamp = event_dict.get("timestamp", "")
        logger_name = event_dict.get("logger", "")
        event = event_dict.get("event", "")

        # Extract structured fields (everything except standard fields)
        standard_fields = {"level", "timestamp", "logger", "event", "exc_info"}
        extra_fields = {k: v for k, v in event_dict.items() if k not in standard_fields}

        # Build the message
        msg_parts = [f"{timestamp} - {logger_name} - {level.upper()} - {event}"]

        # Add structured fields
        if extra_fields:
            fields_str = " ".join(f"{k}={v}" for k, v in extra_fields.items())
            msg_parts.append(f" [{fields_str}]")

        message = "".join(msg_parts)

        # Add color if available
        if HAS_COLORLOG and level in self.color_map:
            color = self.color_map[level]
            # Simple color application - just color the level
            message = message.replace(
                level.upper(),
                f"\033[{self._get_color_code(color)}m{level.upper()}\033[0m",
            )

        return message

    def _get_color_code(self, color: str) -> str:
        """Get ANSI color code for colorlog color name."""
        color_codes = {
            "cyan": "36",
            "green": "32",
            "yellow": "33",
            "red": "31",
            "red,bg_white": "31;47",
        }
        return color_codes.get(color, "0")


def configure_structlog(
    log_format: str = "console",
    debug: bool = False,
    colored: bool = True,
) -> None:
    """Configure structlog with appropriate processors.

    Args:
        log_format: Output format ("console", "json", "simple", "detailed")
        debug: Enable debug-level processing
        colored: Enable colored output for console formats
    """
    # Base processors that are always included
    processors: list[Any] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Add appropriate renderer based on format
    if log_format == "json":
        processors.append(JSONRenderer())
    elif log_format in ("console", "detailed"):
        if colored and HAS_COLORLOG:
            processors.append(StructlogColorRenderer())
        else:
            processors.append(structlog.dev.ConsoleRenderer(colors=False))
    else:  # simple format
        processors.append(
            structlog.dev.ConsoleRenderer(colors=colored and HAS_COLORLOG)
        )

    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def setup_structlog_from_config(config: "LoggingConfig") -> None:
    """Set up structlog from LoggingConfig object.

    Args:
        config: Logging configuration
    """
    # For now, use the first handler's configuration to determine structlog setup
    # In a full implementation, we might want to support multiple structlog outputs
    if not config.handlers:
        return

    primary_handler = config.handlers[0]

    # Map LogFormat to structlog format
    format_mapping = {
        "simple": "simple",
        "detailed": "console",
        "json": "json",
    }

    # Handle both enum and string format values
    format_value = (
        primary_handler.format.value
        if hasattr(primary_handler.format, "value")
        else primary_handler.format
    )

    log_format = format_mapping.get(format_value, "console")

    # Determine if debug level logging is enabled
    debug = any(
        handler.get_log_level_int() <= logging.DEBUG for handler in config.handlers
    )

    configure_structlog(
        log_format=log_format,
        debug=debug,
        colored=primary_handler.colored,
    )


def setup_structlog_simple(
    level: int | str = logging.INFO,
    log_format: str = "console",
    colored: bool = True,
) -> None:
    """Set up structlog with simple configuration (backward compatibility).

    Args:
        level: Logging level (determines debug flag)
        log_format: Format string ("console", "json", "simple")
        colored: Enable colored output
    """
    # Convert level to debug flag
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    debug = level <= logging.DEBUG

    configure_structlog(
        log_format=log_format,
        debug=debug,
        colored=colored,
    )
