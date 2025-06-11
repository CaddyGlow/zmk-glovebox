"""Error handling decorators for CLI commands."""

import json
import logging
import sys
import traceback
from collections.abc import Callable
from functools import wraps
from typing import Any

import typer

from glovebox.core.errors import BuildError, ConfigError, FlashError, KeymapError


__all__ = ["handle_errors", "print_stack_trace_if_verbose"]

logger = logging.getLogger(__name__)


def handle_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to handle common exceptions in CLI commands.

    This decorator catches common exceptions and provides appropriate
    error messages to the user before exiting with a non-zero status code.

    Args:
        func: The function to decorate

    Returns:
        Decorated function with error handling
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except KeymapError as e:
            logger.error(f"Keymap error: {e}")
            print_stack_trace_if_verbose()
            raise typer.Exit(1) from e
        except ConfigError as e:
            logger.error(f"Configuration error: {e}")
            print_stack_trace_if_verbose()
            raise typer.Exit(1) from e
        except BuildError as e:
            logger.error(f"Build error: {e}")
            print_stack_trace_if_verbose()
            raise typer.Exit(1) from e
        except FlashError as e:
            logger.error(f"Flash error: {e}")
            print_stack_trace_if_verbose()
            raise typer.Exit(1) from e
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            print_stack_trace_if_verbose()
            raise typer.Exit(1) from e
        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            print_stack_trace_if_verbose()
            raise typer.Exit(1) from e
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            print_stack_trace_if_verbose()
            raise typer.Exit(1) from e

    return wrapper


def print_stack_trace_if_verbose() -> None:
    """Print stack trace if verbose/debug mode is enabled."""
    # Check if we're in verbose/debug mode based on command line args
    if any(arg in sys.argv for arg in ["-v", "-vv", "--verbose", "--debug"]):
        print("\nStack trace:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
