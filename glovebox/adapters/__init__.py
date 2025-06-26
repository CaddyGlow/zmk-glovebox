"""Adapters package for external system interfaces."""

from glovebox.protocols import (
    ConfigFileAdapterProtocol,
    DockerAdapterProtocol,
    FileAdapterProtocol,
    TemplateAdapterProtocol,
    USBAdapterProtocol,
)

# config_file_adapter is imported directly where needed to avoid circular imports
from .compilation_progress_middleware import (
    CompilationProgressMiddleware,
    create_compilation_progress_middleware,
)
from .docker_adapter import DockerAdapter, create_docker_adapter
from .file_adapter import FileAdapter, create_file_adapter
from .template_adapter import TemplateAdapter, create_template_adapter
from .usb_adapter import USBAdapter, create_usb_adapter


__all__ = [
    "CompilationProgressMiddleware",
    "ConfigFileAdapterProtocol",
    "create_compilation_progress_middleware",
    "DockerAdapterProtocol",
    "DockerAdapter",
    "create_docker_adapter",
    "FileAdapterProtocol",
    "FileAdapter",
    "create_file_adapter",
    "TemplateAdapterProtocol",
    "TemplateAdapter",
    "create_template_adapter",
    "USBAdapterProtocol",
    "USBAdapter",
    "create_usb_adapter",
]
