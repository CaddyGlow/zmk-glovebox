"""Decorators for automatic metrics collection during function execution."""

import functools
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar, Union

from glovebox.core.logging import get_logger
from glovebox.metrics.collector import create_metrics_collector
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
                # Create metrics collector with dependency injection
                collector = create_metrics_collector(
                    operation_type=operation_type,
                    operation_id=operation_id,
                    metrics_service=metrics_service,
                )

                with collector as metrics:
                    # Extract and set context if extractor provided
                    if extract_context:
                        try:
                            context = extract_context(func, args, kwargs)
                            if context:
                                metrics.set_context(**context)
                        except Exception as e:
                            exc_info = logger.isEnabledFor(logging.DEBUG)
                            logger.warning(
                                "Failed to extract context for %s: %s",
                                func.__name__,
                                e,
                                exc_info=exc_info,
                            )

                    # Execute the wrapped function
                    return func(*args, **kwargs)

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
                # Create metrics collector with dependency injection
                collector = create_metrics_collector(
                    operation_type=operation_type,
                    operation_id=operation_id,
                    metrics_service=metrics_service,
                )

                with collector as metrics:
                    # Extract and set context if extractor provided
                    if extract_context:
                        try:
                            context = extract_context(func, args, kwargs)
                            if context:
                                metrics.set_context(**context)
                        except Exception as e:
                            exc_info = logger.isEnabledFor(logging.DEBUG)
                            logger.warning(
                                "Failed to extract context for %s: %s",
                                func.__name__,
                                e,
                                exc_info=exc_info,
                            )

                    # Execute the wrapped async function
                    return await func(*args, **kwargs)

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
