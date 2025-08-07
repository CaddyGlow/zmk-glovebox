"""Structlog logger factory and utilities for Glovebox."""

import logging
from typing import Any

import structlog


def get_struct_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a structlog logger with the given name.

    Args:
        name: The logger name, usually __name__

    Returns:
        A bound structlog logger instance

    Note: For exception logging with debug stack traces, use this pattern:
        try:
            # some operation
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("operation_failed", error=str(e), exc_info=exc_info)
    """
    return structlog.get_logger(name)  # type: ignore[no-any-return]


def get_struct_logger_with_context(
    name: str, **context: Any
) -> structlog.stdlib.BoundLogger:
    """Get a structlog logger with bound context.

    Args:
        name: The logger name, usually __name__
        **context: Context to bind to the logger

    Returns:
        A bound structlog logger with context

    Example:
        logger = get_struct_logger_with_context(__name__, session_id="123", operation="compile")
        logger.info("starting_operation")  # Will include session_id and operation in output
    """
    logger = structlog.get_logger(name)
    return logger.bind(**context)  # type: ignore[no-any-return]


class StructlogMixin:
    """Mixin class to add structured logging capabilities to services.

    This mixin provides a consistent way for services to access structured logging
    with automatic context binding for common service attributes.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the mixin."""
        super().__init__(*args, **kwargs)
        self._logger: structlog.stdlib.BoundLogger | None = None

    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """Get or create a logger for this service with bound context."""
        if self._logger is None:
            base_logger = get_struct_logger(self.__class__.__module__)

            # Bind common service context
            context = {
                "service": self.__class__.__name__,
            }

            # Add service-specific context if available
            if hasattr(self, "service_name"):
                context["service_name"] = self.service_name
            if hasattr(self, "service_version"):
                context["service_version"] = self.service_version

            self._logger = base_logger.bind(**context)

        return self._logger

    def log_operation(
        self, operation: str, **context: Any
    ) -> structlog.stdlib.BoundLogger:
        """Get a logger bound to a specific operation.

        Args:
            operation: Name of the operation being performed
            **context: Additional context for the operation

        Returns:
            Logger bound with operation context
        """
        return self.logger.bind(operation=operation, **context)

    def log_error_with_context(
        self,
        message: str,
        error: Exception,
        **context: Any,
    ) -> None:
        """Log an error with structured context and appropriate stack trace.

        Args:
            message: Error message/event name
            error: The exception that occurred
            **context: Additional context
        """
        # Determine if we should include stack trace based on debug level
        # Use the appropriate method for structured logging
        if hasattr(self.logger, "isEnabledFor"):
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
        elif hasattr(self.logger, "is_enabled_for"):
            exc_info = self.logger.is_enabled_for(logging.DEBUG)
        else:
            # Default to including stack trace for safety
            exc_info = logging.getLogger().isEnabledFor(logging.DEBUG)

        self.logger.error(
            message,
            error=str(error),
            error_type=error.__class__.__name__,
            exc_info=exc_info,
            **context,
        )


def log_operation_context(operation: str, **context: Any) -> Any:
    """Decorator to add operation context to all log calls within a method.

    Args:
        operation: Name of the operation
        **context: Additional context to bind

    Example:
        @log_operation_context("compile_layout", format="zmk")
        def compile_layout(self, data):
            self.logger.info("starting_compilation")  # Will include operation and format
    """

    def decorator(func: Any) -> Any:
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            # Store original logger
            original_logger = getattr(self, "_logger", None)

            # Create operation-bound logger
            if hasattr(self, "logger"):
                self._logger = self.logger.bind(operation=operation, **context)

            try:
                return func(self, *args, **kwargs)
            finally:
                # Restore original logger
                self._logger = original_logger

        return wrapper

    return decorator


# Backward compatibility aliases
def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Backward compatibility alias for get_struct_logger.

    Args:
        name: The logger name, usually __name__

    Returns:
        A bound structlog logger instance
    """
    return get_struct_logger(name)
