"""Parameter consolidation objects for ZMK compilation operations."""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.config.compile_methods import CompilationConfig, ZmkWorkspaceConfig
    from glovebox.config.profile import KeyboardProfile


@dataclass
class ZmkCompilationParams:
    """Simple parameter consolidation for ZMK compilation operations.

    Groups together the core parameters needed for ZMK compilation setup
    to reduce function signature complexity and improve maintainability.
    """

    keymap_file: Path
    config_file: Path
    compilation_config: "CompilationConfig"
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
