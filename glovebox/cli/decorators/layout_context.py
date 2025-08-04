"""Layout context decorators for CLI commands."""

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

import typer
from click import Context as ClickContext

from glovebox.cli.helpers import print_error_message
from glovebox.cli.helpers.auto_profile import resolve_json_file_path
from glovebox.cli.helpers.parameters import create_profile_from_param_unified


logger = logging.getLogger(__name__)


def with_layout_context(
    needs_json: bool = True,
    needs_profile: bool = True,
    validate_json: bool = True,
    default_profile: str = "glove80/v25.05",
) -> Callable[..., Any]:
    """Decorator to provide common layout command context.

    This decorator handles the common boilerplate for layout commands:
    - JSON file resolution from arguments or environment variables
    - JSON file validation (existence, readability)
    - Profile creation and resolution with auto-detection
    - Error handling with consistent messaging

    The decorated function will receive additional keyword arguments:
    - resolved_json_file: Path to the resolved JSON file (if needs_json=True)
    - keyboard_profile: KeyboardProfile instance (if needs_profile=True)

    Args:
        needs_json: Whether the command needs a JSON file resolved
        needs_profile: Whether the command needs a keyboard profile
        validate_json: Whether to validate JSON file existence/readability
        default_profile: Default profile string if none provided

    Returns:
        Decorated function with layout context handling

    Example:
        @handle_errors
        @with_layout_context(needs_json=True, needs_profile=True)
        def my_command(
            ctx: typer.Context,
            json_file: JsonFileArgument = None,
            profile: ProfileOption = None,
            # Injected by decorator:
            resolved_json_file: Path = None,
            keyboard_profile: "KeyboardProfile | None" = None,
        ) -> None:
            # Command implementation with resolved context
            pass
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # Check if the function has a ctx parameter at decoration time
        import inspect

        sig = inspect.signature(func)
        if "ctx" not in sig.parameters:
            raise RuntimeError(
                f"Function '{func.__name__}' decorated with @with_layout_context must have a 'ctx: typer.Context' parameter."
            )

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Find the Context object from the arguments
            # Check for both typer.Context and click.Context since typer is built on click
            ctx = next(
                (arg for arg in args if isinstance(arg, typer.Context | ClickContext)),
                None,
            )
            if ctx is None:
                ctx = kwargs.get("ctx")

            if not isinstance(ctx, typer.Context | ClickContext):
                # This shouldn't happen if typer is working correctly
                logger.warning(
                    "Context not found in args or kwargs for %s. Args: %s, Kwargs keys: %s",
                    func.__name__,
                    [type(arg).__name__ for arg in args],
                    list(kwargs.keys()),
                )
                raise RuntimeError(
                    "with_layout_context decorator could not find typer.Context or click.Context in arguments."
                )

            # Handle JSON file resolution
            if needs_json:
                # Try different parameter names for JSON file
                json_file_arg = (
                    kwargs.get("json_file")
                    or kwargs.get("layout_file")
                    or kwargs.get("file1")  # For comparison commands
                )

                resolved_json_file = resolve_json_file_path(
                    json_file_arg, "GLOVEBOX_JSON_FILE"
                )

                if not resolved_json_file:
                    print_error_message(
                        "JSON file is required. Provide as argument or set GLOVEBOX_JSON_FILE environment variable."
                    )
                    raise typer.Exit(1)

                if validate_json:
                    if not resolved_json_file.exists():
                        print_error_message(
                            f"Layout file not found: {resolved_json_file}"
                        )
                        raise typer.Exit(1)
                    if not resolved_json_file.is_file():
                        print_error_message(f"Path is not a file: {resolved_json_file}")
                        raise typer.Exit(1)

                kwargs["resolved_json_file"] = resolved_json_file

            # Handle profile resolution
            if needs_profile:
                try:
                    keyboard_profile = create_profile_from_param_unified(
                        ctx=ctx,
                        profile=kwargs.get("profile"),
                        default_profile=default_profile,
                        json_file=kwargs.get("resolved_json_file"),
                        no_auto=kwargs.get("no_auto", False),
                    )
                    kwargs["keyboard_profile"] = keyboard_profile
                except Exception as e:
                    exc_info = logger.isEnabledFor(logging.DEBUG)
                    logger.error("Failed to resolve profile: %s", e, exc_info=exc_info)
                    print_error_message(f"Failed to resolve profile: {e}")
                    raise typer.Exit(1) from e

            # Store injected values in the context for functions to access
            if ctx:
                if "resolved_json_file" in kwargs:
                    ctx.meta["resolved_json_file"] = kwargs["resolved_json_file"]
                if "keyboard_profile" in kwargs:
                    ctx.meta["keyboard_profile"] = kwargs["keyboard_profile"]

            # Clean up kwargs to remove parameters not in the original function signature
            # This prevents TypeError: got an unexpected keyword argument
            import inspect

            sig = inspect.signature(func)
            func_params = set(sig.parameters.keys())

            # Remove injected parameters that are not in the function signature
            injected_params = {"resolved_json_file", "keyboard_profile"}
            filtered_kwargs = {
                k: v
                for k, v in kwargs.items()
                if k in func_params or k not in injected_params
            }

            return func(*args, **filtered_kwargs)

        return wrapper

    return decorator
