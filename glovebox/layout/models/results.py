"""Result models for layout operations."""

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import Field, field_serializer, field_validator

from glovebox.models.base import GloveboxBaseModel


class KeymapResult(GloveboxBaseModel):
    """Result of keymap operations."""

    success: bool
    timestamp: datetime = Field(default_factory=datetime.now)
    messages: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @field_serializer("timestamp", when_used="json")
    def serialize_timestamp(self, dt: datetime) -> int:
        """Serialize timestamp to Unix timestamp for JSON."""
        return int(dt.timestamp())

    keymap_path: Path | None = None
    conf_path: Path | None = None
    json_path: Path | None = None
    profile_name: str | None = None
    layer_count: int | None = None

    def add_message(self, message: str) -> None:
        """Add an informational message."""
        if not isinstance(message, str):
            raise ValueError("Message must be a string") from None
        self.messages.append(message)

    def add_error(self, error: str) -> None:
        """Add an error message."""
        if not isinstance(error, str):
            raise ValueError("Error must be a string") from None
        self.errors.append(error)
        self.success = False


class LayoutResult(GloveboxBaseModel):
    """Result of layout operations."""

    success: bool
    timestamp: datetime = Field(default_factory=datetime.now)
    messages: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_serializer("timestamp", when_used="json")
    def serialize_timestamp(self, dt: datetime) -> int:
        """Serialize timestamp to Unix timestamp for JSON."""
        return int(dt.timestamp())

    keymap_path: Path | None = None
    conf_path: Path | None = None
    json_path: Path | None = None

    # Content fields for data-focused operations
    keymap_content: str | None = None
    config_content: str | None = None
    json_content: dict[str, Any] | None = None

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

    def add_message(self, message: str) -> None:
        """Add an informational message."""
        if not isinstance(message, str):
            raise ValueError("Message must be a string") from None
        self.messages.append(message)

    def add_error(self, error: str) -> None:
        """Add an error message."""
        if not isinstance(error, str):
            raise ValueError("Error must be a string") from None
        self.errors.append(error)
        self.success = False

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
