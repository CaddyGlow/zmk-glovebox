"""Base command classes for Glovebox CLI infrastructure.

This module provides abstract base classes for implementing CLI commands:
- BaseCommand: Core functionality for all commands
- IOCommand: Commands with input/output operations
- ServiceCommand: Commands that use domain services
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import typer

from glovebox.cli.decorators.error_handling import handle_errors
from glovebox.cli.helpers.output_formatter import (
    OutputFormatter,
    create_output_formatter,
)
from glovebox.cli.helpers.parameter_helpers import (
    process_input_parameter,
    process_output_parameter,
    read_input_from_result,
    write_output_from_result,
)
from glovebox.cli.helpers.parameter_types import InputResult, OutputResult
from glovebox.cli.helpers.theme import ThemedConsole, get_themed_console


T = TypeVar("T")


class BaseCommand(ABC):
    """Abstract base class for all Glovebox CLI commands.

    Provides:
    - Consistent logging setup
    - Error handling patterns
    - Themed console output
    - Success/failure reporting
    """

    def __init__(self) -> None:
        """Initialize base command with logging and console."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self._console: ThemedConsole | None = None

    @property
    def console(self) -> "ThemedConsole":
        """Get themed console instance lazily."""
        if self._console is None:
            self._console = get_themed_console()
        return self._console

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

    def print_operation_success(
        self, message: str, details: dict[str, Any] | None = None
    ) -> None:
        """Print success message with optional operation details.

        Args:
            message: Main success message
            details: Dictionary of operation details to display
        """
        self.console.print_success(message)
        if details:
            for key, value in details.items():
                if value is not None:
                    self.console.print_info(f"{key.replace('_', ' ').title()}: {value}")

    def print_operation_info(self, message: str) -> None:
        """Print informational message."""
        self.console.print_info(message)

    def print_operation_warning(self, message: str) -> None:
        """Print warning message."""
        self.console.print_warning(message)

    @abstractmethod
    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the command logic.

        This method must be implemented by subclasses.
        """
        pass

    @handle_errors
    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Execute command with error handling."""
        return self.execute(*args, **kwargs)


class IOCommand(BaseCommand):
    """Base class for commands with input/output operations.

    Provides:
    - Simplified parameter handling for files and stdin/stdout
    - Automatic input resolution (file, stdin, library reference)
    - Output formatting and writing
    - JSON/text/table formatting support
    """

    def __init__(self) -> None:
        """Initialize IO command with formatter."""
        super().__init__()
        self.output_formatter = create_output_formatter()

    def load_input(
        self,
        source: str | Path | None,
        supports_stdin: bool = True,
        required: bool = True,
        allowed_extensions: list[str] | None = None,
    ) -> InputResult:
        """Load input from file path or stdin.

        Args:
            source: File path, '-' for stdin, or None
            supports_stdin: Whether to support stdin input
            required: Whether input is required
            allowed_extensions: List of allowed file extensions (e.g., ['.json'])

        Returns:
            InputResult with loaded data
        """
        import os

        import typer

        from glovebox.cli.helpers.parameter_helpers import InputResult

        resolved_path = None
        is_stdin = False
        env_fallback_used = False

        # Handle None/empty value
        if not source:
            if required:
                raise typer.BadParameter("Input is required.")
            else:
                return InputResult(raw_value=None)

        # Handle stdin input
        if supports_stdin and str(source) == "-":
            is_stdin = True
        else:
            # Handle file path
            resolved_path = Path(str(source))

            # Validate file existence
            if not resolved_path.exists():
                raise typer.BadParameter(f"Input file does not exist: {resolved_path}")

            # Validate file extension
            if allowed_extensions and resolved_path.suffix.lower() not in [
                ext.lower() for ext in allowed_extensions
            ]:
                raise typer.BadParameter(
                    f"Unsupported file extension. Allowed: {', '.join(allowed_extensions)}"
                )

        result = InputResult(
            raw_value=source,
            resolved_path=resolved_path,
            is_stdin=is_stdin,
            env_fallback_used=env_fallback_used,
        )

        # Load data if not already loaded
        if result.raw_value and result.data is None:
            result.data = read_input_from_result(result)

        return result

    def load_json_input(self, source: str | Path | None) -> dict[str, Any]:
        """Load and parse JSON input from file, stdin, or library reference.

        Args:
            source: File path, '-' for stdin, '@ref' for library, or None

        Returns:
            Parsed JSON data as dictionary

        Raises:
            ValueError: If JSON is invalid or source cannot be resolved
        """
        if source is None:
            raise ValueError("Input source is required")

        # Use InputHandler for unified input processing (supports @library refs)
        from glovebox.core.io import create_input_handler

        try:
            input_handler = create_input_handler()
            return input_handler.load_json_input(str(source))
        except Exception as e:
            # Re-raise as ValueError for consistency with existing behavior
            raise ValueError(f"Failed to load JSON input: {e}") from e

    def write_output(
        self,
        data: Any,
        destination: str | Path | None,
        format: str = "json",
        supports_stdout: bool = True,
        force_overwrite: bool = False,
        create_dirs: bool = True,
    ) -> OutputResult:
        """Write data to file or stdout with specified format.

        Args:
            data: Data to write
            destination: File path, '-' for stdout, or None
            format: Output format (json, text, table, yaml)
            supports_stdout: Whether to support stdout output
            force_overwrite: Whether to overwrite existing files
            create_dirs: Whether to create parent directories

        Returns:
            OutputResult with write details
        """
        import typer

        from glovebox.cli.helpers.parameter_helpers import OutputResult
        from glovebox.cli.helpers.theme import get_themed_console

        resolved_path = None
        is_stdout = False
        smart_default_used = False
        template_vars: dict[str, str] = {}

        # Handle stdout output
        if supports_stdout and destination == "-":
            is_stdout = True
        elif destination:
            resolved_path = Path(str(destination))

            # Create parent directories if needed
            if create_dirs and resolved_path.parent != Path():
                resolved_path.parent.mkdir(parents=True, exist_ok=True)

            # Check for existing file
            if resolved_path.exists() and not force_overwrite:
                console = get_themed_console()
                console.print_warning(f"Output file already exists: {resolved_path}")
                if not typer.confirm("Overwrite existing file?"):
                    raise typer.Abort()
        elif supports_stdout:
            # Default to stdout when no destination specified and stdout is supported
            is_stdout = True

        result = OutputResult(
            raw_value=destination,
            resolved_path=resolved_path,
            is_stdout=is_stdout,
            smart_default_used=smart_default_used,
            template_vars=template_vars,
        )

        # Format data based on requested format
        if format.lower() == "json":
            import json

            formatted = json.dumps(data, indent=2, default=str)
            write_output_from_result(result, formatted)
        elif format.lower() == "yaml":
            import yaml

            formatted = yaml.dump(data, default_flow_style=False, sort_keys=False)
            write_output_from_result(result, formatted)
        elif format.lower() == "table" and isinstance(data, list | dict):
            # For table format to stdout/file, convert to string representation
            from contextlib import redirect_stdout
            from io import StringIO

            buffer = StringIO()
            with redirect_stdout(buffer):
                self.output_formatter.print_formatted(data, "table")
            formatted = buffer.getvalue()
            write_output_from_result(result, formatted)
        else:
            # Text format or unsupported format
            if isinstance(data, str):
                write_output_from_result(result, data)
            else:
                # Convert to formatted text
                formatted = self.output_formatter.format(data, "text")
                write_output_from_result(result, formatted)

        return result

    def format_and_print(self, data: Any, format: str = "text") -> None:
        """Format and print data to console.

        Args:
            data: Data to format and print
            format: Output format (text, json, table)
        """
        self.output_formatter.print_formatted(data, format)

    def validate_input_file(self, file_path: Path) -> None:
        """Validate input file exists and is accessible.

        Args:
            file_path: Path to validate

        Raises:
            FileNotFoundError: If file does not exist
            ValueError: If path is not a file
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Input file does not exist: {file_path}")

        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")

    def validate_output_path(self, output_path: Path, force: bool = False) -> None:
        """Validate output path and handle existing files.

        Args:
            output_path: Path to validate
            force: Whether to overwrite existing files

        Raises:
            typer.Exit: If validation fails
            typer.Abort: If user cancels overwrite
        """
        if output_path.exists() and not force:
            self.console.print_warning(f"Output file already exists: {output_path}")
            if not typer.confirm("Overwrite existing file?"):
                raise typer.Abort()


class ServiceCommand(BaseCommand):
    """Base class for commands that use domain services.

    Provides:
    - Service initialization patterns
    - Common service operation patterns
    - Caching and metrics integration helpers
    """

    def __init__(self) -> None:
        """Initialize service command."""
        super().__init__()
        self._services: dict[str, Any] = {}

    def get_service(
        self, service_name: str, factory: Callable[..., T], *args: Any, **kwargs: Any
    ) -> T:
        """Get or create a service instance using factory pattern.

        Args:
            service_name: Unique name for the service
            factory: Factory function to create the service
            *args: Positional arguments for factory
            **kwargs: Keyword arguments for factory

        Returns:
            Service instance
        """
        if service_name not in self._services:
            self.logger.debug("Creating service: %s", service_name)
            self._services[service_name] = factory(*args, **kwargs)
        return self._services[service_name]  # type: ignore[no-any-return]

    def clear_services(self) -> None:
        """Clear all cached services."""
        self._services.clear()

    def with_progress(self, operation: str, total: int | None = None) -> Any:
        """Create a progress context for long-running operations.

        Args:
            operation: Description of the operation
            total: Total number of steps (if known)

        Returns:
            Progress context manager
        """
        from glovebox.cli.components import (
            create_progress_context,
            create_progress_display,
        )
        from glovebox.cli.components.progress_config import ProgressConfig

        # Create progress configuration
        config = ProgressConfig(
            operation_name=operation,
            icon_mode=self.console.icon_mode,
        )

        # Create display and context
        display = create_progress_display(config)
        return create_progress_context(display)

    def handle_cache_error(self, error: Exception, operation: str) -> None:
        """Handle cache-related errors gracefully.

        Args:
            error: Cache exception
            operation: Operation description
        """
        self.logger.warning("Cache error during %s: %s", operation, error)
        self.console.print_warning(
            f"Cache operation failed ({operation}), continuing without cache"
        )

    def get_context_value(
        self, ctx: typer.Context, key: str, default: Any = None
    ) -> Any:
        """Safely get a value from Typer context.

        Args:
            ctx: Typer context
            key: Key to retrieve
            default: Default value if not found

        Returns:
            Value from context or default
        """
        if ctx and hasattr(ctx, "obj") and ctx.obj and hasattr(ctx.obj, key):
            return getattr(ctx.obj, key)
        return default

    def require_context_value(
        self, ctx: typer.Context, key: str, error_message: str
    ) -> Any:
        """Get a required value from Typer context.

        Args:
            ctx: Typer context
            key: Key to retrieve
            error_message: Error message if not found

        Returns:
            Value from context

        Raises:
            typer.Exit: If value not found
        """
        value = self.get_context_value(ctx, key)
        if value is None:
            self.console.print_error(error_message)
            raise typer.Exit(1)
        return value
