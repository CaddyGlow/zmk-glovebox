"""Firmware domain - Flash operations and models."""

# Import registry initialization to ensure methods are registered
from glovebox.firmware import registry_init  # noqa: F401

# Import method registry (flasher methods still needed for flash operations)
from glovebox.firmware.method_registry import flasher_registry
from glovebox.firmware.models import BuildResult, FirmwareOutputFiles, OutputPaths


__all__ = [
    # Result models
    "BuildResult",
    "FirmwareOutputFiles",
    "OutputPaths",
    # Method registries (flasher methods still needed)
    "flasher_registry",
]
