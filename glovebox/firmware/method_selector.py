"""Method selection with fallback logic."""

import logging
from typing import Any

from glovebox.config.compile_methods import (
    CompileMethodConfig,
    CrossCompileConfig,
    DockerCompileConfig,
    LocalCompileConfig,
    QemuCompileConfig,
)
from glovebox.config.flash_methods import (
    BootloaderFlashConfig,
    DFUFlashConfig,
    FlashMethodConfig,
    USBFlashConfig,
    WiFiFlashConfig,
)
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

    # Add fallback configs using the enhanced config resolution
    fallback_configs = _create_compiler_fallback_configs(
        primary_config.fallback_methods
    )
    configs.extend(fallback_configs)

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

    # Add fallback configs using the enhanced config resolution
    fallback_configs = _create_flasher_fallback_configs(primary_config.fallback_methods)
    configs.extend(fallback_configs)

    return select_flasher_with_fallback(configs, **dependencies)


def _create_compiler_fallback_configs(
    fallback_methods: list[str],
) -> list[CompileMethodConfig]:
    """Create compiler configurations for fallback methods.

    Args:
        fallback_methods: List of method names to create configs for

    Returns:
        List of compiler configurations with sensible defaults
    """
    configs = []

    for method_name in fallback_methods:
        try:
            config = _create_compiler_config_for_method(method_name)
            if config:
                configs.append(config)
                logger.debug("Created fallback config for compiler: %s", method_name)
        except Exception as e:
            logger.debug(
                "Failed to create fallback config for compiler %s: %s",
                method_name,
                e,
            )
            continue

    return configs


def _create_flasher_fallback_configs(
    fallback_methods: list[str],
) -> list[FlashMethodConfig]:
    """Create flasher configurations for fallback methods.

    Args:
        fallback_methods: List of method names to create configs for

    Returns:
        List of flasher configurations with sensible defaults
    """
    configs = []

    for method_name in fallback_methods:
        try:
            config = _create_flasher_config_for_method(method_name)
            if config:
                configs.append(config)
                logger.debug("Created fallback config for flasher: %s", method_name)
        except Exception as e:
            logger.debug(
                "Failed to create fallback config for flasher %s: %s",
                method_name,
                e,
            )
            continue

    return configs


def _create_compiler_config_for_method(method_name: str) -> CompileMethodConfig | None:
    """Create a compiler configuration for the given method name.

    Args:
        method_name: Name of the compilation method

    Returns:
        Configuration instance with sensible defaults, or None if unknown method
    """
    # Create configs with sensible defaults for fallback scenarios
    if method_name == "docker":
        return DockerCompileConfig()
    elif method_name == "local":
        # Local compiler requires zmk_path, use common locations as fallbacks
        from pathlib import Path

        common_zmk_paths = [
            Path("/opt/zmk"),
            Path("~/zmk").expanduser(),
            Path("./zmk"),
        ]

        # Try to find an existing ZMK installation
        for zmk_path in common_zmk_paths:
            if zmk_path.exists():
                return LocalCompileConfig(zmk_path=zmk_path)

        # If no ZMK found, use default path (may fail availability check)
        return LocalCompileConfig(zmk_path=Path("/opt/zmk"))
    elif method_name == "cross":
        # Cross compiler requires several fields, use sensible ARM defaults
        from pathlib import Path

        return CrossCompileConfig(
            target_arch="arm",
            sysroot=Path("/usr/arm-linux-gnueabihf"),
            toolchain_prefix="arm-linux-gnueabihf-",
        )
    elif method_name == "qemu":
        return QemuCompileConfig()
    else:
        logger.warning("Unknown compiler method for fallback: %s", method_name)
        return None


def _create_flasher_config_for_method(method_name: str) -> FlashMethodConfig | None:
    """Create a flasher configuration for the given method name.

    Args:
        method_name: Name of the flash method

    Returns:
        Configuration instance with sensible defaults, or None if unknown method
    """
    # Create configs with sensible defaults for fallback scenarios
    if method_name == "usb":
        # Use broad device query that matches most removable devices
        return USBFlashConfig(
            device_query="removable=true",
            mount_timeout=30,
            copy_timeout=60,
        )
    elif method_name == "dfu":
        # DFU requires VID/PID, use common ZMK bootloader values
        return DFUFlashConfig(
            vid="0x239A",  # Adafruit VID commonly used for keyboards
            pid="0x000C",  # Generic bootloader PID
            interface=0,
            timeout=30,
        )
    elif method_name == "bootloader":
        # Bootloader defaults to UART protocol
        return BootloaderFlashConfig(
            protocol="uart",
            baud_rate=115200,
        )
    elif method_name == "wifi":
        # WiFi requires host, use common mDNS name
        return WiFiFlashConfig(
            host="keyboard.local",
            port=8080,
            protocol="http",
        )
    else:
        logger.warning("Unknown flasher method for fallback: %s", method_name)
        return None
