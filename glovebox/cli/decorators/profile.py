"""Profile decorators for CLI commands."""

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

import typer
from click.core import Context


logger = logging.getLogger(__name__)


def with_profile(
    default_profile: str = "glove80/v25.05", profile_param_name: str = "profile"
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

            try:
                # Use the unified profile resolution logic
                from glovebox.cli.helpers.profile import (
                    resolve_and_create_profile_unified,
                )

                profile_obj = resolve_and_create_profile_unified(
                    ctx=ctx,
                    profile_option=profile_option,
                    default_profile=default_profile,
                    json_file_path=None,  # Decorator doesn't support auto-detection
                    no_auto=True,  # Disable auto-detection for decorator usage
                )

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
