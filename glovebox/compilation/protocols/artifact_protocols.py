"""Artifact management protocols."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from glovebox.firmware.models import FirmwareOutputFiles


@runtime_checkable
class ArtifactCollectorProtocol(Protocol):
    """Protocol for collecting build artifacts."""

    def collect_artifacts(
        self, output_dir: Path
    ) -> tuple[list[Path], FirmwareOutputFiles]:
        """Collect firmware artifacts from output directory.

        Args:
            output_dir: Directory containing build outputs

        Returns:
            tuple: (list of firmware files, structured output files)
        """
        ...


@runtime_checkable
class FirmwareScannerProtocol(Protocol):
    """Protocol for scanning firmware files."""

    def scan_firmware_files(
        self, directory: Path, pattern: str = "*.uf2"
    ) -> list[Path]:
        """Scan directory for firmware files.

        Args:
            directory: Directory to scan
            pattern: File pattern to match

        Returns:
            list[Path]: List of firmware files found
        """
        ...


@runtime_checkable
class ArtifactValidatorProtocol(Protocol):
    """Protocol for validating build artifacts."""

    def validate_artifacts(self, artifacts: list[Path]) -> bool:
        """Validate that artifacts are valid firmware files.

        Args:
            artifacts: List of artifact files to validate

        Returns:
            bool: True if all artifacts are valid
        """
        ...
