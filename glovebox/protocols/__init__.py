"""Protocol definitions for Glovebox adapters and interfaces.

This package provides standard Protocol classes that define the interfaces
for various components in the Glovebox system. These protocols use Python's
typing.Protocol system with the @runtime_checkable decorator to enable both
static type checking and runtime isinstance() checks.
"""

from .config_file_adapter_protocol import ConfigFileAdapterProtocol
from .docker_adapter_protocol import (
    DockerAdapterProtocol,
    DockerEnv,
    DockerResult,
    DockerVolume,
)
from .file_adapter_protocol import FileAdapterProtocol
from .flash_os_protocol import FlashOSProtocol
from .template_adapter_protocol import TemplateAdapterProtocol
from .usb_adapter_protocol import USBAdapterProtocol


__all__ = [
    "ConfigFileAdapterProtocol",
    "DockerAdapterProtocol",
    "DockerEnv",
    "DockerResult",
    "DockerVolume",
    "FileAdapterProtocol",
    "FlashOSProtocol",
    "TemplateAdapterProtocol",
    "USBAdapterProtocol",
]
