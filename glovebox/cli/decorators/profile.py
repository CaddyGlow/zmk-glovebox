"""Profile decorators for CLI commands."""

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

import typer

from glovebox.cli.helpers.profile import create_profile_from_option
from glovebox.config.profile import KeyboardProfile


logger = logging.getLogger(__name__)


def with_profile(
    default_profile: str = "glove80/default", profile_param_name: str = "profile"
) -> Callable[..., Any]:
    """Decorator to automatically handle profile parameter and profile not found errors.

    This decorator simplifies CLI commands that use keyboard profiles by:
    1. Setting a default profile if none is provided
    2. Creating the KeyboardProfile object
    3. Adding it to the kwargs as "keyboard_profile"
    4. Handling profile creation errors

    Args:
        default_profile: Default profile to use if none is provided
        profile_param_name: Name of the profile parameter in the function

    Returns:
        Decorated function with profile handling
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract the profile from kwargs
            profile_option = kwargs.get(profile_param_name)

            if profile_option is None:
                # Set default profile if none provided
                kwargs[profile_param_name] = default_profile

            try:
                # Create the profile object and add it to kwargs
                profile_obj = create_profile_from_option(kwargs[profile_param_name])
                kwargs["keyboard_profile"] = profile_obj

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
