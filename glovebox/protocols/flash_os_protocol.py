"""Protocol definitions for OS-specific flash operations."""

from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable


if TYPE_CHECKING:
    from glovebox.firmware.flash.models import BlockDevice


@runtime_checkable
class FlashOSProtocol(Protocol):
    """Protocol for OS-specific flash operations.

    This protocol defines the interface for platform-specific operations
    needed for firmware flashing, such as device mounting and file copying.
    """

    @abstractmethod
    def get_device_path(self, device_name: str) -> str:
        """Get the full device path for a device name.

        Args:
            device_name: Device name (e.g., 'sda', 'disk2')

        Returns:
            Full device path (e.g., '/dev/sda', '/dev/disk2')

        Raises:
            OSError: If the device path cannot be determined
        """
        ...

    @abstractmethod
    def mount_device(self, device: "BlockDevice") -> list[str]:
        """Mount a block device and return mount points.

        Args:
            device: BlockDevice to mount

        Returns:
            List of mount points where the device was mounted

        Raises:
            OSError: If mounting fails
        """
        ...

    @abstractmethod
    def unmount_device(self, device: "BlockDevice") -> bool:
        """Unmount a block device.

        Args:
            device: BlockDevice to unmount

        Returns:
            True if successful, False otherwise

        Raises:
            OSError: If unmounting fails
        """
        ...

    @abstractmethod
    def copy_firmware_file(self, firmware_file: Path, mount_point: str) -> bool:
        """Copy firmware file to mounted device.

        Args:
            firmware_file: Path to firmware file
            mount_point: Device mount point

        Returns:
            True if successful, False otherwise

        Raises:
            OSError: If copying fails
        """
        ...

    @abstractmethod
    def sync_filesystem(self, mount_point: str) -> bool:
        """Sync filesystem to ensure data is written.

        Args:
            mount_point: Mount point to sync

        Returns:
            True if successful, False otherwise
        """
        ...
