"""Decorators for automatic metrics collection during function execution."""

import functools
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar, Union

from glovebox.core.logging import get_logger
from glovebox.metrics.collector import create_metrics_collector
from glovebox.metrics.context import clear_metrics_context, set_current_session_id
from glovebox.metrics.models import OperationType
from glovebox.metrics.protocols import MetricsServiceProtocol


# Type variables for generic decorator support
F = TypeVar("F", bound=Callable[..., Any])
AF = TypeVar("AF", bound=Callable[..., Awaitable[Any]])

# Context extractor type
ContextExtractor = Callable[
    [Callable[..., Any], tuple[Any, ...], dict[str, Any]], dict[str, Any]
]


def track_operation(
    operation_type: OperationType,
    extract_context: ContextExtractor | None = None,
    metrics_service: MetricsServiceProtocol | None = None,
    operation_id: str | None = None,
) -> Callable[[F], F]:
    """Decorator to automatically track function execution metrics.

    This decorator wraps functions to collect comprehensive metrics including:
    - Execution timing
    - Success/failure status
    - Context information extracted from function arguments
    - Cache hit/miss events (when applicable)
    - Error categorization and details

    Args:
        operation_type: Type of operation being tracked
        extract_context: Optional function to extract context from args/kwargs
        metrics_service: Optional metrics service instance for dependency injection
        operation_id: Optional operation ID (generates unique one if None)

    Returns:
        Decorated function that automatically collects metrics

    Examples:
        Basic usage:
        >>> @track_operation(OperationType.LAYOUT_COMPILATION)
        ... def compile_layout(json_file: Path, output: Path):
        ...     # Function implementation
        ...     pass

        With context extraction:
        >>> @track_operation(
        ...     OperationType.LAYOUT_COMPILATION,
        ...     extract_context=extract_cli_context
        ... )
        ... def compile_layout_cli(ctx, json_file, output, profile=None):
        ...     # CLI command implementation
        ...     pass
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Synchronous function wrapper with metrics collection."""
            logger = get_logger(__name__)

            try:
                # Extract context first to get session_id if available
                session_id = None
                context = {}
                if extract_context:
                    try:
                        context = extract_context(func, args, kwargs)
                        session_id = context.get("session_id")
                    except Exception as e:
                        exc_info = logger.isEnabledFor(logging.DEBUG)
                        logger.warning(
                            "Failed to extract context for %s: %s",
                            func.__name__,
                            e,
                            exc_info=exc_info,
                        )

                # Set session_id in thread-local context for services to access
                if session_id:
                    set_current_session_id(session_id)
                    logger.info(
                        "Starting %s operation with session ID: %s",
                        operation_type.value,
                        session_id,
                    )

                try:
                    # Create metrics collector with dependency injection and session_id
                    collector = create_metrics_collector(
                        operation_type=operation_type,
                        operation_id=operation_id,
                        metrics_service=metrics_service,
                        session_id=session_id,
                    )

                    with collector as metrics:
                        # Set remaining context if available
                        if context:
                            metrics.set_context(**context)

                        # Execute the wrapped function
                        return func(*args, **kwargs)
                finally:
                    # Clear thread-local context after execution
                    if session_id:
                        clear_metrics_context()

            except Exception as e:
                # Log error but re-raise to maintain original behavior
                exc_info = logger.isEnabledFor(logging.DEBUG)
                logger.error(
                    "Error in tracked operation %s: %s",
                    func.__name__,
                    e,
                    exc_info=exc_info,
                )
                raise

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            """Asynchronous function wrapper with metrics collection."""
            logger = get_logger(__name__)

            try:
                # Extract context first to get session_id if available
                session_id = None
                context = {}
                if extract_context:
                    try:
                        context = extract_context(func, args, kwargs)
                        session_id = context.get("session_id")
                    except Exception as e:
                        exc_info = logger.isEnabledFor(logging.DEBUG)
                        logger.warning(
                            "Failed to extract context for %s: %s",
                            func.__name__,
                            e,
                            exc_info=exc_info,
                        )

                # Set session_id in thread-local context for services to access
                if session_id:
                    set_current_session_id(session_id)
                    logger.info(
                        "Starting %s operation with session ID: %s",
                        operation_type.value,
                        session_id,
                    )

                try:
                    # Create metrics collector with dependency injection and session_id
                    collector = create_metrics_collector(
                        operation_type=operation_type,
                        operation_id=operation_id,
                        metrics_service=metrics_service,
                        session_id=session_id,
                    )

                    with collector as metrics:
                        # Set remaining context if available
                        if context:
                            metrics.set_context(**context)

                        # Execute the wrapped async function
                        return await func(*args, **kwargs)
                finally:
                    # Clear thread-local context after execution
                    if session_id:
                        clear_metrics_context()

            except Exception as e:
                # Log error but re-raise to maintain original behavior
                exc_info = logger.isEnabledFor(logging.DEBUG)
                logger.error(
                    "Error in tracked operation %s: %s",
                    func.__name__,
                    e,
                    exc_info=exc_info,
                )
                raise

        # Return appropriate wrapper based on function type
        if hasattr(func, "__code__") and func.__code__.co_flags & 0x80:
            # Function is a coroutine (async)
            return async_wrapper  # type: ignore
        else:
            # Function is synchronous
            return sync_wrapper  # type: ignore

    return decorator


def track_layout_operation(
    extract_context: ContextExtractor | None = None,
    metrics_service: MetricsServiceProtocol | None = None,
    operation_id: str | None = None,
) -> Callable[[F], F]:
    """Convenience decorator for layout operations.

    Args:
        extract_context: Optional function to extract context from args/kwargs
        metrics_service: Optional metrics service instance for dependency injection
        operation_id: Optional operation ID (generates unique one if None)

    Returns:
        Decorated function that tracks layout compilation metrics
    """
    return track_operation(
        operation_type=OperationType.LAYOUT_COMPILATION,
        extract_context=extract_context,
        metrics_service=metrics_service,
        operation_id=operation_id,
    )


def track_firmware_operation(
    extract_context: ContextExtractor | None = None,
    metrics_service: MetricsServiceProtocol | None = None,
    operation_id: str | None = None,
) -> Callable[[F], F]:
    """Convenience decorator for firmware operations.

    Args:
        extract_context: Optional function to extract context from args/kwargs
        metrics_service: Optional metrics service instance for dependency injection
        operation_id: Optional operation ID (generates unique one if None)

    Returns:
        Decorated function that tracks firmware compilation metrics
    """
    return track_operation(
        operation_type=OperationType.FIRMWARE_COMPILATION,
        extract_context=extract_context,
        metrics_service=metrics_service,
        operation_id=operation_id,
    )


def track_flash_operation(
    extract_context: ContextExtractor | None = None,
    metrics_service: MetricsServiceProtocol | None = None,
    operation_id: str | None = None,
) -> Callable[[F], F]:
    """Convenience decorator for flash operations.

    Args:
        extract_context: Optional function to extract context from args/kwargs
        metrics_service: Optional metrics service instance for dependency injection
        operation_id: Optional operation ID (generates unique one if None)

    Returns:
        Decorated function that tracks firmware flash metrics
    """
    return track_operation(
        operation_type=OperationType.FIRMWARE_FLASH,
        extract_context=extract_context,
        metrics_service=metrics_service,
        operation_id=operation_id,
    )


def track_config_operation(
    extract_context: ContextExtractor | None = None,
    metrics_service: MetricsServiceProtocol | None = None,
    operation_id: str | None = None,
) -> Callable[[F], F]:
    """Convenience decorator for configuration operations.

    Args:
        extract_context: Optional function to extract context from args/kwargs
        metrics_service: Optional metrics service instance for dependency injection
        operation_id: Optional operation ID (generates unique one if None)

    Returns:
        Decorated function that tracks configuration operation metrics
    """
    return track_operation(
        operation_type=OperationType.CONFIG_OPERATION,
        extract_context=extract_context,
        metrics_service=metrics_service,
        operation_id=operation_id,
    )


def track_cache_operation(
    extract_context: ContextExtractor | None = None,
    metrics_service: MetricsServiceProtocol | None = None,
    operation_id: str | None = None,
) -> Callable[[F], F]:
    """Convenience decorator for cache operations.

    Args:
        extract_context: Optional function to extract context from args/kwargs
        metrics_service: Optional metrics service instance for dependency injection
        operation_id: Optional operation ID (generates unique one if None)

    Returns:
        Decorated function that tracks cache operation metrics
    """
    return track_operation(
        operation_type=OperationType.CACHE_OPERATION,
        extract_context=extract_context,
        metrics_service=metrics_service,
        operation_id=operation_id,
    )


def track_file_operation(
    extract_context: ContextExtractor | None = None,
    metrics_service: MetricsServiceProtocol | None = None,
    operation_id: str | None = None,
) -> Callable[[F], F]:
    """Convenience decorator for file operations.

    Args:
        extract_context: Optional function to extract context from args/kwargs
        metrics_service: Optional metrics service instance for dependency injection
        operation_id: Optional operation ID (generates unique one if None)

    Returns:
        Decorated function that tracks file operation metrics
    """
    return track_operation(
        operation_type=OperationType.FILE_OPERATION,
        extract_context=extract_context,
        metrics_service=metrics_service,
        operation_id=operation_id,
    )


def track_validation_operation(
    extract_context: ContextExtractor | None = None,
    metrics_service: MetricsServiceProtocol | None = None,
    operation_id: str | None = None,
) -> Callable[[F], F]:
    """Convenience decorator for validation operations.

    Args:
        extract_context: Optional function to extract context from args/kwargs
        metrics_service: Optional metrics service instance for dependency injection
        operation_id: Optional operation ID (generates unique one if None)

    Returns:
        Decorated function that tracks validation operation metrics
    """
    return track_operation(
        operation_type=OperationType.VALIDATION_OPERATION,
        extract_context=extract_context,
        metrics_service=metrics_service,
        operation_id=operation_id,
    )


def track_cli_operation(
    operation_type: OperationType,
    extract_context: ContextExtractor | None = None,
    metrics_service: MetricsServiceProtocol | None = None,
    operation_id: str | None = None,
) -> Callable[[F], F]:
    """Decorator for tracking generic CLI operations with enhanced context.

    This decorator is designed for CLI commands that don't fit into specific
    operation categories (compilation, flash, etc.) and provides enhanced
    context extraction including command name and arguments.

    Args:
        operation_type: Type of operation being tracked
        extract_context: Optional function to extract context from args/kwargs
        metrics_service: Optional metrics service instance for dependency injection
        operation_id: Optional operation ID (generates unique one if None)

    Returns:
        Decorated function that tracks CLI operation metrics

    Example:
        >>> @track_cli_operation(OperationType.BOOKMARK_OPERATION)
        ... def list_bookmarks(ctx, factory_only=False):
        ...     pass
    """
    return track_operation(
        operation_type=operation_type,
        extract_context=extract_context,
        metrics_service=metrics_service,
        operation_id=operation_id,
    )


def create_operation_tracker(
    operation_type: OperationType,
    extract_context: ContextExtractor | None = None,
    metrics_service: MetricsServiceProtocol | None = None,
) -> Callable[[F], F]:
    """Factory function for creating operation tracking decorators.

    This factory follows the CLAUDE.md pattern for dependency injection and
    provides a consistent interface for creating metrics tracking decorators.

    Args:
        operation_type: Type of operation being tracked
        extract_context: Optional function to extract context from args/kwargs
        metrics_service: Optional metrics service instance for dependency injection

    Returns:
        Decorator function that can be applied to functions for metrics tracking

    Example:
        >>> tracker = create_operation_tracker(
        ...     OperationType.LAYOUT_COMPILATION,
        ...     extract_context=extract_cli_context
        ... )
        >>> @tracker
        ... def my_function():
        ...     pass
    """
    return track_operation(
        operation_type=operation_type,
        extract_context=extract_context,
        metrics_service=metrics_service,
    )
