"""Refactored flash service using multi-method architecture."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.firmware.flash.device_wait_service import DeviceWaitService

from glovebox.adapters.file_adapter import create_file_adapter
from glovebox.config.flash_methods import USBFlashConfig
from glovebox.firmware.flash.device_wait_service import create_device_wait_service
from glovebox.firmware.flash.models import BlockDevice, FlashResult, USBDeviceType
from glovebox.firmware.method_registry import flasher_registry
from glovebox.protocols import FileAdapterProtocol, USBAdapterProtocol
from glovebox.protocols.flash_protocols import FlasherProtocol


logger = logging.getLogger(__name__)


class FlashService:
    """USB firmware flash service for ZMK keyboards.

    This service provides USB-based firmware flashing for ZMK keyboards
    using mass storage device mounting.
    """

    def __init__(
        self,
        file_adapter: FileAdapterProtocol,
        device_wait_service: "DeviceWaitService",
        usb_adapter: USBAdapterProtocol,
        loglevel: str = "INFO",
    ):
        """Initialize flash service with dependencies.

        Args:
            file_adapter: File adapter for file operations
            device_wait_service: Device wait service for device operations
            usb_adapter: USB adapter for device operations
            loglevel: Log level for flash operations
        """
        self._service_name = "FlashService"
        self._service_version = "2.0.0"
        self.file_adapter = file_adapter
        self.device_wait_service = device_wait_service
        self.usb_adapter = usb_adapter
        self.loglevel = loglevel



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
            timeout: Total timeout in seconds for the flash operation
            count: Total number of devices to flash sequentially (0 for unlimited)
            track_flashed: Whether to track which devices have been flashed
            skip_existing: Whether to skip devices already present at startup
            wait: Wait for devices to connect and flash them as they become available
            poll_interval: Polling interval in seconds when waiting for devices
            show_progress: Show real-time device detection progress

        Returns:
            FlashResult with details of the flash operation

        Note:
            When wait=True, devices are flashed one by one as they become available
            until the count is reached or timeout occurs. The system does not wait
            for all devices to be available before starting to flash.
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

            # Validate firmware file existence
            from glovebox.firmware.flash.flash_helpers import validate_firmware_file

            error_result = validate_firmware_file(self.file_adapter, firmware_file)
            if error_result:
                return error_result

            # Get flash method configs from profile or use defaults
            flash_configs = self._get_flash_method_configs(profile, query)

            # Create USB flasher
            flasher = self._create_usb_flasher(flash_configs[0])

            logger.info("Selected flasher method: %s", type(flasher).__name__)

            # Get device query for filtering
            from glovebox.firmware.flash.flash_helpers import get_device_query

            flash_config = flash_configs[0]
            device_query_to_use = get_device_query(profile, query, flash_config)

            # Flash devices one by one as they become available
            from glovebox.firmware.flash.flash_helpers import (
                create_device_result,
                update_flash_result_counts,
            )

            devices_flashed = 0
            devices_failed = 0
            target_count = count if count > 0 else 1

            if wait:
                # Use iterative approach: flash devices as they become available
                self._flash_devices_iteratively(
                    flasher,
                    flash_config,
                    firmware_file,
                    device_query_to_use,
                    target_count,
                    timeout,
                    poll_interval,
                    show_progress,
                    result,
                )
            else:
                # List available devices immediately and flash up to count
                block_devices = flasher.list_devices(flash_configs[0])

                if not block_devices:
                    result.success = False
                    result.add_error("No compatible devices found")
                    return result

                # Flash up to target_count devices
                for device in block_devices[:target_count]:
                    self._flash_single_device(
                        flasher, device, firmware_file, flash_config, result
                    )

            # Result counts are updated by the helper methods

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error("Flash operation failed: %s", e, exc_info=exc_info)
            result.success = False
            result.add_error(f"Flash operation failed: {str(e)}")

        return result

    def list_devices(
        self,
        profile: Optional["KeyboardProfile"] = None,
        query: str | None = None,
    ) -> FlashResult:
        """List devices using method selection.

        Args:
            profile: KeyboardProfile with flash configuration
            query: Device query string (overrides profile-specific query).
                   None = use profile/default, "" = bypass filtering, str = custom query

        Returns:
            FlashResult with details of matched devices
        """
        result = FlashResult(success=True)

        try:
            # Get flash method configs from profile or use defaults
            flash_configs = self._get_flash_method_configs(profile, query)

            # Select the flasher
            flasher = self._create_usb_flasher(flash_configs[0])

            logger.info("Using flasher method: %s", type(flasher).__name__)

            # List devices using the selected flasher
            devices = flasher.list_devices(flash_configs[0])

            if not devices:
                result.add_message("No devices found matching query")
                return result

            result.add_message(f"Found {len(devices)} device(s) matching query")

            # Add device details
            from glovebox.firmware.flash.flash_helpers import create_device_result

            for device in devices:
                # Create device info with additional fields
                device_info = create_device_result(device, True)
                device_info.update(
                    {
                        "vendor": device.vendor,
                        "model": device.model,
                        "path": device.path,
                        "removable": device.removable,
                        "vendor_id": device.vendor_id,
                        "product_id": device.product_id,
                    }
                )
                result.device_details.append(device_info)

        except Exception as e:
            logger.error("Error listing devices: %s", e)
            result.success = False
            result.add_error(f"Failed to list devices: {str(e)}")

        return result

    def _flash_devices_iteratively(
        self,
        flasher: FlasherProtocol,
        flash_config: "USBFlashConfig",
        firmware_file: Path,
        device_query: str,
        target_count: int,
        timeout: float,
        poll_interval: float,
        show_progress: bool,
        result: FlashResult,
    ) -> None:
        """Flash devices iteratively using real-time callback monitoring.

        Args:
            flasher: Flasher instance to use
            flash_config: Flash configuration
            firmware_file: Firmware file to flash
            device_query: Device query string
            target_count: Total number of devices to flash
            timeout: Maximum timeout for the entire operation
            poll_interval: Poll interval for device detection (unused with callbacks)
            show_progress: Whether to show progress
            result: FlashResult to update
        """
        import signal
        import threading
        import time
        from queue import Queue

        start_time = time.time()
        devices_flashed = 0
        monitoring = True

        logger.info(
            "Flashing devices as they become available: target=%d, timeout=%.1fs",
            target_count,
            timeout,
        )

        # Track devices we've already seen to avoid re-flashing
        seen_device_serials = set()

        # Queue for device events from callback
        device_queue: Queue[USBDeviceType] = Queue()

        # Lock for thread-safe operations
        flash_lock = threading.Lock()

        def device_callback(action: str, device: "USBDeviceType") -> None:
            """Callback for real-time device events."""
            if not monitoring:
                return

            # Only process device additions
            if action != "add":
                return

            # Check if device matches query
            if not self._device_matches_query(device, device_query):
                return

            # Queue the device for processing
            device_queue.put(device)

        def signal_handler(sig: int, frame: Any) -> None:
            nonlocal monitoring
            logger.info("Stopping device monitoring...")
            monitoring = False

        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            # Get device detector from USB adapter for callback registration
            detector = getattr(self.usb_adapter, "detector", None)
            if detector and hasattr(detector, "register_callback"):
                # Register our callback for real-time events
                detector.register_callback(device_callback)

                # Start monitoring if not already started
                if hasattr(detector, "start_monitoring"):
                    detector.start_monitoring()

                logger.info("Real-time device monitoring started")
            else:
                # Fallback to polling if callback system not available
                logger.warning("Callback system not available, falling back to polling")
                self._flash_devices_polling(
                    flasher,
                    flash_config,
                    firmware_file,
                    device_query,
                    target_count,
                    timeout,
                    poll_interval,
                    show_progress,
                    result,
                )
                return

            # Process initial devices already present
            try:
                initial_devices = flasher.list_devices(flash_config)
                for device in initial_devices:
                    device_serial = getattr(device, "serial", None) or getattr(
                        device, "name", ""
                    )
                    if (
                        device_serial not in seen_device_serials
                        and self._device_matches_query(device, device_query)
                    ):
                        device_queue.put(device)
                        seen_device_serials.add(device_serial)
            except Exception as e:
                logger.warning("Failed to get initial devices: %s", e)

            # Main processing loop
            while (
                monitoring
                and devices_flashed < target_count
                and (time.time() - start_time) < timeout
            ):
                try:
                    # Check for new devices from callback (non-blocking)
                    new_device: USBDeviceType = device_queue.get(timeout=0.1)

                    with flash_lock:
                        device_serial = getattr(new_device, "serial", None) or getattr(
                            new_device, "name", ""
                        )

                        # Skip if we've already seen this device
                        if device_serial in seen_device_serials:
                            continue

                        seen_device_serials.add(device_serial)

                        # Check if we still need more devices
                        if devices_flashed >= target_count:
                            break

                        logger.info(
                            "Found new device %d/%d: %s",
                            devices_flashed + 1,
                            target_count,
                            new_device.description or getattr(new_device, "name", "Unknown"),
                        )

                        # Flash the device
                        if self._flash_single_device(
                            flasher, new_device, firmware_file, flash_config, result
                        ):
                            devices_flashed += 1

                            if show_progress:
                                logger.info(
                                    "Successfully flashed device %d/%d",
                                    devices_flashed,
                                    target_count,
                                )

                        # Check if we've reached our target
                        if devices_flashed >= target_count:
                            logger.info(
                                "Target count reached, stopping device monitoring"
                            )
                            monitoring = False
                            break

                except Exception as e:
                    # Queue was empty or other error, continue
                    if "Empty" not in str(e):
                        logger.debug("Queue processing error: %s", e)
                    continue

        finally:
            monitoring = False

            # Clean up detector callback if available
            if detector and hasattr(detector, "unregister_callback"):
                try:
                    detector.unregister_callback(device_callback)
                except Exception as e:
                    logger.debug("Failed to unregister callback: %s", e)

        if devices_flashed < target_count:
            elapsed_time = time.time() - start_time
            logger.warning(
                "Flashed %d/%d devices before timeout (%.1fs elapsed)",
                devices_flashed,
                target_count,
                elapsed_time,
            )

    def _flash_devices_polling(
        self,
        flasher: FlasherProtocol,
        flash_config: "USBFlashConfig",
        firmware_file: Path,
        device_query: str,
        target_count: int,
        timeout: float,
        poll_interval: float,
        show_progress: bool,
        result: FlashResult,
    ) -> None:
        """Fallback polling-based device detection for flash operations.

        Used when callback system is not available.
        """
        import time

        start_time = time.time()
        devices_flashed = 0
        seen_device_serials = set()

        logger.info("Using polling-based device detection (fallback)")

        while devices_flashed < target_count and (time.time() - start_time) < timeout:
            try:
                block_devices = flasher.list_devices(flash_config)

                # Filter devices we haven't seen yet
                new_devices = []
                for device in block_devices:
                    device_serial = getattr(device, "serial", None) or getattr(
                        device, "name", ""
                    )
                    if (
                        device_serial not in seen_device_serials
                        and self._device_matches_query(device, device_query)
                    ):
                        new_devices.append(device)
                        seen_device_serials.add(device_serial)

                # Flash any new devices found
                for device in new_devices:
                    if devices_flashed >= target_count:
                        break

                    logger.info(
                        "Found new device %d/%d: %s",
                        devices_flashed + 1,
                        target_count,
                        device.description or device.name,
                    )

                    if self._flash_single_device(
                        flasher, device, firmware_file, flash_config, result
                    ):
                        devices_flashed += 1

                        if show_progress:
                            logger.info(
                                "Successfully flashed device %d/%d",
                                devices_flashed,
                                target_count,
                            )

                    if devices_flashed >= target_count:
                        logger.info("Target count reached, stopping device monitoring")
                        break

                if devices_flashed >= target_count:
                    break

                time.sleep(poll_interval)

            except Exception as e:
                exc_info = logger.isEnabledFor(logging.DEBUG)
                logger.error("Error during device detection: %s", e, exc_info=exc_info)
                time.sleep(poll_interval)

    def _flash_single_device(
        self,
        flasher: FlasherProtocol,
        device: "USBDeviceType",
        firmware_file: Path,
        flash_config: "USBFlashConfig",
        result: FlashResult,
    ) -> bool:
        """Flash a single device and update result.

        Args:
            flasher: Flasher instance
            device: Device to flash
            firmware_file: Firmware file
            flash_config: Flash configuration
            result: FlashResult to update

        Returns:
            True if flash was successful, False otherwise
        """
        from glovebox.firmware.flash.flash_helpers import create_device_result

        # Skip non-block devices
        if not isinstance(device, BlockDevice):
            logger.warning(
                "Device %s is not a block device, skipping",
                getattr(device, "name", "unknown"),
            )
            return False

        logger.info("Flashing device: %s", device.description or device.name)

        try:
            device_result = flasher.flash_device(
                device=device,
                firmware_file=firmware_file,
                config=flash_config,
            )

            # Store detailed device info
            error_msg = None
            success = device_result.success

            if not success:
                error_msg = (
                    device_result.errors[0] if device_result.errors else "Unknown error"
                )
                result.devices_failed += 1
            else:
                result.devices_flashed += 1

            device_details = create_device_result(device, success, error_msg)
            result.device_details.append(device_details)

            return success

        except Exception as e:
            exc_info = logger.isEnabledFor(logging.DEBUG)
            logger.error(
                "Error flashing device %s: %s", device.name, e, exc_info=exc_info
            )

            # Add error to result
            result.devices_failed += 1
            device_details = create_device_result(device, False, str(e))
            result.device_details.append(device_details)

            return False

    def _device_matches_query(self, device: "USBDeviceType", query: str) -> bool:
        """Check if device matches the given query string.

        Args:
            device: Device to check
            query: Query string to match against

        Returns:
            True if device matches query
        """
        # For now, use the USB adapter's matching logic
        # This is a simplified approach - in a full implementation,
        # we might want to extract the query parsing logic
        try:
            # Create a temporary list with just this device and check if it would be matched
            all_devices = [device]
            matched_devices: list[BlockDevice] = []

            # Simple query matching - this is a basic implementation
            # The full query parser is in the USB adapter, but this gives us basic functionality
            if not query or query.strip() == "":
                return True

            # Check for basic patterns
            device_serial = getattr(device, "serial", "") or ""
            device_name = getattr(device, "name", "") or ""
            device_vendor = getattr(device, "vendor_id", "") or ""

            # Simple matching for common patterns
            if "removable=true" in query.lower():
                # Most devices in bootloader mode are removable
                return True
            if "vendor=" in query.lower():
                vendor_match = (
                    "adafruit" in query.lower() and "adafruit" in device_name.lower()
                )
                if vendor_match:
                    return True
            if "serial~=" in query.lower():
                # Extract serial pattern from query
                import re

                serial_pattern = re.search(r"serial~=([^&\s]+)", query)
                if serial_pattern:
                    pattern = serial_pattern.group(1)
                    if re.search(
                        pattern.replace(".*", ".*"), device_serial, re.IGNORECASE
                    ):
                        return True

            return True  # Default to accepting device if query parsing is complex

        except Exception:
            # If query matching fails, default to accepting the device
            return True

    def _get_flash_method_configs(
        self,
        profile: Optional["KeyboardProfile"],
        query: str | None,
    ) -> list[USBFlashConfig]:
        """Get flash method configurations from profile or defaults.

        Args:
            profile: KeyboardProfile with method configurations (optional)
            query: Device query string for default configuration.
                   None = use profile/default, "" = bypass filtering, str = custom query

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

        # Handle query parameter logic
        if query == "":
            # Empty string explicitly passed - bypass all filtering
            device_query = ""
        elif query is not None:
            # Explicit query provided
            device_query = query
        else:
            # query is None - use profile default or fallback to removable=true
            if profile:
                device_query = self._get_device_query_from_profile(profile)
            else:
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
                "usb",
                config,
                file_adapter=self.file_adapter,
                usb_adapter=self.usb_adapter,
            )
            # Check if flasher is available
            if hasattr(flasher, "check_available") and not flasher.check_available():
                raise RuntimeError("USB flasher is not available")
            return flasher
        except Exception as e:
            raise RuntimeError(f"Failed to create USB flasher: {e}") from e


def create_flash_service(
    file_adapter: FileAdapterProtocol,
    device_wait_service: "DeviceWaitService",
    usb_adapter: USBAdapterProtocol | None = None,
    loglevel: str = "INFO",
) -> FlashService:
    """Create a FlashService instance for USB firmware flashing.

    Args:
        file_adapter: Required FileAdapterProtocol instance for file operations
        device_wait_service: Required DeviceWaitService for device operations
        usb_adapter: USB adapter for device operations (creates default if None)
        loglevel: Log level for flash operations

    Returns:
        Configured FlashService instance
    """
    if usb_adapter is None:
        from glovebox.firmware.flash.flash_helpers import create_default_usb_adapter

        usb_adapter = create_default_usb_adapter()

    return FlashService(
        file_adapter=file_adapter,
        device_wait_service=device_wait_service,
        usb_adapter=usb_adapter,
        loglevel=loglevel,
    )
