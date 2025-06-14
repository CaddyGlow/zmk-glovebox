"""ZMK config compilation strategy implementation."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from glovebox.cli.strategies.base import BaseCompilationStrategy, CompilationParams
from glovebox.compilation.models.build_matrix import BuildYamlConfig
from glovebox.config.compile_methods import (
    CacheConfig,
    DockerCompilationConfig,
    DockerUserConfig,
    ZmkCompilationConfig,
    ZmkWorkspaceConfig,
)
from glovebox.config.models.workspace import UserWorkspaceConfig
from glovebox.models.docker_path import DockerPath


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

logger = logging.getLogger(__name__)


class ZmkConfigStrategy(BaseCompilationStrategy):
    """ZMK config compilation strategy.

    Handles standard ZMK firmware compilation using the zmk_config method.
    This strategy builds firmware by setting up a ZMK workspace and using
    west build commands.
    """

    def __init__(self) -> None:
        """Initialize ZMK config strategy."""
        super().__init__("zmk_config")

    def supports_profile(self, profile: "KeyboardProfile") -> bool:
        """Check if strategy supports the given profile.

        ZMK config strategy supports most keyboard profiles except those
        specifically requiring Moergo builds.

        Args:
            profile: Keyboard profile to check

        Returns:
            bool: True if strategy supports this profile
        """
        # ZMK config supports most profiles except Moergo-specific ones
        return not self._is_moergo_profile(profile)

    def extract_docker_image(self, profile: "KeyboardProfile") -> str:
        """Extract Docker image from profile.

        Args:
            profile: Keyboard profile

        Returns:
            str: Docker image for ZMK compilation
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

        # Return default ZMK image
        return self._get_default_docker_image(profile)

    def build_config(
        self, params: CompilationParams, profile: "KeyboardProfile"
    ) -> DockerCompilationConfig:
        """Build ZMK compilation configuration.

        Args:
            params: Compilation parameters from CLI
            profile: Keyboard profile

        Returns:
            ZmkCompilationConfig: Configuration for ZMK compilation
        """
        self._validate_params(params)

        # Build Docker user configuration
        docker_user_config = self._build_docker_user_config(params)

        # Build workspace configuration
        workspace_config = self._build_workspace_config(params, profile)

        # Build cache configuration
        cache_config = CacheConfig(
            enabled=not params.no_cache,
        )

        # Build YAML configuration
        build_yaml_config = BuildYamlConfig()

        return ZmkCompilationConfig(
            jobs=params.jobs,
            docker_user=docker_user_config,
            cache=cache_config,
            build_config=build_yaml_config,
            workspace=workspace_config,
        )

    def get_service_name(self) -> str:
        """Get the compilation service name.

        Returns:
            str: Service name for ZMK config strategy
        """
        return "zmk_config_compilation"

    def _is_moergo_profile(self, profile: "KeyboardProfile") -> bool:
        """Check if profile is a Moergo-specific profile.

        Args:
            profile: Keyboard profile to check

        Returns:
            bool: True if profile requires Moergo compilation
        """
        # Check for Moergo-specific indicators
        keyboard_name = getattr(profile, "keyboard_name", "").lower()
        return "moergo" in keyboard_name or "glove80" in keyboard_name

    def _build_docker_user_config(self, params: CompilationParams) -> DockerUserConfig:
        """Build Docker user configuration from parameters.

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

    def _build_workspace_config(
        self, params: CompilationParams, profile: "KeyboardProfile"
    ) -> ZmkWorkspaceConfig:
        """Build ZMK workspace configuration.

        Args:
            params: Compilation parameters
            profile: Keyboard profile

        Returns:
            ZmkWorkspaceConfig: ZMK workspace configuration
        """
        # Get user workspace config
        user_workspace_config = UserWorkspaceConfig()

        # Create workspace paths
        workspace_root = (
            user_workspace_config.root_directory / f"zmk_{profile.keyboard_name}"
        )

        workspace_path = DockerPath(
            host_path=workspace_root, container_path="/workspace"
        )

        config_path = DockerPath(
            host_path=workspace_root / "config", container_path="/workspace/config"
        )

        build_root = DockerPath(
            host_path=params.output_dir, container_path="/workspace/build"
        )

        return ZmkWorkspaceConfig(
            workspace_path=workspace_path,
            config_path=config_path,
            build_root=build_root,
            build_matrix_file=Path("build.yaml"),
            config_repo_url=self._get_zmk_config_repo(params, profile),
        )

    def _get_zmk_config_repo(
        self, params: CompilationParams, profile: "KeyboardProfile"
    ) -> str | None:
        """Get ZMK config repository URL.

        Args:
            params: Compilation parameters
            profile: Keyboard profile

        Returns:
            str | None: Repository URL if specified
        """
        if params.repo:
            return params.repo

        # Try to get from profile
        if (
            hasattr(profile, "firmware_version")
            and profile.firmware_version
            and hasattr(profile.firmware_version, "repository_url")
        ):
            firmware_config = profile.firmware_version
            if (
                hasattr(firmware_config, "repository_url")
                and firmware_config.repository_url
            ):
                return str(firmware_config.repository_url)

        return None


def create_zmk_config_strategy() -> ZmkConfigStrategy:
    """Create ZMK config compilation strategy.

    Returns:
        ZmkConfigStrategy: Configured strategy instance
    """
    return ZmkConfigStrategy()
