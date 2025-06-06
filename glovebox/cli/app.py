"""Main CLI application for Glovebox."""

import logging
import sys

# Import version from package metadata directly to avoid circular imports
from importlib.metadata import distribution
from typing import Annotated, Optional

import typer
from typer.main import get_command_from_info

from glovebox.core.logging import setup_logging


# Export setup_logging to make it available when importing from this module
__all__ = ["app", "main", "__version__", "setup_logging"]


__version__ = distribution("glovebox").version

logger = logging.getLogger(__name__)


# Context object for sharing state
class AppContext:
    """Application context for storing shared state."""

    def __init__(
        self,
        verbose: int = 0,
        log_file: str | None = None,
        config_file: str | None = None,
    ):
        """Initialize AppContext.

        Args:
            verbose: Verbosity level
            log_file: Path to log file
            config_file: Path to configuration file
        """
        self.verbose = verbose
        self.log_file = log_file
        self.config_file = config_file

        # Initialize user config with CLI-provided config file
        from glovebox.config.user_config import UserConfig

        self.user_config = UserConfig(cli_config_path=config_file)


# Create a custom exception handler that will print stack traces
def exception_callback(e: Exception) -> None:
    import traceback

    # Check if we should print full stack trace (based on verbosity)
    if "--verbose" in sys.argv or "-v" in sys.argv:
        print("\nStack trace:", file=sys.stderr)
        traceback.print_exc()
    # Note: We don't need to log here as that's done by Typer or in our other handlers


# Main app
app = typer.Typer(
    name="glovebox",
    help=f"Glovebox ZMK Keyboard Management Tool v{__version__}",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


# Global callback
@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    verbose: Annotated[
        int,
        typer.Option(
            "-v", "--verbose", count=True, help="Increase verbosity (use -v, -vv)"
        ),
    ] = 0,
    log_file: Annotated[
        str | None, typer.Option("--log-file", help="Log to file")
    ] = None,
    config_file: Annotated[
        str | None,
        typer.Option("-c", "--config", help="Path to configuration file"),
    ] = None,
    version: Annotated[
        bool, typer.Option("--version", help="Show version and exit")
    ] = False,
) -> None:
    """Glovebox ZMK Keyboard Management Tool."""
    if version:
        print(f"Glovebox v{__version__}")
        raise typer.Exit()

    # If no subcommand was invoked and version wasn't requested, show help
    if ctx.invoked_subcommand is None and not version:
        print(ctx.get_help())
        raise typer.Exit()

    # Initialize and store context
    app_context = AppContext(
        verbose=verbose, log_file=log_file, config_file=config_file
    )
    ctx.obj = app_context

    # Set log level based on verbosity or config
    log_level = logging.WARNING
    if verbose == 1:
        log_level = logging.INFO
    elif verbose >= 2:
        log_level = logging.DEBUG
    elif not verbose and log_file is None:
        # If no explicit CLI flags are set, use the config file log level
        log_level = app_context.user_config.get_log_level()

    setup_logging(level=log_level, log_file=log_file)


def main() -> int:
    """Main CLI entry point."""
    try:
        # Initialize and run the app
        from glovebox.cli.commands import register_all_commands

        register_all_commands(app)
        app()
        return 0
    except Exception as e:
        import traceback

        logger.exception(f"Unexpected error: {e}")

        # Check if we should print stack trace (verbosity level)
        if "--verbose" in sys.argv or "-v" in sys.argv:
            print("\nStack trace:", file=sys.stderr)
            traceback.print_exc()

        return 1


if __name__ == "__main__":
    sys.exit(main())
