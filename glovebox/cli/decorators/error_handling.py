"""Error handling decorators for CLI commands."""

import json
import logging
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any

import typer

from glovebox.core.errors import BuildError, ConfigError, FlashError, KeymapError


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
            raise typer.Exit(1) from e
        except ConfigError as e:
            logger.error(f"Configuration error: {e}")
            raise typer.Exit(1) from e
        except BuildError as e:
            logger.error(f"Build error: {e}")
            raise typer.Exit(1) from e
        except FlashError as e:
            logger.error(f"Flash error: {e}")
            raise typer.Exit(1) from e
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            raise typer.Exit(1) from e
        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            raise typer.Exit(1) from e
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            raise typer.Exit(1) from e

    return wrapper
