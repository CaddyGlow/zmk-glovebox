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


class FlashResult(BaseResult):
    """Result of firmware flash operations."""

    devices_flashed: int = 0
    devices_failed: int = 0
    firmware_path: Path | None = None
    device_details: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("devices_flashed", "devices_failed")
    @classmethod
    def validate_device_counts(cls, v: int) -> int:
        """Validate device counts are non-negative."""
        if not isinstance(v, int) or v < 0:
            raise ValueError("Device counts must be non-negative integers") from None
        return v

    @field_validator("firmware_path")
    @classmethod
    def validate_firmware_path(cls, v: Any) -> Path | None:
        """Validate firmware path if provided."""
        if v is None:
            return None
        if isinstance(v, Path):
            return v
        if isinstance(v, str):
            return Path(v)
        # If we get here, v is neither None, Path, nor str
        raise ValueError("Firmware path must be a Path object or string") from None

    @field_validator("device_details")
    @classmethod
    def validate_device_details(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate device details structure."""
        if not isinstance(v, list):
            raise ValueError("Device details must be a list") from None

        for detail in v:
            if not isinstance(detail, dict):
                raise ValueError("Each device detail must be a dictionary") from None
            if "name" not in detail or "status" not in detail:
                raise ValueError(
                    "Device details must have 'name' and 'status' fields"
                ) from None
            if detail["status"] not in ["success", "failed"]:
                raise ValueError(
                    "Device status must be 'success' or 'failed'"
                ) from None

        return v

    def add_device_success(
        self, device_name: str, device_info: dict[str, Any] | None = None
    ) -> None:
        """Record a successful device flash."""
        if not isinstance(device_name, str) or not device_name.strip():
            raise ValueError("Device name must be a non-empty string") from None

        self.devices_flashed += 1
        device_detail = {"name": device_name, "status": "success"}
        if device_info:
            if not isinstance(device_info, dict):
                raise ValueError("Device info must be a dictionary") from None
            device_detail.update(device_info)
        self.device_details.append(device_detail)
        self.add_message(f"Successfully flashed device: {device_name}")

    def add_device_failure(
        self, device_name: str, error: str, device_info: dict[str, Any] | None = None
    ) -> None:
        """Record a failed device flash."""
        if not isinstance(device_name, str) or not device_name.strip():
            raise ValueError("Device name must be a non-empty string") from None
        if not isinstance(error, str) or not error.strip():
            raise ValueError("Error must be a non-empty string") from None

        self.devices_failed += 1
        device_detail = {"name": device_name, "status": "failed", "error": error}
        if device_info:
            if not isinstance(device_info, dict):
                raise ValueError("Device info must be a dictionary") from None
            device_detail.update(device_info)
        self.device_details.append(device_detail)
        self.add_error(f"Failed to flash device {device_name}: {error}")

    def get_flash_summary(self) -> dict[str, Any]:
        """Get flash operation summary."""
        total_devices = self.devices_flashed + self.devices_failed
        return {
            "total_devices": total_devices,
            "devices_flashed": self.devices_flashed,
            "devices_failed": self.devices_failed,
            "success_rate": (
                self.devices_flashed / total_devices if total_devices > 0 else 0.0
            ),
            "firmware_path": str(self.firmware_path) if self.firmware_path else None,
        }

    def validate_flash_consistency(self) -> bool:
        """Validate that device counts match device details."""
        expected_total = len(self.device_details)
        actual_total = self.devices_flashed + self.devices_failed

        if expected_total != actual_total:
            self.add_error(
                f"Device count mismatch: {expected_total} details vs {actual_total} counted"
            )
            return False

        success_count = sum(1 for d in self.device_details if d["status"] == "success")
        failed_count = sum(1 for d in self.device_details if d["status"] == "failed")

        if success_count != self.devices_flashed:
            self.add_error(
                f"Success count mismatch: {success_count} in details vs {self.devices_flashed} counted"
            )
            return False

        if failed_count != self.devices_failed:
            self.add_error(
                f"Failed count mismatch: {failed_count} in details vs {self.devices_failed} counted"
            )
            return False

        return True
