"""Docker volume manager for compilation strategies."""

import logging
from pathlib import Path
from typing import Any

from glovebox.config.compile_methods import GenericDockerCompileConfig
from glovebox.core.errors import GloveboxError


logger = logging.getLogger(__name__)


class VolumeManagerError(GloveboxError):
    """Error in volume management."""


class VolumeManager:
    """Manage Docker volume configuration for compilation.

    Handles volume template expansion, path validation, and
    Docker mount configuration for various compilation strategies.
    """

    def __init__(self) -> None:
        """Initialize volume manager."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def prepare_volumes(
        self,
        config: GenericDockerCompileConfig,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        **context: Any,
    ) -> list[str]:
        """Prepare Docker volume configuration for compilation.

        Expands volume templates with provided context and validates
        that all source paths exist before mounting.

        Args:
            config: Compilation configuration with volume templates
            keymap_file: Path to keymap file
            config_file: Path to config file
            output_dir: Output directory for build artifacts
            **context: Additional context for template expansion

        Returns:
            list[str]: Docker volume mount arguments

        Raises:
            VolumeManagerError: If volume preparation fails
        """
        try:
            self.logger.debug("Preparing volumes for compilation")

            # Build template context
            template_context = self._build_template_context(
                keymap_file=keymap_file,
                config_file=config_file,
                output_dir=output_dir,
                **context,
            )

            # Expand volume templates
            volume_mounts = []
            for volume_template in config.volume_templates:
                expanded_volume = self._expand_volume_template(
                    volume_template, template_context
                )
                volume_mounts.append(expanded_volume)

            self.logger.info("Prepared %d volume mounts", len(volume_mounts))
            return volume_mounts

        except Exception as e:
            msg = f"Failed to prepare volumes: {e}"
            self.logger.error(msg)
            raise VolumeManagerError(msg) from e

    def _build_template_context(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        **additional_context: Any,
    ) -> dict[str, str]:
        """Build template context for volume expansion.

        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            output_dir: Output directory
            **additional_context: Additional context variables

        Returns:
            dict[str, str]: Template context for expansion
        """
        context = {
            # File paths
            "keymap_file": str(keymap_file.resolve()),
            "keymap_dir": str(keymap_file.parent.resolve()),
            "config_file": str(config_file.resolve()),
            "config_dir": str(config_file.parent.resolve()),
            "output_dir": str(output_dir.resolve()),
            # Common directories
            "project_root": str(self._find_project_root(keymap_file)),
            "home_dir": str(Path.home()),
            "cwd": str(Path.cwd()),
        }

        # Add additional context
        for key, value in additional_context.items():
            if isinstance(value, str | Path):
                context[key] = str(value)
            else:
                context[key] = str(value)

        self.logger.debug("Built template context with %d variables", len(context))
        return context

    def _expand_volume_template(
        self, volume_template: str, context: dict[str, str]
    ) -> str:
        """Expand volume template with context variables.

        Args:
            volume_template: Volume template string (e.g., "{keymap_dir}:/workspace")
            context: Template context variables

        Returns:
            str: Expanded volume mount string

        Raises:
            VolumeManagerError: If template expansion fails
        """
        try:
            expanded = volume_template.format(**context)

            # Validate volume mount format (source:target or source:target:options)
            parts = expanded.split(":")
            if len(parts) < 2:
                raise VolumeManagerError(
                    f"Invalid volume format: {expanded}. Expected 'source:target' or 'source:target:options'"
                )

            source_path = Path(parts[0])

            # Check if source path exists (skip if it's a Docker volume name)
            if not source_path.is_absolute():
                self.logger.debug(
                    "Skipping existence check for Docker volume: %s", parts[0]
                )
            elif not source_path.exists():
                raise VolumeManagerError(f"Source path does not exist: {source_path}")

            self.logger.debug("Expanded volume: %s -> %s", volume_template, expanded)
            return expanded

        except KeyError as e:
            raise VolumeManagerError(
                f"Missing template variable in volume '{volume_template}': {e}"
            ) from e
        except Exception as e:
            raise VolumeManagerError(
                f"Failed to expand volume template '{volume_template}': {e}"
            ) from e

    def _find_project_root(self, start_path: Path) -> Path:
        """Find project root directory by looking for common markers.

        Args:
            start_path: Starting path to search from

        Returns:
            Path: Project root directory
        """
        current = start_path.resolve()

        # Look for common project markers
        markers = [
            ".git",
            "pyproject.toml",
            "Cargo.toml",
            "package.json",
            "Makefile",
            "CMakeLists.txt",
        ]

        while current != current.parent:
            for marker in markers:
                if (current / marker).exists():
                    return current
            current = current.parent

        # Fallback to current directory
        return Path.cwd()

    def validate_volume_templates(self, volume_templates: list[str]) -> bool:
        """Validate volume template syntax.

        Args:
            volume_templates: List of volume template strings

        Returns:
            bool: True if all templates are valid

        Raises:
            VolumeManagerError: If any template is invalid
        """
        for template in volume_templates:
            if not template.strip():
                raise VolumeManagerError("Empty volume template")

            if ":" not in template:
                raise VolumeManagerError(
                    f"Invalid volume template format: {template}. Must contain ':'"
                )

            # Check for required template variables
            if "{" in template and "}" in template:
                # Extract template variables
                import re

                variables = re.findall(r"\{([^}]+)\}", template)
                self.logger.debug("Template %s uses variables: %s", template, variables)

        return True


def create_volume_manager() -> VolumeManager:
    """Create volume manager instance.

    Returns:
        VolumeManager: New volume manager
    """
    return VolumeManager()
