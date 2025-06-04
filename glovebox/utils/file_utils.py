"""Utilities for file system operations."""

import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Union, cast


logger = logging.getLogger(__name__)


def prepare_output_paths(target_prefix: str) -> dict[str, Path]:
    """Prepare standardized output file paths.

    Given a target prefix (which can be a path and base name),
    generates a dictionary of standardized output paths.

    Args:
        target_prefix: Base path and name for output files

    Returns:
        Dictionary of output paths with standardized keys

    Examples:
        >>> prepare_output_paths("/tmp/my_keymap")
        {
            'keymap': PosixPath('/tmp/my_keymap.keymap'),
            'conf': PosixPath('/tmp/my_keymap.conf'),
            'json': PosixPath('/tmp/my_keymap.json')
        }
    """
    target_prefix_path = Path(target_prefix).resolve()
    output_dir = target_prefix_path.parent
    base_name = target_prefix_path.name

    return {
        "keymap": output_dir / f"{base_name}.keymap",
        "conf": output_dir / f"{base_name}.conf",
        "json": output_dir / f"{base_name}.json",
    }


def sanitize_filename(filename: str) -> str:
    """Sanitize a string for use as a filename.

    Removes or replaces characters that are invalid in filenames
    across major operating systems.

    Args:
        filename: The string to sanitize

    Returns:
        A sanitized string safe to use as a filename

    Examples:
        >>> sanitize_filename("Layer: My Layer!")
        "Layer_My_Layer_"
    """
    # Replace invalid filename characters with underscores
    safe_name = "".join(
        c if c.isalnum() or c in ["-", "_", "."] else "_" for c in filename
    )

    # Ensure the name isn't empty
    if not safe_name:
        safe_name = "unnamed"

    return safe_name


def create_timestamped_backup(file_path: Path) -> Path | None:
    """Create a timestamped backup of a file.

    If the file exists, creates a backup with the current timestamp
    appended to the filename.

    Args:
        file_path: Path to the file to back up

    Returns:
        Path to the backup file if created, None otherwise

    Examples:
        >>> create_timestamped_backup(Path("config.json"))
        PosixPath('config.json.20250601-123456.bak')
    """
    if not file_path.exists() or not file_path.is_file():
        logger.debug(f"No backup created for non-existent file: {file_path}")
        return None

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = file_path.with_suffix(f"{file_path.suffix}.{timestamp}.bak")

    try:
        shutil.copy2(file_path, backup_path)
        logger.debug(f"Created backup: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to create backup of {file_path}: {e}")
        return None


def ensure_directory_exists(path: Path) -> bool:
    """Ensure a directory exists, creating it if necessary.

    Args:
        path: The directory path to ensure exists

    Returns:
        True if the directory exists or was created successfully, False otherwise

    Examples:
        >>> ensure_directory_exists(Path("/tmp/my_project/output"))
        True
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Failed to create directory {path}: {e}")
        return False


def get_parent_directory(file_path: Path, levels_up: int = 1) -> Path:
    """Get a parent directory of a path.

    Args:
        file_path: The file or directory path
        levels_up: Number of directory levels to go up

    Returns:
        Path to the parent directory

    Raises:
        ValueError: If levels_up is less than 1

    Examples:
        >>> get_parent_directory(Path("/tmp/project/src/file.txt"), 2)
        PosixPath('/tmp/project')
    """
    if levels_up < 1:
        raise ValueError("levels_up must be at least 1")

    result = file_path.resolve()
    for _ in range(levels_up):
        result = result.parent

    return result


def find_files_by_extension(
    directory: Path, extension: str, recursive: bool = False
) -> list[Path]:
    """Find all files with a specific extension in a directory.

    Args:
        directory: The directory to search
        extension: The file extension to search for (with or without dot)
        recursive: Whether to search subdirectories recursively

    Returns:
        List of file paths matching the extension

    Examples:
        >>> find_files_by_extension(Path("/tmp/project"), ".json")
        [PosixPath('/tmp/project/config.json'), PosixPath('/tmp/project/data.json')]
    """
    if not extension.startswith("."):
        extension = f".{extension}"

    pattern = f"**/*{extension}" if recursive else f"*{extension}"

    try:
        return list(directory.glob(pattern))
    except Exception as e:
        logger.error(f"Error searching for {extension} files in {directory}: {e}")
        return []
