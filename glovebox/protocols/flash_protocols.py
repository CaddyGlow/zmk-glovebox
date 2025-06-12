"""Protocol definitions for flash methods."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from glovebox.config.flash_methods import USBFlashConfig
from glovebox.firmware.flash.models import BlockDevice, FlashResult


@runtime_checkable
class FlasherProtocol(Protocol):
    """USB flasher interface for ZMK keyboards."""

    def flash_device(
        self,
        device: BlockDevice,
        firmware_file: Path,
        config: USBFlashConfig,
    ) -> FlashResult:
        """Flash device using USB mounting."""
        ...

    def list_devices(self, config: USBFlashConfig) -> list[BlockDevice]:
        """List compatible USB devices for flashing."""
        ...

    def check_available(self) -> bool:
        """Check if USB flasher is available."""
        ...

    def validate_config(self, config: USBFlashConfig) -> bool:
        """Validate USB flash configuration."""
        ...


__all__ = ["FlasherProtocol"]
