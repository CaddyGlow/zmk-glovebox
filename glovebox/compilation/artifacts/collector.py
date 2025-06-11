"""Artifact collector for compilation builds."""

import logging
from pathlib import Path

from glovebox.adapters import create_file_adapter
from glovebox.compilation.protocols.artifact_protocols import (
    FirmwareScannerProtocol,
)
from glovebox.firmware.models import FirmwareOutputFiles
from glovebox.protocols import FileAdapterProtocol


logger = logging.getLogger(__name__)


class ArtifactCollector:
    """Collect build artifacts from compilation outputs.

    Handles the collection and organization of firmware files and other
    build artifacts from various compilation strategies.
    """

    def __init__(
        self,
        file_adapter: FileAdapterProtocol | None = None,
        firmware_scanner: FirmwareScannerProtocol | None = None,
    ) -> None:
        """Initialize artifact collector.

        Args:
            file_adapter: File operations adapter
            firmware_scanner: Firmware file scanner
        """
        self.file_adapter = file_adapter or create_file_adapter()
        self.firmware_scanner = firmware_scanner

    def collect_artifacts(
        self, output_dir: Path
    ) -> tuple[list[Path], FirmwareOutputFiles]:
        """Collect firmware artifacts from output directory.

        Scans the output directory for firmware files and organizes them
        into a structured format for further processing.

        Args:
            output_dir: Directory containing build outputs

        Returns:
            tuple: (list of firmware files, structured output files)
        """
        logger.info("Collecting artifacts from: %s", output_dir)

        firmware_files = []
        output_files = FirmwareOutputFiles(output_dir=output_dir)

        try:
            # Check if output directory exists
            if not self.file_adapter.check_exists(output_dir):
                logger.warning("Output directory does not exist: %s", output_dir)
                return [], output_files

            # Collect firmware files using multiple strategies
            firmware_files = self._collect_firmware_files(output_dir)

            # Organize files into structured output
            output_files = self._organize_output_files(firmware_files, output_dir)

            logger.info(
                "Collected %d firmware files from %s", len(firmware_files), output_dir
            )

        except Exception as e:
            logger.error("Failed to collect artifacts from %s: %s", output_dir, str(e))

        return firmware_files, output_files

    def _collect_firmware_files(self, output_dir: Path) -> list[Path]:
        """Collect firmware files from output directory.

        Args:
            output_dir: Directory to scan for firmware files

        Returns:
            list[Path]: List of firmware files found
        """
        firmware_files = []

        # Strategy 1: Use firmware scanner if available
        if self.firmware_scanner:
            logger.debug("Using firmware scanner for collection")
            scanner_files = self.firmware_scanner.scan_firmware_files(output_dir)
            firmware_files.extend(scanner_files)
            return firmware_files

        # Strategy 2: Direct scanning for .uf2 files
        firmware_files.extend(self._scan_base_directory(output_dir))
        firmware_files.extend(self._scan_west_build_directories(output_dir))
        firmware_files.extend(self._scan_subdirectories(output_dir))

        return firmware_files

    def _scan_base_directory(self, output_dir: Path) -> list[Path]:
        """Scan base output directory for firmware files.

        Args:
            output_dir: Base output directory

        Returns:
            list[Path]: Firmware files in base directory
        """
        try:
            files = self.file_adapter.list_files(output_dir, "*.uf2")
            logger.debug("Found %d firmware files in base directory", len(files))
            return files
        except Exception as e:
            logger.warning("Failed to scan base directory %s: %s", output_dir, str(e))
            return []

    def _scan_west_build_directories(self, output_dir: Path) -> list[Path]:
        """Scan west build output directories for firmware files.

        Args:
            output_dir: Base output directory

        Returns:
            list[Path]: Firmware files in west build directories
        """
        firmware_files = []
        build_dir = output_dir / "build"

        try:
            if self.file_adapter.check_exists(build_dir) and self.file_adapter.is_dir(
                build_dir
            ):
                logger.debug("Scanning west build directory: %s", build_dir)

                # Check for board-specific build directories
                build_subdirs = self.file_adapter.list_directory(build_dir)
                for subdir in build_subdirs:
                    if self.file_adapter.is_dir(subdir):
                        firmware_files.extend(self._scan_zephyr_directory(subdir))

        except Exception as e:
            logger.warning(
                "Failed to scan west build directories in %s: %s", output_dir, str(e)
            )

        return firmware_files

    def _scan_zephyr_directory(self, build_subdir: Path) -> list[Path]:
        """Scan zephyr directory within build subdirectory.

        Args:
            build_subdir: Build subdirectory to scan

        Returns:
            list[Path]: Firmware files in zephyr directory
        """
        firmware_files = []
        zephyr_dir = build_subdir / "zephyr"

        if self.file_adapter.check_exists(zephyr_dir):
            zmk_uf2 = zephyr_dir / "zmk.uf2"
            if self.file_adapter.check_exists(zmk_uf2):
                firmware_files.append(zmk_uf2)
                logger.debug("Found west build firmware: %s", zmk_uf2)

        return firmware_files

    def _scan_subdirectories(self, output_dir: Path) -> list[Path]:
        """Scan subdirectories for firmware files (legacy support).

        Args:
            output_dir: Base output directory

        Returns:
            list[Path]: Firmware files in subdirectories
        """
        firmware_files = []

        try:
            subdirs = self.file_adapter.list_directory(output_dir)
            for subdir in subdirs:
                if self.file_adapter.is_dir(subdir) and subdir.name != "build":
                    subdir_files = self.file_adapter.list_files(subdir, "*.uf2")
                    firmware_files.extend(subdir_files)
                    logger.debug(
                        "Found %d firmware files in subdirectory %s",
                        len(subdir_files),
                        subdir,
                    )

        except Exception as e:
            logger.warning(
                "Failed to scan subdirectories in %s: %s", output_dir, str(e)
            )

        return firmware_files

    def _organize_output_files(
        self, firmware_files: list[Path], output_dir: Path
    ) -> FirmwareOutputFiles:
        """Organize firmware files into structured output.

        Args:
            firmware_files: List of collected firmware files
            output_dir: Base output directory

        Returns:
            FirmwareOutputFiles: Structured output files
        """
        output_files = FirmwareOutputFiles(output_dir=output_dir)

        if not firmware_files:
            return output_files

        # Set main firmware file (first one found)
        output_files.main_uf2 = firmware_files[0]

        # Try to identify left/right hand files based on directory structure
        for firmware_file in firmware_files:
            parent_dir = firmware_file.parent.name.lower()

            if parent_dir == "lf" or "left" in parent_dir:
                output_files.left_uf2 = firmware_file
            elif parent_dir == "rh" or "right" in parent_dir:
                output_files.right_uf2 = firmware_file

        # Set artifacts directory if we found build artifacts
        build_dir = output_dir / "build"
        if self.file_adapter.check_exists(build_dir):
            output_files.artifacts_dir = build_dir

        logger.debug(
            "Organized output files: main=%s, left=%s, right=%s",
            output_files.main_uf2,
            output_files.left_uf2,
            output_files.right_uf2,
        )

        return output_files


def create_artifact_collector(
    file_adapter: FileAdapterProtocol | None = None,
    firmware_scanner: FirmwareScannerProtocol | None = None,
) -> ArtifactCollector:
    """Create artifact collector instance.

    Args:
        file_adapter: File operations adapter
        firmware_scanner: Firmware file scanner

    Returns:
        ArtifactCollector: New artifact collector instance
    """
    return ArtifactCollector(file_adapter, firmware_scanner)
