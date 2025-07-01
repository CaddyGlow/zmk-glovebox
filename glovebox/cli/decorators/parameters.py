"""Parameter processing decorators for CLI commands.

This module provides decorators that automatically process common parameter patterns,
reducing code duplication and ensuring consistent behavior across CLI commands.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar

import typer
from click import Context as ClickContext

from glovebox.cli.helpers.output_formatter import (
    OutputFormatter,
    create_output_formatter,
)
from glovebox.cli.helpers.parameter_types import (
    FormatResult,
    InputResult,
    OutputResult,
    ValidationResult,
)
from glovebox.cli.helpers.stdin_utils import (
    is_stdin_input,
    read_input_data,
    read_json_input,
)
from glovebox.cli.helpers.theme import get_themed_console


# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


logger = logging.getLogger(__name__)


# =============================================================================
# Context Keys for Parameter Results
# =============================================================================

PARAM_INPUT_RESULT_KEY = "param_input_result"
PARAM_OUTPUT_RESULT_KEY = "param_output_result"
PARAM_FORMAT_RESULT_KEY = "param_format_result"
PARAM_FORMATTER_KEY = "param_formatter"


# =============================================================================
# Input Parameter Decorators
# =============================================================================


def with_input_file(
    param_name: str = "input_file",
    supports_stdin: bool = False,
    env_fallback: str | None = None,
    required: bool = True,
    auto_read: bool = False,
    read_as_json: bool = False,
) -> Callable[[F], F]:
    """Decorator for processing input file parameters.

    Args:
        param_name: Name of the parameter to process
        supports_stdin: Whether to support '-' for stdin input
        env_fallback: Environment variable name for fallback value
        required: Whether the input is required
        auto_read: Whether to automatically read file contents
        read_as_json: Whether to parse content as JSON (requires auto_read=True)
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            ctx = _get_context_from_args(args, kwargs)
            if not ctx:
                return func(*args, **kwargs)

            # Get the raw parameter value
            raw_value = kwargs.get(param_name)

            try:
                # Process the input parameter
                result = _process_input_parameter(
                    raw_value=raw_value,
                    supports_stdin=supports_stdin,
                    env_fallback=env_fallback,
                    required=required,
                    auto_read=auto_read,
                    read_as_json=read_as_json,
                )

                # Store result in context for helper functions
                ctx.obj.setattr(PARAM_INPUT_RESULT_KEY, result)

                return func(*args, **kwargs)

            except Exception as e:
                exc_info = logger.isEnabledFor(logging.DEBUG)
                logger.error(
                    "Input parameter processing failed: %s", e, exc_info=exc_info
                )
                raise typer.Exit(1) from e

        return wrapper  # type: ignore[return-value]

    return decorator


def with_multiple_input_files(
    param_name: str = "input_files",
    validate_existence: bool = True,
    allowed_extensions: list[str] | None = None,
) -> Callable[[F], F]:
    """Decorator for processing multiple input file parameters."""

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            ctx = _get_context_from_args(args, kwargs)
            if not ctx:
                return func(*args, **kwargs)

            raw_value = kwargs.get(param_name, [])

            try:
                results = []
                for file_path in raw_value:
                    result = _process_input_parameter(
                        raw_value=file_path,
                        supports_stdin=False,
                        required=True,
                        validate_existence=validate_existence,
                        allowed_extensions=allowed_extensions,
                    )
                    results.append(result)

                ctx.obj.setattr(f"{PARAM_INPUT_RESULT_KEY}_multiple", results)
                return func(*args, **kwargs)

            except Exception as e:
                exc_info = logger.isEnabledFor(logging.DEBUG)
                logger.error(
                    "Multiple input parameter processing failed: %s",
                    e,
                    exc_info=exc_info,
                )
                raise typer.Exit(1) from e

        return wrapper  # type: ignore[return-value]

    return decorator


# =============================================================================
# Output Parameter Decorators
# =============================================================================


def with_output_file(
    param_name: str = "output",
    supports_stdout: bool = False,
    smart_defaults: bool = False,
    force_param: str = "force",
    create_dirs: bool = True,
    backup_existing: bool = False,
) -> Callable[[F], F]:
    """Decorator for processing output file parameters.

    Args:
        param_name: Name of the parameter to process
        supports_stdout: Whether to support '-' for stdout output
        smart_defaults: Whether to generate smart default filenames
        force_param: Name of the force overwrite parameter
        create_dirs: Whether to create parent directories
        backup_existing: Whether to backup existing files
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            ctx = _get_context_from_args(args, kwargs)
            if not ctx:
                return func(*args, **kwargs)

            raw_value = kwargs.get(param_name)
            force_overwrite = kwargs.get(force_param, False)

            try:
                result = _process_output_parameter(
                    raw_value=raw_value,
                    supports_stdout=supports_stdout,
                    smart_defaults=smart_defaults,
                    force_overwrite=force_overwrite,
                    create_dirs=create_dirs,
                    backup_existing=backup_existing,
                    ctx=ctx,
                )

                ctx.obj.setattr(PARAM_OUTPUT_RESULT_KEY, result)
                return func(*args, **kwargs)

            except Exception as e:
                exc_info = logger.isEnabledFor(logging.DEBUG)
                logger.error(
                    "Output parameter processing failed: %s", e, exc_info=exc_info
                )
                raise typer.Exit(1) from e

        return wrapper  # type: ignore[return-value]

    return decorator


def with_output_directory(
    param_name: str = "output_dir",
    create_dirs: bool = True,
    force_param: str = "force",
) -> Callable[[F], F]:
    """Decorator for processing output directory parameters."""

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            ctx = _get_context_from_args(args, kwargs)
            if not ctx:
                return func(*args, **kwargs)

            raw_value = kwargs.get(param_name)
            force_overwrite = kwargs.get(force_param, False)

            try:
                if raw_value:
                    output_dir = Path(raw_value)
                    if create_dirs:
                        output_dir.mkdir(parents=True, exist_ok=True)
                    elif not output_dir.exists():
                        raise typer.BadParameter(
                            f"Output directory does not exist: {output_dir}"
                        )

                    result = OutputResult(
                        raw_value=raw_value,
                        resolved_path=output_dir,
                    )
                else:
                    result = OutputResult(raw_value=None, resolved_path=Path.cwd())

                ctx.obj.setattr(PARAM_OUTPUT_RESULT_KEY, result)
                return func(*args, **kwargs)

            except Exception as e:
                exc_info = logger.isEnabledFor(logging.DEBUG)
                logger.error(
                    "Output directory parameter processing failed: %s",
                    e,
                    exc_info=exc_info,
                )
                raise typer.Exit(1) from e

        return wrapper  # type: ignore[return-value]

    return decorator


# =============================================================================
# Format Parameter Decorators
# =============================================================================


def with_format(
    format_param: str = "output_format",
    json_param: str | None = None,
    default: str = "table",
    supported_formats: list[str] | None = None,
    create_formatter: bool = True,
) -> Callable[[F], F]:
    """Decorator for processing format parameters.

    Args:
        format_param: Name of the format parameter
        json_param: Name of the JSON boolean parameter (if any)
        default: Default format if none specified
        supported_formats: List of supported format strings
        create_formatter: Whether to create an OutputFormatter instance
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            ctx = _get_context_from_args(args, kwargs)
            if not ctx:
                return func(*args, **kwargs)

            try:
                # Get format values
                format_value = kwargs.get(format_param, default)
                json_flag = kwargs.get(json_param, False) if json_param else False

                # Process format parameter
                result = _process_format_parameter(
                    format_value=format_value,
                    json_flag=json_flag,
                    default=default,
                    supported_formats=supported_formats,
                )

                # Create formatter if requested
                if create_formatter:
                    formatter = create_output_formatter()
                    ctx.obj.setattr(PARAM_FORMATTER_KEY, formatter)

                ctx.obj.setattr(PARAM_FORMAT_RESULT_KEY, result)
                return func(*args, **kwargs)

            except Exception as e:
                exc_info = logger.isEnabledFor(logging.DEBUG)
                logger.error(
                    "Format parameter processing failed: %s", e, exc_info=exc_info
                )
                raise typer.Exit(1) from e

        return wrapper  # type: ignore[return-value]

    return decorator


# =============================================================================
# Combined Parameter Decorators
# =============================================================================


def with_input_output(
    input_param: str = "input_file",
    output_param: str = "output",
    supports_stdin: bool = True,
    supports_stdout: bool = True,
    env_fallback: str | None = "GLOVEBOX_JSON_FILE",
    smart_defaults: bool = True,
    auto_read: bool = False,
    read_as_json: bool = False,
) -> Callable[[F], F]:
    """Decorator combining input and output parameter processing."""

    def decorator(func: F) -> F:
        # Apply decorators in order
        func = with_output_file(
            param_name=output_param,
            supports_stdout=supports_stdout,
            smart_defaults=smart_defaults,
        )(func)

        func = with_input_file(
            param_name=input_param,
            supports_stdin=supports_stdin,
            env_fallback=env_fallback,
            auto_read=auto_read,
            read_as_json=read_as_json,
        )(func)

        return func

    return decorator


def with_input_output_format(
    input_param: str = "input_file",
    output_param: str = "output",
    format_param: str = "output_format",
    json_param: str | None = None,
    supports_stdin: bool = True,
    supports_stdout: bool = True,
    default_format: str = "table",
) -> Callable[[F], F]:
    """Decorator combining input, output, and format parameter processing."""

    def decorator(func: F) -> F:
        # Apply decorators in order
        func = with_format(
            format_param=format_param,
            json_param=json_param,
            default=default_format,
        )(func)

        func = with_input_output(
            input_param=input_param,
            output_param=output_param,
            supports_stdin=supports_stdin,
            supports_stdout=supports_stdout,
        )(func)

        return func

    return decorator


# =============================================================================
# Helper Functions for Parameter Processing
# =============================================================================


def _get_context_from_args(
    args: tuple[Any, ...], kwargs: dict[str, Any]
) -> typer.Context | ClickContext | None:
    """Extract typer.Context or click.Context from function arguments."""
    # Look for Context in args
    for arg in args:
        if isinstance(arg, (typer.Context, ClickContext)):
            return arg

    # Look for Context in kwargs
    ctx = kwargs.get("ctx")
    if isinstance(ctx, (typer.Context, ClickContext)):
        return ctx

    return None


def _process_input_parameter(
    raw_value: str | Path | None,
    supports_stdin: bool = False,
    env_fallback: str | None = None,
    required: bool = True,
    auto_read: bool = False,
    read_as_json: bool = False,
    validate_existence: bool = True,
    allowed_extensions: list[str] | None = None,
) -> InputResult:
    """Process an input parameter value."""
    resolved_path = None
    is_stdin = False
    env_fallback_used = False
    data: dict[str, Any] | str | None = None

    # Handle None/empty value
    if not raw_value:
        if env_fallback:
            env_value = os.getenv(env_fallback)
            if env_value:
                raw_value = env_value
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
    if supports_stdin and is_stdin_input(str(raw_value)):
        is_stdin = True
        if auto_read:
            try:
                if read_as_json:
                    data = read_json_input(str(raw_value))
                else:
                    data = read_input_data(str(raw_value))
            except Exception as e:
                raise typer.BadParameter(f"Failed to read from stdin: {e}") from e
    else:
        # Handle file path
        resolved_path = Path(str(raw_value))

        # Validate file existence
        if validate_existence and not resolved_path.exists():
            raise typer.BadParameter(f"Input file does not exist: {resolved_path}")

        # Validate file extension
        if allowed_extensions and resolved_path.suffix.lower() not in [
            ext.lower() for ext in allowed_extensions
        ]:
            raise typer.BadParameter(
                f"Unsupported file extension. Allowed: {', '.join(allowed_extensions)}"
            )

        # Auto-read file content
        if auto_read and resolved_path.exists():
            try:
                if read_as_json:
                    data = read_json_input(str(resolved_path))
                else:
                    data = read_input_data(str(resolved_path))
            except Exception as e:
                raise typer.BadParameter(
                    f"Failed to read file {resolved_path}: {e}"
                ) from e

    return InputResult(
        raw_value=raw_value,
        resolved_path=resolved_path,
        is_stdin=is_stdin,
        env_fallback_used=env_fallback_used,
        data=data,
    )


def _process_output_parameter(
    raw_value: str | Path | None,
    supports_stdout: bool = False,
    smart_defaults: bool = False,
    force_overwrite: bool = False,
    create_dirs: bool = True,
    backup_existing: bool = False,
    ctx: typer.Context | None = None,
) -> OutputResult:
    """Process an output parameter value."""
    resolved_path = None
    is_stdout = False
    smart_default_used = False
    template_vars: dict[str, str] = {}

    # Handle stdout output
    if supports_stdout and raw_value == "-":
        is_stdout = True
        return OutputResult(
            raw_value=raw_value,
            is_stdout=True,
        )

    # Handle None/empty value with smart defaults
    if not raw_value and smart_defaults:
        # Generate smart default filename
        # This would use context information to create meaningful defaults
        smart_default_used = True
        # For now, use a simple default - this could be enhanced
        resolved_path = Path.cwd() / "output.txt"
    elif raw_value:
        resolved_path = Path(str(raw_value))

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

        # Create backup if requested
        if backup_existing and resolved_path.exists():
            backup_path = resolved_path.with_suffix(f"{resolved_path.suffix}.backup")
            backup_path.write_bytes(resolved_path.read_bytes())
            logger.info("Created backup: %s", backup_path)

    return OutputResult(
        raw_value=raw_value,
        resolved_path=resolved_path,
        is_stdout=is_stdout,
        smart_default_used=smart_default_used,
        template_vars=template_vars,
    )


def _process_format_parameter(
    format_value: str,
    json_flag: bool = False,
    default: str = "table",
    supported_formats: list[str] | None = None,
) -> FormatResult:
    """Process a format parameter value."""
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
