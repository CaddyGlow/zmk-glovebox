"""Protocol definition for file system operations."""

from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class FileAdapterProtocol(Protocol):
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

    def read_binary(self, path: Path) -> bytes:
        """Read binary content from a file.

        Args:
            path: Path to the file to read

        Returns:
            File content as bytes

        Raises:
            GloveboxError: If file cannot be read
        """
        ...

    def write_binary(self, path: Path, content: bytes) -> None:
        """Write binary content to a file.

        Args:
            path: Path to the file to write
            content: Binary content to write

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

    def check_exists(self, path: Path) -> bool:
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

    def create_directory(
        self, path: Path, parents: bool = True, exist_ok: bool = True
    ) -> None:
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

    def remove_dir(self, path: Path, recursive: bool = True) -> None:
        """Remove a directory and optionally its contents.

        Args:
            path: Path to the directory to remove
            recursive: Whether to recursively remove contents (True) or only if empty (False)

        Raises:
            GloveboxError: If directory cannot be removed due to permissions or other errors.
        """
        ...

    def create_timestamped_backup(self, file_path: Path) -> Path | None:
        """Create a timestamped backup of a file.

        If the file exists, creates a backup with the current timestamp
        appended to the filename.

        Args:
            file_path: Path to the file to back up

        Returns:
            Path to the backup file if created, None otherwise
        """
        ...

    def get_file_size(self, path: Path) -> int:
        """Get file size safely with proper error handling.

        Args:
            path: Path to file

        Returns:
            int: File size in bytes

        Raises:
            GloveboxError: If file cannot be accessed or sized
        """
        ...

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize a string for use as a filename.

        Removes or replaces characters that are invalid in filenames
        across major operating systems.

        Args:
            filename: The string to sanitize

        Returns:
            A sanitized string safe to use as a filename
        """
        ...
