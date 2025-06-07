"""Data models for build-related operations."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


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


@dataclass
class FirmwareOutputFiles:
    """Output files from a firmware build operation.

    Attributes:
        output_dir: Base output directory for the build
        main_uf2: Path to the main UF2 firmware file (typically glove80.uf2)
        left_uf2: Optional path to the left hand UF2 file (typically zmk.uf2 in lf directory)
        right_uf2: Optional path to the right hand UF2 file (typically zmk.uf2 in rh directory)
        artifacts_dir: Directory containing all build artifacts
    """

    output_dir: Path
    main_uf2: Path | None = None
    left_uf2: Path | None = None
    right_uf2: Path | None = None
    artifacts_dir: Path | None = None
