"""Initialize method registries with implementations."""

import logging
from typing import cast

from glovebox.config.flash_methods import DFUFlashConfig, USBFlashConfig
from glovebox.firmware.flash.flasher_methods import DFUFlasher, USBFlasher
from glovebox.firmware.method_registry import flasher_registry
from glovebox.protocols.flash_protocols import FlasherProtocol


logger = logging.getLogger(__name__)


def register_flash_methods() -> None:
    """Register all available flash methods."""
    # Register USB flasher - cast helps type checker understand USBFlasher implements FlasherProtocol
    flasher_registry.register_method(
        method_name="usb",
        implementation=cast(type[FlasherProtocol], USBFlasher),
        config_type=USBFlashConfig,
    )
    logger.debug("Registered usb flasher")

    # Register DFU flasher - cast helps type checker understand DFUFlasher implements FlasherProtocol
    flasher_registry.register_method(
        method_name="dfu",
        implementation=cast(type[FlasherProtocol], DFUFlasher),
        config_type=DFUFlashConfig,
    )
    logger.debug("Registered dfu flasher")


def initialize_registries() -> None:
    """Initialize flash method registry with available implementations.

    Note: Compilation methods are now handled by the compilation domain services.
    """
    register_flash_methods()
    logger.info("Flash method registry initialized")


# Auto-initialize when module is imported
initialize_registries()
