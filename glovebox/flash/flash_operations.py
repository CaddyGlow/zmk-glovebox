"""High-level flash operations using OS abstraction layer."""

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional


if TYPE_CHECKING:
    from glovebox.protocols.flash_os_protocol import FlashOSProtocol

from glovebox.core.errors import FlashError
from glovebox.flash.lsdev import BlockDevice
from glovebox.flash.os_adapters import create_flash_os_adapter
from glovebox.models.results import FlashResult


logger = logging.getLogger(__name__)


class FlashOperations:
    """High-level flash operations using OS abstraction."""

    def __init__(self, os_adapter: Optional["FlashOSProtocol"] = None):
        """Initialize flash operations.

        Args:
            os_adapter: Optional OS adapter, defaults to platform-specific adapter
        """
        self._os_adapter = os_adapter or create_flash_os_adapter()
        logger.debug(
            f"FlashOperations initialized with OS adapter: {type(self._os_adapter).__name__}"
        )

    def mount_and_flash(
        self,
        device: BlockDevice,
        firmware_file: Path,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> bool:
        """Mount device and flash firmware with retry logic.

        Args:
            device: BlockDevice object representing the target device
            firmware_file: Path to firmware file to flash
            max_retries: Maximum number of retries
            retry_delay: Delay between retries in seconds

        Returns:
            True if flashing succeeded, False otherwise

        Raises:
            FileNotFoundError: If firmware file is not found
            FlashError: If flashing fails after all retries
        """
        firmware_path = Path(firmware_file).resolve()
        if not firmware_path.exists():
            raise FileNotFoundError(f"Firmware file not found: {firmware_path}")

        device_identifier = (
            f"{device.serial}_{device.label}" if device.serial else device.label
        )

        for attempt in range(max_retries):
            try:
                logger.info(
                    f"Attempt {attempt + 1}/{max_retries}: Mounting device {device.name} ({device_identifier})..."
                )

                # Mount the device
                mount_points = self._os_adapter.mount_device(device)
                if not mount_points:
                    logger.warning(f"No mount points returned for device {device.name}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    else:
                        return False

                mount_point = mount_points[0]  # Use first mount point
                logger.info(f"Device {device_identifier} mounted at {mount_point}")

                # Copy the firmware file
                success = self._os_adapter.copy_firmware_file(
                    firmware_path, mount_point
                )
                if not success:
                    logger.error(f"Failed to copy firmware to {mount_point}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    else:
                        return False

                logger.info("Firmware file copied successfully.")

                # Sync filesystem
                self._os_adapter.sync_filesystem(mount_point)

                # Try to unmount (device might disconnect quickly)
                try:
                    self._os_adapter.unmount_device(device)
                except Exception as e:
                    logger.debug(f"Unmount failed (likely expected): {e}")

                return True  # Flash successful

            except PermissionError as e:
                logger.error(f"Permission error during mount/flash: {e}")
                raise FlashError(f"Permission denied: {e}") from e
            except OSError as e:
                logger.error(f"OS error during mount/flash attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    raise FlashError(
                        f"Failed to flash after retries due to OS error: {e}"
                    ) from e
            except Exception as e:
                logger.error(
                    f"Unexpected error during mount/flash attempt {attempt + 1}: {e}"
                )
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    raise FlashError(
                        f"Failed to flash after retries due to unexpected error: {e}"
                    ) from e

        return False  # Should only be reached if all retries fail without raising


def create_flash_operations(
    os_adapter: Optional["FlashOSProtocol"] = None,
) -> FlashOperations:
    """Factory function to create FlashOperations instance.

    Args:
        os_adapter: Optional OS adapter, defaults to platform-specific adapter

    Returns:
        Configured FlashOperations instance
    """
    return FlashOperations(os_adapter=os_adapter)
