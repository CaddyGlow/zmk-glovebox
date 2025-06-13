"""Parameter consolidation objects for ZMK compilation operations."""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.config.compile_methods import (
        DockerCompilationConfig,
        ZmkWorkspaceConfig,
    )
    from glovebox.config.profile import KeyboardProfile
    from glovebox.models.docker_path import DockerPath


@dataclass
class ZmkCompilationParams:
    """Simple parameter consolidation for ZMK compilation operations.

    Groups together the core parameters needed for ZMK compilation setup
    to reduce function signature complexity and improve maintainability.
    """

    keymap_file: Path
    config_file: Path
    compilation_config: "DockerCompilationConfig"
    keyboard_profile: "KeyboardProfile | None" = None

    @property
    def should_use_dynamic_generation(self) -> bool:
        """Determine if dynamic workspace generation should be used.

        Returns:
            bool: True if dynamic generation should be used
        """
        if not self.keyboard_profile:
            return False

        if (
            not self.compilation_config.zmk_config_repo
            or not self.compilation_config.zmk_config_repo.config_repo_url
        ):
            return True

        repo_url = self.compilation_config.zmk_config_repo.config_repo_url.strip()
        return not repo_url


@dataclass
class ZmkWorkspaceParams:
    """Parameters for workspace and command operations.

    Consolidates workspace-specific parameters needed for command generation
    and workspace management operations.
    """

    workspace_path: Path
    zmk_config: "ZmkWorkspaceConfig"
    keyboard_profile: "KeyboardProfile | None" = None


@dataclass
class ZmkConfigGenerationParams:
    """Consolidated parameters for ZMK config workspace generation.

    Eliminates the 8-parameter method signature in generate_config_workspace
    and provides computed properties to reduce null checks and Docker path management.
    """

    workspace_path: Path
    keymap_file: Path
    config_file: Path
    keyboard_profile: "KeyboardProfile"
    workspace_docker_path: "DockerPath"
    config_docker_path: "DockerPath"
    build_docker_path: "DockerPath"
    shield_name: str | None = None
    board_name: str = "nice_nano_v2"
    zephyr_base_path: str = "zephyr"

    @property
    def effective_shield_name(self) -> str:
        """Get effective shield name, defaulting to keyboard name."""
        return self.shield_name or self.keyboard_profile.keyboard_name

    @property
    def config_directory_host(self) -> Path:
        """Get config directory on host."""
        return self.config_docker_path.host()

    @property
    def workspace_config_directory_host(self) -> Path:
        """Get workspace config directory on host (always workspace/config)."""
        return self.workspace_path / "config"


@dataclass
class ZmkConfigFileParams:
    """Consolidated parameters for individual file generation operations."""

    workspace_path: Path
    keyboard_profile: "KeyboardProfile"
    shield_name: str
    config_docker_path: "DockerPath"
    board_name: str = "nice_nano_v2"
    zephyr_base_path: str = "zephyr"

    @property
    def config_directory_host(self) -> Path:
        """Get config directory on host."""
        return self.config_docker_path.host()
