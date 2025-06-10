"""Build matrix resolver following GitHub Actions workflow pattern."""

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from glovebox.compilation.models.build_matrix import (
    BuildMatrix,
    BuildTarget,
    BuildYamlConfig,
)
from glovebox.core.errors import GloveboxError


logger = logging.getLogger(__name__)


class BuildMatrixResolverError(GloveboxError):
    """Error in build matrix resolution."""


class BuildMatrixResolver:
    """Resolve build matrix from build.yaml following GitHub Actions pattern.

    This class implements the same build matrix resolution logic used by
    ZMK's official GitHub Actions workflow, ensuring compatibility with
    existing ZMK user configurations.
    """

    def __init__(self) -> None:
        """Initialize build matrix resolver."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def resolve_from_build_yaml(self, build_yaml_path: Path) -> BuildMatrix:
        """Parse build.yaml and create build matrix.

        Follows the GitHub Actions workflow pattern used by ZMK:
        - Supports include/board format
        - Handles shield combinations
        - Generates proper artifact names

        Args:
            build_yaml_path: Path to build.yaml file

        Returns:
            BuildMatrix: Resolved build matrix

        Raises:
            BuildMatrixResolverError: If build.yaml parsing fails
        """
        try:
            self.logger.debug("Parsing build.yaml from %s", build_yaml_path)
            build_config = self._load_build_yaml(build_yaml_path)

            # Validate configuration using Pydantic model
            validated_config = BuildYamlConfig.model_validate(build_config)

            # Resolve build targets from configuration
            targets = self._resolve_build_targets(validated_config)

            self.logger.info("Resolved %d build targets", len(targets))
            return BuildMatrix(
                targets=targets,
                board_defaults=validated_config.board or [],
                shield_defaults=validated_config.shield or [],
            )

        except (FileNotFoundError, yaml.YAMLError, ValidationError) as e:
            msg = f"Failed to parse build.yaml: {e}"
            self.logger.error(msg)
            raise BuildMatrixResolverError(msg) from e

    def _load_build_yaml(self, build_yaml_path: Path) -> dict[str, Any]:
        """Load and parse build.yaml file.

        Args:
            build_yaml_path: Path to build.yaml file

        Returns:
            dict: Parsed YAML configuration

        Raises:
            FileNotFoundError: If build.yaml not found
            yaml.YAMLError: If YAML parsing fails
        """
        with build_yaml_path.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _resolve_build_targets(self, config: BuildYamlConfig) -> list[BuildTarget]:
        """Resolve build targets from configuration.

        Implements GitHub Actions build matrix logic:
        1. Use explicit include entries if present
        2. Generate combinations from board/shield defaults
        3. Apply proper artifact naming

        Args:
            config: Validated build configuration

        Returns:
            list[BuildTarget]: Resolved build targets
        """
        targets: list[BuildTarget] = []

        # Process explicit include entries (GitHub Actions pattern)
        if config.include:
            targets.extend(self._process_include_entries(config.include))

        # Generate combinations from defaults if no explicit includes
        if not targets and (config.board or config.shield):
            targets.extend(self._generate_default_combinations(config))

        # Apply artifact naming to all targets
        for target in targets:
            if not target.artifact_name:
                target.artifact_name = self._generate_artifact_name(target)

        return targets

    def _process_include_entries(
        self, include_entries: list[dict[str, Any]]
    ) -> list[BuildTarget]:
        """Process explicit include entries from build.yaml.

        Args:
            include_entries: List of include configurations

        Returns:
            list[BuildTarget]: Build targets from include entries
        """
        targets: list[BuildTarget] = []

        for entry in include_entries:
            board = entry.get("board")
            if not board:
                self.logger.warning("Include entry missing board: %s", entry)
                continue

            target = BuildTarget(
                board=board,
                shield=entry.get("shield"),
                cmake_args=entry.get("cmake-args", []),
                snippet=entry.get("snippet"),
                artifact_name=entry.get("artifact-name"),
            )
            targets.append(target)

        self.logger.debug("Processed %d include entries", len(targets))
        return targets

    def _generate_default_combinations(
        self, config: BuildYamlConfig
    ) -> list[BuildTarget]:
        """Generate board/shield combinations from defaults.

        Args:
            config: Build configuration with defaults

        Returns:
            list[BuildTarget]: Generated build targets
        """
        targets: list[BuildTarget] = []
        boards = config.board or []
        shields = config.shield or []

        # If shields specified, create board+shield combinations
        if shields:
            for board in boards:
                for shield in shields:
                    targets.append(BuildTarget(board=board, shield=shield))
        else:
            # No shields, just boards
            for board in boards:
                targets.append(BuildTarget(board=board))

        self.logger.debug(
            "Generated %d combinations from %d boards, %d shields",
            len(targets),
            len(boards),
            len(shields),
        )
        return targets

    def _generate_artifact_name(self, target: BuildTarget) -> str:
        """Generate artifact name following GitHub Actions pattern.

        Pattern: <board>-<shield> or just <board> if no shield

        Args:
            target: Build target

        Returns:
            str: Generated artifact name
        """
        if target.shield:
            return f"{target.board}-{target.shield}"
        return target.board


def create_build_matrix_resolver() -> BuildMatrixResolver:
    """Create build matrix resolver instance.

    Returns:
        BuildMatrixResolver: New build matrix resolver
    """
    return BuildMatrixResolver()
