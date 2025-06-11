"""Simple artifact collection system using ZMK GitHub Actions conventions."""

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from glovebox.firmware.models import FirmwareOutputFiles


logger = logging.getLogger(__name__)


@dataclass
class BuildMatrixEntry:
    """Single entry from ZMK build.yaml matrix configuration."""

    board: str
    shield: str | None = None
    artifact_name: str | None = None
    snippet: str | None = None
    cmake_args: list[str] | None = None

    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.cmake_args is None:
            self.cmake_args = []


@dataclass
class BuildMatrix:
    """ZMK build.yaml matrix configuration."""

    include: list[BuildMatrixEntry]

    @classmethod
    def from_yaml_file(cls, yaml_file: Path) -> "BuildMatrix":
        """Load build matrix from build.yaml file.

        Args:
            yaml_file: Path to build.yaml file

        Returns:
            BuildMatrix: Loaded build matrix
        """
        try:
            with yaml_file.open() as f:
                data = yaml.safe_load(f)

            entries = []
            for item in data.get("include", []):
                entries.append(BuildMatrixEntry(**item))

            return cls(include=entries)
        except Exception as e:
            logger.error("Failed to load build matrix from %s: %s", yaml_file, e)
            return cls(include=[])

    @classmethod
    def from_workspace_auto_detect(cls, workspace_path: Path) -> "BuildMatrix":
        """Auto-detect and load build matrix from workspace.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            BuildMatrix: Detected build matrix
        """
        # Look for build.yaml in common locations
        potential_files = [
            workspace_path / "build.yaml",
            workspace_path / "build.yml",
            workspace_path / ".github" / "workflows" / "build.yaml",
            workspace_path / ".github" / "workflows" / "build.yml",
        ]

        for yaml_file in potential_files:
            if yaml_file.exists():
                logger.debug("Found build matrix at: %s", yaml_file)
                return cls.from_yaml_file(yaml_file)

        logger.warning("No build.yaml found in workspace: %s", workspace_path)
        return cls(include=[])


class SimpleArtifactCollector:
    """Simple artifact collector using ZMK GitHub Actions conventions.

    Replaces the complex artifact scanning system with a simple, predictable
    approach based on ZMK build matrix files.
    """

    def __init__(self) -> None:
        """Initialize simple artifact collector."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def collect_from_workspace(
        self, workspace_path: Path, build_matrix: BuildMatrix | None = None
    ) -> dict[str, Path]:
        """Collect artifacts using build matrix for naming and location.

        Args:
            workspace_path: Path to workspace directory
            build_matrix: Build matrix configuration (auto-detected if None)

        Returns:
            dict[str, Path]: Mapping of artifact names to file paths
        """
        if build_matrix is None:
            build_matrix = BuildMatrix.from_workspace_auto_detect(workspace_path)

        artifacts = {}

        for entry in build_matrix.include:
            # Generate expected artifact name using ZMK pattern
            artifact_name = self._generate_zmk_artifact_name(entry)

            # Look for .uf2 file in expected build location
            build_dir = self._get_build_directory(workspace_path, entry)
            uf2_file = build_dir / "zephyr" / "zmk.uf2"

            if uf2_file.exists():
                artifacts[artifact_name] = uf2_file
                self.logger.info("Found artifact: %s -> %s", artifact_name, uf2_file)
            else:
                self.logger.warning(
                    "Expected artifact not found: %s at %s", artifact_name, uf2_file
                )

        return artifacts

    def _generate_zmk_artifact_name(self, matrix_entry: BuildMatrixEntry) -> str:
        """Generate artifact name using ZMK GitHub Actions pattern.

        Based on: artifact_name=${artifact_name:-${shield:+$shield-}${board}-zmk}

        Args:
            matrix_entry: Build matrix entry

        Returns:
            str: Generated artifact name
        """
        if matrix_entry.artifact_name:
            return f"{matrix_entry.artifact_name}.uf2"

        shield_prefix = f"{matrix_entry.shield}-" if matrix_entry.shield else ""
        return f"{shield_prefix}{matrix_entry.board}-zmk.uf2"

    def _get_build_directory(
        self, workspace_path: Path, entry: BuildMatrixEntry
    ) -> Path:
        """Get expected build directory for matrix entry.

        Args:
            workspace_path: Path to workspace directory
            entry: Build matrix entry

        Returns:
            Path: Expected build directory
        """
        shield_prefix = f"{entry.shield}-" if entry.shield else ""
        return workspace_path / "build" / f"{shield_prefix}{entry.board}"
        # if entry.shield:
        #     # Split keyboard builds use separate directories
        #     return workspace_path / f"build_{entry.shield}"
        # else:
        #     # Single board builds use build directory
        #     return workspace_path / "build"

    def copy_to_output(
        self, artifacts: dict[str, Path], output_dir: Path
    ) -> dict[str, Path]:
        """Copy artifacts to output directory preserving ZMK names.

        Args:
            artifacts: Mapping of artifact names to source paths
            output_dir: Output directory for artifacts

        Returns:
            dict[str, Path]: Mapping of artifact names to output paths
        """
        copied_artifacts = {}
        output_dir.mkdir(parents=True, exist_ok=True)

        for artifact_name, source_path in artifacts.items():
            dest_path = output_dir / artifact_name
            shutil.copy2(source_path, dest_path)
            copied_artifacts[artifact_name] = dest_path
            self.logger.info("Copied artifact: %s -> %s", source_path, dest_path)

        return copied_artifacts

    def collect_and_copy(
        self,
        workspace_path: Path,
        output_dir: Path,
        build_matrix: BuildMatrix | None = None,
    ) -> FirmwareOutputFiles:
        """Collect artifacts from workspace and copy to output directory.

        Args:
            workspace_path: Path to workspace directory
            output_dir: Output directory for artifacts
            build_matrix: Build matrix configuration (auto-detected if None)

        Returns:
            FirmwareOutputFiles: Structured output files
        """
        # Collect artifacts from workspace
        artifacts = self.collect_from_workspace(workspace_path, build_matrix)

        # Copy to output directory
        copied_artifacts = self.copy_to_output(artifacts, output_dir)

        # Create structured output files
        output_files = FirmwareOutputFiles(output_dir=output_dir)

        # Map artifacts to structured format
        for artifact_name, artifact_path in copied_artifacts.items():
            if not output_files.main_uf2:
                # First artifact becomes main
                output_files.main_uf2 = artifact_path

            # Try to identify left/right hand files
            if "left" in artifact_name.lower() or "lh" in artifact_name.lower():
                output_files.left_uf2 = artifact_path
            elif "right" in artifact_name.lower() or "rh" in artifact_name.lower():
                output_files.right_uf2 = artifact_path

        self.logger.info(
            "Collected %d artifacts: main=%s, left=%s, right=%s",
            len(copied_artifacts),
            output_files.main_uf2.name if output_files.main_uf2 else None,
            output_files.left_uf2.name if output_files.left_uf2 else None,
            output_files.right_uf2.name if output_files.right_uf2 else None,
        )

        return output_files


def generate_zmk_env_vars(matrix_entry: BuildMatrixEntry) -> dict[str, str]:
    """Generate environment variables following ZMK GitHub Actions pattern.

    Args:
        matrix_entry: Build matrix entry

    Returns:
        dict[str, str]: Environment variables for build
    """
    env_vars = {
        "board": matrix_entry.board,
        "display_name": f"{matrix_entry.shield + ' - ' if matrix_entry.shield else ''}{matrix_entry.board}",
    }

    if matrix_entry.shield:
        env_vars["shield"] = matrix_entry.shield

    if matrix_entry.artifact_name:
        env_vars["artifact_name"] = matrix_entry.artifact_name
    else:
        shield_prefix = f"{matrix_entry.shield}-" if matrix_entry.shield else ""
        env_vars["artifact_name"] = f"{shield_prefix}{matrix_entry.board}-zmk"

    if matrix_entry.snippet:
        env_vars["snippet"] = matrix_entry.snippet
        env_vars["extra_west_args"] = f'-S "{matrix_entry.snippet}"'

    # Generate cmake args
    cmake_args = []
    if matrix_entry.shield:
        cmake_args.append(f'-DSHIELD="{matrix_entry.shield}"')
    if matrix_entry.cmake_args:
        cmake_args.extend(matrix_entry.cmake_args)

    if cmake_args:
        env_vars["extra_cmake_args"] = " ".join(cmake_args)

    return env_vars


def create_simple_artifact_collector() -> SimpleArtifactCollector:
    """Create simple artifact collector instance.

    Returns:
        SimpleArtifactCollector: New simple artifact collector
    """
    return SimpleArtifactCollector()


__all__ = [
    "BuildMatrix",
    "BuildMatrixEntry",
    "SimpleArtifactCollector",
    "generate_zmk_env_vars",
    "create_simple_artifact_collector",
]
