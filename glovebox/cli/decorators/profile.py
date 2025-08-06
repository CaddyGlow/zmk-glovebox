"""Profile decorators for CLI commands."""

import logging
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any

import typer
from click.core import Context

from glovebox.core.structlog_logger import get_struct_logger


logger = get_struct_logger(__name__)


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

            # Handle non-required profiles - but still try auto-detection if enabled
            if not required and profile_option is None and not support_auto_detection:
                # For non-required profiles without auto-detection, still try user config defaults
                # Use the unified profile resolution logic to get user config defaults
                try:
                    from glovebox.cli.helpers.profile import (
                        resolve_and_create_profile_unified,
                    )

                    # Apply default profile if provided
                    effective_default_profile = default_profile
                    if firmware_optional and default_profile and "/" in default_profile:
                        # Extract just the keyboard part for firmware-optional profiles
                        effective_default_profile = default_profile.split("/")[0]

                    profile_obj = resolve_and_create_profile_unified(
                        ctx=ctx,
                        profile_option=profile_option,
                        default_profile=effective_default_profile,
                        json_file_path=None,
                        no_auto=True,
                    )

                    # For firmware_optional, allow keyboard-only profiles
                    if firmware_optional and profile_obj.firmware_version is None:
                        # This is acceptable for firmware-optional commands
                        pass

                    # Profile is already stored in context by the unified function
                    # Call the original function
                    return func(*args, **kwargs)
                except Exception:
                    # If profile resolution fails and it's not required, continue with None
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
                            json_file_value = kwargs[candidate]

                            # Handle library references and convert to Path
                            try:
                                if (
                                    isinstance(json_file_value, str)
                                    and json_file_value.startswith("@")
                                    or isinstance(json_file_value, str)
                                ):
                                    from glovebox.cli.helpers.auto_profile import (
                                        resolve_json_file_path,
                                    )

                                    json_file_path = resolve_json_file_path(
                                        json_file_value
                                    )
                                elif isinstance(json_file_value, Path):
                                    json_file_path = json_file_value
                                else:
                                    # Convert to string then resolve
                                    from glovebox.cli.helpers.auto_profile import (
                                        resolve_json_file_path,
                                    )

                                    json_file_path = resolve_json_file_path(
                                        str(json_file_value)
                                    )

                                no_auto = kwargs.get("no_auto", False)
                                break
                            except Exception as e:
                                logger.debug(
                                    "Failed to resolve JSON file %s: %s",
                                    json_file_value,
                                    e,
                                )
                                # Continue to next candidate
                                continue

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

                # If profile is required and we failed to resolve it, provide helpful error
                if required:
                    from glovebox.cli.helpers import print_error_message

                    print_error_message(
                        "Profile is required but could not be resolved. Use --profile KEYBOARD/FIRMWARE (e.g., --profile glove80/v25.05)"
                    )

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
                logger.debug(
                    "No context found for metrics tracking in %s", func.__name__
                )
                return func(*args, **kwargs)

            try:
                # Get session metrics from context
                from glovebox.cli.app import AppContext

                app_ctx: AppContext = ctx.obj
                if not hasattr(app_ctx, "session_metrics"):
                    logger.debug(
                        "No session metrics available in context for %s", func.__name__
                    )
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


def with_cache(
    tag: str,
    cache_param_name: str = "cache_manager",
    compilation_cache: bool = False,
    required: bool = True,
) -> Callable[..., Any]:
    """Decorator to automatically handle cache manager creation and injection.

    This decorator simplifies CLI commands that use cache services by:
    1. Creating cache manager using user config and session metrics
    2. Optionally creating compilation-specific cache services
    3. Storing cache objects in the context for retrieval via helper functions
    4. Handling cache creation errors gracefully

    Args:
        tag: Cache tag for domain isolation (e.g., "compilation", "layout", "metrics")
        cache_param_name: Name of the cache parameter (currently unused, for future expansion)
        compilation_cache: If True, creates compilation cache services tuple
        required: If True, cache creation errors cause command failure

    Returns:
        Decorated function with automatic cache handling

    Example:
        @with_cache("compilation", compilation_cache=True)
        def compile_command(ctx: typer.Context, ...):
            # Access cache services from context
            cache_manager = get_cache_manager_from_context(ctx)
            workspace_service, build_service = get_compilation_cache_services_from_context(ctx)

        @with_cache("layout")
        def layout_command(ctx: typer.Context, ...):
            cache_manager = get_cache_manager_from_context(ctx)
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Find the Context object from the arguments (same pattern as with_metrics)
            ctx = next((arg for arg in args if isinstance(arg, Context)), None)
            if ctx is None:
                ctx = kwargs.get("ctx")

            if not isinstance(ctx, Context):
                if required:
                    logger.error("Cache decorator requires typer.Context as argument")
                    raise typer.Exit(1)
                else:
                    logger.warning(
                        "Cache decorator could not find typer.Context, skipping cache setup"
                    )
                    return func(*args, **kwargs)

            try:
                # Get user config and session metrics from context
                from glovebox.cli.app import AppContext

                app_ctx: AppContext = ctx.obj
                user_config = getattr(app_ctx, "user_config", None)
                session_metrics = getattr(app_ctx, "session_metrics", None)

                if user_config is None and required:
                    logger.error("User config not available in context for cache setup")
                    raise typer.Exit(1)

                # Create cache manager using user config
                if user_config:
                    from glovebox.core.cache import create_cache_from_user_config

                    cache_manager = create_cache_from_user_config(
                        user_config, tag=tag, session_metrics=session_metrics
                    )
                else:
                    # Fallback to default cache if user_config not available
                    from glovebox.core.cache import create_default_cache

                    cache_manager = create_default_cache(
                        tag=tag, session_metrics=session_metrics
                    )

                # Store cache manager in context for helper function access
                if "cache_objects" not in ctx.meta:
                    ctx.meta["cache_objects"] = {}

                ctx.meta["cache_objects"]["cache_manager"] = cache_manager

                # Create compilation cache services if requested
                if compilation_cache:
                    try:
                        from glovebox.compilation.cache import (
                            create_compilation_cache_service,
                        )

                        if user_config is None:
                            raise ValueError(
                                "User config is required for compilation cache services"
                            )

                        cache_manager_comp, workspace_service, build_service = (
                            create_compilation_cache_service(
                                user_config, session_metrics
                            )
                        )

                        # Store compilation cache services in context
                        cache_objects = ctx.meta["cache_objects"]
                        cache_objects["compilation_cache_manager"] = cache_manager_comp
                        cache_objects["workspace_cache_service"] = workspace_service
                        cache_objects["build_cache_service"] = build_service

                    except Exception as e:
                        if required:
                            logger.error(
                                "Failed to create compilation cache services: %s", e
                            )
                            raise typer.Exit(1) from e
                        else:
                            logger.warning(
                                "Failed to create compilation cache services, continuing without cache: %s",
                                e,
                            )

                logger.debug("Cache services created successfully with tag: %s", tag)

            except Exception as e:
                if required:
                    logger.error("Failed to create cache services: %s", e)
                    raise typer.Exit(1) from e
                else:
                    logger.warning(
                        "Failed to create cache services, continuing without cache: %s",
                        e,
                    )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def get_cache_manager_from_context(ctx: typer.Context) -> Any:
    """Helper function to get cache manager from context.

    Args:
        ctx: Typer context with cache objects

    Returns:
        CacheManager instance

    Raises:
        RuntimeError: If cache manager is not available in context
    """
    try:
        # Check if cache_objects exists in ctx.meta
        if hasattr(ctx, "meta") and "cache_objects" in ctx.meta:
            cache_manager = ctx.meta["cache_objects"].get("cache_manager")
            if cache_manager is not None:
                return cache_manager

        raise RuntimeError(
            "Cache manager not available in context. Ensure @with_cache decorator is applied."
        )
    except Exception as e:
        if isinstance(e, RuntimeError):
            raise
        raise RuntimeError("Failed to retrieve cache manager from context") from e


def get_compilation_cache_services_from_context(
    ctx: typer.Context,
) -> tuple[Any, Any, Any]:
    """Helper function to get compilation cache services from context.

    Args:
        ctx: Typer context with cache objects

    Returns:
        Tuple of (cache_manager, workspace_service, build_service)

    Raises:
        RuntimeError: If compilation cache services are not available in context
    """
    try:
        # Check if cache_objects exists in ctx.meta
        if hasattr(ctx, "meta") and "cache_objects" in ctx.meta:
            cache_objects = ctx.meta["cache_objects"]
            cache_manager = cache_objects.get("compilation_cache_manager")
            workspace_service = cache_objects.get("workspace_cache_service")
            build_service = cache_objects.get("build_cache_service")

            if (
                cache_manager is not None
                and workspace_service is not None
                and build_service is not None
            ):
                return cache_manager, workspace_service, build_service

        raise RuntimeError(
            "Compilation cache services not available in context. Ensure @with_cache decorator is applied with compilation_cache=True."
        )
    except Exception as e:
        if isinstance(e, RuntimeError):
            raise
        raise RuntimeError(
            "Failed to retrieve compilation cache services from context"
        ) from e


def with_tmpdir(
    prefix: str = "glovebox_",
    suffix: str = "",
    cleanup: bool = True,
    tmp_param_name: str = "tmp_dir",
) -> Callable[..., Any]:
    """Decorator to automatically handle temporary directory creation and cleanup.

    This decorator simplifies CLI commands that need temporary directories by:
    1. Creating a temporary directory with configurable prefix/suffix
    2. Storing it in the context for retrieval via helper functions
    3. Automatically cleaning up the directory after command completion
    4. Handling cleanup errors gracefully

    Args:
        prefix: Prefix for temporary directory name (default: "glovebox_")
        suffix: Suffix for temporary directory name (default: "")
        cleanup: Whether to automatically clean up the directory (default: True)
        tmp_param_name: Name of the temp directory parameter (currently unused, for future expansion)

    Returns:
        Decorated function with automatic temporary directory handling

    Example:
        @with_tmpdir(prefix="firmware_build_", cleanup=True)
        def compile_command(ctx: typer.Context, ...):
            # Access temp directory from context
            tmp_dir = get_tmpdir_from_context(ctx)
            # Use tmp_dir for temporary files...

        @with_tmpdir(prefix="layout_work_", suffix="_processing")
        def process_layout(ctx: typer.Context, ...):
            tmp_dir = get_tmpdir_from_context(ctx)
            work_files = tmp_dir / "processing"
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Find the Context object from the arguments (same pattern as with_metrics)
            ctx = next((arg for arg in args if isinstance(arg, Context)), None)
            if ctx is None:
                ctx = kwargs.get("ctx")

            if not isinstance(ctx, Context):
                logger.warning(
                    "Temp directory decorator could not find typer.Context, skipping temp dir setup"
                )
                return func(*args, **kwargs)

            import tempfile
            from pathlib import Path

            tmp_dir = None
            try:
                # Create temporary directory
                tmp_dir = Path(tempfile.mkdtemp(prefix=prefix, suffix=suffix))
                logger.debug("Created temporary directory: %s", tmp_dir)

                # Store temp directory in context for helper function access
                if "tmp_objects" not in ctx.meta:
                    ctx.meta["tmp_objects"] = {}

                ctx.meta["tmp_objects"]["tmp_dir"] = tmp_dir

                # Execute the original function
                result = func(*args, **kwargs)

                return result

            except Exception as e:
                logger.error("Error in command with temporary directory: %s", e)
                raise

            finally:
                # Clean up temporary directory if requested
                if cleanup and tmp_dir and tmp_dir.exists():
                    try:
                        import shutil

                        shutil.rmtree(tmp_dir)
                        logger.debug("cleaned_up_temporary_directory", directory=str(tmp_dir))
                    except Exception as cleanup_error:
                        logger.warning(
                            "failed_to_clean_up_temporary_directory",
                            directory=str(tmp_dir),
                            error=str(cleanup_error),
                        )

        return wrapper

    return decorator


def get_tmpdir_from_context(ctx: typer.Context) -> Path:
    """Helper function to get temporary directory from context.

    Args:
        ctx: Typer context with tmp objects

    Returns:
        Path to temporary directory

    Raises:
        RuntimeError: If temporary directory is not available in context
    """
    try:
        # Check if tmp_objects exists in ctx.meta
        if hasattr(ctx, "meta") and "tmp_objects" in ctx.meta:
            tmp_dir = ctx.meta["tmp_objects"].get("tmp_dir")
            if tmp_dir is not None:
                return Path(tmp_dir)

        raise RuntimeError(
            "Temporary directory not available in context. Ensure @with_tmpdir decorator is applied."
        )
    except Exception as e:
        if isinstance(e, RuntimeError):
            raise
        raise RuntimeError("Failed to retrieve temporary directory from context") from e


def with_user_config(
    required: bool = True,
    fallback_to_default: bool = True,
    config_param_name: str = "user_config",
) -> Callable[..., Any]:
    """Decorator to automatically handle user config creation and validation.

    This decorator simplifies CLI commands that need user configuration by:
    1. Extracting user config from context with optional fallback to default
    2. Validating config creation and handling errors consistently
    3. Storing user config in context for retrieval via helper functions
    4. Following CLAUDE.md exception logging patterns

    Args:
        required: If True, config creation errors cause command failure
        fallback_to_default: If True, falls back to create_user_config() when context fails
        config_param_name: Name of the config parameter (currently unused, for future expansion)

    Returns:
        Decorated function with automatic user config handling

    Example:
        @with_user_config(required=True)
        def my_command(ctx: typer.Context, ...):
            # Access user config from context
            user_config = get_user_config_from_context_decorator(ctx)

        @with_user_config(required=False, fallback_to_default=False)
        def optional_config_command(ctx: typer.Context, ...):
            user_config = get_user_config_from_context_decorator(ctx)
            if user_config is None:
                # Handle no config case
                pass
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Find the Context object from the arguments (same pattern as other decorators)
            ctx = next((arg for arg in args if isinstance(arg, Context)), None)
            if ctx is None:
                ctx = kwargs.get("ctx")

            if not isinstance(ctx, Context):
                if required:
                    logger.error(
                        "User config decorator requires typer.Context as argument"
                    )
                    raise typer.Exit(1)
                else:
                    logger.warning(
                        "User config decorator could not find typer.Context, skipping config setup"
                    )
                    return func(*args, **kwargs)

            try:
                # Try to get user config from context first
                from glovebox.cli.helpers.profile import get_user_config_from_context

                user_config = get_user_config_from_context(ctx)

                # If no config in context and fallback is enabled, create default
                if user_config is None and fallback_to_default:
                    try:
                        from glovebox.config import create_user_config

                        user_config = create_user_config()
                        logger.debug("Created fallback user config instance")
                    except Exception as e:
                        exc_info = logger.isEnabledFor(logging.DEBUG)
                        logger.error(
                            "Failed to create fallback user config: %s",
                            e,
                            exc_info=exc_info,
                        )
                        if required:
                            raise typer.Exit(1) from e
                        else:
                            user_config = None

                # Handle required config validation
                if required and user_config is None:
                    logger.error("User config is required but not available")
                    raise typer.Exit(1)

                # Store user config in context for helper function access
                if "config_objects" not in ctx.meta:
                    ctx.meta["config_objects"] = {}

                ctx.meta["config_objects"]["user_config"] = user_config

                logger.debug("User config successfully set up for command")

            except typer.Exit:
                # Re-raise exit exceptions
                raise
            except Exception as e:
                exc_info = logger.isEnabledFor(logging.DEBUG)
                logger.error(
                    "user_config_setup_failed", error=str(e), exc_info=exc_info
                )
                if required:
                    raise typer.Exit(1) from e
                else:
                    logger.warning("continuing_without_user_config", error=str(e))

            return func(*args, **kwargs)

        return wrapper

    return decorator


def get_user_config_from_context_decorator(ctx: typer.Context) -> Any:
    """Helper function to get user config from context (decorator version).

    This is different from get_user_config_from_context in helpers/profile.py
    as it retrieves config stored by the @with_user_config decorator.

    Args:
        ctx: Typer context with config objects

    Returns:
        UserConfig instance

    Raises:
        RuntimeError: If user config is not available in context
    """
    try:
        # Check if config_objects exists in ctx.meta
        if hasattr(ctx, "meta") and "config_objects" in ctx.meta:
            user_config = ctx.meta["config_objects"].get("user_config")
            if user_config is not None:
                return user_config

        raise RuntimeError(
            "User config not available in context. Ensure @with_user_config decorator is applied."
        )
    except Exception as e:
        if isinstance(e, RuntimeError):
            raise
        raise RuntimeError("Failed to retrieve user config from context") from e
