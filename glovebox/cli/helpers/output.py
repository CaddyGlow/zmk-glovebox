"""Helper functions for CLI output formatting."""

from typing import Any, Optional

from glovebox.models.results import BaseResult


def print_success_message(message: str) -> None:
    """Print a success message with a checkmark.

    Args:
        message: The message to print
    """
    print(f"✓ {message}")


def print_error_message(message: str) -> None:
    """Print an error message with an X symbol.

    Args:
        message: The message to print
    """
    print(f"✗ {message}")


def print_list_item(item: str, indent: int = 1) -> None:
    """Print a list item with bullet and indentation.

    Args:
        item: The list item to print
        indent: Number of indentation levels (default: 1)
    """
    print(f"{' ' * (indent * 2)}• {item}")


def print_result(result: BaseResult) -> None:
    """Print operation result with appropriate formatting.

    Args:
        result: The operation result object
    """
    if result.success:
        print_success_message("Operation completed successfully")

        # Print any messages
        if hasattr(result, "messages") and result.messages:
            for message in result.messages:
                print_list_item(message)

        # Print any output files
        if hasattr(result, "get_output_files") and callable(result.get_output_files):
            output_files = result.get_output_files()
            if output_files:
                for file_type, file_path in output_files.items():
                    print_list_item(f"{file_type}: {file_path}")
    else:
        print_error_message("Operation failed")
        for error in result.errors:
            print_list_item(error)
