"""Base classes for layout CLI commands."""

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

    def handle_service_error(self, error: Exception, operation: str) -> None:
        """Handle service layer errors with consistent messaging.

        Args:
            error: Exception from service layer
            operation: Operation description for error message
        """
        print_error_message(f"Failed to {operation}: {error}")
        raise typer.Exit(1) from None

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

    def validate_layout_file(self, layout_file: Path) -> None:
        """Validate that layout file exists and is readable.

        Args:
            layout_file: Path to layout file

        Raises:
            typer.Exit: If file doesn't exist or isn't readable
        """
        if not layout_file.exists():
            print_error_message(f"Layout file not found: {layout_file}")
            raise typer.Exit(1)

        if not layout_file.is_file():
            print_error_message(f"Path is not a file: {layout_file}")
            raise typer.Exit(1)


class LayoutOutputCommand(LayoutFileCommand):
    """Base class for commands with formatted output options."""

    def __init__(self) -> None:
        self.formatter = OutputFormatter()

    def format_output(self, data: Any, output_format: str) -> None:
        """Format and print output based on format type.

        Args:
            data: Data to format and output
            output_format: Format type ('text', 'json', 'table')
        """
        if output_format.lower() == "json":
            print(self.formatter.format(data, "json"))
        elif output_format.lower() == "table":
            self.formatter.print_formatted(data, "table")
        else:
            # Default text format handled by caller
            pass

    def print_text_list(self, items: list[str], title: str | None = None) -> None:
        """Print a list of items in text format.

        Args:
            items: List of items to print
            title: Optional title for the list
        """
        if title:
            print_success_message(title)

        for item in items:
            print_list_item(item)
