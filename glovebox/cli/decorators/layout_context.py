"""Layout context decorators for CLI commands."""

import logging
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any

import typer
from click import Context as ClickContext


if TYPE_CHECKING:
    # Type hints only - not loaded at runtime
    from glovebox.config.profile import KeyboardProfile

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
            json_file: Path | None = None,
            profile: str | None = None,
            **kwargs
        ):
            resolved_json = kwargs.get('resolved_json_file')
            keyboard_profile = kwargs.get('keyboard_profile')
            # ... command implementation
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Lazy import helpers only when decorator is actually used
            from glovebox.cli.helpers import print_error_message
            from glovebox.cli.helpers.auto_profile import resolve_json_file_path
            from glovebox.cli.helpers.parameters import (
                create_profile_from_param_unified,
            )

            # Extract context and parameters
            ctx = None
            json_file = None
            profile_param = None

            # Find the context and parameters in args/kwargs
            for arg in args:
                if isinstance(arg, typer.Context | ClickContext):
                    ctx = arg
                    break

            # Get parameters from kwargs
            json_file = kwargs.get("json_file")
            profile_param = kwargs.get("profile")

            # Process JSON file if needed
            resolved_json_file = None
            if needs_json:
                try:
                    # Use the helper to resolve JSON file path
                    resolved_json_file = resolve_json_file_path(json_file)
                    if resolved_json_file:
                        logger.debug(f"Resolved JSON file: {resolved_json_file}")
                        kwargs["resolved_json_file"] = resolved_json_file
                except Exception as e:
                    print_error_message(f"Failed to resolve JSON file: {e}")
                    raise typer.Exit(1) from e

            # Process profile if needed
            keyboard_profile = None
            if needs_profile:
                try:
                    # Create profile with auto-detection support
                    if ctx is not None:
                        keyboard_profile = create_profile_from_param_unified(
                            ctx=ctx,
                            profile=profile_param,
                            json_file=resolved_json_file,
                            default_profile=default_profile,
                        )
                    else:
                        # Fallback without context
                        from glovebox.config.keyboard_profile import create_keyboard_profile
                        keyboard_profile = create_keyboard_profile(
                            profile_param or default_profile, None, None
                        )
                    if keyboard_profile:
                        logger.debug(f"Using profile: {keyboard_profile}")
                        kwargs["keyboard_profile"] = keyboard_profile
                except Exception as e:
                    print_error_message(f"Failed to create keyboard profile: {e}")
                    raise typer.Exit(1) from e

            # Call the original function with enhanced kwargs
            return func(*args, **kwargs)

        return wrapper

    return decorator
