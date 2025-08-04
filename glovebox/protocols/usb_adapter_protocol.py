"""Protocol definition for USB device operations."""

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable


if TYPE_CHECKING:
    from glovebox.firmware.flash.models import BlockDevice, USBDeviceType
    from glovebox.protocols.device_detector_protocol import DeviceDetectorProtocol


@runtime_checkable
class USBAdapterProtocol(Protocol):
    """Protocol for USB device operations."""

    @property
    def detector(self) -> "DeviceDetectorProtocol":
        """Get the device detector instance."""
        ...

    def detect_device(
        self,
        query: str,
        timeout: int = 60,
        initial_devices: list["BlockDevice"] | None = None,
    ) -> "USBDeviceType":
        """Detect a USB device matching the query.

        Args:
            query: Query string to match devices
            timeout: Maximum time to wait in seconds
            initial_devices: Optional list of devices to exclude from detection

        Returns:
            The first matching USB device

        Raises:
            USBError: If no matching device is found within the timeout
        """
        ...

    def list_matching_devices(self, query: str) -> list["USBDeviceType"]:
        """List all devices matching the query.

        Args:
            query: Query string to match devices

        Returns:
            List of matching USB device objects

        Raises:
            USBError: If there's an error retrieving devices
        """
        ...

    def flash_device(
        self,
        device: "BlockDevice",
        firmware_file: str | Path,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> bool:
        """Flash firmware to a specific device.

        Args:
            device: BlockDevice to flash
            firmware_file: Path to firmware file
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds

        Returns:
            True if flashing succeeded, False otherwise

        Raises:
            USBError: If firmware file doesn't exist or flashing fails
        """
        ...

    def get_all_devices(self, query: str = "") -> list["USBDeviceType"]:
        """Get all available USB devices, optionally filtered by query.

        Args:
            query: Optional query string to filter devices

        Returns:
            List of all USB device objects

        Raises:
            USBError: If there's an error retrieving devices
        """
        ...

    def mount_device(self, device: "BlockDevice") -> list[str]:
        """Mount a block device and return the mount points.

        Args:
            device: BlockDevice to mount

        Returns:
            List of mount points

        Raises:
            USBError: If there's an error mounting the device
        """
        ...

    def unmount_device(self, device: "BlockDevice") -> bool:
        """Unmount a block device.

        Args:
            device: BlockDevice to unmount

        Returns:
            True if successful, False otherwise

        Raises:
            USBError: If there's an error unmounting the device
        """
        ...

    def copy_file(self, source: Path, destination: Path) -> bool:
        """Copy a file from source to destination.

        Args:
            source: Source path
            destination: Destination path

        Returns:
            True if successful, False otherwise

        Raises:
            USBError: If there's an error copying the file
        """
        ...
