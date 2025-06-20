"""Stub implementation for unsupported platforms."""

import logging
import platform
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.protocols.flash_os_protocol import FlashOSProtocol

from glovebox.firmware.flash.models import BlockDevice


logger = logging.getLogger(__name__)


class StubFlashOS:
    """Stub implementation for unsupported platforms."""

    def get_device_path(self, device_name: str) -> str:
        """Stub implementation that raises an error."""
        raise OSError(f"Flash operations not supported on {platform.system()}")

    def mount_device(self, device: BlockDevice) -> list[str]:
        """Stub implementation that raises an error."""
        raise OSError(f"Flash operations not supported on {platform.system()}")

    def unmount_device(self, device: BlockDevice) -> bool:
        """Stub implementation that raises an error."""
        raise OSError(f"Flash operations not supported on {platform.system()}")

    def copy_firmware_file(self, firmware_file: Path, mount_point: str) -> bool:
        """Stub implementation that raises an error."""
        raise OSError(f"Flash operations not supported on {platform.system()}")

    def sync_filesystem(self, mount_point: str) -> bool:
        """Stub implementation that raises an error."""
        raise OSError(f"Flash operations not supported on {platform.system()}")
