"""Adapters package for external system interfaces."""

from glovebox.protocols import (
    ConfigFileAdapterProtocol,
    DockerAdapterProtocol,
    FileAdapterProtocol,
    TemplateAdapterProtocol,
    USBAdapterProtocol,
)

from .config_file_adapter import ConfigFileAdapter, create_config_file_adapter
from .docker_adapter import DockerAdapterImpl, create_docker_adapter
from .file_adapter import FileSystemAdapter, create_file_adapter
from .template_adapter import JinjaTemplateAdapter, create_template_adapter
from .usb_adapter import USBAdapterImpl, create_usb_adapter


__all__ = [
    "ConfigFileAdapter",
    "ConfigFileAdapterProtocol",
    "create_config_file_adapter",
    "DockerAdapterProtocol",
    "DockerAdapterImpl",
    "create_docker_adapter",
    "FileAdapterProtocol",
    "FileSystemAdapter",
    "create_file_adapter",
    "TemplateAdapterProtocol",
    "JinjaTemplateAdapter",
    "create_template_adapter",
    "USBAdapterProtocol",
    "USBAdapterImpl",
    "create_usb_adapter",
]
