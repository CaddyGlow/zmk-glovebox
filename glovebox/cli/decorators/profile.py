"""Profile decorators for CLI commands."""

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

import typer
from click.core import Context


logger = logging.getLogger(__name__)


def with_profile(
    default_profile: str = "glove80/v25.05",
    profile_param_name: str = "profile",
    required: bool = True,
    firmware_optional: bool = False,
    support_auto_detection: bool = False,
) -> Callable[..., Any]:
    """Decorator to automatically handle profile parameter and profile creation.

    This decorator simplifies CLI commands that use keyboard profiles by:
    1. Setting a default profile if none is provided
    2. Creating the KeyboardProfile object using unified logic
    3. Storing it in the context for retrieval
    4. Handling profile creation errors

    The function must have a 'profile' parameter (or custom name via profile_param_name).

    Args:
        default_profile: Default profile to use if none is provided
        profile_param_name: Name of the profile parameter in the function
        required: If True, profile is mandatory; if False, allows None profile
        firmware_optional: If True, allows keyboard-only profiles (no firmware part)
        support_auto_detection: If True, enables auto-detection from JSON files

    Returns:
        Decorated function with profile handling
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Find the Context object from the arguments
            ctx = next((arg for arg in args if isinstance(arg, Context)), None)
            if ctx is None:
                ctx = kwargs.get("ctx")

            if not isinstance(ctx, Context):
                raise RuntimeError(
                    "This decorator requires the function to have a 'typer.Context' parameter."
                )

            # Extract the profile from kwargs
            profile_option = kwargs.get(profile_param_name)

            # Handle non-required profiles
            if not required and profile_option is None:
                # For non-required profiles, store None in context and continue
                if hasattr(ctx.obj, "__dict__"):
                    ctx.obj.keyboard_profile = None
                return func(*args, **kwargs)

            try:
                # Determine if we need to support auto-detection
                json_file_path = None
                no_auto = True

                if support_auto_detection:
                    # Try to find JSON file parameters in the function signature
                    # Look for common parameter names
                    json_file_candidates = [
                        "json_file",
                        "input_file",
                        "layout_file",
                        "file_path",
                    ]
                    for candidate in json_file_candidates:
                        if candidate in kwargs and kwargs[candidate] is not None:
                            json_file_path = kwargs[candidate]
                            no_auto = kwargs.get("no_auto", False)
                            break

                # Use the unified profile resolution logic
                from glovebox.cli.helpers.profile import (
                    resolve_and_create_profile_unified,
                )

                # For firmware_optional profiles, adjust the default profile
                effective_default_profile = default_profile
                if firmware_optional and default_profile and "/" in default_profile:
                    # Extract just the keyboard part for firmware-optional profiles
                    effective_default_profile = default_profile.split("/")[0]

                profile_obj = resolve_and_create_profile_unified(
                    ctx=ctx,
                    profile_option=profile_option,
                    default_profile=effective_default_profile,
                    json_file_path=json_file_path,
                    no_auto=no_auto,
                )

                # For firmware_optional, allow keyboard-only profiles
                if firmware_optional and profile_obj.firmware_version is None:
                    # This is acceptable for firmware-optional commands
                    pass
                elif not firmware_optional and profile_obj.firmware_version is None:
                    # This is not acceptable for firmware-required commands
                    logger.error(
                        "Profile %s requires firmware version but none was provided",
                        profile_option,
                    )
                    raise typer.Exit(1)

                # Profile is already stored in context by the unified function
                # Call the original function
                return func(*args, **kwargs)
            except typer.Exit:
                # Profile creation already handled the error, just re-raise
                raise
            except Exception as e:
                logger.error("Error with profile %s: %s", profile_option, e)
                raise typer.Exit(1) from e

        return wrapper

    return decorator


def with_metrics(
    operation_name: str,
    track_duration: bool = True,
    track_counter: bool = True,
    counter_labels: list[str] | None = None,
    auto_success_failure: bool = True,
) -> Callable[..., Any]:
    """Decorator to automatically handle metrics tracking for CLI commands.

    This decorator eliminates the need for repetitive metrics setup code in every command.
    It automatically creates Counter and Histogram metrics, tracks operation duration,
    and handles success/failure/error counting.

    Args:
        operation_name: Base name for the operation (e.g., "compile", "flash")
        track_duration: Whether to create and track duration histogram
        track_counter: Whether to create and track operation counter
        counter_labels: Labels for counter metrics (default: ["operation", "status"])
        auto_success_failure: Whether to automatically track success/failure/error

    Returns:
        Decorated function with automatic metrics tracking

    Example:
        @with_metrics("compile", track_duration=True)
        def compile_command(ctx: typer.Context, ...):
            # Metrics are automatically tracked
            return some_result()
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Find the Context object from the arguments
            ctx = next((arg for arg in args if isinstance(arg, Context)), None)
            if ctx is None:
                ctx = kwargs.get("ctx")

            if not isinstance(ctx, Context):
                # If no context, run function without metrics
                logger.debug("No context found for metrics tracking in %s", func.__name__)
                return func(*args, **kwargs)

            try:
                # Get session metrics from context
                from glovebox.cli.app import AppContext

                app_ctx: AppContext = ctx.obj
                if not hasattr(app_ctx, "session_metrics"):
                    logger.debug("No session metrics available in context for %s", func.__name__)
                    return func(*args, **kwargs)

                metrics = app_ctx.session_metrics

                # Create metrics instruments
                counter = None
                duration = None

                if track_counter:
                    labels = counter_labels or ["operation", "status"]
                    counter = metrics.Counter(
                        f"{operation_name}_operations_total",
                        f"Total {operation_name} operations",
                        labels,
                    )

                if track_duration:
                    duration = metrics.Histogram(
                        f"{operation_name}_operation_duration_seconds",
                        f"{operation_name} operation duration",
                    )

                # Execute the function with duration tracking
                try:
                    if track_duration and duration:
                        with duration.time():
                            result = func(*args, **kwargs)
                    else:
                        result = func(*args, **kwargs)

                    # Track success if auto tracking is enabled
                    if auto_success_failure and track_counter and counter:
                        counter.labels(operation_name, "success").inc()

                    return result

                except typer.Exit as exit_error:
                    # Handle typer.Exit (CLI exit with specific code)
                    if auto_success_failure and track_counter and counter:
                        if exit_error.exit_code == 0:
                            counter.labels(operation_name, "success").inc()
                        else:
                            counter.labels(operation_name, "failure").inc()
                    raise

                except Exception as e:
                    # Handle general exceptions
                    if auto_success_failure and track_counter and counter:
                        counter.labels(operation_name, "error").inc()
                    raise

            except Exception as metrics_error:
                # Don't let metrics errors break the actual command
                logger.debug(
                    "Metrics tracking error in %s: %s", func.__name__, metrics_error
                )
                return func(*args, **kwargs)

        return wrapper

    return decorator


def get_metrics_from_context(ctx: typer.Context) -> Any:
    """Helper function to get metrics from context.

    Args:
        ctx: Typer context

    Returns:
        SessionMetrics instance or None if not available
    """
    try:
        from glovebox.cli.app import AppContext

        app_ctx: AppContext = ctx.obj
        return getattr(app_ctx, "session_metrics", None)
    except Exception:
        return None


def get_icon_mode_from_context(ctx: typer.Context) -> str:
    """Helper function to get icon mode from context.

    Args:
        ctx: Typer context

    Returns:
        Icon mode string: "emoji", "nerdfont", or "text"
    """
    try:
        from glovebox.cli.app import AppContext

        app_ctx: AppContext = ctx.obj
        return getattr(app_ctx, "icon_mode", "emoji")
    except Exception:
        return "emoji"
