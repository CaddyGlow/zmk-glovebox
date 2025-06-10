"""Refactored flash service using multi-method architecture."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

from glovebox.adapters.file_adapter import create_file_adapter
from glovebox.config.flash_methods import FlashMethodConfig, USBFlashConfig
from glovebox.firmware.flash.models import BlockDevice, FlashResult
from glovebox.firmware.method_selector import select_flasher_with_fallback
from glovebox.protocols import FileAdapterProtocol


logger = logging.getLogger(__name__)


class FlashService:
    """Refactored flash service using multi-method architecture.

    This service uses the method selection system to choose appropriate
    flash methods with automatic fallbacks.
    """

    def __init__(
        self,
        file_adapter: FileAdapterProtocol | None = None,
        loglevel: str = "INFO",
    ):
        """Initialize flash service with dependencies.

        Args:
            file_adapter: File adapter for file operations
            loglevel: Log level for flash operations
        """
        self._service_name = "FlashService"
        self._service_version = "2.0.0"
        self.file_adapter = file_adapter or create_file_adapter()
        self.loglevel = loglevel
        logger.debug(
            "FlashService v2 initialized with File adapter: %s, Log level: %s",
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
        skip_existing: bool = False,
    ) -> FlashResult:
        """Flash firmware from a file to devices using method selection.

        Args:
            firmware_file_path: Path to the firmware file to flash
            profile: KeyboardProfile with flash configuration
            query: Device query string (overrides profile-specific query)
            timeout: Timeout in seconds for waiting for devices
            count: Number of devices to flash (0 for unlimited)
            track_flashed: Whether to track which devices have been flashed
            skip_existing: Whether to skip devices already present at startup

        Returns:
            FlashResult with details of the flash operation
        """
        logger.info(
            "Starting firmware flash operation from file: %s", firmware_file_path
        )

        # Validate firmware file existence
        if not self.file_adapter.check_exists(firmware_file_path):
            result = FlashResult(success=False)
            result.add_error(f"Firmware file not found: {firmware_file_path}")
            return result

        try:
            # Use the main flash method
            return self.flash(
                firmware_file=firmware_file_path,
                profile=profile,
                query=query,
                timeout=timeout,
                count=count,
                track_flashed=track_flashed,
                skip_existing=skip_existing,
            )
        except Exception as e:
            logger.error("Error preparing flash operation: %s", e)
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
        skip_existing: bool = False,
    ) -> FlashResult:
        """Flash firmware using method selection with fallbacks.

        Args:
            firmware_file: Path to the firmware file to flash
            profile: KeyboardProfile with flash configuration
            query: Device query string (overrides profile-specific query)
            timeout: Timeout in seconds for waiting for devices
            count: Number of devices to flash (0 for unlimited)
            track_flashed: Whether to track which devices have been flashed
            skip_existing: Whether to skip devices already present at startup

        Returns:
            FlashResult with details of the flash operation
        """
        logger.info("Starting firmware flash operation using method selection")
        result = FlashResult(success=True)

        try:
            # Convert firmware_file to Path if it's a string
            if isinstance(firmware_file, str):
                firmware_file = Path(firmware_file)

            # Get flash method configs from profile or use defaults
            flash_configs = self._get_flash_method_configs(profile, query)

            # Select the best available flasher with fallbacks
            flasher = select_flasher_with_fallback(flash_configs)

            logger.info("Selected flasher method: %s", type(flasher).__name__)

            # List available devices using the selected flasher
            devices = flasher.list_devices(flash_configs[0])

            if not devices:
                result.success = False
                result.add_error("No compatible devices found")
                return result

            # Flash to available devices (simplified approach)
            devices_flashed = 0
            devices_failed = 0

            for device in devices[: count if count > 0 else len(devices)]:
                logger.info("Flashing device: %s", device.description or device.name)

                device_result = flasher.flash_device(
                    device=device,
                    firmware_file=firmware_file,
                    config=flash_configs[0],
                )

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

                result.device_details.append(device_details)

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

        except Exception as e:
            logger.error("Flash operation failed: %s", e)
            result.success = False
            result.add_error(f"Flash operation failed: {str(e)}")

        return result

    def list_devices(
        self,
        profile: Optional["KeyboardProfile"] = None,
        query: str = "",
    ) -> FlashResult:
        """List devices using method selection.

        Args:
            profile: KeyboardProfile with flash configuration
            query: Device query string (overrides profile-specific query)

        Returns:
            FlashResult with details of matched devices
        """
        result = FlashResult(success=True)

        try:
            # Get flash method configs from profile or use defaults
            flash_configs = self._get_flash_method_configs(profile, query)

            # Select the best available flasher
            flasher = select_flasher_with_fallback(flash_configs)

            logger.info("Using flasher method: %s", type(flasher).__name__)

            # List devices using the selected flasher
            devices = flasher.list_devices(flash_configs[0])

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
            logger.error("Error listing devices: %s", e)
            result.success = False
            result.add_error(f"Failed to list devices: {str(e)}")

        return result

    def _get_flash_method_configs(
        self,
        profile: Optional["KeyboardProfile"],
        query: str,
    ) -> list[FlashMethodConfig]:
        """Get flash method configurations from profile or defaults.

        Args:
            profile: KeyboardProfile with method configurations (optional)
            query: Device query string for fallback configuration

        Returns:
            List of flash method configurations to try
        """
        if profile and hasattr(profile.keyboard_config, "flash_methods"):
            # Use profile's flash method configurations
            return list(profile.keyboard_config.flash_methods)

        # Fallback: Create default USB configuration
        logger.debug("No profile flash methods, using default USB configuration")

        # Use provided query or get default from profile
        device_query = query
        if not device_query and profile:
            device_query = self._get_device_query_from_profile(profile)
        if not device_query:
            device_query = "removable=true"  # Default fallback

        # Create default USB flash config
        default_config = USBFlashConfig(
            device_query=device_query,
            mount_timeout=30,
            copy_timeout=60,
            sync_after_copy=True,
        )

        return [default_config]

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
            return "removable=true"

        # Get flash configuration from profile
        flash_config = profile.keyboard_config.flash
        if flash_config and flash_config.query:
            return flash_config.query

        # Try to build a query from USB VID/PID if available
        if flash_config and flash_config.usb_vid and flash_config.usb_pid:
            query = f"vid={flash_config.usb_vid} and pid={flash_config.usb_pid} and removable=true"
            logger.info("Using VID/PID query: %s", query)
            return query

        # Last resort: default query
        return "removable=true"


def create_flash_service(
    file_adapter: FileAdapterProtocol | None = None,
    loglevel: str = "INFO",
) -> FlashService:
    """Create a FlashService instance with the multi-method architecture.

    Args:
        file_adapter: Optional FileAdapterProtocol instance for file operations
        loglevel: Log level for flash operations

    Returns:
        Configured FlashService instance
    """
    return FlashService(
        file_adapter=file_adapter,
        loglevel=loglevel,
    )
