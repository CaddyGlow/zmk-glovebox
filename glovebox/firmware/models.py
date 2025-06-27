"""Firmware domain models."""

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator

from glovebox.models.base import GloveboxBaseModel


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
        uf2_files: List of all UF2 firmware files found (main, left, right, etc.)
        artifacts_dir: Directory containing all build artifacts
    """

    output_dir: Path
    uf2_files: list[Path]
    artifacts_dir: Path | None = None


class BuildResult(GloveboxBaseModel):
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
            "firmware_files": [str(uf2_file) for uf2_file in self.output_files.uf2_files]
            if self.output_files and self.output_files.uf2_files
            else [],
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

        # Check UF2 files
        for uf2_file in self.output_files.uf2_files:
            if not uf2_file.exists():
                self.add_error(f"Firmware file not found: {uf2_file}")
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


def generate_build_info(
    keymap_file: Path,
    config_file: Path,
    json_file: Path | None,
    repository: str,
    branch: str,
    head_hash: str | None = None,
    build_mode: str = "compilation",
    layout_uuid: str | None = None,
    uf2_files: list[Path] | None = None,
    compilation_duration: float | None = None,
) -> dict[str, Any]:
    """Generate comprehensive build information for inclusion in artifacts.

    Args:
        keymap_file: Path to the keymap file
        config_file: Path to the config file
        json_file: Path to the JSON layout file (optional)
        repository: Git repository name
        branch: Git branch name
        head_hash: Git commit hash (optional)
        build_mode: Build mode identifier
        layout_uuid: Layout UUID from JSON file (optional, will be extracted if not provided)
        uf2_files: List of generated UF2 firmware files (optional)
        compilation_duration: Compilation duration in seconds (optional)

    Returns:
        Dictionary containing build metadata
    """

    def _calculate_sha256(file_path: Path) -> str | None:
        """Calculate SHA256 hash of a file."""
        try:
            if not file_path.exists():
                return None
            return hashlib.sha256(file_path.read_bytes()).hexdigest()
        except Exception as e:
            logger.warning("Failed to calculate SHA256 for %s: %s", file_path, e)
            return None

    def _extract_layout_metadata(json_path: Path) -> dict[str, str | None]:
        """Extract layout metadata from JSON file."""
        try:
            if not json_path.exists():
                return {"uuid": None, "parent_uuid": None, "title": None}

            data = json.loads(json_path.read_text())

            # Extract UUID (prefer layout.id, fallback to uuid field)
            layout_section = data.get("layout", {}) if isinstance(data.get("layout"), dict) else {}
            layout_id = layout_section.get("id") if isinstance(layout_section.get("id"), str) else None
            uuid = layout_id or (data.get("uuid") if isinstance(data.get("uuid"), str) else None)

            # Extract parent UUID
            parent_uuid = layout_section.get("parent_uuid") if isinstance(layout_section.get("parent_uuid"), str) else None
            parent_uuid = parent_uuid or (data.get("parent_uuid") if isinstance(data.get("parent_uuid"), str) else None)

            # Extract title (prefer layout.title, fallback to top-level title)
            title = layout_section.get("title") if isinstance(layout_section.get("title"), str) else None
            title = title or (data.get("title") if isinstance(data.get("title"), str) else None)

            return {
                "uuid": uuid,
                "parent_uuid": parent_uuid,
                "title": title,
            }
        except Exception as e:
            logger.warning("Failed to extract layout metadata from %s: %s", json_path, e)
            return {"uuid": None, "parent_uuid": None, "title": None}

    # Calculate file hashes
    keymap_sha256 = _calculate_sha256(keymap_file)
    config_sha256 = _calculate_sha256(config_file)
    json_sha256 = _calculate_sha256(json_file) if json_file else None

    # Extract layout metadata from JSON file
    layout_metadata = {"uuid": layout_uuid, "parent_uuid": None, "title": None}
    if json_file:
        extracted_metadata = _extract_layout_metadata(json_file)
        # Use provided layout_uuid if available, otherwise use extracted
        layout_metadata["uuid"] = layout_uuid or extracted_metadata["uuid"]
        layout_metadata["parent_uuid"] = extracted_metadata["parent_uuid"]
        layout_metadata["title"] = extracted_metadata["title"]

    # Calculate UF2 file hashes
    uf2_file_info = []
    if uf2_files:
        for uf2_file in uf2_files:
            if uf2_file.exists():
                uf2_info = {
                    "path": str(uf2_file.name),
                    "sha256": _calculate_sha256(uf2_file),
                    "size_bytes": uf2_file.stat().st_size,
                }
                uf2_file_info.append(uf2_info)

    build_info: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "build_mode": build_mode,
        "repository": repository,
        "branch": branch,
        "head_hash": head_hash,
        "compilation_duration_seconds": compilation_duration,
        "files": {
            "keymap": {
                "path": str(keymap_file.name),
                "sha256": keymap_sha256,
            },
            "config": {
                "path": str(config_file.name),
                "sha256": config_sha256,
            },
        },
        "firmware": {
            "uf2_files": uf2_file_info,
            "total_files": len(uf2_file_info),
        },
        "layout": {
            "uuid": layout_metadata["uuid"],
            "parent_uuid": layout_metadata["parent_uuid"],
            "title": layout_metadata["title"],
        },
    }

    # Add JSON file info if present
    if json_file:
        files_dict = build_info["files"]
        if isinstance(files_dict, dict):
            files_dict["json"] = {
                "path": str(json_file.name),
                "sha256": json_sha256,
            }

    return build_info


def create_build_info_file(
    artifacts_dir: Path,
    keymap_file: Path,
    config_file: Path,
    json_file: Path | None,
    repository: str,
    branch: str,
    head_hash: str | None = None,
    build_mode: str = "compilation",
    layout_uuid: str | None = None,
    uf2_files: list[Path] | None = None,
    compilation_duration: float | None = None,
) -> bool:
    """Create build-info.json file in the artifacts directory.

    Args:
        artifacts_dir: Directory where build-info.json should be created
        keymap_file: Path to the keymap file
        config_file: Path to the config file
        json_file: Path to the JSON layout file (optional)
        repository: Git repository name
        branch: Git branch name
        head_hash: Git commit hash (optional)
        build_mode: Build mode identifier
        layout_uuid: Layout UUID from JSON file (optional, will be extracted if not provided)
        uf2_files: List of generated UF2 firmware files (optional)
        compilation_duration: Compilation duration in seconds (optional)

    Returns:
        True if file was created successfully, False otherwise
    """
    try:
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        build_info = generate_build_info(
            keymap_file=keymap_file,
            config_file=config_file,
            json_file=json_file,
            repository=repository,
            branch=branch,
            head_hash=head_hash,
            build_mode=build_mode,
            layout_uuid=layout_uuid,
            uf2_files=uf2_files,
            compilation_duration=compilation_duration,
        )

        build_info_file = artifacts_dir / "build-info.json"
        build_info_file.write_text(json.dumps(build_info, indent=2, ensure_ascii=False))

        logger.debug("Created build-info.json: %s", build_info_file)
        return True

    except Exception as e:
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("Failed to create build-info.json: %s", e, exc_info=exc_info)
        return False


__all__ = [
    "OutputPaths",
    "FirmwareOutputFiles",
    "BuildResult",
    "generate_build_info",
    "create_build_info_file",
]
