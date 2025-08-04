"""Firmware pairing service for split keyboard management."""

import logging
from pathlib import Path
from typing import Optional

from glovebox.firmware.flash.models import (
    FirmwarePair,
    FirmwareSide,
    detect_firmware_side,
)


logger = logging.getLogger(__name__)


class FirmwarePairingService:
    """Service for managing firmware pairing for split keyboards."""

    def __init__(self) -> None:
        """Initialize the firmware pairing service."""
        self.logger = logger

    def detect_firmware_pairs(self, firmware_files: list[Path]) -> list[FirmwarePair]:
        """Detect and create firmware pairs from a list of firmware files.

        Args:
            firmware_files: List of firmware file paths

        Returns:
            List of FirmwarePair objects

        Raises:
            ValueError: If invalid pairs are detected
        """
        if not firmware_files:
            return []

        # Group files by their base name
        file_groups: dict[str, dict[FirmwareSide, Path]] = {}

        for firmware_file in firmware_files:
            side = detect_firmware_side(firmware_file)
            base_name = self._extract_base_name(firmware_file, side)

            if base_name not in file_groups:
                file_groups[base_name] = {}

            if side in file_groups[base_name]:
                raise ValueError(
                    f"Duplicate {side.value} firmware for base '{base_name}': "
                    f"{file_groups[base_name][side]} and {firmware_file}"
                )

            file_groups[base_name][side] = firmware_file

        # Create pairs from grouped files
        pairs = []
        for base_name, sides in file_groups.items():
            if FirmwareSide.LEFT in sides and FirmwareSide.RIGHT in sides:
                # We have a complete pair
                pair = FirmwarePair(
                    left=sides[FirmwareSide.LEFT],
                    right=sides[FirmwareSide.RIGHT],
                    base_name=base_name,
                )
                pairs.append(pair)
                self.logger.info(
                    "Detected firmware pair for '%s': %s (left), %s (right)",
                    base_name,
                    pair.left.name,
                    pair.right.name,
                )
            elif FirmwareSide.UNIFIED in sides:
                # Single unified firmware, not a pair
                self.logger.debug(
                    "Unified firmware detected for '%s': %s",
                    base_name,
                    sides[FirmwareSide.UNIFIED].name,
                )
            else:
                # Incomplete pair
                available = list(sides.keys())
                self.logger.warning(
                    "Incomplete firmware pair for '%s': only %s side(s) found",
                    base_name,
                    available,
                )

        return pairs

    def match_device_to_side(
        self, device_serial: str, device_name: str, volume_label: str = ""
    ) -> FirmwareSide | None:
        """Match a device to its corresponding side based on serial, name, or volume label.

        Args:
            device_serial: Device serial number
            device_name: Device name
            volume_label: Volume label/mount name (most reliable for split keyboards)

        Returns:
            FirmwareSide if detected, None otherwise
        """
        # Check volume label first (most reliable for bootloader mode)
        label_lower = volume_label.lower()
        if label_lower:
            # Common volume label patterns for left devices
            if any(
                pattern in label_lower
                for pattern in ["left", "lh", "_l", "-l", "lh_", "l_hand", "lefthand"]
            ):
                return FirmwareSide.LEFT

            # Common volume label patterns for right devices
            if any(
                pattern in label_lower
                for pattern in ["right", "rh", "_r", "-r", "rh_", "r_hand", "righthand"]
            ):
                return FirmwareSide.RIGHT

        # Check serial number patterns
        serial_lower = device_serial.lower()
        name_lower = device_name.lower()

        # Common patterns for left devices
        if any(
            pattern in serial_lower or pattern in name_lower
            for pattern in ["left", "lh", "_l_", "-l-"]
        ):
            return FirmwareSide.LEFT

        # Common patterns for right devices
        if any(
            pattern in serial_lower or pattern in name_lower
            for pattern in ["right", "rh", "_r_", "-r-"]
        ):
            return FirmwareSide.RIGHT

        # If device has a number suffix, use odd/even convention
        # (odd = left, even = right is common for split keyboards)
        import re

        number_match = re.search(r"(\d+)$", serial_lower)
        if number_match:
            number = int(number_match.group(1))
            if number % 2 == 1:
                return FirmwareSide.LEFT
            else:
                return FirmwareSide.RIGHT

        return None

    def validate_pairing(
        self, firmware_side: FirmwareSide, device_side: FirmwareSide | None
    ) -> bool:
        """Validate that firmware and device sides match.

        Args:
            firmware_side: Side of the firmware
            device_side: Detected side of the device

        Returns:
            True if pairing is valid or cannot be determined
        """
        # If we can't detect device side, allow flashing (user responsibility)
        if device_side is None:
            self.logger.debug("Cannot detect device side, allowing flash")
            return True

        # If firmware is unified, it can go to any device
        if firmware_side == FirmwareSide.UNIFIED:
            return True

        # Check if sides match
        if firmware_side == device_side:
            self.logger.debug(
                "Firmware side (%s) matches device side", firmware_side.value
            )
            return True

        self.logger.warning(
            "Firmware side (%s) does not match device side (%s)",
            firmware_side.value,
            device_side.value,
        )
        return False

    def _extract_base_name(self, firmware_file: Path, side: FirmwareSide) -> str:
        """Extract base name from firmware file.

        Args:
            firmware_file: Path to firmware file
            side: Detected side of the firmware

        Returns:
            Base name without side suffix
        """
        name = firmware_file.stem

        if side == FirmwareSide.LEFT:
            # Remove left side suffixes
            for suffix in ["_lh", "_left", "-left", "_l", "left_", "lh_"]:
                if suffix in name.lower():
                    # Find the suffix position and remove it
                    idx = name.lower().rfind(suffix)
                    if idx != -1:
                        return name[:idx] + name[idx + len(suffix) :]

        elif side == FirmwareSide.RIGHT:
            # Remove right side suffixes
            for suffix in ["_rh", "_right", "-right", "_r", "right_", "rh_"]:
                if suffix in name.lower():
                    # Find the suffix position and remove it
                    idx = name.lower().rfind(suffix)
                    if idx != -1:
                        return name[:idx] + name[idx + len(suffix) :]

        # Return as-is for unified or unknown
        return name

    def suggest_pairing_order(
        self, pairs: list[FirmwarePair]
    ) -> list[tuple[FirmwarePair, str]]:
        """Suggest optimal order for flashing firmware pairs.

        Args:
            pairs: List of firmware pairs

        Returns:
            List of tuples (pair, suggested_order_reason)
        """
        if not pairs:
            return []

        suggestions = []
        for pair in pairs:
            # Prefer flashing left first (common convention)
            reason = "Flash left side first (standard convention)"
            suggestions.append((pair, reason))

        return suggestions


def create_firmware_pairing_service() -> FirmwarePairingService:
    """Create a firmware pairing service instance.

    Returns:
        Configured FirmwarePairingService instance
    """
    return FirmwarePairingService()
