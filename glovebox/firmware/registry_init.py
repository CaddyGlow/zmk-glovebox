"""Initialize method registries with implementations."""

import logging
from typing import cast

from glovebox.config.flash_methods import USBFlashConfig
from glovebox.firmware.flash.flasher_methods import USBFlasher
from glovebox.firmware.method_registry import flasher_registry
from glovebox.protocols.flash_protocols import FlasherProtocol


logger = logging.getLogger(__name__)


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
