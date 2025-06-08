"""Result models for Glovebox operations."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, TypeAlias

from pydantic import BaseModel, Field, field_validator, model_validator

from glovebox.models.build import FirmwareOutputFiles


logger = logging.getLogger(__name__)


class BaseResult(BaseModel):
    """Base class for all operation results."""

    success: bool
    timestamp: datetime = Field(default_factory=datetime.now)
    messages: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_success_consistency(self) -> "BaseResult":
        """Ensure success flag is consistent with errors."""
        if self.errors and self.success:
            logger.warning(
                "Result marked as success but has errors. Setting success=False"
            )
            self.success = False
        return self

    @field_validator("messages", "errors")
    @classmethod
    def validate_message_lists(cls, v: list[str]) -> list[str]:
        """Validate that message lists contain only strings."""
        if not isinstance(v, list):
            raise ValueError("Messages and errors must be lists")
        for item in v:
            if not isinstance(item, str):
                raise ValueError("All messages and errors must be strings")
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

    def is_success(self) -> bool:
        """Check if the operation was successful."""
        return self.success and not self.errors

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the result."""
        return {
            "success": self.success,
            "timestamp": self.timestamp.isoformat(),
            "message_count": len(self.messages),
            "error_count": len(self.errors),
            "errors": self.errors if self.errors else None,
        }


class KeymapResult(BaseResult):
    """Result of keymap operations."""

    keymap_path: Path | None = None
    conf_path: Path | None = None
    json_path: Path | None = None
    profile_name: str | None = None
    layer_count: int | None = None


class LayoutResult(BaseResult):
    """Result of layout operations."""

    keymap_path: Path | None = None
    conf_path: Path | None = None
    json_path: Path | None = None
    profile_name: str | None = None
    layer_count: int | None = None

    @field_validator("keymap_path", "conf_path", "json_path")
    @classmethod
    def validate_paths(cls, v: Any) -> Path | None:
        """Validate that paths are Path objects if provided."""
        if v is None:
            return None
        if isinstance(v, Path):
            return v
        if isinstance(v, str):
            return Path(v)
        # If we get here, v is neither None, Path, nor str
        raise ValueError("Paths must be Path objects or strings") from None

    @field_validator("layer_count")
    @classmethod
    def validate_layer_count(cls, v: int | None) -> int | None:
        """Validate layer count is positive if provided."""
        if v is not None and (not isinstance(v, int) or v < 0):
            raise ValueError("Layer count must be a non-negative integer") from None
        return v

    def get_output_files(self) -> dict[str, Path]:
        """Get dictionary of output file types to paths."""
        files = {}
        if self.keymap_path:
            files["keymap"] = self.keymap_path
        if self.conf_path:
            files["conf"] = self.conf_path
        if self.json_path:
            files["json"] = self.json_path
        return files

    def validate_output_files_exist(self) -> bool:
        """Check if all output files actually exist on disk."""
        files = self.get_output_files()
        missing_files = []

        for file_type, file_path in files.items():
            if not file_path.exists():
                missing_files.append(f"{file_type}: {file_path}")

        if missing_files:
            self.add_error(f"Output files missing: {', '.join(missing_files)}")
            return False

        return True


class BuildResult(BaseResult):
    """Result of firmware build operations."""

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
