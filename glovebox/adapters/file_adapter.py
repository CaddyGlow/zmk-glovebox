"""File adapter for abstracting file system operations."""

import json
import logging
import os
import shlex
import shutil
from pathlib import Path
from typing import Any, Optional, Protocol, runtime_checkable

from glovebox.core.errors import FileSystemError, GloveboxError
from glovebox.utils.error_utils import create_file_error
from glovebox.utils.serialization import GloveboxJSONEncoder


logger = logging.getLogger(__name__)


@runtime_checkable
class FileAdapter(Protocol):
    """Protocol for file system operations."""

    def read_text(self, path: Path, encoding: str = "utf-8") -> str:
        """Read text content from a file.

        Args:
            path: Path to the file to read
            encoding: Text encoding to use

        Returns:
            File content as string

        Raises:
            GloveboxError: If file cannot be read
        """
        ...

    def write_text(self, path: Path, content: str, encoding: str = "utf-8") -> None:
        """Write text content to a file.

        Args:
            path: Path to the file to write
            content: Text content to write
            encoding: Text encoding to use

        Raises:
            GloveboxError: If file cannot be written
        """
        ...

    def read_json(self, path: Path, encoding: str = "utf-8") -> dict[str, Any]:
        """Read and parse JSON content from a file.

        Args:
            path: Path to the JSON file to read
            encoding: Text encoding to use

        Returns:
            Parsed JSON data as dictionary

        Raises:
            GloveboxError: If file cannot be read or JSON is invalid
        """
        ...

    def write_json(
        self, path: Path, data: dict[str, Any], encoding: str = "utf-8", indent: int = 2
    ) -> None:
        """Write data as JSON to a file.

        Args:
            path: Path to the file to write
            data: Data to serialize as JSON
            encoding: Text encoding to use
            indent: JSON indentation level

        Raises:
            GloveboxError: If file cannot be written or data cannot be serialized
        """
        ...

    def exists(self, path: Path) -> bool:
        """Check if a path exists.

        Args:
            path: Path to check

        Returns:
            True if path exists, False otherwise
        """
        ...

    def is_file(self, path: Path) -> bool:
        """Check if a path is a file.

        Args:
            path: Path to check

        Returns:
            True if path is a file, False otherwise
        """
        ...

    def is_dir(self, path: Path) -> bool:
        """Check if a path is a directory.

        Args:
            path: Path to check

        Returns:
            True if path is a directory, False otherwise
        """
        ...

    def mkdir(self, path: Path, parents: bool = True, exist_ok: bool = True) -> None:
        """Create a directory.

        Args:
            path: Directory path to create
            parents: Create parent directories if they don't exist
            exist_ok: Don't raise error if directory already exists

        Raises:
            GloveboxError: If directory cannot be created
        """
        ...

    def copy_file(self, src: Path, dst: Path) -> None:
        """Copy a file from source to destination.

        Args:
            src: Source file path
            dst: Destination file path

        Raises:
            GloveboxError: If file cannot be copied
        """
        ...

    def list_files(self, path: Path, pattern: str = "*") -> list[Path]:
        """List files in a directory matching a pattern.

        Args:
            path: Directory path to search
            pattern: Glob pattern to match files

        Returns:
            List of matching file paths

        Raises:
            GloveboxError: If directory cannot be accessed
        """
        ...

    def list_directory(self, path: Path) -> list[Path]:
        """List all items in a directory.

        Args:
            path: Directory path to list

        Returns:
            List of all paths in the directory

        Raises:
            GloveboxError: If directory cannot be accessed
        """
        ...

    def check_overwrite_permission(self, files: list[Path]) -> bool:
        """Check if user permits overwriting existing files.

        Args:
            files: List of file paths to check

        Returns:
            True if overwrite is permitted, False otherwise
        """
        ...

    def remove_file(self, path: Path) -> None:
        """Remove a file.

        Args:
            path: Path to the file to remove

        Raises:
            GloveboxError: If file cannot be removed due to permissions or other errors (but not if file not found).
        """
        ...


class FileSystemAdapter:
    """File system adapter implementation."""

    def read_text(self, path: Path, encoding: str = "utf-8") -> str:
        """Read text content from a file."""
        try:
            logger.debug("Reading text file: %s", path)
            with path.open(mode="r", encoding=encoding) as f:
                content = f.read()
            logger.debug("Successfully read %d characters from %s", len(content), path)
            return content
        except FileNotFoundError as e:
            error = create_file_error(path, "read_text", e, {"encoding": encoding})
            logger.error("File not found: %s", path)
            raise error from e
        except PermissionError as e:
            error = create_file_error(path, "read_text", e, {"encoding": encoding})
            logger.error("Permission denied reading file: %s", path)
            raise error from e
        except UnicodeDecodeError as e:
            error = create_file_error(path, "read_text", e, {"encoding": encoding})
            logger.error("Encoding error reading file %s: %s", path, e)
            raise error from e
        except Exception as e:
            error = create_file_error(path, "read_text", e, {"encoding": encoding})
            logger.error("Error reading file %s: %s", path, e)
            raise error from e

    def write_text(self, path: Path, content: str, encoding: str = "utf-8") -> None:
        """Write text content to a file."""
        try:
            # Ensure parent directory exists
            self.mkdir(path.parent)

            logger.debug("Writing text file: %s", path)
            with path.open(mode="w", encoding=encoding) as f:
                f.write(content)
            logger.debug("Successfully wrote %d characters to %s", len(content), path)
        except PermissionError as e:
            error = create_file_error(
                path,
                "write_text",
                e,
                {"encoding": encoding, "content_length": len(content)},
            )
            logger.error("Permission denied writing file: %s", path)
            raise error from e
        except Exception as e:
            error = create_file_error(
                path,
                "write_text",
                e,
                {"encoding": encoding, "content_length": len(content)},
            )
            logger.error("Error writing file %s: %s", path, e)
            raise error from e

    def read_json(self, path: Path, encoding: str = "utf-8") -> dict[str, Any]:
        """Read and parse JSON content from a file."""
        try:
            logger.debug("Reading JSON file: %s", path)
            content = self.read_text(path, encoding)
            data = json.loads(content)
            logger.debug("Successfully parsed JSON from %s", path)
            return data if isinstance(data, dict) else {"data": data}
        except json.JSONDecodeError as e:
            error = create_file_error(path, "read_json", e, {"encoding": encoding})
            logger.error("Invalid JSON in file %s: %s", path, e)
            raise error from e
        except FileSystemError:
            # Let FileSystemError from read_text pass through
            raise
        except Exception as e:
            error = create_file_error(path, "read_json", e, {"encoding": encoding})
            logger.error("Error reading JSON file %s: %s", path, e)
            raise error from e

    def write_json(
        self,
        path: Path,
        data: dict[str, Any],
        encoding: str = "utf-8",
        indent: int = 2,
        encoder_cls: type[json.JSONEncoder] = GloveboxJSONEncoder,
    ) -> None:
        """Write data as JSON to a file.

        Args:
            path: Path to write the file
            data: Dictionary data to serialize
            encoding: File encoding
            indent: JSON indentation level
            encoder_cls: JSON encoder class to use for serialization
        """
        try:
            logger.debug("Writing JSON file: %s", path)
            content = json.dumps(
                data, indent=indent, ensure_ascii=False, cls=encoder_cls
            )
            self.write_text(path, content, encoding)
            logger.debug("Successfully wrote JSON to %s", path)
        except TypeError as e:
            error = create_file_error(
                path,
                "write_json",
                e,
                {
                    "encoding": encoding,
                    "indent": indent,
                    "data_type": type(data).__name__,
                },
            )
            logger.error("Cannot serialize data to JSON for file %s: %s", path, e)
            raise error from e
        except FileSystemError:
            # Let FileSystemError from write_text pass through
            raise
        except Exception as e:
            error = create_file_error(
                path,
                "write_json",
                e,
                {
                    "encoding": encoding,
                    "indent": indent,
                    "data_type": type(data).__name__,
                },
            )
            logger.error("Error writing JSON file %s: %s", path, e)
            raise error from e

    def exists(self, path: Path) -> bool:
        """Check if a path exists."""
        return path.exists()

    def is_file(self, path: Path) -> bool:
        """Check if a path is a file."""
        return path.is_file()

    def is_dir(self, path: Path) -> bool:
        """Check if a path is a directory."""
        return path.is_dir()

    def mkdir(self, path: Path, parents: bool = True, exist_ok: bool = True) -> None:
        """Create a directory."""
        try:
            logger.debug("Creating directory: %s", path)
            path.mkdir(parents=parents, exist_ok=exist_ok)
            logger.debug("Successfully created directory: %s", path)
        except PermissionError as e:
            error = create_file_error(
                path, "mkdir", e, {"parents": parents, "exist_ok": exist_ok}
            )
            logger.error("Permission denied creating directory: %s", path)
            raise error from e
        except Exception as e:
            error = create_file_error(
                path, "mkdir", e, {"parents": parents, "exist_ok": exist_ok}
            )
            logger.error("Error creating directory %s: %s", path, e)
            raise error from e

    def copy_file(self, src: Path, dst: Path) -> None:
        """Copy a file from source to destination."""
        try:
            # Ensure destination directory exists
            self.mkdir(dst.parent)

            logger.debug("Copying file: %s -> %s", src, dst)
            shutil.copy2(src, dst)
            logger.debug("Successfully copied file: %s -> %s", src, dst)
        except FileNotFoundError as e:
            error = create_file_error(
                src, "copy_file", e, {"source": str(src), "destination": str(dst)}
            )
            logger.error("Source file not found: %s", src)
            raise error from e
        except PermissionError as e:
            error = create_file_error(
                src, "copy_file", e, {"source": str(src), "destination": str(dst)}
            )
            logger.error("Permission denied copying file: %s -> %s", src, dst)
            raise error from e
        except FileSystemError:
            # Let FileSystemError from mkdir pass through
            raise
        except Exception as e:
            error = create_file_error(
                src, "copy_file", e, {"source": str(src), "destination": str(dst)}
            )
            logger.error("Error copying file %s to %s: %s", src, dst, e)
            raise error from e

    def list_files(self, path: Path, pattern: str = "*") -> list[Path]:
        """List files in a directory matching a pattern."""
        try:
            logger.debug("Listing files in %s with pattern '%s'", path, pattern)
            if not self.is_dir(path):
                error = create_file_error(
                    path,
                    "list_files",
                    ValueError("Not a directory"),
                    {"pattern": pattern},
                )
                logger.error("Path is not a directory: %s", path)
                raise error

            files = list(path.glob(pattern))
            files = [f for f in files if f.is_file()]
            logger.debug(
                "Found %d files matching pattern '%s' in %s", len(files), pattern, path
            )
            return files
        except FileSystemError:
            # Let FileSystemError pass through
            raise
        except Exception as e:
            error = create_file_error(path, "list_files", e, {"pattern": pattern})
            logger.error("Error listing files in %s: %s", path, e)
            raise error from e

    def list_directory(self, path: Path) -> list[Path]:
        """List all items in a directory."""
        try:
            logger.debug("Listing directory contents: %s", path)
            if not self.is_dir(path):
                error = create_file_error(
                    path, "list_directory", ValueError("Not a directory"), {}
                )
                logger.error("Path is not a directory: %s", path)
                raise error

            items = list(path.iterdir())
            logger.debug("Found %d items in %s", len(items), path)
            return items
        except FileSystemError:
            # Let FileSystemError pass through
            raise
        except Exception as e:
            error = create_file_error(path, "list_directory", e, {})
            logger.error("Error listing directory %s: %s", path, e)
            raise error from e

    def check_overwrite_permission(self, files: list[Path]) -> bool:
        """Check if user permits overwriting existing files."""
        existing_files = [f for f in files if self.exists(f)]
        if not existing_files:
            return True

        print("\nWarning: The following output files already exist:")
        for f in existing_files:
            print(f" - {f}")

        try:
            response = (
                input("Do you want to overwrite these files? (y/N): ").strip().lower()
            )
        except EOFError:
            print(
                "\nNon-interactive environment detected. Assuming 'No' for overwrite."
            )
            response = "n"

        if response == "y":
            logger.debug("User chose to overwrite existing files.")
            return True
        else:
            logger.warning("Operation cancelled by user (or non-interactive 'No').")
            return False

    def remove_file(self, path: Path) -> None:
        """Remove a file. Does not raise error if file not found."""
        try:
            logger.debug("Removing file: %s", path)
            # missing_ok=True ensures no FileNotFoundError is raised if the path doesn't exist.
            path.unlink(missing_ok=True)
            logger.debug("Successfully removed file (or it didn't exist): %s", path)
        except PermissionError as e:
            error = create_file_error(path, "remove_file", e, {})
            logger.error("Permission denied removing file: %s", path)
            raise error from e
        except Exception as e:
            # Catch other potential errors like IsADirectoryError
            error = create_file_error(path, "remove_file", e, {})
            logger.error("Error removing file %s: %s", path, e)
            raise error from e


def create_file_adapter() -> FileAdapter:
    """Create a file adapter with default implementation."""
    return FileSystemAdapter()
