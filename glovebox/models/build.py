"""Data models for build-related operations."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class OutputPaths:
    """Paths for compiled keymap output files.

    Attributes:
        keymap: Path to the .keymap file
        conf: Path to the .conf file
        json: Path to the .json file
    """

    keymap: Path
    conf: Path
    json: Path
