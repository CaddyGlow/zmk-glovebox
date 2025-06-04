"""USB adapter for device detection and flashing operations."""

import logging
import threading
import time
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from glovebox.core.errors import FlashError, USBError
from glovebox.flash.detect import DeviceDetector
from glovebox.flash.lsdev import BlockDevice, Lsdev
from glovebox.flash.usb import mount_and_flash
from glovebox.utils.error_utils import create_usb_error


logger = logging.getLogger(__name__)


@runtime_checkable
class USBAdapter(Protocol):
    """Protocol for USB device operations."""

    def detect_device(
        self,
        query: str,
        timeout: int = 60,
        initial_devices: list[BlockDevice] | None = None,
    ) -> BlockDevice:
        """Detect a USB device matching the query."""
        ...

    def list_matching_devices(self, query: str) -> list[BlockDevice]:
        """List all devices matching the query."""
        ...

    def flash_device(
        self,
        device: BlockDevice,
        firmware_file: str | Path,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> bool:
        """Flash firmware to a specific device."""
        ...

    def get_all_devices(self, query: str = "") -> list[BlockDevice]:
        """Get all available block devices, optionally filtered by query."""
        ...

    def mount(self, device: BlockDevice) -> list[str]:
        """Mount a block device and return the mount points."""
        ...

    def unmount(self, device: BlockDevice) -> bool:
        """Unmount a block device."""
        ...

    def copy_file(self, source: Path, destination: Path) -> bool:
        """Copy a file from source to destination."""
        ...


class USBAdapterImpl:
    """Implementation of USB adapter."""

    def __init__(self) -> None:
        """Initialize the USB adapter."""
        self.detector = DeviceDetector()
        self.lsdev = Lsdev()
        self._lock = threading.RLock()
        logger.debug("USBAdapter initialized")

    def detect_device(
        self,
        query: str,
        timeout: int = 60,
        initial_devices: list[BlockDevice] | None = None,
    ) -> BlockDevice:
        """
        Detect a USB device matching the query.

        Args:
            query: Query string to match devices
            timeout: Maximum time to wait in seconds
            initial_devices: Optional list of devices to exclude from detection

        Returns:
            The first matching BlockDevice

        Raises:
            TimeoutError: If no matching device is found within the timeout
            ValueError: If the query string is invalid
            USBError: If there's an error during device detection
        """
        logger.info("Detecting device with query: %s", query)

        try:
            return self.detector.detect_device(query, timeout, initial_devices)
        except TimeoutError as e:
            error = create_usb_error(
                query,
                "detect_device",
                e,
                {
                    "timeout": timeout,
                    "initial_devices_count": len(initial_devices)
                    if initial_devices
                    else 0,
                },
            )
            logger.error(
                "Device detection timed out after %d seconds for query: %s",
                timeout,
                query,
            )
            raise error from e
        except ValueError as e:
            error = create_usb_error(
                query,
                "detect_device",
                e,
                {
                    "timeout": timeout,
                    "initial_devices_count": len(initial_devices)
                    if initial_devices
                    else 0,
                },
            )
            logger.error("Invalid query for device detection: %s", query)
            raise error from e
        except Exception as e:
            error = create_usb_error(
                query,
                "detect_device",
                e,
                {
                    "timeout": timeout,
                    "initial_devices_count": len(initial_devices)
                    if initial_devices
                    else 0,
                },
            )
            logger.error("Device detection failed: %s", e)
            raise error from e

    def list_matching_devices(self, query: str) -> list[BlockDevice]:
        """
        List all devices matching the query.

        Args:
            query: Query string to match devices

        Returns:
            List of matching BlockDevice objects

        Raises:
            ValueError: If the query string is invalid
            USBError: If there's an error retrieving devices
        """
        logger.debug("Listing devices matching query: %s", query)

        try:
            return self.detector.list_matching_devices(query)
        except ValueError as e:
            error = create_usb_error(query, "list_matching_devices", e, {})
            logger.error("Invalid query for device listing: %s", query)
            raise error from e
        except Exception as e:
            error = create_usb_error(query, "list_matching_devices", e, {})
            logger.error("Failed to list matching devices: %s", e)
            raise error from e

    def flash_device(
        self,
        device: BlockDevice,
        firmware_file: str | Path,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> bool:
        """
        Flash firmware to a specific device.

        Args:
            device: BlockDevice to flash
            firmware_file: Path to firmware file
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds

        Returns:
            True if flashing succeeded, False otherwise

        Raises:
            USBError: If firmware file doesn't exist or flashing fails after retries
        """
        firmware_path = Path(firmware_file)
        logger.info("Flashing device %s with firmware: %s", device.name, firmware_path)

        if not firmware_path.exists():
            error = create_usb_error(
                device.name,
                "flash_device",
                FileNotFoundError(f"Firmware file not found: {firmware_path}"),
                {
                    "firmware_path": str(firmware_path),
                    "max_retries": max_retries,
                    "retry_delay": retry_delay,
                    "device_model": device.model
                    if hasattr(device, "model")
                    else "unknown",
                },
            )
            logger.error("Firmware file not found: %s", firmware_path)
            raise error

        try:
            return mount_and_flash(device, firmware_path, max_retries, retry_delay)
        except Exception as e:
            error = create_usb_error(
                device.name,
                "flash_device",
                e,
                {
                    "firmware_path": str(firmware_path),
                    "max_retries": max_retries,
                    "retry_delay": retry_delay,
                    "device_model": device.model
                    if hasattr(device, "model")
                    else "unknown",
                },
            )
            logger.error("Failed to flash device %s: %s", device.name, e)
            raise error from e

    def get_all_devices(self, query: str = "") -> list[BlockDevice]:
        """
        Get all available block devices, optionally filtered by query.

        Args:
            query: Optional query string to filter devices

        Returns:
            List of all BlockDevice objects

        Raises:
            USBError: If there's an error retrieving devices
        """
        logger.debug("Getting all block devices")

        try:
            devices = self.lsdev.get_devices()
            if query:
                return self.detector.list_matching_devices(query)
            return devices
        except Exception as e:
            error = create_usb_error("all", "get_all_devices", e, {"query": query})
            logger.error("Failed to get block devices: %s", e)
            raise error from e

    def mount(self, device: BlockDevice) -> list[str]:
        """
        Mount a block device and return the mount points.

        Args:
            device: BlockDevice to mount

        Returns:
            List of mount points

        Raises:
            USBError: If there's an error mounting the device
        """
        logger.debug("Mounting device: %s", device.name)
        # This is a stub implementation
        # In a real implementation, this would use platform-specific code to mount the device
        return []

    def unmount(self, device: BlockDevice) -> bool:
        """
        Unmount a block device.

        Args:
            device: BlockDevice to unmount

        Returns:
            True if successful, False otherwise

        Raises:
            USBError: If there's an error unmounting the device
        """
        logger.debug("Unmounting device: %s", device.name)
        # This is a stub implementation
        # In a real implementation, this would use platform-specific code to unmount the device
        return True

    def copy_file(self, source: Path, destination: Path) -> bool:
        """
        Copy a file from source to destination.

        Args:
            source: Source path
            destination: Destination path

        Returns:
            True if successful, False otherwise

        Raises:
            USBError: If there's an error copying the file
        """
        logger.debug("Copying file from %s to %s", source, destination)
        try:
            import shutil

            shutil.copy2(source, destination)
            return True
        except Exception as e:
            error = create_usb_error(
                str(source),
                "copy_file",
                e,
                {"source": str(source), "destination": str(destination)},
            )
            logger.error("Failed to copy file: %s", e)
            raise error from e


def create_usb_adapter() -> USBAdapter:
    """
    Factory function to create a USBAdapter instance.

    Returns:
        Configured USBAdapter instance

    Example:
        >>> adapter = create_usb_adapter()
        >>> devices = adapter.get_all_devices()
        >>> print(f"Found {len(devices)} devices")
    """
    logger.debug("Creating USBAdapter")
    adapter: USBAdapter = USBAdapterImpl()
    return adapter
