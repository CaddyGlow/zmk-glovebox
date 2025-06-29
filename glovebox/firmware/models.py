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
            "firmware_files": [
                str(uf2_file) for uf2_file in self.output_files.uf2_files
            ]
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

    def set_success_messages(
        self, compilation_strategy: str, was_cached: bool = False
    ) -> None:
        """Set unified success messages based on compilation strategy and cache status.

        Args:
            compilation_strategy: The compilation strategy used ('zmk_west', 'moergo_nix', etc.)
            was_cached: Whether this was a cached build result
        """
        if not self.success or not self.output_files:
            return

        uf2_count = len(self.output_files.uf2_files)

        # Generate unified success message
        if was_cached:
            cache_msg = "Used cached build result"
            if uf2_count > 0:
                self.messages = [
                    f"{cache_msg} • Generated {uf2_count} firmware file{'s' if uf2_count != 1 else ''}"
                ]
            else:
                self.messages = [cache_msg]
        else:
            if uf2_count > 0:
                self.messages = [
                    f"Generated {uf2_count} firmware file{'s' if uf2_count != 1 else ''}"
                ]
            else:
                self.messages = ["Build completed successfully"]

        # Add file details with full paths for better user feedback
        if uf2_count > 0:
            file_paths = [str(f) for f in self.output_files.uf2_files]
            if uf2_count <= 3:  # Show individual files for small counts
                self.messages.extend(f"  • {path}" for path in file_paths)
            else:
                # Show first few files and count for many files
                self.messages.extend(f"  • {path}" for path in file_paths[:2])
                self.messages.append(f"  • ... and {uf2_count - 2} more files")


def generate_build_info(
    repository: str,
    branch: str,
    keymap_content: str,
    config_content: str,
    head_hash: str | None = None,
    build_mode: str = "compilation",
    layout_uuid: str | None = None,
    uf2_files: list[Path] | None = None,
    compilation_duration: float | None = None,
) -> dict[str, Any]:
    """Generate comprehensive build information for inclusion in artifacts.

    Args:
        repository: Git repository name
        branch: Git branch name
        keymap_content: Keymap content string
        config_content: Config content string
        head_hash: Git commit hash (optional)
        build_mode: Build mode identifier
        layout_uuid: Layout UUID from JSON file (optional)
        uf2_files: List of generated UF2 firmware files (optional)
        compilation_duration: Compilation duration in seconds (optional)

    Returns:
        Dictionary containing build metadata
    """

    def _calculate_sha256_from_content(content: str | None) -> str | None:
        """Calculate SHA256 hash from content string."""
        try:
            if content is None:
                return None
            return hashlib.sha256(content.encode("utf-8")).hexdigest()
        except Exception as e:
            logger.warning("Failed to calculate SHA256 from content: %s", e)
            return None

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
            layout_section = (
                data.get("layout", {}) if isinstance(data.get("layout"), dict) else {}
            )
            layout_id = (
                layout_section.get("id")
                if isinstance(layout_section.get("id"), str)
                else None
            )
            uuid = layout_id or (
                data.get("uuid") if isinstance(data.get("uuid"), str) else None
            )

            # Extract parent UUID
            parent_uuid = (
                layout_section.get("parent_uuid")
                if isinstance(layout_section.get("parent_uuid"), str)
                else None
            )
            parent_uuid = parent_uuid or (
                data.get("parent_uuid")
                if isinstance(data.get("parent_uuid"), str)
                else None
            )

            # Extract title (prefer layout.title, fallback to top-level title)
            title = (
                layout_section.get("title")
                if isinstance(layout_section.get("title"), str)
                else None
            )
            title = title or (
                data.get("title") if isinstance(data.get("title"), str) else None
            )

            return {
                "uuid": uuid,
                "parent_uuid": parent_uuid,
                "title": title,
            }
        except Exception as e:
            logger.warning(
                "Failed to extract layout metadata from %s: %s", json_path, e
            )
            return {"uuid": None, "parent_uuid": None, "title": None}

    # Calculate content hashes
    keymap_sha256 = _calculate_sha256_from_content(keymap_content)
    config_sha256 = _calculate_sha256_from_content(config_content)

    # Use provided layout metadata
    layout_metadata = {"uuid": layout_uuid, "parent_uuid": None, "title": None}

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
                "sha256": keymap_sha256,
            },
            "config": {
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

    # No JSON file handling for memory-based builds

    return build_info


def create_build_info_file(
    artifacts_dir: Path,
    repository: str,
    branch: str,
    keymap_file: Path | None = None,
    config_file: Path | None = None,
    keymap_content: str | None = None,
    config_content: str | None = None,
    json_file: Path | None = None,
    head_hash: str | None = None,
    build_mode: str = "compilation",
    layout_uuid: str | None = None,
    uf2_files: list[Path] | None = None,
    compilation_duration: float | None = None,
) -> bool:
    """Create build-info.json file from either file paths or content.

    Args:
        artifacts_dir: Directory where build-info.json should be created
        repository: Git repository name
        branch: Git branch name
        keymap_file: Path to the keymap file (optional, used if content not provided)
        config_file: Path to the config file (optional, used if content not provided)
        keymap_content: Keymap content string (optional, used instead of file)
        config_content: Config content string (optional, used instead of file)
        json_file: Path to the JSON layout file (optional)
        head_hash: Git commit hash (optional)
        build_mode: Build mode identifier
        layout_uuid: Layout UUID (optional)
        uf2_files: List of generated UF2 firmware files (optional)
        compilation_duration: Compilation duration in seconds (optional)

    Returns:
        True if file was created successfully, False otherwise
    """
    try:
        # Get content either from provided strings or by reading files
        actual_keymap_content = keymap_content
        actual_config_content = config_content

        if actual_keymap_content is None and keymap_file is not None:
            actual_keymap_content = keymap_file.read_text()
        if actual_config_content is None and config_file is not None:
            actual_config_content = config_file.read_text()

        if actual_keymap_content is None or actual_config_content is None:
            raise ValueError("Must provide either file paths or content strings")

        artifacts_dir.mkdir(parents=True, exist_ok=True)

        build_info = generate_build_info(
            repository=repository,
            branch=branch,
            keymap_content=actual_keymap_content,
            config_content=actual_config_content,
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
