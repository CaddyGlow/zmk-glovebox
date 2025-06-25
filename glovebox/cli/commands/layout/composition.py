"""Command composition helpers for layout CLI commands."""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from glovebox.cli.helpers import print_error_message

from .formatters import create_layout_output_formatter


logger = logging.getLogger(__name__)

T = TypeVar("T")


class LayoutCommandComposer:
    """Composer for layout command operations with common patterns."""

    def __init__(self) -> None:
        self.formatter = create_layout_output_formatter()

    def execute_with_error_handling(
        self,
        operation: Callable[[], T],
        operation_name: str,
        output_format: str = "text",
    ) -> T | None:
        """Execute an operation with standardized error handling.

        Args:
            operation: Operation to execute
            operation_name: Name of operation for error messages
            output_format: Output format for error reporting

        Returns:
            Operation result or None if failed
        """
        try:
            return operation()
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Failed to %s: %s", operation_name, e, exc_info=exc_info)

            if output_format.lower() == "json":
                error_result = {"error": str(e), "operation": operation_name}
                self.formatter.format_results(error_result, output_format)
            else:
                print_error_message(f"Failed to {operation_name}: {e}")
            return None

    def execute_layout_operation(
        self,
        layout_file: Path,
        operation: Callable[[Path], dict[str, Any]],
        operation_name: str,
        output_format: str = "text",
        result_title: str | None = None,
    ) -> None:
        """Execute a layout operation and format the output.

        Args:
            layout_file: Path to layout file
            operation: Operation function that takes layout file and returns results
            operation_name: Name of operation for error messages
            output_format: Output format
            result_title: Title for output (defaults to operation_name)
        """

        def execute() -> dict[str, Any]:
            return operation(layout_file)

        result = self.execute_with_error_handling(
            execute, operation_name, output_format
        )

        if result is not None:
            title = result_title or operation_name.replace("_", " ").title()
            self.formatter.format_results(result, output_format, title)

    def execute_field_operation(
        self,
        layout_file: Path,
        operation: Callable[[Path], dict[str, Any]],
        operation_name: str,
        output_format: str = "text",
    ) -> None:
        """Execute a field operation and format the output.

        Args:
            layout_file: Path to layout file
            operation: Operation function that takes layout file and returns results
            operation_name: Name of operation for error messages
            output_format: Output format
        """

        def execute() -> dict[str, Any]:
            return operation(layout_file)

        result = self.execute_with_error_handling(
            execute, operation_name, output_format
        )

        if result is not None:
            self.formatter.format_field_results(result, output_format)

    def execute_layer_operation(
        self,
        layout_file: Path,
        operation: Callable[[Path], list[str]],
        operation_name: str,
        output_format: str = "text",
    ) -> None:
        """Execute a layer operation and format the output.

        Args:
            layout_file: Path to layout file
            operation: Operation function that takes layout file and returns layer list
            operation_name: Name of operation for error messages
            output_format: Output format
        """

        def execute() -> list[str]:
            return operation(layout_file)

        result = self.execute_with_error_handling(
            execute, operation_name, output_format
        )

        if result is not None:
            self.formatter.format_layer_results(result, output_format)

    def execute_comparison_operation(
        self,
        file1: Path,
        file2: Path,
        operation: Callable[[Path, Path], dict[str, Any]],
        operation_name: str,
        output_format: str = "text",
    ) -> None:
        """Execute a comparison operation and format the output.

        Args:
            file1: First file to compare
            file2: Second file to compare
            operation: Operation function that takes two files and returns comparison results
            operation_name: Name of operation for error messages
            output_format: Output format
        """

        def execute() -> dict[str, Any]:
            return operation(file1, file2)

        result = self.execute_with_error_handling(
            execute, operation_name, output_format
        )

        if result is not None:
            self.formatter.format_comparison_results(result, output_format)

    def execute_file_operation(
        self,
        input_file: Path,
        operation: Callable[[Path], Path | None],
        operation_name: str,
        output_format: str = "text",
    ) -> None:
        """Execute a file operation and format the output.

        Args:
            input_file: Input file path
            operation: Operation function that takes input file and returns output path
            operation_name: Name of operation for error messages
            output_format: Output format
        """

        def execute() -> Path | None:
            return operation(input_file)

        output_file = self.execute_with_error_handling(
            execute, operation_name, output_format
        )

        if output_file is not None:
            self.formatter.format_file_operation_results(
                operation_name, input_file, output_file, output_format
            )

    def execute_batch_operation(
        self,
        items: list[T],
        operation: Callable[[T], dict[str, Any]],
        operation_name: str,
        output_format: str = "text",
    ) -> None:
        """Execute a batch operation on multiple items.

        Args:
            items: Items to process
            operation: Operation function to apply to each item
            operation_name: Name of operation for error messages
            output_format: Output format
        """
        results = []
        errors = []

        for item in items:
            try:
                result = operation(item)
                results.append(result)
            except Exception as e:
                exc_info = logger.isEnabledFor(logging.DEBUG)
                logger.error(
                    "Failed to %s item %s: %s",
                    operation_name,
                    item,
                    e,
                    exc_info=exc_info,
                )
                errors.append({"item": str(item), "error": str(e)})

        # Combine results
        batch_result = {
            "successful_operations": len(results),
            "failed_operations": len(errors),
            "results": results,
        }

        if errors:
            batch_result["errors"] = errors

        title = f"Batch {operation_name.replace('_', ' ').title()}"
        self.formatter.format_results(batch_result, output_format, title)


def create_layout_command_composer() -> LayoutCommandComposer:
    """Create a layout command composer instance.

    Returns:
        Configured LayoutCommandComposer instance
    """
    return LayoutCommandComposer()
