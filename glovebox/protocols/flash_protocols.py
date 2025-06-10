"""Protocol definitions for flash methods."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from glovebox.config.flash_methods import FlashMethodConfig, USBFlashConfig
from glovebox.firmware.flash.models import BlockDevice, FlashResult


@runtime_checkable
class FlasherProtocol(Protocol):
    """Generic flasher interface."""

    def flash_device(
        self,
        device: BlockDevice,
        firmware_file: Path,
        config: FlashMethodConfig,
    ) -> FlashResult:
        """Flash device using this method."""
        ...

    def list_devices(self, config: FlashMethodConfig) -> list[BlockDevice]:
        """List compatible devices for this flash method."""
        ...

    def check_available(self) -> bool:
        """Check if this flasher is available."""
        ...

    def validate_config(self, config: FlashMethodConfig) -> bool:
        """Validate method-specific configuration."""
        ...


@runtime_checkable
class USBFlasherProtocol(Protocol):
    """USB-specific flasher interface."""

    def flash_device(
        self,
        device: BlockDevice,
        firmware_file: Path,
        config: USBFlashConfig,  # Type-specific config
    ) -> FlashResult:
        """Flash device using USB mounting."""
        ...

    def mount_device(self, device: BlockDevice, config: USBFlashConfig) -> list[str]:
        """Mount USB device for flashing."""
        ...

    def unmount_device(self, device: BlockDevice, config: USBFlashConfig) -> bool:
        """Unmount USB device after flashing."""
        ...

    def validate_config(self, config: USBFlashConfig) -> bool:
        """Validate USB-specific configuration."""
        ...
