"""Helper functions for accessing processed parameter results from context.

This module provides helper functions that work with the parameter decorators
to access processed parameter results from the typer.Context.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import typer

from glovebox.cli.helpers.output_formatter import OutputFormatter
from glovebox.cli.helpers.parameter_types import (
    FormatResult,
    InputResult,
    OutputResult,
    ValidationResult,
)
from glovebox.cli.helpers.stdin_utils import (
    is_stdin_input,
)
from glovebox.cli.helpers.theme import get_themed_console


logger = logging.getLogger(__name__)

# Context keys (must match those in parameters.py)
PARAM_INPUT_RESULT_KEY = "param_input_result"
PARAM_OUTPUT_RESULT_KEY = "param_output_result"
PARAM_FORMAT_RESULT_KEY = "param_format_result"
PARAM_FORMATTER_KEY = "param_formatter"


# =============================================================================
# Context Access Helper Functions
# =============================================================================


def get_input_result_from_context(ctx: typer.Context) -> InputResult | None:
    """Get the processed input parameter result from context."""
    if hasattr(ctx.obj, PARAM_INPUT_RESULT_KEY):
        result = getattr(ctx.obj, PARAM_INPUT_RESULT_KEY)
        return result if isinstance(result, InputResult) else None
    return None


def get_output_result_from_context(ctx: typer.Context) -> OutputResult | None:
    """Get the processed output parameter result from context."""
    if hasattr(ctx.obj, PARAM_OUTPUT_RESULT_KEY):
        result = getattr(ctx.obj, PARAM_OUTPUT_RESULT_KEY)
        return result if isinstance(result, OutputResult) else None
    return None


def get_format_result_from_context(ctx: typer.Context) -> FormatResult | None:
    """Get the processed format parameter result from context."""
    if hasattr(ctx.obj, PARAM_FORMAT_RESULT_KEY):
        result = getattr(ctx.obj, PARAM_FORMAT_RESULT_KEY)
        return result if isinstance(result, FormatResult) else None
    return None


def get_formatter_from_context(ctx: typer.Context) -> OutputFormatter | None:
    """Get the OutputFormatter instance from context."""
    if hasattr(ctx.obj, PARAM_FORMATTER_KEY):
        result = getattr(ctx.obj, PARAM_FORMATTER_KEY)
        return result if isinstance(result, OutputFormatter) else None
    return None


def get_multiple_input_results_from_context(
    ctx: typer.Context,
) -> list[InputResult] | None:
    """Get multiple processed input parameter results from context."""
    key = f"{PARAM_INPUT_RESULT_KEY}_multiple"
    if hasattr(ctx.obj, key):
        result = getattr(ctx.obj, key)
        return result if isinstance(result, list) else None
    return None


# =============================================================================
# Convenience Access Functions
# =============================================================================


def get_input_data_from_context(ctx: typer.Context) -> Any:
    """Get the input data from context (if auto-read was enabled)."""
    result = get_input_result_from_context(ctx)
    if result and result.data is not None:
        return result.data
    return None


def get_input_path_from_context(ctx: typer.Context) -> Path | None:
    """Get the resolved input file path from context."""
    result = get_input_result_from_context(ctx)
    if result:
        return result.resolved_path
    return None


def get_output_path_from_context(ctx: typer.Context) -> Path | None:
    """Get the resolved output file path from context."""
    result = get_output_result_from_context(ctx)
    if result and not result.is_stdout:
        return result.resolved_path
    return None


def is_output_stdout_from_context(ctx: typer.Context) -> bool:
    """Check if output should go to stdout."""
    result = get_output_result_from_context(ctx)
    return result.is_stdout if result else False


def get_format_type_from_context(ctx: typer.Context) -> str:
    """Get the format type from context."""
    result = get_format_result_from_context(ctx)
    return result.format_type if result else "table"


def is_json_format_from_context(ctx: typer.Context) -> bool:
    """Check if the format is JSON."""
    result = get_format_result_from_context(ctx)
    return result.is_json if result else False


# =============================================================================
# Input Processing Helper Functions
# =============================================================================


def process_input_parameter(
    value: str | Path | None,
    supports_stdin: bool = False,
    env_fallback: str | None = None,
    required: bool = True,
    validate_existence: bool = True,
    allowed_extensions: list[str] | None = None,
) -> InputResult:
    """Process an input parameter value without decorator context.

    This function can be used independently of decorators for simple input processing.
    """
    resolved_path = None
    is_stdin = False
    env_fallback_used = False

    # Handle None/empty value
    if not value:
        if env_fallback:
            env_value = os.getenv(env_fallback)
            if env_value:
                value = env_value
                env_fallback_used = True
            elif required:
                raise typer.BadParameter(
                    f"Input required. Set {env_fallback} environment variable or provide argument."
                )
        elif required:
            raise typer.BadParameter("Input file is required.")
        else:
            return InputResult(raw_value=None)

    # Handle stdin input
    if supports_stdin and is_stdin_input(str(value)):
        is_stdin = True
    else:
        # Handle file path
        resolved_path = Path(str(value))

        # Validate file existence
        if validate_existence and not resolved_path.exists():
            raise typer.BadParameter(f"Input file does not exist: {resolved_path}")

        # Validate file extension (skip for library references as they're resolved later)
        if (
            allowed_extensions
            and not str(value).startswith("@")
            and resolved_path.suffix.lower()
            not in [ext.lower() for ext in allowed_extensions]
        ):
            raise typer.BadParameter(
                f"Unsupported file extension. Allowed: {', '.join(allowed_extensions)}"
            )

    return InputResult(
        raw_value=value,
        resolved_path=resolved_path,
        is_stdin=is_stdin,
        env_fallback_used=env_fallback_used,
    )


def read_input_from_result(
    result: InputResult, as_json: bool = False, as_binary: bool = False
) -> Any:
    """Read data from an InputResult.

    Args:
        result: The InputResult to read from
        as_json: Whether to parse the content as JSON
        as_binary: Whether to read as binary data

    Returns:
        The file content as string, dict (if JSON), or bytes (if binary)
    """
    if result.data is not None:
        # Data was already read during processing
        return result.data

    if result.is_stdin:
        # Read from stdin using core IO infrastructure
        try:
            from glovebox.core.io import create_input_handler

            input_handler = create_input_handler()

            if as_json:
                return input_handler.load_json_input("-")
            elif as_binary:
                import sys

                return sys.stdin.buffer.read()
            else:
                import sys

                return sys.stdin.read()
        except Exception as e:
            logger.error("Failed to read from stdin: %s", e)
            raise typer.BadParameter(f"Failed to read from stdin: {e}") from e
    elif result.resolved_path:
        # Read from file using pathlib (CLAUDE.md requirement)
        try:
            if as_binary:
                return result.resolved_path.read_bytes()
            elif as_json:
                import json

                content = result.resolved_path.read_text(encoding="utf-8")
                parsed_data = json.loads(content)
                if not isinstance(parsed_data, dict):
                    msg = f"Expected JSON object from {result.resolved_path}, got {type(parsed_data).__name__}"
                    raise ValueError(msg)
                return parsed_data
            else:
                return result.resolved_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error("Failed to read from %s: %s", result.resolved_path, e)
            raise typer.BadParameter(
                f"Failed to read file {result.resolved_path}: {e}"
            ) from e
    else:
        raise ValueError("No valid input source in result")


# =============================================================================
# Output Processing Helper Functions
# =============================================================================


def process_output_parameter(
    value: str | Path | None,
    supports_stdout: bool = False,
    smart_default_template: str | None = None,
    template_vars: dict[str, str] | None = None,
    force_overwrite: bool = False,
    create_dirs: bool = True,
) -> OutputResult:
    """Process an output parameter value without decorator context."""
    resolved_path = None
    is_stdout = False
    smart_default_used = False
    final_template_vars = template_vars or {}

    # Handle stdout output
    if supports_stdout and value == "-":
        is_stdout = True
        return OutputResult(
            raw_value=value,
            is_stdout=True,
            template_vars=final_template_vars,
        )

    # Handle None/empty value with smart defaults
    if not value and smart_default_template:
        # Generate filename from template
        try:
            filename = smart_default_template.format(**final_template_vars)
            resolved_path = Path.cwd() / filename
            smart_default_used = True
        except KeyError as e:
            raise typer.BadParameter(f"Missing template variable: {e}") from e
    elif value:
        resolved_path = Path(str(value))

    # Validate and prepare output path
    if resolved_path:
        # Create parent directories if needed
        if create_dirs and resolved_path.parent != Path():
            resolved_path.parent.mkdir(parents=True, exist_ok=True)

        # Check for existing file
        if resolved_path.exists() and not force_overwrite:
            console = get_themed_console()
            console.print_warning(f"Output file already exists: {resolved_path}")
            if not typer.confirm("Overwrite existing file?"):
                raise typer.Abort()

    return OutputResult(
        raw_value=value,
        resolved_path=resolved_path,
        is_stdout=is_stdout,
        smart_default_used=smart_default_used,
        template_vars=final_template_vars,
    )


def write_output_from_result(
    result: OutputResult, content: str | bytes, encoding: str = "utf-8"
) -> None:
    """Write content using an OutputResult.

    Args:
        result: The OutputResult specifying where to write
        content: The content to write
        encoding: Text encoding (ignored for binary content)
    """
    if result.is_stdout:
        # Write to stdout
        if isinstance(content, bytes):
            import sys

            sys.stdout.buffer.write(content)
        else:
            print(content)
    elif result.resolved_path:
        # Write to file
        if isinstance(content, bytes):
            result.resolved_path.write_bytes(content)
        else:
            result.resolved_path.write_text(content, encoding=encoding)

        console = get_themed_console()
        console.print_success(f"Written to: {result.resolved_path}")
    else:
        raise ValueError("No valid output destination in result")


# =============================================================================
# Format Processing Helper Functions
# =============================================================================


def process_format_parameter(
    format_value: str,
    json_flag: bool = False,
    default: str = "table",
    supported_formats: list[str] | None = None,
) -> FormatResult:
    """Process a format parameter value without decorator context."""
    # Use default supported formats if none provided
    if supported_formats is None:
        supported_formats = ["table", "text", "json", "markdown", "rich-table", "yaml"]

    # Handle JSON flag override
    if json_flag:
        format_value = "json"

    # Validate format
    if format_value not in supported_formats:
        raise typer.BadParameter(
            f"Unsupported format '{format_value}'. Supported: {', '.join(supported_formats)}"
        )

    return FormatResult(
        format_type=format_value,
        is_json=(format_value == "json"),
        supports_rich=(format_value.startswith("rich-")),
        legacy_format=(format_value in ["table", "text"]),
    )


def format_and_output_data(
    data: Any,
    result: OutputResult,
    format_result: FormatResult,
    formatter: OutputFormatter | None = None,
) -> None:
    """Format data according to format result and output using output result.

    Args:
        data: The data to format and output
        result: OutputResult specifying output destination
        format_result: FormatResult specifying format options
        formatter: Optional OutputFormatter instance
    """
    from glovebox.cli.helpers.output_formatter import create_output_formatter

    if formatter is None:
        formatter = create_output_formatter()

    # Format the data
    formatted_content = formatter.format(data, format_result.format_type)

    # Output the formatted content
    write_output_from_result(result, formatted_content)


# =============================================================================
# Validation Helper Functions
# =============================================================================


def validate_input_file(
    path: Path,
    must_exist: bool = True,
    allowed_extensions: list[str] | None = None,
    max_size_mb: float | None = None,
) -> ValidationResult:
    """Validate an input file."""
    warnings: list[str] = []
    suggestions: list[str] = []

    # Check existence
    if must_exist and not path.exists():
        return ValidationResult(
            is_valid=False,
            error_message=f"Input file does not exist: {path}",
            suggestions=["Check the file path", "Ensure the file exists"],
        )

    # Check if it's a file (not directory)
    if path.exists() and not path.is_file():
        return ValidationResult(
            is_valid=False,
            error_message=f"Path is not a file: {path}",
        )

    # Check file extension
    if allowed_extensions and path.suffix.lower() not in [
        ext.lower() for ext in allowed_extensions
    ]:
        return ValidationResult(
            is_valid=False,
            error_message=f"Unsupported file extension '{path.suffix}'",
            suggestions=[f"Supported extensions: {', '.join(allowed_extensions)}"],
        )

    # Check file size
    if max_size_mb and path.exists():
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > max_size_mb:
            warnings.append(f"Large file detected: {size_mb:.1f}MB")
            if size_mb > max_size_mb * 2:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"File too large: {size_mb:.1f}MB (max: {max_size_mb}MB)",
                )

    return ValidationResult(
        is_valid=True,
        warnings=warnings,
        suggestions=suggestions,
    )


def validate_output_path(
    path: Path,
    force_overwrite: bool = False,
    create_dirs: bool = True,
    check_permissions: bool = True,
) -> ValidationResult:
    """Validate an output path."""
    warnings = []
    suggestions = []

    # Check if file already exists
    if path.exists() and not force_overwrite:
        warnings.append(f"Output file already exists: {path}")
        suggestions.append("Use --force to overwrite or choose a different filename")

    # Check parent directory
    parent = path.parent
    if not parent.exists():
        if create_dirs:
            try:
                parent.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Cannot create parent directory: {parent} (permission denied)",
                )
            except Exception as e:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Cannot create parent directory: {parent} ({e})",
                )
        else:
            return ValidationResult(
                is_valid=False,
                error_message=f"Parent directory does not exist: {parent}",
                suggestions=[
                    "Create the directory manually",
                    "Use --create-dirs option",
                ],
            )

    # Check write permissions
    if check_permissions:
        try:
            # Test write permission by creating a temporary file
            test_file = parent / f".glovebox_write_test_{os.getpid()}"
            test_file.touch()
            test_file.unlink()
        except PermissionError:
            return ValidationResult(
                is_valid=False,
                error_message=f"No write permission in directory: {parent}",
            )
        except Exception as e:
            warnings.append(f"Could not verify write permissions: {e}")

    return ValidationResult(
        is_valid=True,
        warnings=warnings,
        suggestions=suggestions,
    )


def resolve_firmware_input_file(
    input_file: str | Path | None,
    env_var: str = "GLOVEBOX_JSON_FILE",
    allowed_extensions: list[str] | None = None,
) -> Path | None:
    """Resolve input file path for firmware commands.

    Handles both JSON layout files and keymap files, with environment variable
    fallback for JSON files only.

    Args:
        input_file: Input file path from CLI argument
        env_var: Environment variable to check for JSON files
        allowed_extensions: List of allowed file extensions (e.g., [".json", ".keymap"])

    Returns:
        Resolved Path object or None if not found

    Raises:
        FileNotFoundError: If the specified file doesn't exist
        ValueError: If the file extension is not allowed
    """
    if allowed_extensions is None:
        allowed_extensions = [".json", ".keymap"]

    # If no input file provided, check environment variable (JSON only)
    if input_file is None:
        env_value = os.environ.get(env_var)
        if env_value:
            input_file = env_value
            logger.debug("Using %s environment variable: %s", env_var, input_file)
        else:
            return None

    # Handle library references
    if isinstance(input_file, str) and input_file.startswith("@"):
        from glovebox.cli.helpers.library_resolver import resolve_library_reference

        try:
            resolved_path = resolve_library_reference(input_file)
        except ValueError as e:
            raise FileNotFoundError(f"Could not resolve library reference: {e}") from e
    else:
        # Convert to Path and resolve
        resolved_path = Path(input_file).resolve()

    # Check if file exists
    if not resolved_path.exists():
        raise FileNotFoundError(f"Input file not found: {resolved_path}")

    # Check file extension
    if resolved_path.suffix.lower() not in allowed_extensions:
        raise ValueError(
            f"Invalid file type: {resolved_path.suffix}. "
            f"Allowed extensions: {', '.join(allowed_extensions)}"
        )

    return resolved_path
