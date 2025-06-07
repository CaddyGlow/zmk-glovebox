"""Flash service for firmware flashing operations."""

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from glovebox.adapters.file_adapter import FileAdapter, create_file_adapter
from glovebox.adapters.usb_adapter import USBAdapter, create_usb_adapter
from glovebox.flash.lsdev import BlockDevice
from glovebox.models.results import FlashResult
from glovebox.services.base_service import BaseServiceImpl


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile


logger = logging.getLogger(__name__)


class FlashService(BaseServiceImpl):
    """Service for all firmware flashing operations.

    Responsible for USB device detection, firmware transfer to devices,
    and tracking flash operations across multiple devices.

    Attributes:
        usb_adapter: Adapter for USB device operations
        file_adapter: Adapter for file system operations
    """

    def __init__(
        self,
        usb_adapter: USBAdapter,
        file_adapter: FileAdapter,
        loglevel: str = "INFO",
    ):
        """Initialize flash service with explicit dependencies.

        Args:
            usb_adapter: USB adapter for device operations
            file_adapter: File adapter for file operations
            loglevel: Log level for subprocess operations (used when executing docker)
        """
        super().__init__(service_name="FlashService", service_version="1.0.0")
        self.usb_adapter = usb_adapter
        self.file_adapter = file_adapter
        self.loglevel = loglevel
        logger.debug(
            "FlashService initialized with USB adapter: %s, File adapter: %s, Log level: %s",
            type(self.usb_adapter).__name__,
            type(self.file_adapter).__name__,
            self.loglevel,
        )

    def flash_from_file(
        self,
        firmware_file_path: Path,
        profile: Optional["KeyboardProfile"] = None,
        query: str = "",
        timeout: int = 60,
        count: int = 1,
        track_flashed: bool = True,
    ) -> FlashResult:
        """
        Flash firmware from a file to devices matching the query.

        This method handles file existence checks before flashing.

        Args:
            firmware_file_path: Path to the firmware file to flash
            profile: KeyboardProfile with flash configuration
            query: Device query string (overrides profile-specific query)
            timeout: Timeout in seconds for waiting for devices
            count: Number of devices to flash (0 for unlimited)
            track_flashed: Whether to track which devices have been flashed

        Returns:
            FlashResult with details of the flash operation
        """
        logger.info(
            f"Starting firmware flash operation from file: {firmware_file_path}"
        )

        # Validate firmware file existence
        if not self.file_adapter.exists(firmware_file_path):
            result = FlashResult(success=False)
            result.add_error(f"Firmware file not found: {firmware_file_path}")
            return result

        # Call the main flash method with path already verified
        try:
            return self.flash(
                firmware_file=firmware_file_path,
                profile=profile,
                query=query,
                timeout=timeout,
                count=count,
                track_flashed=track_flashed,
                skip_file_check=True,  # Skip the duplicate file check
            )
        except Exception as e:
            logger.error(f"Error preparing flash operation: {e}")
            result = FlashResult(success=False)
            result.add_error(f"Flash preparation failed: {str(e)}")
            return result

    def flash(
        self,
        firmware_file: str | Path,
        profile: Optional["KeyboardProfile"] = None,
        query: str = "",
        timeout: int = 60,
        count: int = 1,
        track_flashed: bool = True,
        skip_file_check: bool = False,
    ) -> FlashResult:
        """
        Flash firmware to devices matching the query.

        Args:
            firmware_file: Path to the firmware file to flash
            profile: KeyboardProfile with flash configuration
            query: Device query string (overrides profile-specific query)
            timeout: Timeout in seconds for waiting for devices
            count: Number of devices to flash (0 for unlimited)
            track_flashed: Whether to track which devices have been flashed
            skip_file_check: Skip the file existence check (used by flash_from_file)

        Returns:
            FlashResult with details of the flash operation
        """
        logger.info("Starting firmware flash operation")
        result = FlashResult(success=True)

        # Convert firmware_file to Path if it's a string
        if isinstance(firmware_file, str):
            firmware_file = Path(firmware_file)

        # Validate firmware file if check not skipped
        if not skip_file_check and not self.file_adapter.exists(firmware_file):
            result.success = False
            result.add_error(f"Firmware file not found: {firmware_file}")
            return result

        # If query is empty, get default query from keyboard profile
        if not query:
            query = self._get_device_query_from_profile(profile)

        logger.info(f"Using device query: {query}")
        devices_flashed = 0
        devices_failed = 0
        flashed_devices = set()  # Track flashed devices

        try:
            # Use the original firmware file directly
            temp_firmware_file = firmware_file

            # Check if we're trying to flash multiple devices
            if count != 1:
                result.add_message(
                    f"Watching for {count if count > 0 else 'unlimited'} devices matching query: {query}"
                )
                result.add_message(f"Timeout: {timeout} seconds")
                result.add_message("Waiting for devices... (Ctrl+C to cancel)")

            # Track start time for timeout
            start_time = time.time()

            # Flash to the specified number of devices
            while (count == 0 or devices_flashed < count) and (
                time.time() - start_time < timeout
            ):
                # Find devices matching query
                # Note: In the future, we'll pass environment variables here
                devices = self.usb_adapter.get_all_devices(query)

                if not devices:
                    # No devices found, wait a bit and try again
                    time.sleep(0.5)
                    continue

                for device in devices:
                    # Skip already flashed devices if tracking is enabled
                    if track_flashed and device.serial in flashed_devices:
                        continue

                    # Flash to this device
                    device_result = self._flash_device(device, temp_firmware_file)

                    # Store detailed device info
                    device_details = {
                        "name": device.description or device.path,
                        "serial": device.serial,
                        "status": "success" if device_result.success else "failed",
                    }

                    if not device_result.success:
                        device_details["error"] = (
                            device_result.errors[0]
                            if device_result.errors
                            else "Unknown error"
                        )
                        devices_failed += 1
                    else:
                        devices_flashed += 1
                        if track_flashed:
                            flashed_devices.add(device.serial)

                    result.device_details.append(device_details)

                    # If we've flashed enough devices, break
                    if count > 0 and devices_flashed >= count:
                        break

                # Wait a bit before checking for more devices
                time.sleep(0.5)

            # Check if we timed out
            if (
                time.time() - start_time >= timeout
                and devices_flashed < count
                and count > 0
            ):
                result.add_message(f"Timeout after {timeout} seconds")

            # Update result with device counts
            result.devices_flashed = devices_flashed
            result.devices_failed = devices_failed

            # Overall success depends on whether we flashed any devices and if any failed
            if devices_flashed == 0:
                result.success = False
                result.add_error("No devices were flashed")
            elif devices_failed > 0:
                result.success = False
                result.add_error(f"{devices_failed} device(s) failed to flash")
            else:
                result.add_message(f"Successfully flashed {devices_flashed} device(s)")

        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            result.add_message("Operation cancelled by user")
            result.success = devices_flashed > 0
        except Exception as e:
            logger.error(f"Error in flash operation: {e}")
            result.success = False
            result.add_error(f"Flash operation failed: {str(e)}")

        return result

    def _flash_device(self, device: BlockDevice, firmware_file: Path) -> FlashResult:
        """
        Flash firmware to a specific device.

        Args:
            device: Block device to flash to
            firmware_file: Path to the firmware file

        Returns:
            FlashResult for this specific device
        """
        result = FlashResult(success=True)
        logger.info(f"Flashing to device: {device.description or device.path}")

        try:
            # Mount the device
            # Note: In the future, we'll pass environment variables here
            mount_point = self.usb_adapter.mount(device)
            if not mount_point or not mount_point[0]:
                result.success = False
                result.add_error(f"Failed to mount device: {device.path}")
                return result

            # Copy firmware to device
            # Note: In the future, we'll pass environment variables here
            success = self.usb_adapter.copy_file(
                firmware_file, Path(mount_point[0]) / firmware_file.name
            )
            if not success:
                result.success = False
                result.add_error(f"Failed to copy firmware to {mount_point[0]}")
                return result

            # Unmount the device
            # Note: In the future, we'll pass environment variables here
            self.usb_adapter.unmount(device)

            result.add_message(
                f"Successfully flashed to {device.description or device.path}"
            )

        except Exception as e:
            logger.error(f"Error flashing device {device.path}: {e}")
            result.success = False
            result.add_error(f"Error flashing device: {str(e)}")

        return result

    def list_devices_with_profile(
        self, profile_name: str, query: str = ""
    ) -> FlashResult:
        """
        List devices matching a query using a profile name.

        Args:
            profile_name: Name of the profile to use (e.g., 'glove80/v25.05')
            query: Device query string (overrides profile-specific query)

        Returns:
            FlashResult with details of matched devices
        """
        logger.info(f"Listing devices with profile: {profile_name}")
        result = FlashResult(success=False)

        try:
            # Create profile from name
            from glovebox.cli.helpers.profile import create_profile_from_option

            profile = create_profile_from_option(profile_name)

            # Use the profile-based method
            return self.list_devices(profile=profile, query=query)

        except Exception as e:
            logger.error(f"Error creating profile from name: {e}")
            result.add_error(f"Failed to create profile: {str(e)}")
            return result

    def list_devices(
        self, profile: Optional["KeyboardProfile"] = None, query: str = ""
    ) -> FlashResult:
        """
        List devices matching a query.

        Args:
            profile: KeyboardProfile with flash configuration
            query: Device query string (overrides profile-specific query)

        Returns:
            FlashResult with details of matched devices
        """
        result = FlashResult(success=True)

        # If query is empty, use the profile's query
        if not query and profile:
            query = self._get_device_query_from_profile(profile)

        try:
            # Find devices matching the query
            # Note: In the future, we'll pass environment variables here
            devices = self.usb_adapter.get_all_devices(query)

            if not devices:
                result.add_message("No devices found matching query")
                return result

            result.add_message(f"Found {len(devices)} device(s) matching query")

            # Add device details
            for device in devices:
                device_info = {
                    "name": device.description or device.path,
                    "serial": device.serial,
                    "vendor": device.vendor,
                    "model": device.model,
                    "path": device.path,
                    "removable": device.removable,
                    "status": "available",
                }
                result.device_details.append(device_info)

        except Exception as e:
            logger.error(f"Error listing devices: {e}")
            result.success = False
            result.add_error(f"Failed to list devices: {str(e)}")

        return result

    def _get_device_query_from_profile(
        self, profile: Optional["KeyboardProfile"]
    ) -> str:
        """Get the device query from the keyboard profile.

        Args:
            profile: KeyboardProfile with flash configuration

        Returns:
            Device query string to use
        """
        if not profile:
            # Default fallback query for glove80
            default_query = "vendor=Adafruit and serial~=GLV80-.* and removable=true"
            logger.warning(f"No profile provided, using default query: {default_query}")
            return default_query

        # Get flash configuration from profile
        flash_config = profile.keyboard_config.flash
        if flash_config and flash_config.query:
            return flash_config.query

        # Try to build a query from USB VID/PID if available
        if flash_config and flash_config.usb_vid and flash_config.usb_pid:
            query = f"vid={flash_config.usb_vid} and pid={flash_config.usb_pid} and removable=true"
            logger.info(f"Using VID/PID query: {query}")
            return query

        # Last resort: default query
        default_query = "removable=true"
        logger.warning(f"No query in profile, using fallback: {default_query}")
        return default_query


def create_flash_service(
    usb_adapter: USBAdapter | None = None,
    file_adapter: FileAdapter | None = None,
    loglevel: str = "INFO",
) -> FlashService:
    """Create a FlashService instance with optional dependency injection.

    This factory function provides a consistent way to create service instances
    with proper dependency injection. It allows for easier testing and
    configuration of services.

    Args:
        usb_adapter: Optional USB adapter for device operations
        file_adapter: Optional file adapter for file operations
        loglevel: Log level for subprocess operations (used when executing docker)

    Returns:
        Configured FlashService instance
    """
    # Create default adapters if not provided
    if usb_adapter is None:
        usb_adapter = create_usb_adapter()
    if file_adapter is None:
        file_adapter = create_file_adapter()

    # Return service with explicit dependencies
    return FlashService(
        usb_adapter=usb_adapter,
        file_adapter=file_adapter,
        loglevel=loglevel,
    )
