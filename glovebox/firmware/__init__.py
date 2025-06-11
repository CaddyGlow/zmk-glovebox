"""Firmware domain - Build and flash operations."""

# Import registry initialization to ensure methods are registered
from glovebox.firmware import registry_init  # noqa: F401
from glovebox.firmware.build_service import create_build_service

# Import method registry (flasher methods still needed for flash operations)
from glovebox.firmware.method_registry import flasher_registry
from glovebox.firmware.models import BuildResult, FirmwareOutputFiles, OutputPaths
from glovebox.firmware.options import BuildServiceCompileOpts


__all__ = [
    # Service creation
    "create_build_service",
    # Result models
    "BuildResult",
    "FirmwareOutputFiles",
    "OutputPaths",
    "BuildServiceCompileOpts",
    # Method registries (flasher methods still needed)
    "flasher_registry",
]
