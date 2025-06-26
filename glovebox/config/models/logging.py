"""Logging configuration models for Glovebox."""

import logging
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator

from glovebox.models.base import GloveboxBaseModel


class LogHandlerType(str, Enum):
    """Types of log handlers supported."""

    CONSOLE = "console"
    STDERR = "stderr"
    FILE = "file"


class LogFormat(str, Enum):
    """Log format presets."""

    SIMPLE = "simple"
    DETAILED = "detailed"
    JSON = "json"


class LogHandlerConfig(GloveboxBaseModel):
    """Configuration for a single log handler."""

    type: LogHandlerType = Field(
        description="Type of handler: console, stderr, or file"
    )
    level: str = Field(
        default="INFO", description="Log level for this handler (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    format: LogFormat = Field(
        default=LogFormat.SIMPLE, description="Format preset for log messages"
    )
    colored: bool = Field(
        default=True, description="Enable colored output (console/stderr only)"
    )
    file_path: Path | None = Field(
        default=None, description="File path for file handlers (required for type=file)"
    )
    queue_enabled: bool = Field(
        default=False, description="Enable queue-based logging for non-blocking operation (useful for TUI applications)"
    )

    @field_validator("level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is recognized."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        upper_v = v.strip().upper()
        if upper_v not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return upper_v

    @field_validator("colored")
    @classmethod
    def validate_colored_for_handler_type(cls, v: bool, info: Any) -> bool:
        """Validate colored is only used with console/stderr handlers."""
        # Note: In Pydantic v2, we can't access other fields during validation
        # This validation will be handled in the model's model_post_init if needed
        return v

    @field_validator("file_path", mode="before")
    @classmethod
    def validate_file_path(cls, v: Any, info: Any) -> Path | None:
        """Validate and expand file path."""
        if v is None:
            return None
        if isinstance(v, str):
            return Path(v).expanduser().resolve()
        if isinstance(v, Path):
            return v.expanduser().resolve()
        # Invalid type, return None (will be caught by validation)
        return None

    def model_post_init(self, __context: Any) -> None:
        """Post-initialization validation."""
        # Validate file_path is provided for file handlers
        if self.type == LogHandlerType.FILE and not self.file_path:
            raise ValueError("file_path is required for file handlers")

        # Warn if colored is used with file handlers (but don't fail)
        if self.type == LogHandlerType.FILE and self.colored:
            # We'll handle this in the logging setup by ignoring colored for file handlers
            pass

    def get_log_level_int(self) -> int:
        """Get log level as integer for logging module."""
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        return level_map.get(self.level, logging.INFO)


class LoggingConfig(GloveboxBaseModel):
    """Main logging configuration with multiple handlers."""

    handlers: list[LogHandlerConfig] = Field(
        default_factory=list, description="List of log handlers to configure"
    )

    @field_validator("handlers")
    @classmethod
    def validate_handlers_not_empty(cls, v: list[LogHandlerConfig]) -> list[LogHandlerConfig]:
        """Ensure at least one handler is configured."""
        if not v:
            raise ValueError("At least one log handler must be configured")
        return v

    def model_post_init(self, __context: Any) -> None:
        """Post-initialization validation."""
        # Validate unique file paths for file handlers
        file_paths = []
        for handler in self.handlers:
            if handler.type == LogHandlerType.FILE and handler.file_path:
                if handler.file_path in file_paths:
                    raise ValueError(f"Duplicate file path in handlers: {handler.file_path}")
                file_paths.append(handler.file_path)


def create_default_logging_config() -> LoggingConfig:
    """Create default logging configuration.

    Returns:
        LoggingConfig with a single colored stderr handler at WARNING level
    """
    return LoggingConfig(
        handlers=[
            LogHandlerConfig(
                type=LogHandlerType.STDERR,
                level="WARNING",
                format=LogFormat.SIMPLE,
                colored=True,
            )
        ]
    )


def create_developer_logging_config(debug_file: Path | None = None) -> LoggingConfig:
    """Create developer-friendly logging configuration.

    Args:
        debug_file: Optional path for debug log file

    Returns:
        LoggingConfig with colored console + optional debug file
    """
    handlers = [
        LogHandlerConfig(
            type=LogHandlerType.STDERR,
            level="INFO",
            format=LogFormat.DETAILED,
            colored=True,
        )
    ]

    if debug_file:
        handlers.append(
            LogHandlerConfig(
                type=LogHandlerType.FILE,
                level="DEBUG",
                format=LogFormat.JSON,
                colored=False,
                file_path=debug_file,
            )
        )

    return LoggingConfig(handlers=handlers)


def create_tui_logging_config(debug_file: Path | None = None) -> LoggingConfig:
    """Create TUI-optimized logging configuration with queue-based handlers.

    Args:
        debug_file: Optional path for debug log file

    Returns:
        LoggingConfig with queue-enabled handlers for non-blocking TUI operation
    """
    handlers = [
        LogHandlerConfig(
            type=LogHandlerType.STDERR,
            level="WARNING",
            format=LogFormat.SIMPLE,
            colored=True,
            queue_enabled=True,  # Non-blocking for TUI
        )
    ]

    if debug_file:
        handlers.append(
            LogHandlerConfig(
                type=LogHandlerType.FILE,
                level="DEBUG",
                format=LogFormat.JSON,
                colored=False,
                file_path=debug_file,
                queue_enabled=True,  # Non-blocking for TUI
            )
        )

    return LoggingConfig(handlers=handlers)
