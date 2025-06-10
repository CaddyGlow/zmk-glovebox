"""Device waiting service with USB monitoring for flash operations."""

import logging
import time
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.config.flash_methods import USBFlashConfig

from glovebox.adapters.usb_adapter import create_usb_adapter
from glovebox.cli.helpers.output import print_info_message, print_warning_message
from glovebox.firmware.flash.models import BlockDevice
from glovebox.firmware.flash.usb_monitor import create_usb_monitor
from glovebox.firmware.flash.wait_state import DeviceWaitState


logger = logging.getLogger(__name__)


class DeviceWaitService:
    """Service for waiting for USB devices with real-time monitoring."""

    def __init__(self) -> None:
        """Initialize device wait service."""
        self.usb_monitor = create_usb_monitor()
        self.usb_adapter = create_usb_adapter()

    def wait_for_devices(
        self,
        target_count: int,
        timeout: float,
        query: str,
        flash_config: "USBFlashConfig",
        poll_interval: float = 0.5,
        show_progress: bool = True,
    ) -> list[BlockDevice]:
        """Wait for devices using event-driven monitoring.

        Args:
            target_count: Number of devices to wait for
            timeout: Maximum time to wait in seconds
            query: Device query string for filtering
            flash_config: USB flash configuration
            poll_interval: Polling interval for progress updates
            show_progress: Whether to show progress messages

        Returns:
            List of found devices (may be fewer than target if timeout)
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
                print_info_message(
                    f"Found {initial_count} device(s), target reached immediately"
                )
                return initial_devices[:target_count]
            elif initial_count > 0:
                print_info_message(
                    f"Found {initial_count} device(s), waiting for {target_count - initial_count} more... (timeout: {timeout:.0f}s)"
                )
            else:
                print_info_message(
                    f"Waiting for {target_count} device(s)... (timeout: {timeout:.0f}s)"
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
        def device_callback(action: str, device: BlockDevice) -> None:
            if action == "add" and self._matches_query(device, query):
                state.add_device(device)
                if show_progress:
                    print_info_message(
                        f"Found device: {device.serial or device.name} [{len(state.found_devices)}/{target_count}]"
                    )

                if state.is_target_reached:
                    state.stop_waiting()

            elif action == "remove":
                old_count = len(state.found_devices)
                state.remove_device(device)
                if show_progress and len(state.found_devices) < old_count:
                    print_warning_message(
                        f"Device removed. Remaining: [{len(state.found_devices)}/{target_count}]"
                    )

        try:
            # Start monitoring and register callback
            self.usb_monitor.register_callback(device_callback)
            self.usb_monitor.start_monitoring()

            # Wait for devices or timeout
            while not state.should_stop_waiting:
                time.sleep(poll_interval)

            if state.is_timeout and show_progress:
                print_warning_message(
                    f"Timeout reached. Found {len(state.found_devices)} of {target_count} devices."
                )

            return state.found_devices[:target_count] if state.found_devices else []

        finally:
            # Clean up monitoring
            self.usb_monitor.unregister_callback(device_callback)
            self.usb_monitor.stop_monitoring()

    def _matches_query(self, device: BlockDevice, query: str) -> bool:
        """Check if device matches the query string."""
        # Use USB adapter's existing query matching logic
        matching_devices = self.usb_adapter.list_matching_devices(query)
        return any(d.path == device.path for d in matching_devices)


def create_device_wait_service() -> DeviceWaitService:
    """Factory function to create DeviceWaitService."""
    return DeviceWaitService()
