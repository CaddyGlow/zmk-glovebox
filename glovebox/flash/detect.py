"""Device detection functionality for firmware flashing."""

import logging
import re
import threading

from glovebox.core.errors import FlashError
from glovebox.flash.lsdev import BlockDevice, BlockDeviceError, Lsdev


logger = logging.getLogger(__name__)


class DeviceDetector:
    """Class for detecting devices based on query criteria."""

    def __init__(self) -> None:
        """Initialize the device detector."""
        self.lsdev = Lsdev()
        self._lock = threading.RLock()
        self._detected_devices: list[BlockDevice] = []
        self._initial_devices: set[str] = set()
        self._conditions: list[tuple[str, str, str]] = []
        self._event = threading.Event()

    def parse_query(self, query_str: str) -> list[tuple[str, str, str]]:
        """
        Parse a device query string into a list of conditions.

        Args:
            query_str: Query string in format "field1=value1 and field2~=value2"

        Returns:
            List of tuples (field, operator, value)

        Examples:
            >>> parse_query("model=nRF52 and vendor=Adafruit")
            [('model', '=', 'nRF52'), ('vendor', '=', 'Adafruit')]

            >>> parse_query("model~=nRF.* and removable=true")
            [('model', '~=', 'nRF.*'), ('removable', '=', 'true')]
        """
        conditions = []

        # Split by 'and' (case insensitive)
        parts = [p.strip() for p in query_str.split(" and ")]

        for part in parts:
            # Skip empty parts resulting from splitting an empty string or consecutive 'and's
            if not part:
                continue

            # Check for different operators
            if "~=" in part:
                field, value = part.split("~=", 1)
                conditions.append((field.strip(), "~=", value.strip()))
            elif "!=" in part:
                field, value = part.split("!=", 1)
                conditions.append((field.strip(), "!=", value.strip()))
            elif "=" in part:
                field, value = part.split("=", 1)
                conditions.append((field.strip(), "=", value.strip()))
            else:
                # Raise error for invalid format instead of just warning
                raise ValueError(f"Invalid query condition: {part}")

        return conditions

    def evaluate_condition(
        self, device: BlockDevice, field: str, operator: str, value: str
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
        # Get the device attribute value
        if hasattr(device, field):
            device_value = getattr(device, field)
        else:
            logger.debug(f"Device has no attribute '{field}'")
            return False

        # Convert to string for comparison
        if device_value is None:
            device_value = ""
        elif isinstance(device_value, bool):
            device_value = str(device_value).lower()
        else:
            device_value = str(device_value)

        # Standardize boolean value representation for comparison
        compare_value = value.lower()
        if compare_value in ("true", "yes", "1"):
            compare_value = "true"
        elif compare_value in ("false", "no", "0"):
            compare_value = "false"

        # Evaluate based on operator
        if operator == "=":
            # Perform case-insensitive comparison for '='
            return bool(device_value.lower() == compare_value)
        elif operator == "!=":
            # Perform case-insensitive comparison for '!='
            return bool(device_value.lower() != compare_value)
        elif operator == "~=":
            try:
                # Use re.IGNORECASE for case-insensitive regex matching
                pattern = re.compile(compare_value, re.IGNORECASE)
                match_result = pattern.search(device_value)
                return bool(match_result)
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{compare_value}': {e}")
                return False  # Return False on regex error
        else:
            logger.warning(f"Unknown operator: {operator}")
            return False

    def device_callback(self, action: str, device: BlockDevice) -> None:
        """
        Callback function for device events.

        Args:
            action: Action type ('add' or 'remove')
            device: The device that was added or removed
        """
        if action != "add":
            return

        with self._lock:
            # Skip devices that were already present at start
            if device.name in self._initial_devices:
                return

            # Check if device matches all conditions
            matches = True
            for field, operator, value in self._conditions:
                if not self.evaluate_condition(device, field, operator, value):
                    matches = False
                    break

            if matches:
                logger.info(f"Found matching device: {device.name} ({device.model})")
                self._detected_devices.append(device)
                self._event.set()  # Signal that a device was found

    def detect_device(
        self,
        query_str: str,
        timeout: int = 60,
        initial_devices: list[BlockDevice] | None = None,
    ) -> BlockDevice:
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
            BlockDeviceError: If there's an error retrieving block devices.
        """
        logger.info(f"Waiting for device matching: {query_str}")

        try:
            self._conditions = self.parse_query(query_str)
            # Require at least one valid condition if query_str is not empty
            if not self._conditions and query_str:
                raise ValueError(
                    f"Query string '{query_str}' resulted in no valid conditions."
                )
        except ValueError as e:
            logger.error(f"Invalid query string: {e}")
            raise ValueError(f"Invalid query string: {e}") from e

        # Get initial device list to detect new devices
        if initial_devices is None:
            try:
                initial_devices = self.lsdev.get_devices()
                logger.debug(f"Initial devices: {[d.name for d in initial_devices]}")
            except Exception as e:
                logger.warning(f"Failed to get initial device list: {e}")
                initial_devices = []

        # Reset state
        with self._lock:
            self._detected_devices = []
            self._initial_devices = {d.name for d in initial_devices}
            self._event.clear()

        # Register callback for device events
        self.lsdev.register_callback(self.device_callback)

        try:
            # Start monitoring for device events
            self.lsdev.start_monitoring()

            # Check if any existing devices match (that weren't in initial_devices)
            current_devices = self.lsdev.get_devices()
            for device in current_devices:
                if device.name not in self._initial_devices:
                    self.device_callback("add", device)

            # Wait for a matching device or timeout
            if not self._event.wait(timeout):
                logger.error(
                    f"Timeout: Device matching '{query_str}' not found after {timeout} seconds."
                )
                raise TimeoutError(
                    f"Device matching '{query_str}' not found after {timeout} seconds."
                ) from None  # B904

            # Return the first detected device
            with self._lock:
                if self._detected_devices:
                    detected_device: BlockDevice = self._detected_devices[0]
                    return detected_device
                else:
                    # This shouldn't happen if _event was set, but just in case
                    raise TimeoutError(
                        f"Device matching '{query_str}' not found after {timeout} seconds."
                    ) from None  # B904

        finally:
            # Clean up
            self.lsdev.unregister_callback(self.device_callback)
            self.lsdev.stop_monitoring()

    def list_matching_devices(self, query_str: str) -> list[BlockDevice]:
        """
        List all devices matching the query.

        Args:
            query_str: Query string to match devices

        Returns:
            List of matching BlockDevice objects

        Raises:
            ValueError: If the query string is invalid.
            BlockDeviceError: If there's an error retrieving block devices.
        """
        try:
            conditions = self.parse_query(query_str)
        except ValueError as e:
            logger.error(f"Invalid query string: {e}")
            raise ValueError(f"Invalid query string: {e}") from e

        try:
            devices = self.lsdev.get_devices()
            matching_devices = []

            for device in devices:
                # Check if device matches all conditions
                matches = True
                for field, operator, value in conditions:
                    if not self.evaluate_condition(device, field, operator, value):
                        matches = False
                        break

                if matches:
                    matching_devices.append(device)

            logger.debug(
                f"Found {len(matching_devices)} devices matching query '{query_str}'"
            )
            return matching_devices

        except BlockDeviceError as e:
            logger.error(f"Error getting block devices: {e}")
            raise  # Re-raise BlockDeviceError
        except Exception as e:
            # Catch other unexpected errors during listing
            logger.error(f"Unexpected error listing devices: {e}")
            raise FlashError(f"Unexpected error listing devices: {e}") from e


# Create a singleton instance for global use
_detector = DeviceDetector()


def parse_query(query_str: str) -> list[tuple[str, str, str]]:
    """
    Parse a device query string into a list of conditions.

    This is a wrapper around the DeviceDetector method for backward compatibility.
    """
    return _detector.parse_query(query_str)


def evaluate_condition(
    device: BlockDevice, field: str, operator: str, value: str
) -> bool:
    """
    Evaluate if a device matches a condition.

    This is a wrapper around the DeviceDetector method for backward compatibility.
    """
    return _detector.evaluate_condition(device, field, operator, value)


def detect_device(
    query_str: str,
    timeout: int = 60,
    initial_devices: list[BlockDevice] | None = None,
) -> BlockDevice:
    """
    Wait for and detect a device matching the query.

    This is a wrapper around the DeviceDetector method for backward compatibility.
    """
    return _detector.detect_device(query_str, timeout, initial_devices)


def list_matching_devices(query_str: str) -> list[BlockDevice]:
    """
    List all devices matching the query.

    This is a wrapper around the DeviceDetector method for backward compatibility.
    """
    return _detector.list_matching_devices(query_str)
