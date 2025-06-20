"""Refactored flash service using multi-method architecture."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

from glovebox.adapters.file_adapter import create_file_adapter
from glovebox.config.flash_methods import USBFlashConfig
from glovebox.firmware.flash.device_wait_service import create_device_wait_service
from glovebox.firmware.flash.models import FlashResult
from glovebox.firmware.method_registry import flasher_registry
from glovebox.protocols import FileAdapterProtocol
from glovebox.protocols.flash_protocols import FlasherProtocol


logger = logging.getLogger(__name__)


class FlashService:
    """USB firmware flash service for ZMK keyboards.

    This service provides USB-based firmware flashing for ZMK keyboards
    using mass storage device mounting.
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
        self.device_wait_service = create_device_wait_service()
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
        wait: bool = False,
        poll_interval: float = 0.5,
        show_progress: bool = True,
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
            wait: Wait for devices to connect before flashing
            poll_interval: Polling interval in seconds when waiting for devices
            show_progress: Show real-time device detection progress

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
            # Use the main flash method with wait parameters
            return self.flash(
                firmware_file=firmware_file_path,
                profile=profile,
                query=query,
                timeout=timeout,
                count=count,
                track_flashed=track_flashed,
                skip_existing=skip_existing,
                wait=wait,
                poll_interval=poll_interval,
                show_progress=show_progress,
            )
        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Error preparing flash operation: %s", e, exc_info=exc_info)
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
        wait: bool = False,
        poll_interval: float = 0.5,
        show_progress: bool = True,
    ) -> FlashResult:
        """Flash firmware to USB devices.

        Args:
            firmware_file: Path to the firmware file to flash
            profile: KeyboardProfile with flash configuration
            query: Device query string (overrides profile-specific query)
            timeout: Timeout in seconds for waiting for devices
            count: Number of devices to flash (0 for unlimited)
            track_flashed: Whether to track which devices have been flashed
            skip_existing: Whether to skip devices already present at startup
            wait: Wait for devices to connect before flashing
            poll_interval: Polling interval in seconds when waiting for devices
            show_progress: Show real-time device detection progress

        Returns:
            FlashResult with details of the flash operation
        """
        logger.info(
            "Starting firmware flash operation using method selection with wait=%s",
            wait,
        )
        result = FlashResult(success=True)

        try:
            # Convert firmware_file to Path if it's a string
            if isinstance(firmware_file, str):
                firmware_file = Path(firmware_file)

            # Get flash method configs from profile or use defaults
            flash_configs = self._get_flash_method_configs(profile, query)

            # Create USB flasher
            flasher = self._create_usb_flasher(flash_configs[0])

            logger.info("Selected flasher method: %s", type(flasher).__name__)

            # Get devices - either wait for them or list immediately
            if wait:
                # Use device wait service to wait for devices
                # Check if we have a USB flash config for device query
                device_query_to_use = query
                flash_config = flash_configs[0]

                if hasattr(flash_config, "device_query") and flash_config.device_query:
                    device_query_to_use = flash_config.device_query
                elif not device_query_to_use:
                    device_query_to_use = "removable=true"  # Default query

                # Use wait service with USB flash configs
                devices = self.device_wait_service.wait_for_devices(
                    target_count=count if count > 0 else 1,
                    timeout=float(timeout),
                    query=device_query_to_use,
                    flash_config=flash_config,
                    poll_interval=poll_interval,
                    show_progress=show_progress,
                )
            else:
                # List available devices immediately using the selected flasher
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
            if devices_flashed == 0 and devices_failed == 0:
                result.success = False
                result.add_error("No devices were flashed")
            elif devices_failed > 0:
                result.success = False
                if devices_flashed > 0:
                    result.add_error(
                        f"{devices_failed} device(s) failed to flash, {devices_flashed} succeeded"
                    )
                else:
                    result.add_error(f"{devices_failed} device(s) failed to flash")
            else:
                result.add_message(f"Successfully flashed {devices_flashed} device(s)")

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Flash operation failed: %s", e, exc_info=exc_info)
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
            flasher = self._create_usb_flasher(flash_configs[0])

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
    ) -> list[USBFlashConfig]:
        """Get flash method configurations from profile or defaults.

        Args:
            profile: KeyboardProfile with method configurations (optional)
            query: Device query string for default configuration

        Returns:
            List of flash method configurations to try
        """
        if (
            profile
            and hasattr(profile.keyboard_config, "flash_methods")
            and profile.keyboard_config.flash_methods
        ):
            # Use profile's flash method configurations
            return list(profile.keyboard_config.flash_methods)

        # Fallback: Create default USB configuration
        logger.debug("No profile flash methods, using default USB configuration")

        # Use provided query or get default from profile
        device_query = query
        if not device_query and profile:
            device_query = self._get_device_query_from_profile(profile)
        if not device_query:
            device_query = "removable=true"  # Default query

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
        """Get the device query from the keyboard profile flash methods.

        Args:
            profile: KeyboardProfile with flash configuration

        Returns:
            Device query string to use
        """
        if not profile:
            return "removable=true"

        # Try to get device query from first USB flash method
        for method in profile.keyboard_config.flash_methods:
            if hasattr(method, "device_query") and method.device_query:
                return method.device_query

        # Default query
        return "removable=true"

    def _create_usb_flasher(self, config: USBFlashConfig) -> FlasherProtocol:
        """Create USB flasher instance.

        Args:
            config: USB flash configuration

        Returns:
            Configured USB flasher instance

        Raises:
            RuntimeError: If USB flasher cannot be created
        """
        try:
            flasher = flasher_registry.create_method(
                "usb", config, file_adapter=self.file_adapter
            )
            # Check if flasher is available
            if hasattr(flasher, "check_available") and not flasher.check_available():
                raise RuntimeError("USB flasher is not available")
            return flasher
        except Exception as e:
            raise RuntimeError(f"Failed to create USB flasher: {e}") from e


def create_flash_service(
    file_adapter: FileAdapterProtocol | None = None,
    loglevel: str = "INFO",
) -> FlashService:
    """Create a FlashService instance for USB firmware flashing.

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
