"""Main CLI application for Glovebox."""

import logging
import sys

# Import version from package metadata directly to avoid circular imports
from importlib.metadata import distribution
from typing import Annotated, Any

import typer

from glovebox.cli.decorators.error_handling import print_stack_trace_if_verbose
from glovebox.config.profile import KeyboardProfile
from glovebox.core.logging import setup_logging


# Export setup_logging to make it available when importing from this module
__all__ = ["app", "main", "__version__", "setup_logging"]


__version__ = distribution("glovebox").version

logger = logging.getLogger(__name__)

# Global reference to session metrics for exit code capture
_global_session_metrics = None


def _set_global_session_metrics(session_metrics: Any) -> None:
    """Set global reference to session metrics for exit code capture."""
    global _global_session_metrics
    _global_session_metrics = session_metrics


def _set_exit_code_in_session_metrics(exit_code: int) -> None:
    """Set exit code in global session metrics if available."""
    global _global_session_metrics
    if _global_session_metrics:
        try:
            _global_session_metrics.set_exit_code(exit_code)
        except Exception as e:
            logger.debug("Failed to set exit code in session metrics: %s", e)


def _set_cli_args_in_session_metrics(cli_args: list[str]) -> None:
    """Set CLI args in global session metrics if available."""
    global _global_session_metrics
    if _global_session_metrics:
        try:
            _global_session_metrics.set_cli_args(cli_args)
        except Exception as e:
            logger.debug("Failed to set CLI args in session metrics: %s", e)


# Context object for sharing state
class AppContext:
    """Application context for storing shared state."""

    keyboard_profile: KeyboardProfile | None = None

    def __init__(
        self,
        verbose: int = 0,
        log_file: str | None = None,
        config_file: str | None = None,
        no_emoji: bool = False,
    ):
        """Initialize AppContext.

        Args:
            verbose: Verbosity level
            log_file: Path to log file
            config_file: Path to configuration file
            no_emoji: Whether to disable emoji icons
        """
        import uuid

        self.verbose = verbose
        self.log_file = log_file
        self.config_file = config_file
        self.no_emoji = no_emoji
        self.session_id = str(uuid.uuid4())

        # Initialize user config with CLI-provided config file
        from glovebox.config.user_config import create_user_config

        self.user_config = create_user_config(cli_config_path=config_file)
        self.keyboard_profile = None

        # Initialize SessionMetrics for prometheus_client-compatible metrics
        from glovebox.core.metrics import create_session_metrics

        # Create session metrics with cache-based storage using session UUID
        self.session_metrics = create_session_metrics(self.session_id)

    @property
    def use_emoji(self) -> bool:
        """Get whether to use emoji based on CLI flag and config.

        CLI --no-emoji flag takes precedence over config file setting.

        Returns:
            True if emoji should be used, False otherwise
        """
        if self.no_emoji:
            # CLI flag overrides config
            return False

        # Try new icon_mode field first, fall back to emoji_mode for compatibility
        if hasattr(self.user_config._config, "icon_mode"):
            icon_mode = self.user_config._config.icon_mode
            return str(icon_mode) == "emoji" if icon_mode is not None else True
        else:
            # Legacy fallback
            if hasattr(self.user_config._config, "emoji_mode"):
                emoji_mode = self.user_config._config.emoji_mode
                return bool(emoji_mode) if emoji_mode is not None else True
            else:
                return True  # Default to True if neither field exists

    @property
    def icon_mode(self) -> str:
        """Get icon mode based on CLI flag and config.

        CLI --no-emoji flag takes precedence over config file setting.

        Returns:
            Icon mode string: "emoji", "nerdfont", or "text"
        """
        if self.no_emoji:
            # CLI flag overrides config
            return "text"

        # Try new icon_mode field first, fall back to emoji_mode for compatibility
        if hasattr(self.user_config._config, "icon_mode"):
            icon_mode = self.user_config._config.icon_mode
            return str(icon_mode) if icon_mode is not None else "emoji"
        else:
            # Legacy fallback
            if hasattr(self.user_config._config, "emoji_mode"):
                emoji_mode = self.user_config._config.emoji_mode
                emoji_enabled = bool(emoji_mode) if emoji_mode is not None else True
                return "emoji" if emoji_enabled else "text"
            else:
                return "emoji"  # Default to emoji if neither field exists

    def save_session_metrics(self) -> None:
        """Save session metrics to file."""
        if hasattr(self, "session_metrics"):
            self.session_metrics.save()


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
    no_emoji: Annotated[
        bool,
        typer.Option("--no-emoji", help="Disable emoji icons in output"),
    ] = False,
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
        verbose=verbose, log_file=log_file, config_file=config_file, no_emoji=no_emoji
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

    # Run startup checks (version updates, etc.)
    _run_startup_checks(app_context)

    # CLI session setup for metrics
    if ctx.invoked_subcommand is not None:
        # Set up auto-save for session metrics when CLI exits
        import atexit

        def save_metrics_on_exit() -> None:
            """Save session metrics when CLI exits."""
            try:
                app_context.save_session_metrics()
            except Exception as e:
                # Don't let metrics saving break CLI exit
                logger.debug("Failed to save session metrics on exit: %s", e)

        atexit.register(save_metrics_on_exit)

        # Set global reference for exit code capture
        _set_global_session_metrics(app_context.session_metrics)

        # Capture CLI args for this session
        import sys

        app_context.session_metrics.set_cli_args(sys.argv)


def _run_startup_checks(app_context: AppContext) -> None:
    """Run application startup checks using the startup service."""
    try:
        from glovebox.core.startup_service import create_startup_service

        startup_service = create_startup_service(app_context.user_config)
        startup_service.run_startup_checks()

    except Exception as e:
        # Silently fail for startup checks - don't interrupt user workflow
        logger.debug("Failed to run startup checks: %s", e)


def main() -> int:
    """Main CLI entry point."""
    exit_code = 0

    try:
        # Initialize and run the app
        from glovebox.cli.commands import register_all_commands

        register_all_commands(app)

        app()
        exit_code = 0

    except SystemExit as e:
        # Capture SystemExit code (normal CLI exit)
        exit_code = e.code if isinstance(e.code, int) else 0

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")

        # Check if we should print stack trace (verbosity level)
        print_stack_trace_if_verbose()

        exit_code = 1

    finally:
        # Set exit code in global session metrics for this session
        _set_exit_code_in_session_metrics(exit_code)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
