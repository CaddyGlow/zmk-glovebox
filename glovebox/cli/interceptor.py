"""CLI command interceptor for automatic metrics tracking."""

import logging
from collections.abc import Callable
from typing import Any

import typer

from glovebox.core.logging import get_logger
from glovebox.metrics.context_extractors import extract_cli_context
from glovebox.metrics.decorators import track_operation
from glovebox.metrics.models import OperationType


logger = get_logger(__name__)


class CLICommandInterceptor:
    """Intercepts CLI commands for automatic metrics tracking."""

    def __init__(self) -> None:
        """Initialize the CLI command interceptor."""
        self.logger = get_logger(__name__)
        self._original_commands: dict[str, Callable[..., Any]] = {}

    def wrap_command(self, command_func: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap a command function with automatic metrics tracking.

        Args:
            command_func: The original command function to wrap

        Returns:
            Wrapped command function with metrics tracking
        """
        # Apply the track_operation decorator with CLI_OPERATION type
        wrapped_func = track_operation(
            OperationType.CLI_OPERATION, extract_context=extract_cli_context
        )(command_func)

        return wrapped_func

    def intercept_typer_app(self, app: typer.Typer) -> None:
        """Intercept all commands in a Typer app for automatic tracking.

        Args:
            app: The Typer app to intercept commands for
        """
        try:
            # Intercept registered commands - they are stored as lists
            if hasattr(app, "registered_commands") and app.registered_commands:
                for command in app.registered_commands:
                    if hasattr(command, "callback") and command.callback:
                        original_callback = command.callback
                        command.callback = self.wrap_command(original_callback)

            # Intercept registered groups (sub-apps) - also stored as lists
            if hasattr(app, "registered_groups") and app.registered_groups:
                for group in app.registered_groups:
                    if (
                        hasattr(group, "typer_instance")
                        and group.typer_instance is not None
                    ):
                        self.intercept_typer_app(group.typer_instance)
                    elif (
                        hasattr(group, "click_command")
                        and hasattr(group.click_command, "typer_instance")
                        and group.click_command.typer_instance is not None
                    ):
                        self.intercept_typer_app(group.click_command.typer_instance)

            self.logger.debug(
                "Successfully intercepted CLI commands for metrics tracking"
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to intercept CLI commands: %s", e, exc_info=exc_info
            )

    def setup_global_interceptor(self, app: typer.Typer) -> None:
        """Set up global command interception for the main Typer app.

        Args:
            app: The main Typer application
        """
        try:
            # Intercept the main app
            self.intercept_typer_app(app)

            self.logger.info(
                "CLI command interceptor activated for automatic metrics tracking"
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to setup global CLI interceptor: %s", e, exc_info=exc_info
            )


def create_cli_interceptor() -> CLICommandInterceptor:
    """Create a CLI command interceptor instance.

    Returns:
        Configured CLI command interceptor
    """
    return CLICommandInterceptor()
