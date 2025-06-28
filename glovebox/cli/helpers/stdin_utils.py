"""Utilities for handling stdin input in CLI commands."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def read_input_data(input_source: str | Path | None) -> str:
    """Read input data from file path or stdin.

    Args:
        input_source: File path, '-' for stdin, or None

    Returns:
        Input data as string

    Raises:
        ValueError: If input_source is None or invalid
        FileNotFoundError: If file doesn't exist
        OSError: If file cannot be read
    """
    if input_source is None:
        msg = "Input source is required. Use file path or '-' for stdin."
        raise ValueError(msg)

    if input_source == "-":
        # Read from stdin
        return sys.stdin.read()

    # Read from file
    file_path = Path(input_source)
    if not file_path.exists():
        msg = f"Input file not found: {file_path}"
        raise FileNotFoundError(msg)

    return file_path.read_text(encoding="utf-8")


def read_json_input(input_source: str | Path | None) -> dict[str, Any]:
    """Read and parse JSON input from file path or stdin.

    Args:
        input_source: File path, '-' for stdin, or None

    Returns:
        Parsed JSON data as dictionary

    Raises:
        ValueError: If input_source is None or JSON is invalid
        FileNotFoundError: If file doesn't exist
        OSError: If file cannot be read
    """
    import json

    data_str = read_input_data(input_source)
    source_desc = "stdin" if input_source == "-" else str(input_source)

    try:
        parsed_data = json.loads(data_str)
        if not isinstance(parsed_data, dict):
            msg = f"Expected JSON object from {source_desc}, got {type(parsed_data).__name__}"
            raise ValueError(msg)
        return parsed_data
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON in {source_desc}: {e}"
        raise ValueError(msg) from e


def read_binary_input(input_source: str | Path | None) -> bytes:
    """Read binary input from file path or stdin.

    Args:
        input_source: File path, '-' for stdin, or None

    Returns:
        Input data as bytes

    Raises:
        ValueError: If input_source is None or invalid
        FileNotFoundError: If file doesn't exist
        OSError: If file cannot be read
    """
    if input_source is None:
        msg = "Input source is required. Use file path or '-' for stdin."
        raise ValueError(msg)

    if input_source == "-":
        # Read binary from stdin
        return sys.stdin.buffer.read()

    # Read from file
    file_path = Path(input_source)
    if not file_path.exists():
        msg = f"Input file not found: {file_path}"
        raise FileNotFoundError(msg)

    return file_path.read_bytes()


def is_stdin_input(input_source: str | Path | None) -> bool:
    """Check if input source represents stdin.

    Args:
        input_source: Input source to check

    Returns:
        True if input represents stdin ('-'), False otherwise
    """
    return input_source == "-"


def get_input_filename_for_templates(input_source: str | Path | None) -> str | None:
    """Get filename for template generation from input source.

    Args:
        input_source: Input source (file path, '-' for stdin, or None)

    Returns:
        Filename for template use, or None if stdin/invalid
    """
    if input_source is None or input_source == "-":
        return None

    return str(Path(input_source).name)


def resolve_input_source_with_env(
    input_source: str | Path | None, env_var_name: str
) -> str | Path | None:
    """Resolve input source with environment variable fallback.

    Args:
        input_source: Direct input source
        env_var_name: Environment variable name to check if input_source is None

    Returns:
        Resolved input source (may still be None)
    """
    import os

    if input_source is not None:
        return input_source

    env_value = os.getenv(env_var_name)
    return env_value if env_value else None
