"""Device detection service implementation."""

import logging
import re
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from glovebox.firmware.flash.models import BlockDevice

from glovebox.firmware.flash.models import BlockDevice
from glovebox.firmware.flash.usb_monitor import USBDeviceMonitorBase
from glovebox.protocols.device_detector_protocol import DeviceDetectorProtocol


logger = logging.getLogger(__name__)


class MountPointCache:
    """Cache for system mount points to avoid repeated file access."""

    def __init__(self) -> None:
        self._mountpoints: dict[str, str] = {}
        self._last_updated: float = 0
        self._cache_ttl: int = 5  # Seconds before refreshing cache
        self._lock = threading.RLock()

    def get_mountpoints(self) -> dict[str, str]:
        """Get mapping of device names to mount points."""
        with self._lock:
            now = time.time()
            if now - self._last_updated > self._cache_ttl:
                self._update_cache()
            return self._mountpoints.copy()

    def _update_cache(self) -> None:
        """Update the mount point cache from /proc/mounts."""
        mountpoints = {}
        try:
            with Path("/proc/mounts").open(encoding="utf-8") as f:
                for line in f:
                    fields = line.split()
                    if len(fields) < 2 or not fields[0].startswith("/dev/"):
                        continue

                    device = fields[0][5:]  # Remove /dev/ prefix
                    mount_point = fields[1]
                    mountpoints[device] = mount_point

            self._mountpoints = mountpoints
            self._last_updated = time.time()
        except OSError as e:
            logger.warning("Failed to read mount points: %s", e)


class DeviceDetector(DeviceDetectorProtocol):
    """Service for USB block device detection and monitoring.

    Provides device detection functionality with proper dependency injection
    and follows the service pattern used throughout the codebase.
    """

    def __init__(
        self,
        usb_monitor: USBDeviceMonitorBase,
        mount_cache: MountPointCache | None = None,
    ):
        """Initialize device detector with dependencies.

        Args:
            usb_monitor: USB monitoring implementation (platform-specific)
            mount_cache: Optional mount point cache (creates default if None)
        """
        self._monitor = usb_monitor
        self._mount_cache = mount_cache or MountPointCache()

    def get_devices(self) -> list["BlockDevice"]:
        """Get all currently detected USB block devices."""
        return self._monitor.get_devices()

    def get_device_by_name(self, name: str) -> "BlockDevice | None":
        """Get a block device by name."""
        devices = self.get_devices()
        for device in devices:
            if device.name == name:
                return device
        return None

    def get_devices_by_query(self, **kwargs: Any) -> list["BlockDevice"]:
        """Get devices matching the specified criteria."""
        devices = self.get_devices()
        result = []

        for device in devices:
            match = True
            for key, value in kwargs.items():
                if not hasattr(device, key) or getattr(device, key) != value:
                    match = False
                    break
            if match:
                result.append(device)

        return result

    def start_monitoring(self) -> None:
        """Start USB device monitoring."""
        self._monitor.start_monitoring()

    def stop_monitoring(self) -> None:
        """Stop USB device monitoring."""
        self._monitor.stop_monitoring()

    def register_callback(self, callback: Callable[[str, "BlockDevice"], None]) -> None:
        """Register a callback for device events."""
        self._monitor.register_callback(callback)

    def unregister_callback(
        self, callback: Callable[[str, "BlockDevice"], None]
    ) -> None:
        """Unregister a callback."""
        self._monitor.unregister_callback(callback)

    def wait_for_device(
        self, timeout: int = 60, poll_interval: float = 0.5
    ) -> "BlockDevice | None":
        """Wait for a new USB device to appear."""
        return self._monitor.wait_for_device(timeout, poll_interval)

    # DeviceDetectorProtocol implementation

    def parse_query(self, query_str: str) -> list[tuple[str, str, str]]:
        """Parse a device query string into a list of conditions.

        Args:
            query_str: Query string in format "field1=value1 and field2~=value2"

        Returns:
            List of tuples (field, operator, value)

        Raises:
            ValueError: If the query string is invalid.
        """
        if not query_str.strip():
            return []

        conditions = []
        parts = query_str.split(" and ")

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Support different operators
            if "~=" in part:
                field, value = part.split("~=", 1)
                operator = "~="
            elif "!=" in part:
                field, value = part.split("!=", 1)
                operator = "!="
            elif "=" in part:
                field, value = part.split("=", 1)
                operator = "="
            else:
                raise ValueError(f"Invalid query condition: {part}")

            field = field.strip()
            value = value.strip()

            if not field or not value:
                raise ValueError(f"Empty field or value in condition: {part}")

            conditions.append((field, operator, value))

        return conditions

    def evaluate_condition(
        self, device: "BlockDevice", field: str, operator: str, value: str
    ) -> bool:
        """Evaluate if a device matches a condition.

        Args:
            device: BlockDevice object to check
            field: Device attribute to check
            operator: Comparison operator ('=', '!=', '~=')
            value: Value to compare against

        Returns:
            True if the condition matches, False otherwise
        """
        if not hasattr(device, field):
            return False

        device_attr = getattr(device, field, "")

        # Handle boolean values with case-insensitive comparison
        if isinstance(device_attr, bool):
            device_value = str(device_attr)
            if operator == "=":
                return device_value.lower() == value.lower()
            elif operator == "!=":
                return device_value.lower() != value.lower()
            elif operator == "~=":
                return value.lower() in device_value.lower()
        else:
            device_value = str(device_attr)

        if operator == "=":
            return device_value == value
        elif operator == "!=":
            return device_value != value
        elif operator == "~=":
            # Support regex patterns for ~= operator
            try:
                # First try as regex pattern
                pattern = re.compile(value, re.IGNORECASE)
                return bool(pattern.search(device_value))
            except re.error:
                # Fallback to substring matching if not valid regex
                return value.lower() in device_value.lower()
        else:
            return False

    def detect_device(
        self,
        query_str: str,
        timeout: int = 60,
        initial_devices: list["BlockDevice"] | None = None,
    ) -> "BlockDevice":
        """Wait for and detect a device matching the query.

        Args:
            query_str: Query string to match devices
            timeout: Maximum time to wait in seconds
            initial_devices: Optional list of devices to exclude from detection

        Returns:
            The first matching BlockDevice

        Raises:
            TimeoutError: If no matching device is found within the timeout.
            ValueError: If the query string is invalid.
        """
        conditions = self.parse_query(query_str)
        initial_names = {d.name for d in initial_devices or []}

        start_time = time.time()

        while time.time() - start_time < timeout:
            current_devices = self.get_devices()

            for device in current_devices:
                # Skip devices that were present initially
                if device.name in initial_names:
                    continue

                # Check if device matches all conditions
                match = True
                for field, operator, value in conditions:
                    if not self.evaluate_condition(device, field, operator, value):
                        match = False
                        break

                if match:
                    return device

            time.sleep(0.5)  # Poll every 500ms

        raise TimeoutError(
            f"No device matching query '{query_str}' found within {timeout} seconds"
        )

    def list_matching_devices(self, query_str: str) -> list["BlockDevice"]:
        """List all devices matching the query.

        Args:
            query_str: Query string to match devices

        Returns:
            List of matching BlockDevice objects

        Raises:
            ValueError: If the query string is invalid.
        """
        if not query_str.strip():
            return self.get_devices()

        conditions = self.parse_query(query_str)
        matching_devices = []

        for device in self.get_devices():
            match = True
            for field, operator, value in conditions:
                if not self.evaluate_condition(device, field, operator, value):
                    match = False
                    break

            if match:
                matching_devices.append(device)

        return matching_devices


def create_device_detector(
    usb_monitor: Any,
    mount_cache: MountPointCache,
) -> DeviceDetector:
    """Create a DeviceDetector instance with explicit dependency injection.

    Args:
        usb_monitor: Required USB monitor instance for device monitoring
        mount_cache: Required mount point cache for caching operations

    Returns:
        Configured DeviceDetector instance
    """
    return DeviceDetector(
        usb_monitor=usb_monitor,
        mount_cache=mount_cache,
    )
