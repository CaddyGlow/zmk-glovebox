"""Protocol for mount point cache operations."""

from typing import TYPE_CHECKING, Protocol, runtime_checkable


if TYPE_CHECKING:
    from glovebox.firmware.flash.models import BlockDevicePathMap


@runtime_checkable
class MountCacheProtocol(Protocol):
    """Protocol for caching and retrieving mount point information."""

    def get_mountpoints(self) -> "BlockDevicePathMap":
        """Get mapping of device names to mount points."""
        ...
