"""Artifact management for compilation builds."""

# Artifact managers will be added in Phase 5
# from glovebox.compilation.artifacts.collector import ArtifactCollector
# from glovebox.compilation.artifacts.firmware_scanner import FirmwareScanner
# from glovebox.compilation.artifacts.validator import ArtifactValidator


def create_artifact_collector() -> None:
    """Create artifact collector.

    Returns:
        ArtifactCollector: Artifact collector instance
    """
    # Implementation will be added in Phase 5
    pass


def create_firmware_scanner() -> None:
    """Create firmware scanner.

    Returns:
        FirmwareScanner: Firmware scanner instance
    """
    # Implementation will be added in Phase 5
    pass


def create_artifact_validator() -> None:
    """Create artifact validator.

    Returns:
        ArtifactValidator: Artifact validator instance
    """
    # Implementation will be added in Phase 5
    pass


__all__: list[str] = [
    # Artifact managers (to be added)
    # "ArtifactCollector",
    # "FirmwareScanner",
    # "ArtifactValidator",
    # Factory functions
    "create_artifact_collector",
    "create_firmware_scanner",
    "create_artifact_validator",
]
