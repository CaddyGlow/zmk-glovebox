"""ZMK config compilation service implementation."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.compilation.protocols.workspace_protocols import (
    ZmkConfigWorkspaceManagerProtocol,
)
from glovebox.compilation.services.base_compilation_service import (
    BaseCompilationService,
)
from glovebox.compilation.workspace.zmk_config_workspace_manager import (
    create_zmk_config_workspace_manager,
)
from glovebox.config.compile_methods import GenericDockerCompileConfig
from glovebox.core.errors import BuildError


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

logger = logging.getLogger(__name__)


class ZmkConfigCompilationService(BaseCompilationService):
    """ZMK config compilation service following GitHub Actions workflow pattern.

    Implements the ZMK config build strategy that clones a configuration
    repository and builds firmware using the west build system, following
    the same pattern as the official ZMK GitHub Actions workflow.
    """

    def __init__(
        self,
        workspace_manager: ZmkConfigWorkspaceManagerProtocol | None = None,
        **base_kwargs: Any,
    ) -> None:
        """Initialize ZMK config compilation service.

        Args:
            workspace_manager: ZMK config workspace manager
            **base_kwargs: Arguments passed to BaseCompilationService
        """
        super().__init__("zmk_config_compilation", "1.0.0", **base_kwargs)

        # Create workspace manager with content generator for dynamic workspace support
        from glovebox.compilation.generation.zmk_config_generator import (
            create_zmk_config_content_generator,
        )

        content_generator = create_zmk_config_content_generator()
        self.workspace_manager = (
            workspace_manager
            or create_zmk_config_workspace_manager(content_generator=content_generator)
        )

    def _setup_workspace(
        self,
        keymap_file: Path,
        config_file: Path,
        config: GenericDockerCompileConfig,
        keyboard_profile: "KeyboardProfile | None" = None,
    ) -> Path | None:
        """Setup ZMK config workspace for compilation.

        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            config: Compilation configuration
            keyboard_profile: Keyboard profile for dynamic generation

        Returns:
            Path | None: Workspace path if successful, None if failed
        """
        try:
            # Determine workspace initialization strategy
            if self._should_use_dynamic_generation(config, keyboard_profile):
                if not keyboard_profile:
                    self.logger.error(
                        "Keyboard profile required for dynamic generation"
                    )
                    return None
                return self._setup_dynamic_workspace(
                    keymap_file, config_file, config, keyboard_profile
                )
            else:
                return self._setup_repository_workspace(
                    keymap_file, config_file, config
                )

        except Exception as e:
            self.logger.error("Failed to setup ZMK config workspace: %s", e)
            return None

    def _build_compilation_command(
        self, workspace_path: Path, config: GenericDockerCompileConfig
    ) -> str:
        """Build west compilation command for ZMK config strategy.

        Args:
            workspace_path: Path to workspace directory
            config: Compilation configuration

        Returns:
            str: West build command
        """
        # ZMK config uses west build with specific board configuration
        board_name = self._extract_board_name(config)
        return f"west build -s app -b {board_name}"

    def _should_use_dynamic_generation(
        self,
        config: GenericDockerCompileConfig,
        keyboard_profile: "KeyboardProfile | None",
    ) -> bool:
        """Determine if dynamic workspace generation should be used.

        Args:
            config: Compilation configuration
            keyboard_profile: Keyboard profile

        Returns:
            bool: True if dynamic generation should be used
        """
        if not keyboard_profile:
            return False

        # Use dynamic generation if no repository URL is configured
        if not config.zmk_config_repo or not config.zmk_config_repo.config_repo_url:
            return True

        repo_url = config.zmk_config_repo.config_repo_url.strip()
        return not repo_url

    def _setup_dynamic_workspace(
        self,
        keymap_file: Path,
        config_file: Path,
        config: GenericDockerCompileConfig,
        keyboard_profile: "KeyboardProfile",
    ) -> Path | None:
        """Setup dynamic ZMK config workspace.

        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            config: Compilation configuration
            keyboard_profile: Keyboard profile for dynamic generation

        Returns:
            Path | None: Workspace path if successful
        """
        # Generate workspace path for dynamic mode
        workspace_path = self._get_dynamic_workspace_path(config, keyboard_profile)

        # Extract shield and board names for dynamic workspace
        shield_name = self._extract_shield_name(config, keyboard_profile)
        board_name = self._extract_board_name(config)

        # Initialize dynamic workspace
        if self.workspace_manager.initialize_dynamic_workspace(
            workspace_path=workspace_path,
            keymap_file=keymap_file,
            config_file=config_file,
            keyboard_profile=keyboard_profile,
            shield_name=shield_name,
            board_name=board_name,
        ):
            return workspace_path

        return None

    def _setup_repository_workspace(
        self, keymap_file: Path, config_file: Path, config: GenericDockerCompileConfig
    ) -> Path | None:
        """Setup repository-based ZMK config workspace.

        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            config: Compilation configuration

        Returns:
            Path | None: Workspace path if successful
        """
        if not config.zmk_config_repo:
            self.logger.error("ZMK config repository configuration is missing")
            return None

        workspace_path = Path(config.zmk_config_repo.workspace_path)

        # Initialize repository workspace
        if self.workspace_manager.initialize_workspace(
            config_repo_config=config.zmk_config_repo,
            keymap_file=keymap_file,
            config_file=config_file,
        ):
            return workspace_path

        return None

    def _get_dynamic_workspace_path(
        self, config: GenericDockerCompileConfig, keyboard_profile: "KeyboardProfile"
    ) -> Path:
        """Get workspace path for dynamic generation.

        Args:
            config: Compilation configuration
            keyboard_profile: Keyboard profile

        Returns:
            Path: Dynamic workspace path
        """
        if config.zmk_config_repo and config.zmk_config_repo.workspace_path:
            return Path(config.zmk_config_repo.workspace_path)

        # Fallback to default dynamic workspace location
        return Path.cwd() / "build" / f"zmk_config_{keyboard_profile.keyboard_name}"

    def _extract_shield_name(
        self, config: GenericDockerCompileConfig, keyboard_profile: "KeyboardProfile"
    ) -> str:
        """Extract shield name from configuration or keyboard profile.

        Args:
            config: Compilation configuration
            keyboard_profile: Keyboard profile

        Returns:
            str: Shield name
        """
        # Use keyboard name as shield name for dynamic generation
        return keyboard_profile.keyboard_name

    def _extract_board_name(self, config: GenericDockerCompileConfig) -> str:
        """Extract board name from compilation configuration.

        Args:
            config: Compilation configuration

        Returns:
            str: Board name for west build
        """
        # Use board targets from config
        if config.board_targets and len(config.board_targets) > 0:
            return config.board_targets[0]

        # Default board for most ZMK keyboards
        return "nice_nano_v2"

    def validate_config(self, config: GenericDockerCompileConfig) -> bool:
        """Validate configuration for ZMK config compilation strategy.

        Args:
            config: Compilation configuration to validate

        Returns:
            bool: True if configuration is valid
        """
        # For dynamic generation mode, zmk_config_repo can be None
        if not config.zmk_config_repo:
            # Allow if dynamic generation will be used (via keyboard profile)
            self.logger.debug("ZMK config repo not specified - assuming dynamic mode")
            return True

        # If zmk_config_repo is provided, validate workspace path
        if not config.zmk_config_repo.workspace_path:
            self.logger.error("ZMK config workspace path is required")
            return False

        self.logger.debug("ZMK config validation passed")
        return True


def create_zmk_config_service(
    workspace_manager: ZmkConfigWorkspaceManagerProtocol | None = None,
    compilation_cache: Any | None = None,
    **base_kwargs: Any,
) -> ZmkConfigCompilationService:
    """Create ZMK config compilation service.

    Args:
        workspace_manager: ZMK config workspace manager
        compilation_cache: Compilation cache instance
        **base_kwargs: Arguments passed to BaseCompilationService

    Returns:
        ZmkConfigCompilationService: Configured service instance
    """
    # Pass compilation cache to base service
    if compilation_cache:
        base_kwargs["compilation_cache"] = compilation_cache

    return ZmkConfigCompilationService(
        workspace_manager=workspace_manager,
        **base_kwargs,
    )
