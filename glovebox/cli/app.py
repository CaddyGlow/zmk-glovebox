"""Main CLI application for Glovebox."""

import logging
import sys

# Import version from package metadata directly to avoid circular imports
from importlib.metadata import distribution
from typing import Annotated, Optional

import typer
from typer.main import get_command_from_info

from glovebox.cli.decorators.error_handling import print_stack_trace_if_verbose
from glovebox.config.profile import KeyboardProfile
from glovebox.core.logging import setup_logging


# Export setup_logging to make it available when importing from this module
__all__ = ["app", "main", "__version__", "setup_logging"]


__version__ = distribution("glovebox").version

logger = logging.getLogger(__name__)


# Context object for sharing state
class AppContext:
    """Application context for storing shared state."""

    keyboard_profile: KeyboardProfile | None = None

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
        from glovebox.config.user_config import create_user_config

        self.user_config = create_user_config(cli_config_path=config_file)
        self.keyboard_profile = None


# Create a custom exception handler that will print stack traces
def exception_callback(e: Exception) -> None:
    # Check if we should print full stack trace (based on verbosity)
    print_stack_trace_if_verbose()
    # Note: We don't need to log here as that's done by Typer or in our other handlers


# Main app
app = typer.Typer(
    name="glovebox",
    help=f"""Glovebox ZMK Keyboard Management Tool v{__version__}

A comprehensive tool for ZMK keyboard firmware management that transforms
keyboard layouts through a multi-stage pipeline:

Layout Editor → JSON File → ZMK Files → Firmware → Flash
  (Design)    →  (.json)  → (.keymap + .conf) → (.uf2) → (Keyboard)

Common workflows:
  • Compile layouts:  glovebox layout compile layout.json output/ --profile glove80/v25.05
  • Build firmware:   glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05
  • Flash devices:    glovebox firmware flash firmware.uf2 --profile glove80/v25.05
  • Show status:      glovebox status""",
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
            "-v",
            "--verbose",
            count=True,
            help="Increase verbosity (-v=INFO, -vv=DEBUG)",
        ),
    ] = 0,
    debug: Annotated[
        bool,
        typer.Option("--debug", help="Enable debug logging (equivalent to -vv)"),
    ] = False,
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

    # Set log level based on verbosity, debug flag, or config
    log_level = logging.WARNING
    if debug:
        log_level = logging.DEBUG
    elif verbose == 1:
        log_level = logging.INFO
    elif verbose >= 2:
        log_level = logging.DEBUG
    elif not verbose and log_file is None:
        # If no explicit CLI flags are set, use the config file log level
        log_level = app_context.user_config.get_log_level_int()

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

        # Check if we should print stack trace (verbosity level)
        print_stack_trace_if_verbose()

        return 1


if __name__ == "__main__":
    sys.exit(main())
