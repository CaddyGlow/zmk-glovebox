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
from typing import Any  # UP035: Removed Dict, Union

from glovebox.core.errors import FlashError
from glovebox.flash.lsdev import (
    BlockDevice,
    BlockDeviceError,
    Lsdev,
    print_device_info,
)
from glovebox.models.results import FlashResult


# Import detect_device from the correct module

logger = logging.getLogger(__name__)


def get_device_path(device_name: str) -> str:
    """
    Get the full device path for a device name.

    Args:
        device_name: Device name (e.g., 'sda', 'disk2')

    Returns:
        Full device path
    """
    import platform

    system = platform.system().lower()

    if system == "linux" or system == "darwin":
        return f"/dev/{device_name}"
    elif system == "windows":
        # Windows path might need different handling depending on the tool (udisksctl won't work)
        # For now, just return the name, assuming a Windows-specific tool would be used.
        logger.warning("Windows flashing path construction might need adjustment.")
        raise FlashError("Unsupported operating system") from None  # B904
    else:
        # For other unsupported OS, return name and warn
        logger.warning(f"Unsupported OS for device path construction: {system}")
        raise FlashError("Unsupported operating system") from None  # B904

    # This is unreachable but needed to satisfy mypy
    return device_name


def mount_and_flash(
    device: BlockDevice,
    firmware_file: str | Path,  # UP035
    max_retries: int = 3,
    retry_delay: float = 2.0,  # Allow float for delay
) -> bool:
    """
    Mount device using udisksctl and flash firmware with retry logic.

    Args:
        device: BlockDevice object representing the target device.
        firmware_file: Path to firmware file to flash.
        max_retries: Maximum number of retries
        retry_delay: Delay between retries in seconds

    Returns:
    Returns:
        Boolean indicating success or failure.

    Raises:
        FileNotFoundError: If firmware file or udisksctl is not found.
        BlockDeviceError: If the platform is not supported for mounting (non-Linux).
        PermissionError: If authorization fails during mount.
        FlashError: For other flashing related errors.
    """
    firmware_path = Path(firmware_file).resolve()
    if not firmware_path.exists():
        # Use FileNotFoundError for missing files
        raise FileNotFoundError(
            f"Firmware file not found: {firmware_path}"
        ) from None  # B904

    system = platform.system().lower()
    if system not in ["linux"]:
        # udisksctl is primarily a Linux tool. macOS/Windows need different approaches.
        raise BlockDeviceError(
            f"Automated mounting with udisksctl is not supported on {system}."
        ) from None  # B904

    # Construct the full device path (e.g., /dev/sda)
    device_path = get_device_path(device.name)
    device_identifier = (
        f"{device.serial}_{device.label}" if device.serial else device.label
    )

    # Check if udisksctl exists
    if not shutil.which("udisksctl"):
        raise FileNotFoundError(
            "`udisksctl` command not found. Please install udisks2."
        ) from None  # B904

    for attempt in range(max_retries):
        mount_point = None
        try:
            logger.info(
                f"Attempt {attempt + 1}/{max_retries}: Mounting device {device_path} ({device_identifier})..."
            )

            # Mount using udisksctl
            mount_result = subprocess.run(
                ["udisksctl", "mount", "--no-user-interaction", "-b", device_path],
                capture_output=True,
                text=True,
                check=False,  # Don't check=True, handle errors manually
                timeout=10,  # Add a timeout
            )
            logger.debug(f"Mount command stdout: {mount_result.stdout}")
            logger.debug(f"Mount command stderr: {mount_result.stderr}")

            if mount_result.returncode != 0:
                # Check stderr for common errors
                if "already mounted" in mount_result.stderr.lower():
                    logger.warning(
                        f"Device {device_path} already mounted. Trying to find mount point."
                    )
                    # Proceed to find mount point below
                elif "not authorized" in mount_result.stderr.lower():
                    logger.error(
                        f"Authorization failed for mounting {device_path}. Check polkit rules."
                    )
                    # Raise PermissionError for auth issues
                    raise PermissionError(
                        f"Authorization failed for mounting {device_path}"
                    ) from None  # B904
                else:
                    logger.warning(
                        f"Mount command failed (exit code {mount_result.returncode}). Retrying..."
                    )
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    else:
                        logger.error(
                            f"Failed to mount {device_path} after {max_retries} attempts."
                        )
                        return False  # Failed after retries

            # Extract mount point from udisksctl output or info
            if mount_result.returncode == 0 and " at " in mount_result.stdout:
                # Example output: "Mounted /dev/sda at /run/media/user/GLV80RHBOOT"
                mount_point_match = re.search(r" at (/\S+)", mount_result.stdout)
                if mount_point_match:
                    mount_point = mount_point_match.group(1).strip()

            # If mount_point not found from output, try getting info
            if not mount_point:
                logger.debug(
                    f"Mount point not found in mount output, querying udisksctl info for {device_path}..."
                )
                try:
                    info_result = subprocess.run(
                        ["udisksctl", "info", "-b", device_path],
                        capture_output=True,
                        text=True,
                        check=True,  # Check info success
                        timeout=5,
                    )
                    logger.debug(f"Info command stdout: {info_result.stdout}")
                    # More robust regex for MountPoints, handling potential spaces and variations
                    mount_point_line = re.search(
                        r"^\s*MountPoints?:\s*(/\S+)", info_result.stdout, re.MULTILINE
                    )
                    if mount_point_line:
                        mount_point = mount_point_line.group(1).strip()
                    else:
                        # Handle cases where MountPoints might be on the next line (less common now)
                        lines = info_result.stdout.splitlines()
                        for i, line in enumerate(lines):
                            if "MountPoints:" in line and i + 1 < len(lines):
                                possible_mount = lines[i + 1].strip()
                                if possible_mount.startswith("/"):
                                    mount_point = possible_mount
                                    break
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    logger.warning(
                        f"Failed to get udisksctl info for {device_path}: {e}"
                    )
                except Exception as e:
                    logger.error(f"Unexpected error getting udisksctl info: {e}")

            if not mount_point or not Path(mount_point).is_dir():
                logger.warning(
                    f"Could not reliably determine mount point for {device_path}."
                )
                if attempt < max_retries - 1:
                    logger.info(f"Retrying mount/info in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    continue
                else:
                    logger.error(
                        f"Failed to find mount point for {device_path} after {max_retries} attempts."
                    )
                    return False  # Failed to find mount point

            logger.info(f"Device {device_identifier} mounted at {mount_point}")

            # Copy the firmware file
            dest_path = Path(mount_point) / firmware_path.name  # Use Path object
            logger.info(f"Copying {firmware_path} to {dest_path}")
            # Use copy2 to preserve metadata, copy to directory preserves filename
            shutil.copy2(firmware_path, mount_point)
            # Optional: Add fsync to ensure data is written
            try:
                # fsync the directory containing the new file
                fd = os.open(mount_point, os.O_RDONLY)
                os.fsync(fd)
                os.close(fd)
                logger.debug(f"fsync successful on directory {mount_point}")
            except OSError as e:
                logger.warning(
                    f"Could not fsync mount point directory {mount_point}: {e}"
                )
            except Exception as e:
                logger.warning(f"Unexpected error during fsync: {e}")

            logger.info("Firmware file copied successfully.")

            # Trying to unmount, but it might fail as the device disconnects quickly
            try:
                logger.debug(f"Attempting to unmount {mount_point} ({device_path})")
                # Use --force as the device might already be gone
                unmount_result = subprocess.run(
                    [
                        "udisksctl",
                        "unmount",
                        "--no-user-interaction",
                        "-b",
                        device_path,
                        "--force",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,  # Short timeout
                    check=False,  # Don't fail on error
                )
                logger.debug(f"Unmount stdout: {unmount_result.stdout}")
                logger.debug(f"Unmount stderr: {unmount_result.stderr}")
                if unmount_result.returncode == 0:
                    logger.debug("Unmount command successful")
                else:
                    # Log non-zero exit code as debug, it's often expected
                    logger.debug(
                        f"Unmount command finished (exit code {unmount_result.returncode}), device likely disconnected."
                    )

            except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
                logger.debug(f"Unmount failed or timed out (likely expected): {e}")
            except Exception as e:
                logger.warning(f"Unexpected error during unmount: {e}")

            return True  # Flash successful

        except FileNotFoundError as e:
            # Handle missing udisksctl specifically
            logger.error(f"Error: {e}. Please ensure udisks2 is installed.")
            raise  # Re-raise critical error
        except PermissionError as e:
            # Handle permission errors during mount
            logger.error(f"Permission error during mount/flash: {e}")
            raise  # Re-raise critical error
        except (OSError, subprocess.SubprocessError) as e:
            # Catch errors during copy or other subprocess calls
            logger.error(
                f"OS or Subprocess error during mount/flash attempt {attempt + 1}: {e}"
            )
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error(
                    "All mount/flash attempts failed due to OS/Subprocess error."
                )
                # Attempt cleanup unmount if possible
                if mount_point:
                    # (Cleanup unmount logic as before)
                    pass
                raise FlashError(
                    f"Failed to flash after retries due to OS/Subprocess error: {e}"
                ) from e
        except Exception as e:
            # Catch any other unexpected errors
            logger.error(
                f"Unexpected error during mount/flash attempt {attempt + 1}: {e}"
            )
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error("All mount/flash attempts failed due to unexpected error.")
                # Attempt cleanup unmount if possible
                if mount_point:
                    # (Cleanup unmount logic as before)
                    pass
                # Wrap unexpected errors in FlashError
                raise FlashError(
                    f"Failed to flash after retries due to unexpected error: {e}"
                ) from e

    return False  # Should only be reached if all retries fail without raising


class FirmwareFlasher:
    """Class for flashing firmware to devices."""

    def __init__(self) -> None:
        """Initialize the firmware flasher."""
        self.lsdev = Lsdev()
        self._lock = threading.RLock()
        self._device_event = threading.Event()
        self._current_device: BlockDevice | None = None
        self._flashed_devices: set[str] = set()
        self._detector: Any = None

        # Import here to avoid circular imports
        from .detect import DeviceDetector

        self._detector = DeviceDetector()

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
        firmware_file: str | Path,  # UP035
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
            ) from None  # B904

        if not firmware_path.name.lower().endswith(".uf2"):
            result.add_message(
                f"Warning: Firmware file does not have .uf2 extension: {firmware_path.name}"
            )

        # Validate query early
        try:
            from .detect import parse_query

            parse_query(query)
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

        # Register callback for device detection
        if self._detector is not None:
            self._detector.lsdev.register_callback(self._device_callback)

        try:
            # Start monitoring for device events
            if self._detector is not None:
                self._detector.lsdev.start_monitoring()

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
                    if self._detector is not None:
                        matching_devices = self._detector.list_matching_devices(query)
                        for device in matching_devices:
                            device_id = self._extract_device_id(device)
                            if (
                                not track_flashed
                                or device_id not in self._flashed_devices
                            ):
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
                    if mount_and_flash(device, firmware_path):
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
            if self._detector is not None:
                self._detector.lsdev.unregister_callback(self._device_callback)
                self._detector.lsdev.stop_monitoring()

        final_success = (result.devices_failed == 0) and (
            result.devices_flashed == max_flashes if not is_infinite else True
        )
        result.success = final_success

        summary_msg = f"Flash summary: {result.devices_flashed} succeeded, {result.devices_failed} failed."
        logger.info(summary_msg)
        result.add_message(summary_msg)

        return result


# Create a singleton instance for global use
_flasher = FirmwareFlasher()


def flash_firmware(
    firmware_file: str | Path,  # UP035
    query: str = "vendor=Adafruit and serial~=GLV80-.* and removable=true",
    timeout: int = 60,
    count: int = 1,
    track_flashed: bool = True,
) -> FlashResult:
    """
    Detect and flash firmware to one or more devices matching the query.

    This is a wrapper around the FirmwareFlasher method for backward compatibility.
    """
    return _flasher.flash_firmware(
        firmware_file=firmware_file,
        query=query,
        timeout=timeout,
        count=count,
        track_flashed=track_flashed,
    )
