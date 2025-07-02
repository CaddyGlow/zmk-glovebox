"""Input handling utilities for Glovebox.

This module provides the InputHandler class for loading JSON data from various sources:
- JSON files
- stdin (using "-" convention)
- Library references (@name or @uuid)
- Environment variables
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from glovebox.core.errors import FileSystemError, GloveboxError
from glovebox.models.base import GloveboxBaseModel


logger = logging.getLogger(__name__)


class InputError(GloveboxError):
    """Exception raised for errors in input handling."""

    pass


class InputData(GloveboxBaseModel):
    """Model for input data with source metadata."""

    data: dict[str, Any]
    source: str
    source_type: str

    class Config:
        """Pydantic config."""

        extra = "allow"


class InputHandler:
    """Handles loading JSON data from various sources.

    This class provides a unified interface for loading JSON data from:
    - File paths
    - stdin (when source is "-")
    - Library references (starting with "@")
    - Environment variables

    All data is loaded into memory immediately to provide consistent behavior
    regardless of the source.
    """

    def __init__(self) -> None:
        """Initialize the InputHandler."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def load_json_input(self, source: str) -> dict[str, Any]:
        """Load JSON data from the specified source.

        Args:
            source: The source to load from. Can be:
                - A file path
                - "-" for stdin
                - "@name" or "@uuid" for library references
                - An environment variable name

        Returns:
            Dictionary containing the loaded JSON data

        Raises:
            InputError: If the source cannot be loaded or parsed
        """
        try:
            # Handle stdin
            if source == "-":
                return self._load_from_stdin()

            # Handle library references
            if source.startswith("@"):
                return self.resolve_library_reference(source)

            # Check if it's an environment variable
            if source in os.environ:
                return self.load_from_environment(source)

            # Default to file loading
            return self._load_from_file(source)

        except InputError:
            # Re-raise InputError as-is
            raise
        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to load JSON input from %s: %s", source, e, exc_info=exc_info
            )
            raise InputError(f"Failed to load JSON input from '{source}': {e}") from e

    def _load_from_file(self, file_path: str) -> dict[str, Any]:
        """Load JSON data from a file.

        Args:
            file_path: Path to the JSON file

        Returns:
            Dictionary containing the loaded JSON data

        Raises:
            InputError: If the file cannot be read or parsed
        """
        try:
            path = Path(file_path)

            if not path.exists():
                raise InputError(f"File not found: {file_path}")

            if not path.is_file():
                raise InputError(f"Not a file: {file_path}")

            with path.open("r", encoding="utf-8") as f:
                content = f.read()

            data = json.loads(content)

            # Ensure we return a dict
            if not isinstance(data, dict):
                self.logger.warning(
                    "JSON file %s contains non-dict data, wrapping in dict", file_path
                )
                data = {"data": data}

            self.logger.debug("Loaded JSON data from file: %s", file_path)
            return data

        except json.JSONDecodeError as e:
            self.logger.error("Invalid JSON in file %s: %s", file_path, e)
            raise InputError(f"Invalid JSON in file '{file_path}': {e}") from e
        except PermissionError as e:
            self.logger.error("Permission denied reading file %s", file_path)
            raise InputError(f"Permission denied reading file '{file_path}'") from e
        except OSError as e:
            self.logger.error("OS error reading file %s: %s", file_path, e)
            raise InputError(f"Error reading file '{file_path}': {e}") from e

    def _load_from_stdin(self) -> dict[str, Any]:
        """Load JSON data from stdin.

        Returns:
            Dictionary containing the loaded JSON data

        Raises:
            InputError: If stdin cannot be read or parsed
        """
        try:
            if sys.stdin.isatty():
                raise InputError("No data provided on stdin (terminal is interactive)")

            content = sys.stdin.read()

            if not content.strip():
                raise InputError("No data provided on stdin")

            data = json.loads(content)

            # Ensure we return a dict
            if not isinstance(data, dict):
                self.logger.warning(
                    "JSON from stdin contains non-dict data, wrapping in dict"
                )
                data = {"data": data}

            self.logger.debug("Loaded JSON data from stdin")
            return data

        except json.JSONDecodeError as e:
            self.logger.error("Invalid JSON from stdin: %s", e)
            raise InputError(f"Invalid JSON from stdin: {e}") from e
        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Error reading from stdin: %s", e, exc_info=exc_info)
            raise InputError(f"Error reading from stdin: {e}") from e

    def resolve_library_reference(self, ref: str) -> dict[str, Any]:
        """Resolve a library reference to JSON data.

        Library references are in the format:
        - @name: Reference by library name
        - @uuid: Reference by library UUID

        Args:
            ref: The library reference string

        Returns:
            Dictionary containing the library data

        Raises:
            InputError: If the library reference cannot be resolved
        """
        if not ref.startswith("@"):
            raise InputError(f"Invalid library reference format: {ref}")

        lib_id = ref[1:]  # Remove the @ prefix

        if not lib_id:
            raise InputError("Empty library reference")

        # TODO: Implement actual library resolution logic
        # This would typically involve:
        # 1. Checking local cache
        # 2. Querying a library service
        # 3. Downloading/loading the library data

        # For now, we'll raise a not implemented error
        raise InputError(
            f"Library reference resolution not yet implemented for '{ref}'. "
            "Please use a file path or stdin instead."
        )

    def load_from_environment(self, var_name: str) -> dict[str, Any]:
        """Load JSON data from an environment variable.

        Args:
            var_name: Name of the environment variable

        Returns:
            Dictionary containing the loaded JSON data

        Raises:
            InputError: If the environment variable cannot be read or parsed
        """
        try:
            if var_name not in os.environ:
                raise InputError(f"Environment variable not found: {var_name}")

            content = os.environ[var_name]

            if not content.strip():
                raise InputError(f"Environment variable '{var_name}' is empty")

            data = json.loads(content)

            # Ensure we return a dict
            if not isinstance(data, dict):
                self.logger.warning(
                    "JSON from environment variable %s contains non-dict data, wrapping in dict",
                    var_name,
                )
                data = {"data": data}

            self.logger.debug(
                "Loaded JSON data from environment variable: %s", var_name
            )
            return data

        except json.JSONDecodeError as e:
            self.logger.error(
                "Invalid JSON in environment variable %s: %s", var_name, e
            )
            raise InputError(
                f"Invalid JSON in environment variable '{var_name}': {e}"
            ) from e
        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Error loading from environment variable %s: %s",
                var_name,
                e,
                exc_info=exc_info,
            )
            raise InputError(
                f"Error loading from environment variable '{var_name}': {e}"
            ) from e


def create_input_handler() -> InputHandler:
    """Create an InputHandler instance.

    Factory function following CLAUDE.md patterns for creating
    InputHandler instances.

    Returns:
        InputHandler: Configured input handler instance
    """
    return InputHandler()
