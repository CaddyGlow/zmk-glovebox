"""Adapters package for external system interfaces."""

from .docker_adapter import DockerAdapter, DockerAdapterImpl, create_docker_adapter
from .file_adapter import FileAdapter, FileSystemAdapter, create_file_adapter
from .template_adapter import (
    JinjaTemplateAdapter,
    TemplateAdapter,
    create_template_adapter,
)
from .usb_adapter import USBAdapter, USBAdapterImpl, create_usb_adapter


__all__ = [
    "FileAdapter",
    "FileSystemAdapter",
    "create_file_adapter",
    "TemplateAdapter",
    "JinjaTemplateAdapter",
    "create_template_adapter",
    "DockerAdapter",
    "DockerAdapterImpl",
    "create_docker_adapter",
    "USBAdapter",
    "USBAdapterImpl",
    "create_usb_adapter",
]
