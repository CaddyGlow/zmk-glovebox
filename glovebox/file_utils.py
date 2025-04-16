
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def read_optional_file(file_path: Path, description: str) -> str:
    """
    Reads an optional file, logging info/warnings, and returns its content or empty string.

    Args:
        file_path: The path to the file to read.
        description: A description of the file's purpose for logging messages.

    Returns:
        The file content as a string, or an empty string if the file
        doesn't exist or cannot be read.
    """
    content = ""
    if file_path.is_file():
        logger.info(f"Reading {description} from: {file_path}")
        try:
            with open(file_path, "r") as f:
                content = f.read()
        except IOError as e:
            logger.warning(
                f"Could not read {description} file {file_path}: {e}. Proceeding without it."
            )
    else:
        logger.info(
            f"Optional {description} file not found at {file_path}. Proceeding without it."
        )
    return content
