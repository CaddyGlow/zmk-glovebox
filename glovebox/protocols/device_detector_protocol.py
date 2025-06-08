"""Protocol definition for device detection functionality."""

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable


if TYPE_CHECKING:
    from glovebox.flash.lsdev import BlockDevice


@runtime_checkable
class DeviceDetectorProtocol(Protocol):
    """Protocol for device detection operations.

    This protocol defines the interface for device detection and query
    operations used to find devices for firmware flashing.
    """

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
        initial_devices: list[Any] | None = None,
    ) -> Any:
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

    def list_matching_devices(self, query_str: str) -> list[Any]:
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
