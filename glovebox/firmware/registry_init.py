"""Initialize method registries with implementations."""

import logging
from typing import cast

from glovebox.config.compile_methods import DockerCompileConfig
from glovebox.config.flash_methods import DFUFlashConfig, USBFlashConfig
from glovebox.firmware.compile.methods import DockerCompiler
from glovebox.firmware.flash.flasher_methods import DFUFlasher, USBFlasher
from glovebox.firmware.method_registry import compiler_registry, flasher_registry
from glovebox.protocols.compile_protocols import CompilerProtocol
from glovebox.protocols.flash_protocols import FlasherProtocol


logger = logging.getLogger(__name__)


def register_compile_methods() -> None:
    """Register all available compilation methods."""
    # Register Docker compiler - cast helps type checker understand DockerCompiler implements CompilerProtocol
    compiler_registry.register_method(
        method_name="docker",
        implementation=cast(type[CompilerProtocol], DockerCompiler),
        config_type=DockerCompileConfig,
    )
    logger.debug("Registered docker compiler")


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
    """Initialize all method registries with available implementations."""
    register_compile_methods()
    register_flash_methods()
    logger.info("Method registries initialized")


# Auto-initialize when module is imported
initialize_registries()
