"""Protocol definition for device detection functionality."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable


if TYPE_CHECKING:
    from glovebox.firmware.flash.models import BlockDevice


@runtime_checkable
class DeviceDetectorProtocol(Protocol):
    """Protocol for device detection operations.

    This protocol defines the interface for device detection and query
    operations used to find devices for firmware flashing.
    """

    def get_devices(self) -> list["BlockDevice"]:
        """Get all available USB block devices.

        Returns:
            List of all detected BlockDevice objects
        """
        ...

    def get_device_by_name(self, name: str) -> "BlockDevice | None":
        """Get a specific device by name.

        Args:
            name: Device name to search for

        Returns:
            BlockDevice if found, None otherwise
        """
        ...

    def get_devices_by_query(self, **kwargs: Any) -> list["BlockDevice"]:
        """Get devices matching specific criteria.

        Args:
            **kwargs: Device attributes to match

        Returns:
            List of matching BlockDevice objects
        """
        ...

    def start_monitoring(self) -> None:
        """Start USB device monitoring."""
        ...

    def stop_monitoring(self) -> None:
        """Stop USB device monitoring."""
        ...

    def register_callback(self, callback: Callable[[str, "BlockDevice"], None]) -> None:
        """Register a callback for device events.

        Args:
            callback: Function to call when devices are added/removed
        """
        ...

    def unregister_callback(
        self, callback: Callable[[str, "BlockDevice"], None]
    ) -> None:
        """Unregister a callback.

        Args:
            callback: Callback function to remove
        """
        ...

    def wait_for_device(
        self, timeout: int = 60, poll_interval: float = 0.5
    ) -> "BlockDevice | None":
        """Wait for a new USB device to appear.

        Args:
            timeout: Maximum time to wait in seconds
            poll_interval: Time between polling attempts

        Returns:
            BlockDevice if detected, None if timeout
        """
        ...

    def parse_query(self, query_str: str) -> list[tuple[str, str, str]]:
        """
        Parse a device query string into a list of conditions.

        Args:
            query_str: Query string in format "field1=value1 and field2~=value2"

        Returns:
            List of tuples (field, operator, value)

        Raises:
            ValueError: If the query string is invalid.
        """
        ...

    def evaluate_condition(
        self, device: Any, field: str, operator: str, value: str
    ) -> bool:
        """
        Evaluate if a device matches a condition.

        Args:
            device: BlockDevice object to check
            field: Device attribute to check
            operator: Comparison operator ('=', '!=', '~=')
            value: Value to compare against

        Returns:
            True if the condition matches, False otherwise
        """
        ...

    def detect_device(
        self,
        query_str: str,
        timeout: int = 60,
        initial_devices: list["BlockDevice"] | None = None,
    ) -> "BlockDevice":
        """
        Wait for and detect a device matching the query.

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
        ...

    def list_matching_devices(self, query_str: str) -> list["BlockDevice"]:
        """
        List all devices matching the query.

        Args:
            query_str: Query string to match devices

        Returns:
            List of matching BlockDevice objects

        Raises:
            ValueError: If the query string is invalid.
        """
        ...
