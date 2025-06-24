"""Flash method implementations."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.protocols import FileAdapterProtocol, USBAdapterProtocol

from glovebox.config.flash_methods import USBFlashConfig
from glovebox.firmware.flash.models import BlockDevice, FlashResult


logger = logging.getLogger(__name__)


class USBFlasher:
    """USB-based firmware flasher implementation.

    Implements FlasherProtocol for type safety.
    """

    def __init__(
        self,
        usb_adapter: "USBAdapterProtocol",
        file_adapter: "FileAdapterProtocol",
    ):
        """Initialize USB flasher with dependencies."""
        self.usb_adapter = usb_adapter
        self.file_adapter = file_adapter

    def flash_device(
        self,
        device: BlockDevice,
        firmware_file: Path,
        config: USBFlashConfig,
    ) -> FlashResult:
        """Flash device using USB method."""
        logger.info("Starting USB flash operation for device: %s", device.name)
        result = FlashResult(success=True)

        try:
            # Validate inputs
            if not self._validate_inputs(device, firmware_file, config, result):
                return result

            # Check USB adapter availability
            if not self.check_available():
                result.success = False
                result.add_error("USB adapter is not available")
                return result

            # Mount the device with timeout
            logger.debug("Mounting device: %s", device.name)
            mount_points = self.usb_adapter.mount_device(device)

            if not mount_points or not mount_points[0]:
                result.success = False
                result.add_error(f"Failed to mount device: {device.path}")
                return result

            mount_point = Path(mount_points[0])
            logger.debug("Device mounted at: %s", mount_point)

            try:
                # Copy firmware to device with timeout
                logger.debug("Copying firmware to device")
                target_file = mount_point / firmware_file.name

                success = self.usb_adapter.copy_file(firmware_file, target_file)
                if not success:
                    result.success = False
                    result.add_error(f"Failed to copy firmware to {mount_point}")
                    return result

                # Sync filesystem if configured
                if config.sync_after_copy:
                    logger.debug("Syncing filesystem")
                    self._sync_device(mount_point)

                result.add_message(
                    f"Successfully flashed to {device.description or device.path}"
                )
                logger.info("USB flash completed successfully")

            finally:
                # Always unmount the device
                logger.debug("Unmounting device")
                self.usb_adapter.unmount_device(device)

        except Exception as e:
            logger.error("USB flash failed: %s", e)
            result.success = False
            result.add_error(f"USB flash failed: {str(e)}")

        return result

    def list_devices(self, config: USBFlashConfig) -> list[BlockDevice]:
        """List devices compatible with USB flashing."""
        try:
            logger.debug("Listing USB devices with query: %s", config.device_query)
            devices = self.usb_adapter.list_matching_devices(config.device_query)
            logger.debug("Found %d USB devices", len(devices))
            return devices
        except Exception as e:
            logger.error("Failed to list USB devices: %s", e)
            return []

    def check_available(self) -> bool:
        """Check if USB flasher is available."""
        try:
            # Check if USB adapter is available
            return hasattr(self.usb_adapter, "get_all_devices")
        except Exception:
            return False

    def validate_config(self, config: USBFlashConfig) -> bool:
        """Validate USB-specific configuration."""
        if not config.device_query:
            logger.error("Device query not specified")
            return False
        if config.mount_timeout <= 0:
            logger.error("Mount timeout must be positive")
            return False
        if config.copy_timeout <= 0:
            logger.error("Copy timeout must be positive")
            return False
        return True

    def _validate_inputs(
        self,
        device: BlockDevice,
        firmware_file: Path,
        config: USBFlashConfig,
        result: FlashResult,
    ) -> bool:
        """Validate flash inputs."""
        # Validate device
        if not device or not device.path:
            result.success = False
            result.add_error("Invalid device")
            return False

        # Validate firmware file
        if not self.file_adapter.check_exists(firmware_file):
            result.success = False
            result.add_error(f"Firmware file not found: {firmware_file}")
            return False

        # Validate configuration
        if not self.validate_config(config):
            result.success = False
            result.add_error("Invalid USB flash configuration")
            return False

        return True

    def _sync_device(self, mount_point: Path) -> None:
        """Sync device filesystem."""
        try:
            # Use the flash operations to sync
            if hasattr(self.usb_adapter, "_flash_ops"):
                flash_ops = self.usb_adapter._flash_ops
                if hasattr(flash_ops, "sync_filesystem"):
                    flash_ops.sync_filesystem(str(mount_point))
        except Exception as e:
            logger.warning("Failed to sync device filesystem: %s", e)


def create_usb_flasher(
    usb_adapter: "USBAdapterProtocol",
    file_adapter: "FileAdapterProtocol",
) -> USBFlasher:
    """Create a USBFlasher instance with explicit dependency injection.
    
    Args:
        usb_adapter: Required USB adapter for device operations
        file_adapter: Required file adapter for file operations
    
    Returns:
        Configured USBFlasher instance
    """
    return USBFlasher(
        usb_adapter=usb_adapter,
        file_adapter=file_adapter,
    )
