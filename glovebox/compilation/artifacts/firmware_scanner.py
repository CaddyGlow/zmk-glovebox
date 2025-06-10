"""Firmware scanner for detecting firmware files in various directory structures."""

import logging
from pathlib import Path

from glovebox.adapters import create_file_adapter
from glovebox.protocols import FileAdapterProtocol


logger = logging.getLogger(__name__)


class FirmwareScanner:
    """Scan directory structures for firmware files.

    Provides intelligent scanning of build output directories to locate
    firmware files (.uf2) in various directory structures used by different
    compilation strategies.
    """

    def __init__(self, file_adapter: FileAdapterProtocol | None = None) -> None:
        """Initialize firmware scanner.

        Args:
            file_adapter: File operations adapter
        """
        self.file_adapter = file_adapter or create_file_adapter()

    def scan_firmware_files(
        self, directory: Path, pattern: str = "*.uf2"
    ) -> list[Path]:
        """Scan directory for firmware files.

        Performs comprehensive scanning of directory structure using multiple
        strategies to locate firmware files in various build output formats.

        Args:
            directory: Directory to scan
            pattern: File pattern to match

        Returns:
            list[Path]: List of firmware files found
        """
        logger.debug("Scanning for firmware files in: %s", directory)

        if not self.file_adapter.check_exists(directory):
            logger.warning("Directory does not exist: %s", directory)
            return []

        firmware_files = []

        # Strategy 1: Scan base directory
        firmware_files.extend(self._scan_direct(directory, pattern))

        # Strategy 2: Scan west build structure
        firmware_files.extend(self._scan_west_structure(directory, pattern))

        # Strategy 3: Scan ZMK config structure
        firmware_files.extend(self._scan_zmk_config_structure(directory, pattern))

        # Strategy 4: Scan legacy subdirectories
        firmware_files.extend(self._scan_legacy_structure(directory, pattern))

        # Remove duplicates while preserving order
        unique_files = []
        seen = set()
        for file_path in firmware_files:
            if file_path not in seen:
                seen.add(file_path)
                unique_files.append(file_path)

        logger.debug("Found %d firmware files in %s", len(unique_files), directory)

        return unique_files

    def _scan_direct(self, directory: Path, pattern: str) -> list[Path]:
        """Scan directory directly for firmware files.

        Args:
            directory: Directory to scan
            pattern: File pattern to match

        Returns:
            list[Path]: Firmware files in directory
        """
        try:
            files = self.file_adapter.list_files(directory, pattern)
            logger.debug("Direct scan found %d files in %s", len(files), directory)
            return files
        except Exception as e:
            logger.warning(
                "Failed to scan directory %s directly: %s", directory, str(e)
            )
            return []

    def _scan_west_structure(self, directory: Path, pattern: str) -> list[Path]:
        """Scan west build directory structure.

        West builds typically create:
        build/
        ├── board_name/
        │   └── zephyr/
        │       └── zmk.uf2
        └── other_board/
            └── zephyr/
                └── zmk.uf2

        Args:
            directory: Base directory to scan
            pattern: File pattern to match

        Returns:
            list[Path]: Firmware files in west structure
        """
        firmware_files = []
        build_dir = directory / "build"

        try:
            if self.file_adapter.check_exists(build_dir) and self.file_adapter.is_dir(
                build_dir
            ):
                # Scan board-specific directories
                board_dirs = self.file_adapter.list_directory(build_dir)
                for board_dir in board_dirs:
                    if self.file_adapter.is_dir(board_dir):
                        zephyr_dir = board_dir / "zephyr"
                        if self.file_adapter.check_exists(zephyr_dir):
                            zephyr_files = self.file_adapter.list_files(
                                zephyr_dir, pattern
                            )
                            firmware_files.extend(zephyr_files)
                            logger.debug(
                                "West structure scan found %d files in %s",
                                len(zephyr_files),
                                zephyr_dir,
                            )

        except Exception as e:
            logger.warning("Failed to scan west structure in %s: %s", directory, str(e))

        return firmware_files

    def _scan_zmk_config_structure(self, directory: Path, pattern: str) -> list[Path]:
        """Scan ZMK config build directory structure.

        ZMK config builds may create:
        artifacts/
        ├── board_name.uf2
        ├── board_shield.uf2
        └── build-info.json

        Args:
            directory: Base directory to scan
            pattern: File pattern to match

        Returns:
            list[Path]: Firmware files in ZMK config structure
        """
        firmware_files = []
        artifacts_dir = directory / "artifacts"

        try:
            if self.file_adapter.check_exists(
                artifacts_dir
            ) and self.file_adapter.is_dir(artifacts_dir):
                artifact_files = self.file_adapter.list_files(artifacts_dir, pattern)
                firmware_files.extend(artifact_files)
                logger.debug(
                    "ZMK config structure scan found %d files in %s",
                    len(artifact_files),
                    artifacts_dir,
                )

        except Exception as e:
            logger.warning(
                "Failed to scan ZMK config structure in %s: %s", directory, str(e)
            )

        return firmware_files

    def _scan_legacy_structure(self, directory: Path, pattern: str) -> list[Path]:
        """Scan legacy directory structure.

        Legacy builds may create:
        output/
        ├── lf/
        │   └── zmk.uf2
        ├── rh/
        │   └── zmk.uf2
        └── glove80.uf2

        Args:
            directory: Base directory to scan
            pattern: File pattern to match

        Returns:
            list[Path]: Firmware files in legacy structure
        """
        firmware_files = []

        try:
            # Common subdirectory names for left/right hand splits
            subdirs_to_check = ["lf", "rh", "left", "right", "artifacts"]

            # Get all subdirectories
            all_subdirs = self.file_adapter.list_directory(directory)

            for subdir in all_subdirs:
                if (
                    self.file_adapter.is_dir(subdir)
                    and subdir.name
                    not in ["build"]  # Skip build dir (handled separately)
                ):
                    subdir_files = self.file_adapter.list_files(subdir, pattern)
                    firmware_files.extend(subdir_files)

                    if subdir_files:
                        logger.debug(
                            "Legacy structure scan found %d files in %s",
                            len(subdir_files),
                            subdir,
                        )

        except Exception as e:
            logger.warning(
                "Failed to scan legacy structure in %s: %s", directory, str(e)
            )

        return firmware_files

    def scan_specific_patterns(
        self, directory: Path, patterns: list[str]
    ) -> dict[str, list[Path]]:
        """Scan for multiple file patterns.

        Args:
            directory: Directory to scan
            patterns: List of file patterns to match

        Returns:
            dict: Mapping of pattern to list of matching files
        """
        results = {}

        for pattern in patterns:
            results[pattern] = self.scan_firmware_files(directory, pattern)

        return results

    def get_firmware_info(self, firmware_file: Path) -> dict[str, str | None]:
        """Get information about a firmware file.

        Args:
            firmware_file: Path to firmware file

        Returns:
            dict: Firmware file information
        """
        if not self.file_adapter.check_exists(firmware_file):
            return {"exists": "false", "error": "File does not exist"}

        try:
            file_size = firmware_file.stat().st_size if firmware_file.exists() else 0
            parent_dir = firmware_file.parent.name

            # Determine likely board/shield based on filename and location
            board_hint = None
            if "_" in firmware_file.stem:
                board_hint = firmware_file.stem.split("_")[0]
            elif parent_dir.lower() in ["lf", "left"]:
                board_hint = "left_hand"
            elif parent_dir.lower() in ["rh", "right"]:
                board_hint = "right_hand"

            return {
                "exists": "true",
                "size_bytes": str(file_size),
                "parent_directory": parent_dir,
                "board_hint": board_hint,
                "filename": firmware_file.name,
            }

        except Exception as e:
            return {"exists": "true", "error": f"Failed to get info: {e}"}


def create_firmware_scanner(
    file_adapter: FileAdapterProtocol | None = None,
) -> FirmwareScanner:
    """Create firmware scanner instance.

    Args:
        file_adapter: File operations adapter

    Returns:
        FirmwareScanner: New firmware scanner instance
    """
    return FirmwareScanner(file_adapter)
