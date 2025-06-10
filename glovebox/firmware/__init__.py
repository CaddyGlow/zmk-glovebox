"""Firmware domain - Build and flash operations."""

# Import registry initialization to ensure methods are registered
from glovebox.firmware import registry_init  # noqa: F401
from glovebox.firmware.build_service import create_build_service

# Import compile methods
from glovebox.firmware.compile import DockerCompiler, create_docker_compiler

# Import method registry
from glovebox.firmware.method_registry import compiler_registry, flasher_registry

# Import method selection utilities
from glovebox.firmware.method_selector import (
    CompilerNotAvailableError,
    FlasherNotAvailableError,
    get_compiler_with_fallback_chain,
    get_flasher_with_fallback_chain,
    select_compiler_with_fallback,
    select_flasher_with_fallback,
)
from glovebox.firmware.models import BuildResult, FirmwareOutputFiles, OutputPaths
from glovebox.firmware.options import BuildServiceCompileOpts


__all__ = [
    # Legacy service creation
    "create_build_service",
    # Result models
    "BuildResult",
    "FirmwareOutputFiles",
    "OutputPaths",
    "BuildServiceCompileOpts",
    # Method selection
    "select_compiler_with_fallback",
    "select_flasher_with_fallback",
    "get_compiler_with_fallback_chain",
    "get_flasher_with_fallback_chain",
    "CompilerNotAvailableError",
    "FlasherNotAvailableError",
    # Method registries
    "compiler_registry",
    "flasher_registry",
    # Compile methods
    "DockerCompiler",
    "create_docker_compiler",
]
