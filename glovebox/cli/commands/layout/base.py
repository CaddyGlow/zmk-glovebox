"""Base classes for layout CLI commands."""

from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from glovebox.cli.core.command_base import IOCommand


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.layout.service import LayoutService


class BaseLayoutCommand(IOCommand):
    """Base class with common error handling patterns."""

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


class ProfileAwareLayoutCommand(BaseLayoutCommand):
    """Base class for layout commands that need keyboard profile resolution."""

    def get_keyboard_profile(
        self, ctx: typer.Context, layout_data: dict[str, Any], no_auto: bool
    ) -> "KeyboardProfile":
        """Get keyboard profile from context or auto-detect.

        Args:
            ctx: Typer context containing profile information
            layout_data: Layout data dictionary that may contain keyboard field
            no_auto: Whether to disable automatic profile detection

        Returns:
            KeyboardProfile instance

        Raises:
            typer.Exit: If no profile can be determined
        """
        from glovebox.cli.helpers.profile import get_keyboard_profile_from_context

        keyboard_profile = get_keyboard_profile_from_context(ctx)

        if keyboard_profile is None and not no_auto:
            keyboard_field = layout_data.get("keyboard")
            if keyboard_field:
                from glovebox.config import create_keyboard_profile

                keyboard_profile = create_keyboard_profile(keyboard_field)

        if keyboard_profile is None:
            self.console.print_error(
                "No keyboard profile available. Use --profile or enable auto-detection."
            )
            raise typer.Exit(1)

        return keyboard_profile

    def create_layout_service(self) -> "LayoutService":
        """Create and return layout service with all dependencies.

        Returns:
            LayoutService instance with full dependency injection
        """
        from glovebox.cli.commands.layout.dependencies import (
            create_full_layout_service,
        )

        return create_full_layout_service()

    def execute_with_profile(
        self, ctx: typer.Context, input: str, no_auto: bool, **kwargs: Any
    ) -> None:
        """Template method for profile-aware command execution.

        Args:
            ctx: Typer context
            input: Input source (file, stdin, library reference)
            no_auto: Whether to disable automatic profile detection
            **kwargs: Additional command-specific parameters
        """
        try:
            layout_data = self.load_json_input(input)
            keyboard_profile = self.get_keyboard_profile(ctx, layout_data, no_auto)
            service = self.create_layout_service()

            # Call abstract method for specific command logic
            self.execute_command(layout_data, keyboard_profile, service, **kwargs)

        except Exception as e:
            self.handle_service_error(e, self.get_operation_name())

    @abstractmethod
    def execute_command(
        self,
        layout_data: dict[str, Any],
        keyboard_profile: "KeyboardProfile",
        service: "LayoutService",
        **kwargs: Any,
    ) -> None:
        """Execute the specific command logic.

        Args:
            layout_data: Parsed layout data dictionary
            keyboard_profile: Resolved keyboard profile
            service: Layout service instance
            **kwargs: Additional command-specific parameters
        """
        pass

    @abstractmethod
    def get_operation_name(self) -> str:
        """Get the operation name for error reporting.

        Returns:
            Human-readable operation name for error messages
        """
        pass


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
