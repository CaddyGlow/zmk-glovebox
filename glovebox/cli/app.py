"""Main CLI application for Glovebox."""

import logging
import sys

# Import version from package metadata directly to avoid circular imports
from importlib.metadata import distribution
from typing import Annotated, Optional

import typer

from glovebox.core.logging import setup_logging


__version__ = distribution("glovebox").version

logger = logging.getLogger(__name__)


# Context object for sharing state
class AppContext:
    """Application context for storing shared state."""

    def __init__(self, verbose: int = 0, log_file: str | None = None):
        """Initialize AppContext.

        Args:
            verbose: Verbosity level
            log_file: Path to log file
        """
        self.verbose = verbose
        self.log_file = log_file


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

    # Store context
    ctx.ensure_object(AppContext)
    ctx.obj.verbose = verbose
    ctx.obj.log_file = log_file

    # Set log level based on verbosity
    log_level = logging.WARNING
    if verbose == 1:
        log_level = logging.INFO
    elif verbose >= 2:
        log_level = logging.DEBUG

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
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
