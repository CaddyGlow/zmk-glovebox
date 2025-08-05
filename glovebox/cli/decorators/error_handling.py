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
from glovebox.core.structlog_logger import get_struct_logger


__all__ = ["handle_errors", "print_stack_trace_if_verbose"]

logger = get_struct_logger(__name__)


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
            logger.error("keymap_error", error=str(e))
            print_stack_trace_if_verbose()
            raise typer.Exit(1) from e
        except ConfigError as e:
            logger.error("configuration_error", error=str(e))
            print_stack_trace_if_verbose()
            raise typer.Exit(1) from e
        except BuildError as e:
            logger.error("build_error", error=str(e))
            print_stack_trace_if_verbose()
            raise typer.Exit(1) from e
        except FlashError as e:
            logger.error("flash_error", error=str(e))
            print_stack_trace_if_verbose()
            raise typer.Exit(1) from e
        except json.JSONDecodeError as e:
            logger.error("invalid_json", error=str(e))
            print_stack_trace_if_verbose()
            raise typer.Exit(1) from e
        except FileNotFoundError as e:
            logger.error("file_not_found", error=str(e))
            print_stack_trace_if_verbose()
            raise typer.Exit(1) from e
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("unexpected_error", error=str(e), exc_info=exc_info)
            print_stack_trace_if_verbose()
            raise typer.Exit(1) from e

    return wrapper


def print_stack_trace_if_verbose() -> None:
    """Print stack trace if verbose/debug mode is enabled."""
    # Check if we're in verbose/debug mode based on command line args
    if any(arg in sys.argv for arg in ["-v", "-vv", "--verbose", "--debug"]):
        print("\nStack trace:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
