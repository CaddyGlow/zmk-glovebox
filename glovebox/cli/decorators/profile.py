"""Profile decorators for CLI commands."""

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

import typer
from click.core import Context

from glovebox.cli.helpers.profile import create_profile_from_option
from glovebox.config.profile import KeyboardProfile


logger = logging.getLogger(__name__)


def with_profile(
    default_profile: str = "glove80/v25.05", profile_param_name: str = "profile"
) -> Callable[..., Any]:
    """Decorator to automatically handle profile parameter and profile creation.

    This decorator simplifies CLI commands that use keyboard profiles by:
    1. Setting a default profile if none is provided
    2. Creating the KeyboardProfile object
    3. Adding it to the kwargs as "keyboard_profile"
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
            # Find the typer.Context object from the arguments
            ctx = next((arg for arg in args if isinstance(arg, Context)), None)
            if ctx is None:
                ctx = kwargs.get("ctx")

            if not isinstance(ctx, Context):
                raise RuntimeError(
                    "This decorator requires the function to have a 'typer.Context' parameter."
                )

            # Extract the profile from kwargs
            profile_option = kwargs.get(profile_param_name)

            if profile_option is None:
                # Set default profile if none provided
                kwargs[profile_param_name] = default_profile
                # ctx.obj.keyboard_profile = create_profile_from_option(profile_option)

            try:
                # Create the profile object and add it to kwargs, and ctx.obj
                profile_obj = create_profile_from_option(kwargs[profile_param_name])

                kwargs["keyboard_profile"] = profile_obj
                ctx.obj.keyboard_profile = create_profile_from_option(profile_option)

                # Call the original function with the profile object
                return func(*args, **kwargs)
            except typer.Exit:
                # Profile creation already handled the error, just re-raise
                raise
            except Exception as e:
                logger.error(
                    f"Error with profile {kwargs.get(profile_param_name)}: {e}"
                )
                raise typer.Exit(1) from e

        return wrapper

    return decorator
