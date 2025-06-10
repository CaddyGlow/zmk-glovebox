"""Artifact management for compilation builds."""

# Phase 5: Artifact Management - Implementation completed
from glovebox.compilation.artifacts.collector import (
    ArtifactCollector,
    create_artifact_collector,
)
from glovebox.compilation.artifacts.firmware_scanner import (
    FirmwareScanner,
    create_firmware_scanner,
)
from glovebox.compilation.artifacts.validator import (
    ArtifactValidator,
    create_artifact_validator,
)


__all__: list[str] = [
    # Phase 5: Artifact managers
    "ArtifactCollector",
    "FirmwareScanner",
    "ArtifactValidator",
    # Factory functions
    "create_artifact_collector",
    "create_firmware_scanner",
    "create_artifact_validator",
]
