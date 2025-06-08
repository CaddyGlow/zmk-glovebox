"""Firmware domain models."""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


logger = logging.getLogger(__name__)


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


class BuildResult(BaseModel):
    """Result of firmware build operations."""

    success: bool
    timestamp: datetime = Field(default_factory=datetime.now)
    messages: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    output_files: FirmwareOutputFiles | None = None
    build_id: str | None = None
    build_time_seconds: float | None = None

    @field_validator("build_time_seconds")
    @classmethod
    def validate_build_time(cls, v: float | None) -> float | None:
        """Validate build time is positive if provided."""
        if v is not None and (not isinstance(v, int | float) or v < 0):
            raise ValueError("Build time must be a non-negative number") from None
        return float(v) if v is not None else None

    @field_validator("build_id")
    @classmethod
    def validate_build_id(cls, v: str | None) -> str | None:
        """Validate build ID format if provided."""
        if v is not None and (not isinstance(v, str) or not v.strip()):
            raise ValueError("Build ID must be a non-empty string") from None
        return v

    def add_message(self, message: str) -> None:
        """Add an informational message."""
        if not isinstance(message, str):
            raise ValueError("Message must be a string") from None
        self.messages.append(message)
        logger.info(message)

    def add_error(self, error: str) -> None:
        """Add an error message."""
        if not isinstance(error, str):
            raise ValueError("Error must be a string") from None
        self.errors.append(error)
        logger.error(error)
        self.success = False

    def get_build_info(self) -> dict[str, Any]:
        """Get build information dictionary."""
        return {
            "build_id": self.build_id,
            "main_firmware_path": str(self.output_files.main_uf2)
            if self.output_files and self.output_files.main_uf2
            else None,
            "left_firmware_path": str(self.output_files.left_uf2)
            if self.output_files and self.output_files.left_uf2
            else None,
            "right_firmware_path": str(self.output_files.right_uf2)
            if self.output_files and self.output_files.right_uf2
            else None,
            "artifacts_dir": str(self.output_files.artifacts_dir)
            if self.output_files and self.output_files.artifacts_dir
            else None,
            "output_dir": str(self.output_files.output_dir)
            if self.output_files
            else None,
            "build_time_seconds": self.build_time_seconds,
            "success": self.success,
        }

    def validate_build_artifacts(self) -> bool:
        """Check if build artifacts are valid and accessible."""
        if not self.success or not self.output_files:
            return False

        # Check main UF2 file
        if self.output_files.main_uf2 and not self.output_files.main_uf2.exists():
            self.add_error(
                f"Main firmware file not found: {self.output_files.main_uf2}"
            )
            return False

        # Check left-hand UF2 file
        if self.output_files.left_uf2 and not self.output_files.left_uf2.exists():
            self.add_error(
                f"Left-hand firmware file not found: {self.output_files.left_uf2}"
            )
            return False

        # Check right-hand UF2 file
        if self.output_files.right_uf2 and not self.output_files.right_uf2.exists():
            self.add_error(
                f"Right-hand firmware file not found: {self.output_files.right_uf2}"
            )
            return False

        # Check artifacts directory
        if (
            self.output_files.artifacts_dir
            and not self.output_files.artifacts_dir.exists()
        ):
            self.add_error(
                f"Artifacts directory not found: {self.output_files.artifacts_dir}"
            )
            return False

        return True


__all__ = [
    "OutputPaths",
    "FirmwareOutputFiles",
    "BuildResult",
]
