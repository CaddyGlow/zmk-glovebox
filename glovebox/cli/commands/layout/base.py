"""Base classes for layout CLI commands."""

import logging
from pathlib import Path
from typing import Any

import typer

from glovebox.cli.core.command_base import IOCommand
from glovebox.cli.helpers.output_formatter import OutputFormatter
from glovebox.cli.helpers.theme import get_themed_console


class BaseLayoutCommand(IOCommand):
    """Base class with common error handling patterns."""

    def handle_service_error(self, error: Exception, operation: str) -> None:
        """Handle service layer errors with consistent messaging.

        Args:
            error: Exception from service layer
            operation: Operation description for error message
        """
        # CLAUDE.md pattern: debug-aware stack traces
        exc_info = self.logger.isEnabledFor(logging.DEBUG)
        self.logger.error("Failed to %s: %s", operation, error, exc_info=exc_info)
        self.console.print_error(f"Failed to {operation}: {error}")
        raise typer.Exit(1) from error

    def print_operation_success(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Print success message with operation details.

        Args:
            message: Main success message
            details: Dictionary of operation details to display
        """
        self.console.print_success(message)
        if details:
            for key, value in details.items():
                if value is not None:
                    self.console.print_info(f"{key.replace('_', ' ').title()}: {value}")


class LayoutFileCommand(BaseLayoutCommand):
    """Base class for commands that operate on layout files."""

    def validate_layout_file(self, file_path: Path) -> None:
        """Validate that a layout file exists and is readable.

        Args:
            file_path: Path to layout file to validate
        """
        if not file_path.exists():
            self.console.print_error(f"Layout file not found: {file_path}")
            raise typer.Exit(1)

        if not file_path.is_file():
            self.console.print_error(f"Path is not a file: {file_path}")
            raise typer.Exit(1)

        if file_path.suffix.lower() != ".json":
            self.console.print_error(f"Layout file must be a JSON file: {file_path}")
            raise typer.Exit(1)


class LayoutOutputCommand(LayoutFileCommand):
    """Base class for commands with formatted output options."""

    def format_output(self, data: Any, output_format: str = "text") -> None:
        """Format and output data in specified format.

        Args:
            data: Data to format and output
            output_format: Output format (text, json, table)
        """
        if output_format.lower() == "json":
            self.format_and_print(data, "json")
        elif output_format.lower() == "table" and isinstance(data, list):
            self.format_and_print(data, "table")
        else:
            # Use LayoutOutputFormatter for text output
            from glovebox.cli.commands.layout.formatters import (
                create_layout_output_formatter,
            )

            formatter = create_layout_output_formatter()
            formatter._format_text(data)
