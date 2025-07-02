"""Device waiting service with USB monitoring for flash operations."""

import logging
import time
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.config.flash_methods import USBFlashConfig

from glovebox.firmware.flash.models import BlockDevice, USBDevice, USBDeviceType
from glovebox.firmware.flash.usb_monitor import USBDeviceMonitorBase, create_usb_monitor
from glovebox.firmware.flash.wait_state import DeviceWaitState
from glovebox.protocols.usb_adapter_protocol import USBAdapterProtocol


logger = logging.getLogger(__name__)


class DeviceWaitService:
    """Service for waiting for USB devices with real-time monitoring."""

    def __init__(
        self,
        usb_adapter: USBAdapterProtocol | None = None,
        usb_monitor: USBDeviceMonitorBase | None = None,
    ) -> None:
        """Initialize device wait service.

        Args:
            usb_adapter: USB adapter for device operations. If None, creates default.
            usb_monitor: USB monitor for device events. If None, creates default.
        """
        if usb_adapter is None:
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

            usb_adapter = create_usb_adapter(flash_operations, detector)

        if usb_monitor is None:
            usb_monitor = create_usb_monitor()

        self.usb_adapter = usb_adapter
        self.usb_monitor = usb_monitor

    def wait_for_devices(
        self,
        target_count: int,
        timeout: float,
        query: str,
        flash_config: "USBFlashConfig",
        poll_interval: float = 0.5,
        show_progress: bool = True,
    ) -> list[USBDeviceType]:
        """Wait for devices using event-driven monitoring.

        Args:
            target_count: Number of devices to wait for
            timeout: Maximum time to wait in seconds
            query: Device query string for filtering
            flash_config: USB flash configuration
            poll_interval: Polling interval for progress updates
            show_progress: Whether to show progress messages

        Returns:
            List of found USB devices (may be fewer than target if timeout)
        """
        logger.info(
            "Starting device wait: target=%d, timeout=%.1fs, query='%s'",
            target_count,
            timeout,
            query,
        )

        # Get initial device count
        initial_devices = self.usb_adapter.list_matching_devices(query)
        initial_count = len(initial_devices)

        if show_progress:
            if initial_count >= target_count:
                logger.info(
                    "Found %d device(s), target reached immediately", initial_count
                )
                return initial_devices[:target_count]
            elif initial_count > 0:
                logger.info(
                    "Found %d device(s), waiting for %d more... (timeout: %.0fs)",
                    initial_count,
                    target_count - initial_count,
                    timeout,
                )
            else:
                logger.info(
                    "Waiting for %d device(s)... (timeout: %.0fs)",
                    target_count,
                    timeout,
                )

        # Create wait state
        state = DeviceWaitState(
            target_count=target_count,
            query=query,
            timeout=timeout,
            poll_interval=poll_interval,
            show_progress=show_progress,
            found_devices=initial_devices.copy(),
        )

        # If already have enough devices, return immediately
        if state.is_target_reached:
            return state.found_devices[:target_count]

        # Create callback for device events
        def device_callback(action: str, device: USBDeviceType) -> None:
            if action == "add" and self._matches_query(device, query):
                state.add_device(device)
                if show_progress:
                    logger.info(
                        "Found device: %s [%d/%d]",
                        device.serial or device.name,
                        len(state.found_devices),
                        target_count,
                    )

                if state.is_target_reached:
                    state.stop_waiting()

            elif action == "remove":
                old_count = len(state.found_devices)
                state.remove_device(device)
                if show_progress and len(state.found_devices) < old_count:
                    logger.warning(
                        "Device removed. Remaining: [%d/%d]",
                        len(state.found_devices),
                        target_count,
                    )

        try:
            # Start monitoring and register callback
            self.usb_monitor.register_callback(device_callback)
            self.usb_monitor.start_monitoring()

            # Wait for devices or timeout
            while not state.should_stop_waiting:
                time.sleep(poll_interval)

            if state.is_timeout and show_progress:
                logger.warning(
                    "Timeout reached. Found %d of %d devices.",
                    len(state.found_devices),
                    target_count,
                )

            return state.found_devices[:target_count] if state.found_devices else []

        finally:
            # Clean up monitoring
            self.usb_monitor.unregister_callback(device_callback)
            self.usb_monitor.stop_monitoring()

    def _matches_query(self, device: USBDeviceType, query: str) -> bool:
        """Check if device matches the query string."""
        # Use USB adapter's existing query matching logic
        matching_devices = self.usb_adapter.list_matching_devices(query)
        return any(d.device_node == device.device_node for d in matching_devices)


def create_device_wait_service() -> DeviceWaitService:
    """Factory function to create DeviceWaitService."""
    return DeviceWaitService()
