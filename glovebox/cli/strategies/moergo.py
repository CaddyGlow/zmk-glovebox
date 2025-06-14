"""Moergo compilation strategy implementation."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from glovebox.cli.strategies.base import BaseCompilationStrategy, CompilationParams
from glovebox.config.compile_methods import (
    DockerCompilationConfig,
    DockerUserConfig,
    MoergoCompilationConfig,
)
from glovebox.models.docker_path import DockerPath


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

logger = logging.getLogger(__name__)


class MoergoStrategy(BaseCompilationStrategy):
    """Moergo compilation strategy.

    Handles Moergo Glove80 firmware compilation using the Nix-based Docker
    container and Moergo-specific build processes.
    """

    def __init__(self) -> None:
        """Initialize Moergo strategy."""
        super().__init__("moergo")

    def supports_profile(self, profile: "KeyboardProfile") -> bool:
        """Check if strategy supports the given profile.

        Moergo strategy only supports Moergo/Glove80 keyboards.

        Args:
            profile: Keyboard profile to check

        Returns:
            bool: True if profile is Moergo/Glove80
        """
        keyboard_name = getattr(profile, "keyboard_name", "").lower()
        return "moergo" in keyboard_name or "glove80" in keyboard_name

    def extract_docker_image(self, profile: "KeyboardProfile") -> str:
        """Extract Docker image from profile.

        Args:
            profile: Keyboard profile

        Returns:
            str: Docker image for Moergo compilation
        """
        # Try to get Docker image from profile firmware config
        if (
            hasattr(profile, "firmware_version")
            and profile.firmware_version
            and hasattr(profile.firmware_version, "docker_config")
        ):
            firmware_config = profile.firmware_version.docker_config
            if (
                firmware_config
                and hasattr(firmware_config, "image")
                and firmware_config.image
            ):
                return str(firmware_config.image)

        # Return Moergo-specific image
        return "glove80-zmk-config-docker"

    def build_config(
        self, params: CompilationParams, profile: "KeyboardProfile"
    ) -> DockerCompilationConfig:
        """Build Moergo compilation configuration.

        Args:
            params: Compilation parameters from CLI
            profile: Keyboard profile

        Returns:
            MoergoCompilationConfig: Configuration for Moergo compilation
        """
        self._validate_params(params)

        # Build Docker user configuration (Moergo disables user mapping by default)
        docker_user_config = self._build_docker_user_config(params)

        # Build workspace path configuration
        workspace_path = self._build_workspace_path(params, profile)

        # Get repository branch from parameters or profile
        branch = self._get_repository_branch(params, profile)

        return MoergoCompilationConfig(
            jobs=params.jobs,
            docker_user=docker_user_config,
            workspace_path=workspace_path,
            branch=branch,
            build_commands=self._build_moergo_commands(params),
        )

    def get_service_name(self) -> str:
        """Get the compilation service name.

        Returns:
            str: Service name for Moergo strategy
        """
        return "moergo_compilation"

    def _build_docker_user_config(self, params: CompilationParams) -> DockerUserConfig:
        """Build Docker user configuration for Moergo.

        Moergo compilation disables user mapping by default.

        Args:
            params: Compilation parameters

        Returns:
            DockerUserConfig: Docker user configuration
        """
        return DockerUserConfig(
            enable_user_mapping=not params.no_docker_user_mapping,
            manual_uid=params.docker_uid,
            manual_gid=params.docker_gid,
            manual_username=params.docker_username,
            host_home_dir=Path(params.docker_home) if params.docker_home else None,
            container_home_dir=params.docker_container_home or "/tmp",
        )

    def _build_workspace_path(
        self, params: CompilationParams, profile: "KeyboardProfile"
    ) -> DockerPath:
        """Build workspace path configuration for Moergo.

        Args:
            params: Compilation parameters
            profile: Keyboard profile

        Returns:
            DockerPath: Workspace path configuration
        """
        # Use output directory as the host path, map to /config in container
        return DockerPath(host_path=params.output_dir, container_path="/config")

    def _get_repository_branch(
        self, params: CompilationParams, profile: "KeyboardProfile"
    ) -> str:
        """Get repository branch for Moergo compilation.

        Args:
            params: Compilation parameters
            profile: Keyboard profile

        Returns:
            str: Repository branch to use
        """
        # Use branch from parameters if specified
        if params.branch:
            return params.branch

        # Try to get from profile firmware version
        if (
            hasattr(profile, "firmware_version")
            and profile.firmware_version
            and hasattr(profile.firmware_version, "version")
        ):
            firmware_config = profile.firmware_version
            if hasattr(firmware_config, "version") and firmware_config.version:
                return str(firmware_config.version)

        # Default to stable Moergo branch
        return "v25.05"

    def _build_moergo_commands(self, params: CompilationParams) -> list[str]:
        """Build Moergo-specific build commands.

        Args:
            params: Compilation parameters

        Returns:
            list[str]: Build commands for Moergo compilation
        """
        commands = []

        # Set working directory to /config
        commands.append("cd /config")

        # Set environment variables for the build
        commands.append("export UID=$(id -u)")
        commands.append("export GID=$(id -g)")

        # Run the Nix build
        commands.append(
            "nix-build ./config --arg firmware 'import /src/default.nix {}' -j2 -o /tmp/combined --show-trace"
        )

        # Install the firmware file with proper ownership
        commands.append(
            'install -o "$UID" -g "$GID" /tmp/combined/glove80.uf2 ./glove80.uf2'
        )

        return commands


def create_moergo_strategy() -> MoergoStrategy:
    """Create Moergo compilation strategy.

    Returns:
        MoergoStrategy: Configured strategy instance
    """
    return MoergoStrategy()
