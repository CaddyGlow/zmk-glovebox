"""Output handler for writing data to files, directories, or stdout.

This module provides a unified interface for handling output operations
with support for various formats (JSON, YAML, raw text) and destinations.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

from glovebox.core.errors import GloveboxError
from glovebox.core.structlog_logger import get_struct_logger
from glovebox.services.base_service import BaseService


class OutputError(GloveboxError):
    """Raised when output operations fail."""

    pass


class OutputHandler(BaseService):
    """Handle writing to files, directories, or stdout.

    This class provides a memory-first pattern for output operations,
    supporting various formats and destinations. All writes happen
    at the end of processing.
    """

    def __init__(self) -> None:
        """Initialize the output handler."""
        super().__init__(service_name="OutputHandler", service_version="1.0.0")

    def write_output(self, data: Any, destination: str, format: str = "json") -> None:
        """Write data to the specified destination.

        Args:
            data: The data to write
            destination: Output destination (file path, directory, or '-' for stdout)
            format: Output format ('json', 'yaml', or 'text')

        Raises:
            OutputError: If writing fails
        """
        try:
            if destination == "-":
                self.write_to_stdout(data, format)
            else:
                path = Path(destination)
                if path.suffix or not path.exists():
                    # It's a file or non-existent path (treat as file)
                    self.write_to_file(data, path, format)
                elif path.is_dir():
                    # It's a directory - data must be a dict
                    if not isinstance(data, dict):
                        raise OutputError(
                            f"Directory output requires dict data, got {type(data).__name__}"
                        )
                    self.write_to_directory(data, path)
                else:
                    raise OutputError(f"Invalid destination: {destination}")
        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to write output to %s: %s", destination, e, exc_info=exc_info
            )
            if isinstance(e, OutputError):
                raise
            raise OutputError(f"Failed to write output: {e}") from e

    def write_to_stdout(self, data: Any, format: str = "json") -> None:
        """Write data to stdout.

        Args:
            data: The data to write
            format: Output format ('json', 'yaml', or 'text')

        Raises:
            OutputError: If writing fails
        """
        try:
            if format == "json":
                output = self._format_json(data)
            elif format == "yaml":
                output = self._format_yaml(data)
            elif format == "text":
                output = self._format_text(data)
            else:
                raise OutputError(f"Unsupported format: {format}")

            sys.stdout.write(output)
            if not output.endswith("\n"):
                sys.stdout.write("\n")
            sys.stdout.flush()

            self.logger.debug("Wrote %d bytes to stdout", len(output))
        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Failed to write to stdout: %s", e, exc_info=exc_info)
            raise OutputError(f"Failed to write to stdout: {e}") from e

    def write_to_file(self, data: Any, path: Path, format: str = "json") -> None:
        """Write data to a file.

        Args:
            data: The data to write
            path: File path
            format: Output format ('json', 'yaml', or 'text')

        Raises:
            OutputError: If writing fails
        """
        try:
            # Ensure parent directory exists
            path.parent.mkdir(parents=True, exist_ok=True)

            if format == "json":
                content = self._format_json(data)
            elif format == "yaml":
                content = self._format_yaml(data)
            elif format == "text":
                content = self._format_text(data)
            else:
                raise OutputError(f"Unsupported format: {format}")

            # Write atomically
            path.write_text(content, encoding="utf-8")

            self.logger.debug("Wrote %d bytes to %s", len(content), path)
        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to write to file %s: %s", path, e, exc_info=exc_info
            )
            raise OutputError(f"Failed to write to file {path}: {e}") from e

    def write_to_directory(self, files: dict[str, Any], directory: Path) -> None:
        """Write multiple files to a directory.

        Args:
            files: Dictionary mapping relative paths to content
            directory: Target directory

        Raises:
            OutputError: If writing fails
        """
        if not isinstance(files, dict):
            raise OutputError(
                f"Expected dict for directory output, got {type(files).__name__}"
            )

        try:
            # Ensure directory exists
            directory.mkdir(parents=True, exist_ok=True)

            written_files = []
            for relative_path, content in files.items():
                file_path = directory / relative_path

                # Ensure parent directories exist
                file_path.parent.mkdir(parents=True, exist_ok=True)

                # Determine format from extension
                suffix = file_path.suffix.lower()
                if suffix in [".json"]:
                    format = "json"
                elif suffix in [".yaml", ".yml"]:
                    format = "yaml"
                else:
                    format = "text"

                self.write_to_file(content, file_path, format)
                written_files.append(str(file_path))

            self.logger.debug(
                "Wrote %d files to %s: %s",
                len(written_files),
                directory,
                ", ".join(written_files),
            )
        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to write to directory %s: %s", directory, e, exc_info=exc_info
            )
            if isinstance(e, OutputError):
                raise
            raise OutputError(f"Failed to write to directory {directory}: {e}") from e

    def _format_json(self, data: Any) -> str:
        """Format data as JSON.

        Args:
            data: Data to format

        Returns:
            JSON string

        Raises:
            OutputError: If formatting fails
        """
        try:
            # Handle Pydantic models
            if hasattr(data, "to_dict"):
                data = data.to_dict()
            elif hasattr(data, "model_dump"):
                data = data.model_dump(
                    by_alias=True, exclude_unset=True, exclude_none=True, mode="json"
                )

            return json.dumps(data, indent=2, ensure_ascii=False)
        except Exception as e:
            raise OutputError(f"Failed to format as JSON: {e}") from e

    def _format_yaml(self, data: Any) -> str:
        """Format data as YAML.

        Args:
            data: Data to format

        Returns:
            YAML string

        Raises:
            OutputError: If formatting fails
        """
        try:
            # Handle Pydantic models
            if hasattr(data, "to_dict"):
                data = data.to_dict()
            elif hasattr(data, "model_dump"):
                data = data.model_dump(
                    by_alias=True, exclude_unset=True, exclude_none=True, mode="json"
                )

            return yaml.dump(
                data, default_flow_style=False, allow_unicode=True, sort_keys=False
            )
        except Exception as e:
            raise OutputError(f"Failed to format as YAML: {e}") from e

    def _format_text(self, data: Any) -> str:
        """Format data as text.

        Args:
            data: Data to format

        Returns:
            Text string

        Raises:
            OutputError: If formatting fails
        """
        try:
            if isinstance(data, str):
                return data
            elif isinstance(data, bytes):
                return data.decode("utf-8")
            elif hasattr(data, "__str__"):
                return str(data)
            else:
                # Fallback to JSON for complex types
                return self._format_json(data)
        except Exception as e:
            raise OutputError(f"Failed to format as text: {e}") from e


def create_output_handler() -> OutputHandler:
    """Create an output handler instance.

    Returns:
        OutputHandler instance
    """
    return OutputHandler()
