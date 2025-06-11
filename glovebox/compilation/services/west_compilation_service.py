"""West compilation service for ZMK firmware builds."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.compilation.protocols.workspace_protocols import (
    WestWorkspaceManagerProtocol,
)
from glovebox.compilation.services.base_compilation_service import (
    BaseCompilationService,
)
from glovebox.compilation.workspace.west_workspace_manager import (
    create_west_workspace_manager,
)
from glovebox.config.compile_methods import GenericDockerCompileConfig


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

logger = logging.getLogger(__name__)


class WestCompilationService(BaseCompilationService):
    """West compilation service for ZMK firmware builds.

    Implements the traditional ZMK west workspace build strategy with
    workspace initialization and board-specific compilation.
    """

    def __init__(
        self,
        workspace_manager: WestWorkspaceManagerProtocol | None = None,
        **base_kwargs: Any,
    ) -> None:
        """Initialize west compilation service.

        Args:
            workspace_manager: West workspace manager
            **base_kwargs: Arguments passed to BaseCompilationService
        """
        super().__init__("west_compilation", "1.0.0", **base_kwargs)
        self.workspace_manager = workspace_manager or create_west_workspace_manager()

    def _setup_workspace(
        self,
        keymap_file: Path,
        config_file: Path,
        config: GenericDockerCompileConfig,
        keyboard_profile: "KeyboardProfile | None" = None,
    ) -> Path | None:
        """Setup West workspace for compilation.

        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            config: Compilation configuration
            keyboard_profile: Keyboard profile (unused in west strategy)

        Returns:
            Path | None: Workspace path if successful, None if failed
        """
        try:
            if not config.west_workspace:
                self.logger.error("West workspace configuration is missing")
                return None

            workspace_path = Path(config.west_workspace.workspace_path)

            # Initialize west workspace
            if self.workspace_manager.initialize_workspace(
                workspace_config=config.west_workspace,
                keymap_file=keymap_file,
                config_file=config_file,
            ):
                return workspace_path

            return None

        except Exception as e:
            self.logger.error("Failed to setup West workspace: %s", e)
            return None

    def _build_compilation_command(
        self, workspace_path: Path, config: GenericDockerCompileConfig
    ) -> str:
        """Build west compilation command for west strategy.

        Args:
            workspace_path: Path to workspace directory
            config: Compilation configuration

        Returns:
            str: West build command
        """
        # Use board targets from config for west builds
        if config.board_targets and len(config.board_targets) > 0:
            # Use first board target as primary build target
            board = config.board_targets[0]
        else:
            # Default board for most ZMK keyboards
            board = "nice_nano_v2"

        # For west strategy, we build without shield specification by default
        # Shield configuration is typically handled through the keymap files
        return f"west build -b {board}"

    def validate_config(self, config: GenericDockerCompileConfig) -> bool:
        """Validate configuration for west compilation strategy.

        Args:
            config: Compilation configuration to validate

        Returns:
            bool: True if configuration is valid
        """
        if not config.west_workspace:
            self.logger.error("West workspace configuration is required")
            return False

        if not config.west_workspace.workspace_path:
            self.logger.error("West workspace path is required")
            return False

        self.logger.debug("West workspace validation passed")
        return True


def create_west_service(
    workspace_manager: WestWorkspaceManagerProtocol | None = None,
    compilation_cache: Any | None = None,
    **base_kwargs: Any,
) -> WestCompilationService:
    """Create West compilation service.

    Args:
        workspace_manager: West workspace manager
        compilation_cache: Compilation cache instance
        **base_kwargs: Arguments passed to BaseCompilationService

    Returns:
        WestCompilationService: Configured service instance
    """
    # Pass compilation cache to base service
    if compilation_cache:
        base_kwargs["compilation_cache"] = compilation_cache

    return WestCompilationService(
        workspace_manager=workspace_manager,
        **base_kwargs,
    )
