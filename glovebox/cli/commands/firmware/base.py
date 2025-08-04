"""Base classes for firmware CLI commands."""

from pathlib import Path
from typing import Any

import typer

from glovebox.cli.core.command_base import IOCommand


class BaseFirmwareCommand(IOCommand):
    """Base class for firmware commands with common error handling patterns."""

    def print_operation_success(
        self, message: str, details: dict[str, Any] | None = None
    ) -> None:
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


class FirmwareFileCommand(BaseFirmwareCommand):
    """Base class for commands that work with firmware files."""

    def validate_firmware_file(self, file_path: Path) -> None:
        """Validate firmware file exists and has correct extension.

        Args:
            file_path: Path to firmware file

        Raises:
            typer.Exit: If validation fails
        """
        self.validate_input_file(file_path)

        if file_path.suffix.lower() not in [".uf2", ".json"]:
            self.console.print_error(
                f"Invalid firmware file extension: {file_path.suffix}"
            )
            self.console.print_info("Supported extensions: .uf2, .json")
            raise typer.Exit(1)


class FirmwareOutputCommand(BaseFirmwareCommand):
    """Base class for commands that generate firmware output."""

    def handle_firmware_result(self, result: Any, format: str = "text") -> None:
        """Handle firmware operation result with consistent formatting.

        Args:
            result: Result object from firmware service
            format: Output format (text, json)
        """
        if hasattr(result, "success") and result.success:
            if format == "json":
                self.format_and_print(result.to_dict(), "json")
            else:
                self.print_operation_success(
                    "Firmware operation completed successfully"
                )
        else:
            error_msg = "Firmware operation failed"
            if hasattr(result, "errors") and result.errors:
                error_msg += f": {'; '.join(result.errors)}"
            self.handle_service_error(ValueError(error_msg), "process firmware")
