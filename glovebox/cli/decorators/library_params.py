"""Decorator for automatic library reference resolution in CLI parameters."""

import functools
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import typer
from click import Context as ClickContext

from glovebox.cli.helpers.library_resolver import (
    is_library_reference,
    resolve_library_reference,
)


logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def with_library_resolution(*param_names: str) -> Callable[[F], F]:
    """Decorator that automatically resolves library references in specified parameters.

    This decorator intercepts parameters that start with @ and resolves them
    to actual file paths using the library service.

    Args:
        *param_names: Names of parameters to check for library references

    Returns:
        Decorated function with library resolution

    Example:
        @with_library_resolution("json_file", "input_file")
        def my_command(json_file: str, input_file: str):
            # json_file and input_file will be resolved if they start with @
            pass
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get the context if available
            ctx = None
            if args and isinstance(args[0], typer.Context | ClickContext):
                ctx = args[0]

            # Process each specified parameter
            for param_name in param_names:
                if param_name in kwargs:
                    value = kwargs[param_name]

                    # Skip if None or not a string
                    if value is None or not isinstance(value, str):
                        continue

                    # Check if it's a library reference
                    if is_library_reference(value):
                        try:
                            resolved_path = resolve_library_reference(value)
                            kwargs[param_name] = str(resolved_path)
                            logger.debug(
                                "Resolved library reference %s to %s",
                                value,
                                resolved_path,
                            )
                        except Exception as e:
                            # Let the error propagate with clear message
                            logger.error(
                                "Failed to resolve library reference %s: %s", value, e
                            )
                            raise typer.BadParameter(
                                f"Cannot resolve library reference '{value}': {e}"
                            ) from e

            return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def resolve_library_params(ctx: typer.Context, param_mapping: dict[str, str]) -> None:
    """Resolve library references in context parameters.

    This function modifies the context parameters in-place, resolving any
    library references to actual file paths.

    Args:
        ctx: Typer context containing parameters
        param_mapping: Mapping of parameter names to resolve

    Example:
        resolve_library_params(ctx, {"json_file": "json_file", "base_file": "base"})
    """
    if not hasattr(ctx, "params") or not ctx.params:
        return

    for _param_name, param_key in param_mapping.items():
        if param_key in ctx.params:
            value = ctx.params[param_key]

            # Skip if None or not a string
            if value is None or not isinstance(value, str):
                continue

            # Check if it's a library reference
            if is_library_reference(value):
                try:
                    resolved_path = resolve_library_reference(value)
                    ctx.params[param_key] = str(resolved_path)
                    logger.debug(
                        "Resolved library reference %s to %s in context",
                        value,
                        resolved_path,
                    )
                except Exception as e:
                    logger.error("Failed to resolve library reference %s: %s", value, e)
                    raise typer.BadParameter(
                        f"Cannot resolve library reference '{value}': {e}"
                    ) from e


def library_resolvable_callback(ctx: typer.Context, value: str | None) -> str | None:
    """Typer callback for parameters that support library resolution.

    This can be used as a callback function for Typer parameters to
    automatically resolve library references.

    Args:
        ctx: Typer context
        value: Parameter value

    Returns:
        Resolved value or original value if not a library reference
    """
    if value is None or not isinstance(value, str):
        return value

    if is_library_reference(value):
        try:
            resolved_path = resolve_library_reference(value)
            return str(resolved_path)
        except Exception as e:
            raise typer.BadParameter(
                f"Cannot resolve library reference '{value}': {e}"
            ) from e

    return value
