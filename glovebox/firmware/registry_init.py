"""Initialize method registries with implementations."""

from typing import cast

from glovebox.config.flash_methods import USBFlashConfig
from glovebox.core.structlog_logger import get_struct_logger
from glovebox.firmware.flash.flasher_methods import USBFlasher
from glovebox.firmware.method_registry import flasher_registry
from glovebox.protocols.flash_protocols import FlasherProtocol


logger = get_struct_logger(__name__)


def register_flash_methods() -> None:
    """Register USB flash method."""
    # Register USB flasher - cast helps type checker understand USBFlasher implements FlasherProtocol
    flasher_registry.register_method(
        method_name="usb",
        implementation=cast(type[FlasherProtocol], USBFlasher),
        config_type=USBFlashConfig,
    )


def initialize_registries() -> None:
    """Initialize flash method registry with available implementations.

    Note: Compilation methods are now handled by the compilation domain services.
    """
    register_flash_methods()


# Auto-initialize when module is imported
initialize_registries()
