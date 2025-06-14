"""Moergo compilation strategy implementation."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from glovebox.cli.strategies.base import BaseCompilationStrategy, CompilationParams
from glovebox.config.compile_methods import (
    DockerCompilationConfig,
    DockerUserConfig,
    MoergoCompilationConfig,
    ZmkCompilationConfig,
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

    # def extract_docker_image(
    #     self, config: MoergoCompilationConfig, profile: "KeyboardProfile"
    # ) -> str:
    #     """Extract Docker image from profile.
    #
    #     Args:
    #         profile: Keyboard profile
    #
    #     Returns:
    #         str: Docker image for Moergo compilation
    #     """
    #     # Try to get Docker image from profile firmware config
    #     if (
    #         hasattr(profile, "firmware_version")
    #         and profile.firmware_version
    #         and hasattr(profile.firmware_version, "docker_config")
    #     ):
    #         pass
    #         # TODO:we have to loop over the compile_methods
    #         # to find the right one should be the first normally
    #
    #         # firmware_config = profile.keyboard_config.compile_methods.
    #         # if (
    #         #     firmware_config
    #         #     and hasattr(firmware_config, "image")
    #         #     and firmware_config.image
    #         # ):
    #         #     return str(firmware_config.image)
    #
    #     # Return Moergo-specific image
    #     return config.image

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

        config = MoergoCompilationConfig()

        # Build Docker user configuration (Moergo disables user mapping by default)
        config = self._build_docker_user_config(config, params)

        # Build workspace path configuration
        config = self._build_workspace_path(config, params)

        # Get repository branch from parameters or profile
        config.branch = self._get_repository_branch(config, params, profile)

        return config

    def get_service_name(self) -> str:
        """Get the compilation service name.

        Returns:
            str: Service name for Moergo strategy
        """
        return "moergo_compilation"

    def _build_docker_user_config(
        self, config: MoergoCompilationConfig, params: CompilationParams
    ) -> MoergoCompilationConfig:
        """Build Docker user configuration for Moergo.

        Moergo compilation disables user mapping by default.

        Args:
            params: Compilation parameters

        Returns:
            DockerUserConfig: Docker user configuration
        """
        if params.no_docker_user_mapping is not None:
            config.docker_user.enable_user_mapping = not params.no_docker_user_mapping

        if params.docker_uid is not None:
            config.docker_user.manual_uid = params.docker_uid

        if params.docker_gid is not None:
            config.docker_user.manual_gid = params.docker_gid

        if params.docker_username is not None:
            config.docker_user.manual_username = params.docker_username

        if params.docker_home is not None:
            config.docker_user.host_home_dir = Path(params.docker_home)

        if params.docker_container_home is not None:
            config.docker_user.container_home_dir = params.docker_container_home

        return config

    def _build_workspace_path(
        self, config: "MoergoCompilationConfig", params: CompilationParams
    ) -> "MoergoCompilationConfig":
        """Build workspace path configuration for Moergo.

        Args:
            params: Compilation parameters
            profile: Keyboard profile

        Returns:
            DockerPath: Workspace path configuration
        """
        # Use output directory as the host path, map to /workspace in container
        # if params.workspace_dir:
        #     config.workspace_path.host_path = params.workspace_dir
        return config

    def _get_repository_branch(
        self,
        config: "MoergoCompilationConfig",
        params: CompilationParams,
        profile: "KeyboardProfile",
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

        # Try to get from profile firmware config
        if (
            hasattr(profile, "firmware_config")
            and profile.firmware_config
            and hasattr(profile.firmware_config, "build_options")
        ):
            build_options = profile.firmware_config.build_options
            if hasattr(build_options, "branch") and build_options.branch:
                return str(build_options.branch)

        # Default to stable Moergo branch
        return config.branch


def create_moergo_strategy() -> MoergoStrategy:
    """Create Moergo compilation strategy.

    Returns:
        MoergoStrategy: Configured strategy instance
    """
    return MoergoStrategy()
