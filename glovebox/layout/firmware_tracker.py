"""Firmware build tracking utilities."""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from glovebox.adapters.file_adapter import create_file_adapter
from glovebox.layout.models import LayoutData
from glovebox.protocols import FileAdapterProtocol


logger = logging.getLogger(__name__)


class FirmwareTracker:
    """Tracks firmware builds and links them to layout files."""

    def __init__(self, file_adapter: FileAdapterProtocol | None = None):
        """Initialize firmware tracker."""
        self._file_adapter = file_adapter or create_file_adapter()

    def track_build(
        self,
        layout_file: Path,
        firmware_file: Path,
        profile: str,
        build_id: str | None = None,
    ) -> None:
        """Track a firmware build in the layout metadata.

        Args:
            layout_file: Path to layout JSON file
            firmware_file: Path to generated firmware file
            profile: Profile used for build (e.g., "glove80/v25.05")
            build_id: Optional build ID from compilation
        """
        try:
            # Calculate firmware hash
            firmware_hash = self._calculate_file_hash(firmware_file)

            # Load layout file
            layout_data = self._load_layout(layout_file)

            # Update firmware tracking metadata
            layout_data.last_firmware_build = {
                "date": datetime.now().isoformat(),
                "profile": profile,
                "firmware_path": str(firmware_file.resolve()),
                "firmware_hash": firmware_hash,
                "build_id": build_id or "",
            }

            # Save updated layout
            self._save_layout(layout_data, layout_file)

            logger.info("Tracked firmware build for %s", layout_file.name)

        except Exception as e:
            logger.warning("Failed to track firmware build: %s", e)

    def get_build_info(self, layout_file: Path) -> dict[str, Any] | None:
        """Get firmware build info for a layout file."""
        try:
            layout_data = self._load_layout(layout_file)
            return (
                layout_data.last_firmware_build
                if layout_data.last_firmware_build
                else None
            )
        except Exception as e:
            logger.warning("Failed to get build info: %s", e)
            return None

    def is_firmware_current(self, layout_file: Path, firmware_file: Path) -> bool:
        """Check if firmware file is current for the layout."""
        try:
            build_info = self.get_build_info(layout_file)
            if not build_info:
                return False

            # Check if firmware file exists and hash matches
            if not firmware_file.exists():
                return False

            current_hash = self._calculate_file_hash(firmware_file)
            return current_hash == build_info.get("firmware_hash")

        except Exception:
            return False

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file."""
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        sha256_hash = hashlib.sha256()
        with file_path.open("rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)

        return f"sha256:{sha256_hash.hexdigest()}"

    def _load_layout(self, json_file: Path) -> LayoutData:
        """Load layout from JSON file."""
        if not json_file.exists():
            raise FileNotFoundError(f"Layout file not found: {json_file}")

        content = self._file_adapter.read_text(json_file)
        data = json.loads(content)
        return LayoutData.model_validate(data)

    def _save_layout(self, layout_data: LayoutData, output_path: Path) -> None:
        """Save layout to JSON file."""
        # Use model_dump with serialization mode for proper datetime handling
        data = layout_data.model_dump(by_alias=True, exclude_unset=True, mode="json")
        content = json.dumps(data, indent=2, ensure_ascii=False)
        self._file_adapter.write_text(output_path, content)


def create_firmware_tracker() -> FirmwareTracker:
    """Create a firmware tracker instance."""
    return FirmwareTracker()
