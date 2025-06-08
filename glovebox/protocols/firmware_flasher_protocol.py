"""Protocol definition for firmware flashing functionality."""

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable


if TYPE_CHECKING:
    from glovebox.flash.models import FlashResult


@runtime_checkable
class FirmwareFlasherProtocol(Protocol):
    """Protocol for firmware flashing operations.

    This protocol defines the interface for flashing firmware to USB devices.
    """

    def flash_firmware(
        self,
        firmware_file: str | Path,
        query: str = "vendor=Adafruit and serial~=GLV80-.* and removable=true",
        timeout: int = 60,
        count: int = 1,
        track_flashed: bool = True,
    ) -> "FlashResult":
        """
        Detect and flash firmware to one or more devices matching the query.

        Args:
            firmware_file: Path to the firmware file (.uf2).
            query: Query string to identify the target device(s).
            timeout: Timeout in seconds to wait for each device.
            count: Number of devices to flash (0 for infinite).
            track_flashed: Whether to track and skip already flashed devices.

        Returns:
            FlashResult object with flash operation results

        Raises:
            FileNotFoundError: If the firmware file does not exist.
            ValueError: If the query string is invalid.
        """
        ...
