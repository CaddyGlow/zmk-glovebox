"""Main CLI application for Glovebox."""

import logging
import sys
from typing import TYPE_CHECKING, Annotated

import typer

from glovebox.cli.decorators.error_handling import print_stack_trace_if_verbose
from glovebox.core.logging import setup_logging, setup_logging_from_config


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile


# Export setup_logging to make it available when importing from this module
__all__ = ["app", "main", "__version__", "setup_logging"]


# Try to get version from multiple sources
try:
    from glovebox._version import __version__
except ImportError:
    try:
        from importlib.metadata import distribution

        __version__ = distribution("glovebox").version
    except Exception:
        __version__ = "unknown"

logger = logging.getLogger(__name__)


# Context object for sharing state
class AppContext:
    """Application context for storing shared state."""

    keyboard_profile: "KeyboardProfile | None" = None

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

        # Initialize SessionMetrics for prometheus_client-compatible metrics
        from glovebox.core.metrics import create_session_metrics

        # Create session metrics with cache-based storage using session UUID
        self.session_metrics = create_session_metrics(self.session_id)

        with self.session_metrics.time_operation("create_user_config"):
            self.user_config = create_user_config(cli_config_path=config_file)

        self.keyboard_profile = None

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
            # Handle both enum and string values
            if hasattr(icon_mode, "value"):
                return icon_mode.value == "emoji"
            else:
                return str(icon_mode) == "emoji"
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
            # Handle both enum and string values for compatibility
            return icon_mode.value if hasattr(icon_mode, "value") else str(icon_mode)
        else:
            # Legacy fallback
            if hasattr(self.user_config._config, "emoji_mode"):
                emoji_mode = self.user_config._config.emoji_mode
                emoji_enabled = bool(emoji_mode) if emoji_mode is not None else True
                return "emoji" if emoji_enabled else "text"

            # Default to emoji if neither field exists
            return "emoji"


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
    # Determine if CLI flags override user config
    cli_overrides = debug or verbose or log_file is not None

    if cli_overrides:
        # Use legacy setup_logging with CLI overrides
        if debug:
            log_level = logging.DEBUG
        elif verbose == 1:
            log_level = logging.INFO
        elif verbose >= 2:
            log_level = logging.DEBUG
        else:
            log_level = app_context.user_config.get_log_level_int()

        setup_logging(level=log_level, log_file=log_file)
    else:
        # Use new configuration-based logging
        setup_logging_from_config(app_context.user_config._config.logging_config)

    # Run startup checks (version updates, etc.)
    _run_startup_checks(app_context)

    # CLI session setup complete


def _run_startup_checks(app_context: AppContext) -> None:
    """Run application startup checks using the startup service."""
    try:
        from glovebox.core.startup_service import create_startup_service

        # Show early progress display if any cache-related operations might happen
        # For now, default to False - this can be made configurable later
        show_early_display = False

        if show_early_display:
            from glovebox.cli.progress.workspace import (  # type: ignore[import-untyped]
                create_early_workspace_display,
            )

            with create_early_workspace_display("Startup Checks"):
                from glovebox.cli.helpers.theme import Icons

                logger.info(
                    "%s Running startup checks...", Icons.get_icon("FIRMWARE", "text")
                )
                startup_service = create_startup_service(app_context.user_config)
                startup_service.run_startup_checks()
                logger.info(
                    "%s Startup checks completed", Icons.get_icon("SUCCESS", "text")
                )
        else:
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
        # CLI cleanup complete
        pass

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
