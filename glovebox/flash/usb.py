"""USB device flashing functionality."""

import logging
import os
import platform
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from glovebox.core.errors import FlashError
from glovebox.flash.detect import create_device_detector
from glovebox.flash.flash_operations import create_flash_operations
from glovebox.flash.lsdev import (
    BlockDevice,
    BlockDeviceError,
    Lsdev,
    print_device_info,
)
from glovebox.models.results import FlashResult
from glovebox.protocols.device_detector_protocol import DeviceDetectorProtocol
from glovebox.protocols.firmware_flasher_protocol import FirmwareFlasherProtocol


logger = logging.getLogger(__name__)


def get_device_path(device_name: str) -> str:
    """
    Get the full device path for a device name.

    Args:
        device_name: Device name (e.g., 'sda', 'disk2')

    Returns:
        Full device path

    Raises:
        FlashError: If running on an unsupported OS
    """

    system = platform.system().lower()

    if system == "linux" or system == "darwin":
        return f"/dev/{device_name}"

    # Handle unsupported operating systems
    if system == "windows":
        # Windows path might need different handling depending on the tool (udisksctl won't work)
        logger.warning("Windows flashing path construction might need adjustment.")
    else:
        # For other unsupported OS
        logger.warning(f"Unsupported OS for device path construction: {system}")

    raise FlashError(f"Unsupported operating system: {system}") from None


class FirmwareFlasherImpl:
    """Implementation class for flashing firmware to devices."""

    def __init__(
        self,
        detector: DeviceDetectorProtocol | None = None,
        lsdev: Lsdev | None = None,
    ) -> None:
        """
        Initialize the firmware flasher.

        Args:
            detector: Optional DeviceDetectorProtocol for dependency injection
            lsdev: Optional Lsdev instance for dependency injection
        """
        self.lsdev = lsdev or Lsdev()
        self._lock = threading.RLock()
        self._device_event = threading.Event()
        self._current_device: BlockDevice | None = None
        self._flashed_devices: set[str] = set()
        self._detector = detector or create_device_detector()

    def _extract_device_id(self, device: BlockDevice) -> str:
        """Extract a unique device ID for tracking."""
        # Look for USB symlinks which contain the serial number
        for symlink in device.symlinks:
            if symlink.startswith("usb-"):
                return symlink

        # Fallback to serial if available, or name as last resort
        return device.serial if device.serial else device.name

    def _device_callback(self, action: str, device: BlockDevice) -> None:
        """Callback for device detection events."""
        if action != "add":
            return

        with self._lock:
            # Skip already flashed devices
            device_id = self._extract_device_id(device)
            if device_id in self._flashed_devices:
                logger.debug(f"Skipping already flashed device: {device_id}")
                return

            # Store the detected device and signal the waiting thread
            self._current_device = device
            self._device_event.set()

    def flash_firmware(
        self,
        firmware_file: str | Path,
        query: str = "vendor=Adafruit and serial~=GLV80-.* and removable=true",
        timeout: int = 60,
        count: int = 1,  # Default to flashing one device
        track_flashed: bool = True,  # Track already flashed devices
    ) -> FlashResult:
        """
        Detect and flash firmware to one or more devices matching the query.

        Args:
            firmware_file: Path to the firmware file (.uf2).
            query: Query string to identify the target device(s).
            timeout: Timeout in seconds to wait for each device.
            count: Number of devices to flash (0 for infinite).
            track_flashed: Whether to track and skip already flashed devices.

        Returns:
            FlashResult object with flash operation results

        Raises:
            FileNotFoundError: If the firmware file does not exist.
            ValueError: If the query string is invalid.
        """
        firmware_path = Path(firmware_file).resolve()
        result = FlashResult(success=False, firmware_path=firmware_path)

        if not firmware_path.exists():
            raise FileNotFoundError(
                f"Firmware file not found: {firmware_path}"
            ) from None

        if not firmware_path.name.lower().endswith(".uf2"):
            result.add_message(
                f"Warning: Firmware file does not have .uf2 extension: {firmware_path.name}"
            )

        # Validate query early
        try:
            self._detector.parse_query(query)
        except ValueError as e:
            raise ValueError(f"Invalid query string: {e}") from e

        # Determine loop condition
        max_flashes = float("inf") if count == 0 else count
        is_infinite = count == 0

        # Reset tracking state
        with self._lock:
            if not track_flashed:
                self._flashed_devices = set()
            self._device_event.clear()
            self._current_device = None

        # Get reference to lsdev from detector for proper callbacks
        detector_lsdev = getattr(self._detector, "lsdev", self.lsdev)

        # Register callback for device detection
        detector_lsdev.register_callback(self._device_callback)

        try:
            # Start monitoring for device events
            detector_lsdev.start_monitoring()

            while result.devices_flashed + result.devices_failed < max_flashes:
                current_attempt = result.devices_flashed + result.devices_failed + 1
                target_info = (
                    f"{current_attempt}/{int(max_flashes)}"
                    if not is_infinite
                    else f"cycle {current_attempt}"
                )
                logger.info(
                    f"--- Waiting for device {target_info} matching '{query}' ---"
                )
                result.add_message(f"Waiting for device {target_info}...")

                try:
                    # Get current devices with their details
                    current_block_devices = self.lsdev.get_devices()
                    print_device_info(current_block_devices)

                    # Check if any existing devices match the query
                    matching_devices = self._detector.list_matching_devices(query)
                    for device in matching_devices:
                        device_id = self._extract_device_id(device)
                        if not track_flashed or device_id not in self._flashed_devices:
                            self._current_device = device
                            self._device_event.set()
                            break

                    # Wait for a matching device or timeout
                    if not self._device_event.wait(timeout):
                        if is_infinite:
                            logger.info(
                                f"Device detection timed out ({timeout}s). Continuing to wait..."
                            )
                            result.add_message(
                                "Device detection timed out. Continuing..."
                            )
                            self._device_event.clear()
                            continue
                        else:
                            timeout_msg = (
                                f"Device detection timed out after {timeout} seconds."
                            )
                            logger.error(timeout_msg)
                            result.add_error(timeout_msg)
                            break

                    # Get the detected device
                    with self._lock:
                        device = self._current_device
                        self._device_event.clear()

                    if device is None:
                        # This shouldn't happen if _device_event was set, but just in case
                        logger.warning("Device event triggered but no device found")
                        continue

                    # Extract device ID for tracking
                    device_id = self._extract_device_id(device)
                    logger.debug(f"Detected device ID: {device_id}")
                    logger.debug(f"Detected device: {device}")

                    # Skip already flashed devices if tracking is enabled
                    if track_flashed and device_id in self._flashed_devices:
                        logger.info(f"Skipping already flashed device: {device.name}")
                        result.add_message(
                            f"Skipping already flashed device: {device.name}"
                        )
                        continue

                    result.add_message(
                        f"Detected device: {device.name} ({device.model})"
                    )

                    # Attempt to flash the detected device
                    logger.info(f"Attempting to flash {device.name}...")
                    # Use flash operations for mounting and flashing
                    flash_ops = create_flash_operations()
                    if flash_ops.mount_and_flash(device, firmware_path):
                        device_info = {
                            "model": device.model,
                            "vendor": device.vendor,
                            "serial": device.serial,
                        }
                        result.add_device_success(device.name, device_info)

                        success_msg = f"Successfully flashed device {device.name} ({result.devices_flashed}/{int(max_flashes) if not is_infinite else '∞'})"
                        logger.info(success_msg)

                        # Add device to flashed set if tracking is enabled
                        if track_flashed:
                            self._flashed_devices.add(device_id)
                            logger.debug(
                                f"Added device {device_id} to flashed devices list"
                            )

                        # Wait a bit for device to reboot/disconnect before next search
                        time.sleep(3)
                    else:
                        # mount_and_flash returned False (non-critical failure after retries)
                        device_info = {
                            "model": device.model,
                            "vendor": device.vendor,
                            "serial": device.serial,
                        }
                        fail_msg = f"Failed to flash device {device.name} after retries"
                        result.add_device_failure(device.name, fail_msg, device_info)
                        logger.error(fail_msg)

                except (
                    FileNotFoundError,
                    BlockDeviceError,
                    PermissionError,
                    ValueError,
                ) as e:
                    # Catch critical errors from detect or mount_and_flash
                    critical_err_msg = (
                        f"Critical error during flash attempt {target_info}: {e}"
                    )
                    logger.error(critical_err_msg)
                    result.add_error(critical_err_msg)
                    break
                except KeyboardInterrupt:
                    logger.info("Flash operation interrupted by user.")
                    result.add_message("Operation interrupted by user.")
                    break
                except Exception as e:
                    # Catch unexpected errors
                    unexpected_err_msg = (
                        f"Unexpected error during flash attempt {target_info}: {e}"
                    )
                    logger.exception(unexpected_err_msg)
                    result.add_error(unexpected_err_msg)
                    break

        finally:
            # Clean up
            detector_lsdev.unregister_callback(self._device_callback)
            detector_lsdev.stop_monitoring()

        final_success = (result.devices_failed == 0) and (
            result.devices_flashed == max_flashes if not is_infinite else True
        )
        result.success = final_success

        summary_msg = f"Flash summary: {result.devices_flashed} succeeded, {result.devices_failed} failed."
        logger.info(summary_msg)
        result.add_message(summary_msg)

        return result


def create_firmware_flasher(
    detector: DeviceDetectorProtocol | None = None, lsdev: Lsdev | None = None
) -> FirmwareFlasherProtocol:
    """Factory function to create a FirmwareFlasher instance.

    Args:
        detector: Optional DeviceDetectorProtocol for dependency injection
        lsdev: Optional Lsdev instance for dependency injection

    Returns:
        Configured FirmwareFlasherProtocol instance

    Example:
        >>> flasher = create_firmware_flasher()
        >>> result = flasher.flash_firmware("firmware.uf2")
        >>> print(f"Flashed {result.devices_flashed} devices")
    """
    logger.debug("Creating FirmwareFlasher")
    return FirmwareFlasherImpl(detector=detector, lsdev=lsdev)


