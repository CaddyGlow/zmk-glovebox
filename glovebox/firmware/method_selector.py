"""Method selection with fallback logic."""

import logging
from typing import Any

from glovebox.config.compile_methods import CompileMethodConfig
from glovebox.config.flash_methods import FlashMethodConfig
from glovebox.core.errors import BuildError, FlashError
from glovebox.firmware.method_registry import compiler_registry, flasher_registry
from glovebox.protocols.compile_protocols import CompilerProtocol
from glovebox.protocols.flash_protocols import FlasherProtocol


logger = logging.getLogger(__name__)


class CompilerNotAvailableError(BuildError):
    """Raised when no compiler is available."""

    pass


class FlasherNotAvailableError(FlashError):
    """Raised when no flasher is available."""

    pass


def select_compiler_with_fallback(
    configs: list[CompileMethodConfig],
    **dependencies: Any,
) -> CompilerProtocol:
    """Select first available compiler from config list.

    Args:
        configs: List of compilation method configurations to try
        **dependencies: Additional dependencies to pass to compiler creation

    Returns:
        First available compiler instance

    Raises:
        CompilerNotAvailableError: If no compiler is available
    """
    if not configs:
        raise CompilerNotAvailableError("No compiler configurations provided")

    for config in configs:
        try:
            compiler = compiler_registry.create_method(
                config.method_type,
                config,
                **dependencies,
            )
            if compiler.check_available():
                logger.info("Selected compiler: %s", config.method_type)
                return compiler
            else:
                logger.debug("Compiler %s is not available", config.method_type)
        except Exception as e:
            logger.debug("Compiler %s failed to initialize: %s", config.method_type, e)
            continue

    # No compiler available
    available_methods = compiler_registry.get_available_methods()
    registered_methods = compiler_registry.get_registered_methods()

    error_msg = (
        f"No available compilers from {len(configs)} configurations. "
        f"Registered methods: {registered_methods}, "
        f"Available methods: {available_methods}"
    )
    raise CompilerNotAvailableError(error_msg)


def select_flasher_with_fallback(
    configs: list[FlashMethodConfig],
    **dependencies: Any,
) -> FlasherProtocol:
    """Select first available flasher from config list.

    Args:
        configs: List of flash method configurations to try
        **dependencies: Additional dependencies to pass to flasher creation

    Returns:
        First available flasher instance

    Raises:
        FlasherNotAvailableError: If no flasher is available
    """
    if not configs:
        raise FlasherNotAvailableError("No flasher configurations provided")

    for config in configs:
        try:
            flasher = flasher_registry.create_method(
                config.method_type,
                config,
                **dependencies,
            )
            if flasher.check_available():
                logger.info("Selected flasher: %s", config.method_type)
                return flasher
            else:
                logger.debug("Flasher %s is not available", config.method_type)
        except Exception as e:
            logger.debug("Flasher %s failed to initialize: %s", config.method_type, e)
            continue

    # No flasher available
    available_methods = flasher_registry.get_available_methods()
    registered_methods = flasher_registry.get_registered_methods()

    error_msg = (
        f"No available flashers from {len(configs)} configurations. "
        f"Registered methods: {registered_methods}, "
        f"Available methods: {available_methods}"
    )
    raise FlasherNotAvailableError(error_msg)


def get_compiler_with_fallback_chain(
    primary_config: CompileMethodConfig,
    **dependencies: Any,
) -> CompilerProtocol:
    """Get compiler with automatic fallback chain from config.

    Args:
        primary_config: Primary compiler configuration with fallback_methods
        **dependencies: Additional dependencies to pass to compiler creation

    Returns:
        First available compiler instance from the fallback chain

    Raises:
        CompilerNotAvailableError: If no compiler in chain is available
    """
    # Build full config list: primary + fallbacks
    configs = [primary_config]

    # Add fallback configs (need to create them from method names)
    for fallback_method in primary_config.fallback_methods:
        try:
            # Create a basic config for the fallback method
            # This is a simplified approach - in practice, you might want
            # to have a proper config resolution system
            if fallback_method == "docker":
                from glovebox.config.compile_methods import DockerCompileConfig

                fallback_config = DockerCompileConfig()
                configs.append(fallback_config)
            # Add other method types as they're implemented
        except Exception as e:
            logger.debug(
                "Failed to create fallback config for %s: %s", fallback_method, e
            )
            continue

    return select_compiler_with_fallback(configs, **dependencies)


def get_flasher_with_fallback_chain(
    primary_config: FlashMethodConfig,
    **dependencies: Any,
) -> FlasherProtocol:
    """Get flasher with automatic fallback chain from config.

    Args:
        primary_config: Primary flasher configuration with fallback_methods
        **dependencies: Additional dependencies to pass to flasher creation

    Returns:
        First available flasher instance from the fallback chain

    Raises:
        FlasherNotAvailableError: If no flasher in chain is available
    """
    # Build full config list: primary + fallbacks
    configs = [primary_config]

    # Add fallback configs (need to create them from method names)
    for fallback_method in primary_config.fallback_methods:
        try:
            # Create a basic config for the fallback method
            if fallback_method == "usb":
                from glovebox.config.flash_methods import USBFlashConfig

                fallback_config = USBFlashConfig(device_query="")
                configs.append(fallback_config)
            # Add other method types as they're implemented
        except Exception as e:
            logger.debug(
                "Failed to create fallback config for %s: %s", fallback_method, e
            )
            continue

    return select_flasher_with_fallback(configs, **dependencies)
