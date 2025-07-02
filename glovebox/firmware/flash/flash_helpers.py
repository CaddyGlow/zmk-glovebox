"""Helper functions for flash operations to reduce duplication."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.firmware.flash.models import FlashResult


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

logger = logging.getLogger(__name__)


def create_device_result(
    device: Any, success: bool, error_message: str | None = None
) -> dict[str, Any]:
    """Create standardized device result dictionary.

    Args:
        device: Device object (BlockDevice or USBDevice)
        success: Whether operation succeeded
        error_message: Optional error message

    Returns:
        Standardized device result dictionary
    """
    device_details = {
        "name": getattr(device, "description", None)
        or getattr(device, "path", "unknown"),
        "serial": getattr(device, "serial", "unknown"),
        "status": "success" if success else "failed",
    }

    if not success and error_message:
        device_details["error"] = error_message

    return device_details


def validate_firmware_file(
    file_adapter: Any, firmware_file_path: Path
) -> FlashResult | None:
    """Validate firmware file exists.

    Args:
        file_adapter: File adapter for checking existence
        firmware_file_path: Path to firmware file

    Returns:
        FlashResult with error if file doesn't exist, None if valid
    """
    if not file_adapter.check_exists(firmware_file_path):
        result = FlashResult(success=False)
        result.add_error(f"Firmware file not found: {firmware_file_path}")
        return result
    return None


def get_device_query(
    profile: "KeyboardProfile | None",
    query: str | None,
    flash_config: Any | None = None,
) -> str:
    """Determine device query string from various sources.

    Args:
        profile: Optional keyboard profile
        query: User-provided query (overrides profile)
        flash_config: Optional flash configuration

    Returns:
        Device query string to use
    """
    # Explicit query takes precedence
    if query:
        return query

    # Try flash config query
    if (
        flash_config
        and hasattr(flash_config, "device_query")
        and flash_config.device_query
    ):
        return str(flash_config.device_query)

    # Try profile flash methods
    if profile and hasattr(profile.keyboard_config, "flash_methods"):
        for method in profile.keyboard_config.flash_methods:
            if hasattr(method, "device_query") and method.device_query:
                return str(method.device_query)

    # Default fallback
    return "removable=true"


def update_flash_result_counts(
    result: FlashResult, devices_flashed: int, devices_failed: int
) -> None:
    """Update flash result with device counts and status.

    Args:
        result: FlashResult to update
        devices_flashed: Number of successfully flashed devices
        devices_failed: Number of failed devices
    """
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


def create_default_usb_adapter() -> Any:
    """Create default USB adapter with all dependencies.

    Returns:
        Configured USB adapter instance
    """
    # Import here to avoid circular import when using default
    from glovebox.adapters.usb_adapter import create_usb_adapter
    from glovebox.firmware.flash.device_detector import (
        MountPointCache,
        create_device_detector,
    )
    from glovebox.firmware.flash.flash_operations import create_flash_operations
    from glovebox.firmware.flash.os_adapters import create_flash_os_adapter
    from glovebox.firmware.flash.usb_monitor import create_usb_monitor

    # Create required dependencies for USB adapter
    os_adapter = create_flash_os_adapter()
    flash_operations = create_flash_operations(os_adapter)
    mount_cache = MountPointCache()
    usb_monitor = create_usb_monitor()
    detector = create_device_detector(usb_monitor, mount_cache)

    return create_usb_adapter(flash_operations, detector)
