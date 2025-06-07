"""USB adapter for device detection and flashing operations."""

import logging
import threading
import time
from pathlib import Path
from typing import Any

from glovebox.core.errors import FlashError, USBError
from glovebox.flash.detect import DeviceDetector
from glovebox.flash.lsdev import BlockDevice, Lsdev
from glovebox.flash.usb import mount_and_flash
from glovebox.protocols.usb_adapter_protocol import USBAdapterProtocol
from glovebox.utils.error_utils import create_usb_error


logger = logging.getLogger(__name__)


class USBAdapterImpl:
    """Implementation of USB adapter."""

    def __init__(self) -> None:
        """Initialize the USB adapter."""
        self._detector: DeviceDetector | None = None
        self._lsdev: Lsdev | None = None
        self._lock = threading.RLock()
        logger.debug("USBAdapter initialized")

    @property
    def detector(self) -> DeviceDetector:
        """Get or create the detector instance."""
        if self._detector is None:
            self._detector = DeviceDetector()
        return self._detector

    @property
    def lsdev(self) -> Lsdev:
        """Get or create the lsdev instance."""
        if self._lsdev is None:
            self._lsdev = Lsdev()
        return self._lsdev

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
            if query:
                return self.detector.list_matching_devices(query)
            else:
                return self.lsdev.get_devices()
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

        # Check if device already has mount points
        if device.mountpoints:
            mount_points = list(device.mountpoints.values())
            logger.debug("Device already mounted at: %s", mount_points)
            return mount_points

        # Platform-specific mounting
        import platform
        import subprocess

        mount_points = []

        try:
            if platform.system() == "Darwin":  # macOS
                # Use diskutil to mount the device
                logger.debug(
                    "Attempting to mount device %s using diskutil", device.name
                )

                # First try to mount the whole disk
                result = subprocess.run(
                    ["diskutil", "mount", device.name], capture_output=True, text=True
                )

                if result.returncode == 0:
                    # Parse the output to get the mount point
                    output = result.stdout.strip()
                    if "mounted on" in output:
                        mount_point = output.split("mounted on")[-1].strip()
                        mount_points.append(mount_point)
                        logger.info(
                            "Successfully mounted %s at %s", device.name, mount_point
                        )
                else:
                    # Try mounting partitions if whole disk mount failed
                    logger.debug("Whole disk mount failed, trying partitions")
                    for partition in device.partitions:
                        result = subprocess.run(
                            ["diskutil", "mount", partition],
                            capture_output=True,
                            text=True,
                        )
                        if result.returncode == 0:
                            output = result.stdout.strip()
                            if "mounted on" in output:
                                mount_point = output.split("mounted on")[-1].strip()
                                mount_points.append(mount_point)
                                logger.info(
                                    "Successfully mounted partition %s at %s",
                                    partition,
                                    mount_point,
                                )

                if not mount_points:
                    logger.warning("No mount points found for device %s", device.name)

            elif platform.system() == "Linux":
                # Use udisksctl for Linux (modern approach)
                logger.debug("Attempting to mount device %s using udisksctl", device.name)
                
                # Try to mount the whole device first
                result = subprocess.run(
                    ["udisksctl", "mount", "-b", device.device_node],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    # Parse the output to get the mount point
                    output = result.stdout.strip()
                    if "Mounted" in output and "at" in output:
                        mount_point = output.split("at")[-1].strip()
                        mount_points.append(mount_point)
                        logger.info("Successfully mounted %s at %s", device.name, mount_point)
                else:
                    # Try mounting partitions if whole device mount failed
                    logger.debug("Whole device mount failed, trying partitions")
                    for partition in device.partitions:
                        result = subprocess.run(
                            ["udisksctl", "mount", "-b", f"/dev/{partition}"],
                            capture_output=True,
                            text=True
                        )
                        if result.returncode == 0:
                            output = result.stdout.strip()
                            if "Mounted" in output and "at" in output:
                                mount_point = output.split("at")[-1].strip()
                                mount_points.append(mount_point)
                                logger.info("Successfully mounted partition %s at %s", partition, mount_point)
                
                if not mount_points:
                    logger.warning("No mount points found for device %s", device.name)
            else:
                logger.warning(
                    "Unsupported platform for mounting: %s", platform.system()
                )

        except subprocess.CalledProcessError as e:
            error = create_usb_error(
                device.name, "mount", e, {"stdout": e.stdout, "stderr": e.stderr}
            )
            logger.error("Failed to mount device %s: %s", device.name, e)
            raise error from e
        except Exception as e:
            error = create_usb_error(device.name, "mount", e)
            logger.error("Unexpected error mounting device %s: %s", device.name, e)
            raise error from e

        return mount_points

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
        
        # Platform-specific unmounting
        import platform
        import subprocess
        
        try:
            if platform.system() == "Darwin":  # macOS
                # Use diskutil to unmount the device
                logger.debug("Attempting to unmount device %s using diskutil", device.name)
                
                unmounted = False
                
                # Try to unmount all mount points for this device
                if device.mountpoints:
                    for mount_point in device.mountpoints.values():
                        result = subprocess.run(
                            ["diskutil", "unmount", mount_point],
                            capture_output=True,
                            text=True
                        )
                        if result.returncode == 0:
                            logger.info("Successfully unmounted %s from %s", device.name, mount_point)
                            unmounted = True
                        else:
                            logger.warning("Failed to unmount %s from %s: %s", device.name, mount_point, result.stderr)
                
                # Also try unmounting by device name
                result = subprocess.run(
                    ["diskutil", "unmount", device.name],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    logger.info("Successfully unmounted device %s", device.name)
                    unmounted = True
                
                return unmounted
                
            elif platform.system() == "Linux":
                # Use udisksctl for Linux
                logger.debug("Attempting to unmount device %s using udisksctl", device.name)
                
                unmounted = False
                
                # Try to unmount all mount points for this device
                if device.mountpoints:
                    for partition, mount_point in device.mountpoints.items():
                        # Try udisksctl first (modern way)
                        result = subprocess.run(
                            ["udisksctl", "unmount", "-b", f"/dev/{partition}"],
                            capture_output=True,
                            text=True
                        )
                        if result.returncode == 0:
                            logger.info("Successfully unmounted partition %s from %s", partition, mount_point)
                            unmounted = True
                        else:
                            # Fallback to umount command
                            result = subprocess.run(
                                ["umount", mount_point],
                                capture_output=True,
                                text=True
                            )
                            if result.returncode == 0:
                                logger.info("Successfully unmounted %s using umount", mount_point)
                                unmounted = True
                            else:
                                logger.warning("Failed to unmount %s: %s", mount_point, result.stderr)
                
                return unmounted
                
            else:
                logger.warning("Unsupported platform for unmounting: %s", platform.system())
                return False
                
        except subprocess.CalledProcessError as e:
            error = create_usb_error(
                device.name,
                "unmount", 
                e,
                {"stdout": e.stdout, "stderr": e.stderr}
            )
            logger.error("Failed to unmount device %s: %s", device.name, e)
            raise error from e
        except Exception as e:
            error = create_usb_error(device.name, "unmount", e)
            logger.error("Unexpected error unmounting device %s: %s", device.name, e)
            raise error from e

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


def create_usb_adapter() -> USBAdapterProtocol:
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
    adapter: USBAdapterProtocol = USBAdapterImpl()
    return adapter
