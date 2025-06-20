"""OS-specific implementations for flash operations."""

import platform
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.protocols.flash_os_protocol import FlashOSProtocol

from .adapters.os_utils import is_wsl2


def create_flash_os_adapter() -> "FlashOSProtocol":
    """Create appropriate OS adapter for flash operations.

    Returns:
        OS-specific flash adapter instance

    Raises:
        OSError: If no suitable adapter is available for the current platform
    """
    system = platform.system().lower()

    if system == "linux":
        if is_wsl2():
            from .adapters import WSL2FlashOS

            return WSL2FlashOS()
        else:
            from .adapters import LinuxFlashOS

            return LinuxFlashOS()
    elif system == "darwin":
        from .adapters import MacOSFlashOS

        return MacOSFlashOS()
    elif system == "windows":
        from .adapters import WindowsFlashOS

        return WindowsFlashOS()
    else:
        from .adapters import StubFlashOS

        return StubFlashOS()


__all__ = [
    "create_flash_os_adapter",
]
