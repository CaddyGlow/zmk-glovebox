"""Moergo compilation service for ZMK firmware builds."""

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.compilation.services.base_compilation_service import (
    BaseCompilationService,
)
from glovebox.config.compile_methods import MoergoCompilationConfig
from glovebox.config.models.keyboard import CompileMethodConfigUnion
from glovebox.core.errors import BuildError


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

logger = logging.getLogger(__name__)


class MoergoCompilationService(BaseCompilationService):
    """Moergo compilation service for ZMK firmware builds.

    Implements a simplified Docker-based build strategy that mounts
    config and keymap files to a temporary Docker volume without caching.
    """

    def __init__(
        self,
        config: CompileMethodConfigUnion | None = None,
        **base_kwargs: Any,
    ) -> None:
        """Initialize Moergo compilation service.

        Args:
            config: Moergo compilation configuration
            **base_kwargs: Arguments passed to BaseCompilationService
        """
        super().__init__("moergo_compilation", "1.0.0", **base_kwargs)

    def _setup_workspace(
        self,
        keymap_file: Path,
        config_file: Path,
        config: CompileMethodConfigUnion,
        keyboard_profile: "KeyboardProfile",
    ) -> Path | None:
        """Setup temporary workspace for Moergo compilation.

        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            config: Moergo compilation configuration
            keyboard_profile: Keyboard profile (unused in Moergo strategy)

        Returns:
            Path | None: Temporary workspace path if successful, None if failed
        """
        try:
            if not isinstance(config, MoergoCompilationConfig):
                raise BuildError("Invalid compilation configuration")

            # Create temporary directory for build files
            temp_dir = Path(tempfile.mkdtemp(prefix="moergo-build-"))
            config.build_root.host_path = temp_dir
            self.logger.debug("Created temporary workspace: %s", temp_dir)

            config_path = temp_dir / "config"

            # Copy keymap and config files to temp directory
            temp_keymap = config_path / f"{keyboard_profile.keyboard_name}.keymap"
            temp_config = config_path / f"{keyboard_profile.keyboard_name}.conf"

            temp_keymap.write_text(keymap_file.read_text())
            temp_config.write_text(config_file.read_text())

            self.logger.debug(
                "Copied files to temp workspace: %s, %s", temp_keymap, temp_config
            )

            return temp_dir

        except Exception as e:
            self._handle_workspace_setup_error("Moergo", e)
            return None

    def _build_compilation_command(
        self, workspace_path: Path, config: CompileMethodConfigUnion
    ) -> str:
        """Build Docker compilation command for Moergo strategy.

        Args:
            workspace_path: Path to temporary workspace directory
            config: Moergo compilation configuration

        Returns:
            str: Docker build command
        """
        if not isinstance(config, MoergoCompilationConfig):
            raise BuildError("Invalid compilation configuration")

        # # Build docker command with volume mount to temp folder
        # container_path = config.build_root.container_path
        # workspace_path = config.build_root.host_path
        # command_parts = [
        #     "docker",
        #     "run",
        #     "--rm",
        #     "-v",
        #     "-e",
        #     f"BRANCH={config.branch}",
        #     f"{workspace_path}:{container_path}",
        #     config.image,
        # ]

        command_parts: list[str] = []
        return " ".join(command_parts)

    def _validate_strategy_specific(self, config: CompileMethodConfigUnion) -> bool:
        """Validate Moergo strategy-specific configuration requirements.

        Args:
            config: Compilation configuration to validate

        Returns:
            bool: True if strategy-specific requirements are met
        """
        if not isinstance(config, MoergoCompilationConfig):
            self.logger.error("Invalid configuration type for Moergo strategy")
            return False

        # Moergo strategy specific validation
        if not config.branch:
            self.logger.error("Branch is required for Moergo compilation")
            return False

        return True

    # def _cleanup_workspace(self, workspace_path: Path) -> None:
    #     """Clean up temporary workspace after compilation.
    #
    #     Args:
    #         workspace_path: Path to temporary workspace to clean up
    #     """
    #     if not isinstance(config, MoergoCompilationConfig):
    #         raise BuildError("Invalid compilation configuration")
    #
    #     if self.moergo_config.cleanup_workspace and workspace_path.exists():
    #         try:
    #             import shutil
    #
    #             shutil.rmtree(workspace_path)
    #             self.logger.debug("Cleaned up temporary workspace: %s", workspace_path)
    #         except Exception as e:
    #             self.logger.warning(
    #                 "Failed to clean up workspace %s: %s", workspace_path, e
    #             )


def create_moergo_service(
    config: CompileMethodConfigUnion | None = None,
    **base_kwargs: Any,
) -> MoergoCompilationService:
    """Create Moergo compilation service.

    Args:
        config: Moergo compilation configuration
        **base_kwargs: Arguments passed to BaseCompilationService

    Returns:
        MoergoCompilationService: Configured service instance
    """
    return MoergoCompilationService(
        config=config,
        **base_kwargs,
    )
