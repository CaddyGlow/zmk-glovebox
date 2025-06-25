"""Base classes for layout CLI commands."""

import logging
from pathlib import Path
from typing import Any

import typer

from glovebox.cli.helpers import (
    print_error_message,
    print_list_item,
    print_success_message,
)
from glovebox.cli.helpers.output_formatter import OutputFormatter


class BaseLayoutCommand:
    """Base class with common error handling patterns."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)

    def handle_service_error(self, error: Exception, operation: str) -> None:
        """Handle service layer errors with consistent messaging.

        Args:
            error: Exception from service layer
            operation: Operation description for error message
        """
        # CLAUDE.md pattern: debug-aware stack traces
        exc_info = self.logger.isEnabledFor(logging.DEBUG)
        self.logger.error("Failed to %s: %s", operation, error, exc_info=exc_info)
        print_error_message(f"Failed to {operation}: {error}")
        raise typer.Exit(1) from error

    def print_operation_success(self, message: str, details: dict[str, Any]) -> None:
        """Print success message with operation details.

        Args:
            message: Main success message
            details: Dictionary of operation details to display
        """
        print_success_message(message)
        for key, value in details.items():
            if value is not None:
                print_list_item(f"{key.replace('_', ' ').title()}: {value}")


class LayoutFileCommand(BaseLayoutCommand):
    """Base class for commands that operate on layout files."""

    def __init__(self) -> None:
        super().__init__()

    def validate_layout_file(self, file_path: Path) -> None:
        """Validate that a layout file exists and is readable.

        Args:
            file_path: Path to layout file to validate
        """
        if not file_path.exists():
            print_error_message(f"Layout file not found: {file_path}")
            raise typer.Exit(1)

        if not file_path.is_file():
            print_error_message(f"Path is not a file: {file_path}")
            raise typer.Exit(1)

        if file_path.suffix.lower() != ".json":
            print_error_message(f"Layout file must be a JSON file: {file_path}")
            raise typer.Exit(1)


class LayoutOutputCommand(LayoutFileCommand):
    """Base class for commands with formatted output options."""

    def __init__(self) -> None:
        super().__init__()
        self.formatter = OutputFormatter()

    def format_output(self, data: Any, output_format: str = "text") -> None:
        """Format and output data in specified format.

        Args:
            data: Data to format and output
            output_format: Output format (text, json, table)
        """
        if output_format.lower() == "json":
            import json

            print(json.dumps(data, indent=2, default=str))
        elif output_format.lower() == "table" and isinstance(data, list):
            self.formatter._print_list_table(data)
        else:
            # Use LayoutOutputFormatter for text output
            from glovebox.cli.commands.layout.formatters import (
                create_layout_output_formatter,
            )

            formatter = create_layout_output_formatter()
            formatter._format_text(data)
