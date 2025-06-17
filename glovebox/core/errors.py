from pathlib import Path


class GloveboxError(Exception):
    """Base exception for all Glovebox errors."""

    def __init__(self, message: str, context: dict[str, object] | None = None):
        """Initialize exception with message and optional context.

        Args:
            message: Error message
            context: Optional dictionary with additional error context data
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def add_context(self, key: str, value: object) -> None:
        """Add additional context to the error."""
        self.context[key] = value

    def __str__(self) -> str:
        """Return string representation of the error."""
        if not self.context:
            return self.message

        context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
        return f"{self.message} [context: {context_str}]"


# Service layer errors


class KeymapError(GloveboxError):
    """Exception raised for errors in keymap operations."""

    pass


class LayoutError(GloveboxError):
    """Exception raised for errors in layout operations."""

    pass


class CompilationError(GloveboxError):
    """Exception raised for errors in compilation operations."""

    pass


class BuildError(GloveboxError):
    """Exception raised for errors in firmware building."""

    pass


class FlashError(GloveboxError):
    """Exception raised for errors in firmware flashing."""

    pass


class ConfigError(GloveboxError):
    """Exception raised for errors in configuration handling."""

    pass


class ConfigurationError(ConfigError):
    """Exception raised for configuration errors."""

    pass


class ProfileNotFoundError(ConfigError):
    """Exception raised when a profile is not found."""

    pass


class InvalidProfileError(ConfigError):
    """Exception raised when a profile is invalid."""

    pass


# Adapter layer errors


class AdapterError(GloveboxError):
    """Base exception for all adapter-related errors."""

    pass


class DockerError(AdapterError):
    """Exception raised for errors in Docker operations."""

    pass


class FileSystemError(AdapterError):
    """Exception raised for errors in file system operations."""

    @classmethod
    def from_file_error(
        cls, path: str, operation: str, original_error: Exception
    ) -> "FileSystemError":
        """Create a FileSystemError from a file operation error.

        Args:
            path: File path that caused the error
            operation: Operation being performed (read, write, etc.)
            original_error: Original exception that was raised

        Returns:
            FileSystemError with context about the file operation
        """
        error = cls(
            f"File operation '{operation}' failed on '{path}': {original_error}"
        )
        error.add_context("path", path)
        error.add_context("operation", operation)
        error.add_context("error_type", type(original_error).__name__)
        return error


class TemplateError(AdapterError):
    """Exception raised for errors in template operations."""

    @classmethod
    def from_template_error(
        cls,
        template: str | Path,
        operation: str,
        original_error: Exception,
        context: dict[str, object] | None = None,
    ) -> "TemplateError":
        """Create a TemplateError from a template operation error.

        Args:
            template: Template path or content that caused the error
            operation: Operation being performed (render, parse, etc.)
            original_error: Original exception that was raised
            context: Additional context data

        Returns:
            TemplateError with context about the template operation
        """
        template_id = (
            str(template)
            if isinstance(template, Path)
            else f"<template string: {len(template)} chars>"
        )
        error = cls(
            f"Template operation '{operation}' failed on '{template_id}': {original_error}"
        )
        error.add_context("template", template_id)
        error.add_context("operation", operation)
        error.add_context("error_type", type(original_error).__name__)

        if context:
            for key, value in context.items():
                error.add_context(key, value)

        return error


class USBError(AdapterError):
    """Exception raised for errors in USB device operations."""

    @classmethod
    def from_device_error(
        cls, device_id: str, operation: str, original_error: Exception
    ) -> "USBError":
        """Create a USBError from a device operation error.

        Args:
            device_id: Device identifier
            operation: Operation being performed (detect, flash, etc.)
            original_error: Original exception that was raised

        Returns:
            USBError with context about the device operation
        """
        error = cls(
            f"USB device operation '{operation}' failed on '{device_id}': {original_error}"
        )
        error.add_context("device_id", device_id)
        error.add_context("operation", operation)
        error.add_context("error_type", type(original_error).__name__)
        return error
