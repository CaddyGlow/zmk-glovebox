"""Utilities for standardized error handling and creation."""

import logging
from pathlib import Path
from typing import Any, Optional, TypeVar, cast

from glovebox.core.errors import (
    AdapterError,
    DockerError,
    FileSystemError,
    GloveboxError,
    TemplateError,
    USBError,
)


# Generic type var for error types that extend GloveboxError
E = TypeVar("E", bound=GloveboxError)

logger = logging.getLogger(__name__)


def create_error(
    error_class: type[E],
    message: str,
    original_error: Exception | None = None,
    context: dict[str, Any] | None = None,
) -> E:
    """Create a standardized error with context information.

    This is a generic error creation utility that can be used to create any type
    of error that extends GloveboxError.

    Args:
        error_class: The class of error to create (must extend GloveboxError)
        message: The error message
        original_error: The original exception that caused this error, if any
        context: Additional error context information

    Returns:
        An instance of the specified error class with context

    Example:
        ```python
        try:
            # Some operation that might fail
            process_data(data)
        except ValueError as e:
            error = create_error(
                ValidationError,
                "Data validation failed",
                e,
                {"data_type": type(data).__name__, "data_length": len(data)}
            )
            raise error from e
        ```
    """
    # Create the error instance
    error = error_class(message)

    # Add context if provided
    if context:
        for key, value in context.items():
            error.add_context(key, value)

    # Add original error type if provided
    if original_error:
        error.add_context("error_type", type(original_error).__name__)

    return error


def create_file_error(
    path: str | Path,
    operation: str,
    error: Exception,
    context: dict[str, Any] | None = None,
) -> FileSystemError:
    """Create a standardized FileSystemError with common context information.

    Args:
        path: The file path that was being operated on
        operation: The file operation being performed (read, write, etc.)
        error: The original exception
        context: Additional error context

    Returns:
        FileSystemError with context

    Example:
        ```python
        try:
            with open(file_path, 'r') as f:
                content = f.read()
        except FileNotFoundError as e:
            error = create_file_error(file_path, "read", e, {"encoding": "utf-8"})
            raise error from e
        ```
    """
    # Use the from_file_error class method for FileSystemError
    error_instance = FileSystemError.from_file_error(str(path), operation, error)

    # Add optional additional context
    if context:
        for key, value in context.items():
            error_instance.add_context(key, value)

    return error_instance


def create_usb_error(
    device_id: str,
    operation: str,
    error: Exception,
    context: dict[str, Any] | None = None,
) -> USBError:
    """Create a standardized USBError with common context information.

    Args:
        device_id: Device identifier or query
        operation: Operation being performed
        error: The original exception
        context: Additional error context

    Returns:
        USBError with context

    Example:
        ```python
        try:
            device = detect_device(query)
        except TimeoutError as e:
            error = create_usb_error(
                query,
                "detect_device",
                e,
                {"timeout": timeout, "initial_devices_count": len(initial_devices)}
            )
            raise error from e
        ```
    """
    error_instance = USBError.from_device_error(device_id, operation, error)

    if context:
        for key, value in context.items():
            error_instance.add_context(key, value)

    return error_instance


def create_template_error(
    template: str | Path,
    operation: str,
    error: Exception,
    context: dict[str, Any] | None = None,
) -> TemplateError:
    """Create a standardized TemplateError with common context information.

    Args:
        template: The template path or content string
        operation: The operation being performed
        error: The original exception
        context: Additional error context

    Returns:
        TemplateError with context

    Example:
        ```python
        try:
            template = env.get_template(template_path.name)
            rendered_content = template.render(context)
        except TemplateNotFound as e:
            error = create_template_error(
                template_path,
                "render_template",
                e,
                {"context_keys": list(context.keys())}
            )
            raise error from e
        ```
    """
    return TemplateError.from_template_error(template, operation, error, context)


def create_docker_error(
    message: str,
    command: str | list[str] | None = None,
    error: Exception | None = None,
    context: dict[str, Any] | None = None,
) -> DockerError:
    """Create a standardized DockerError with common context information.

    Args:
        message: The error message
        command: The Docker command that failed
        error: The original exception
        context: Additional error context

    Returns:
        DockerError with context

    Example:
        ```python
        try:
            return_code, stdout_lines, stderr_lines = stream_process.run_command(docker_cmd)
        except subprocess.SubprocessError as e:
            error = create_docker_error(
                f"Docker subprocess error: {e}",
                docker_cmd,
                e,
                {"image": image, "volumes_count": len(volumes)}
            )
            raise error from e
        ```
    """
    error_instance = DockerError(message)

    # Add command context if provided
    if command:
        import shlex

        if isinstance(command, list):
            cmd_str = " ".join(shlex.quote(str(arg)) for arg in command)
            error_instance.add_context("command", cmd_str)
        else:
            error_instance.add_context("command", command)

    # Add error type if provided
    if error:
        error_instance.add_context("error_type", type(error).__name__)

    # Add additional context
    if context:
        for key, value in context.items():
            error_instance.add_context(key, value)

    return error_instance
