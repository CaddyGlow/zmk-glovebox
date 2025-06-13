"""ZMK config compilation service implementation."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.compilation.helpers.zmk_helpers import (
    build_zmk_compilation_commands,
    build_zmk_fallback_commands,
    build_zmk_init_commands,
    setup_zmk_workspace_paths,
)
from glovebox.compilation.models.compilation_params import (
    ZmkCompilationParams,
    ZmkWorkspaceParams,
)
from glovebox.compilation.protocols.workspace_protocols import (
    ZmkConfigWorkspaceManagerProtocol,
)
from glovebox.compilation.services.base_compilation_service import (
    BaseCompilationService,
)
from glovebox.compilation.workspace.zmk_config_workspace_manager import (
    create_zmk_config_workspace_manager,
)
from glovebox.config.compile_methods import CompilationConfig
from glovebox.config.models.workspace import UserWorkspaceConfig
from glovebox.core.errors import BuildError


if TYPE_CHECKING:
    from glovebox.compilation.models.build_matrix import BuildMatrix
    from glovebox.config.compile_methods import ZmkWorkspaceConfig
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
        user_workspace_config: UserWorkspaceConfig | None = None,
        **base_kwargs: Any,
    ) -> None:
        """Initialize ZMK config compilation service.

        Args:
            workspace_manager: ZMK config workspace manager
            user_workspace_config: User workspace configuration
            **base_kwargs: Arguments passed to BaseCompilationService
        """
        super().__init__("zmk_config_compilation", "1.0.0", **base_kwargs)

        # Store user workspace configuration
        self.user_workspace_config = user_workspace_config or UserWorkspaceConfig()

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
        config: CompilationConfig,
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
            # Create consolidated parameters
            params = ZmkCompilationParams(
                keymap_file=keymap_file,
                config_file=config_file,
                compilation_config=config,
                keyboard_profile=keyboard_profile,
            )

            # Use helper function for path setup
            setup_zmk_workspace_paths(params)

            # Log the created directories
            workspace_path = config.zmk_config_repo.workspace_path.host_path
            build_path = config.zmk_config_repo.build_root.host_path
            config_path = config.zmk_config_repo.config_path.host_path

            self.logger.info("Using separate build directory: %s", build_path)
            self.logger.info("Using separate config directory: %s", config_path)
            self.logger.info("Workspace directory: %s", workspace_path)

            if params.should_use_dynamic_generation:
                if not keyboard_profile:
                    self.logger.error(
                        "Keyboard profile required for dynamic generation"
                    )
                    return None
                return self._setup_dynamic_workspace(
                    keymap_file, config_file, config, keyboard_profile
                )
            else:
                if not config.zmk_config_repo:
                    self.logger.error(
                        "ZMK config repository configuration is missing for repository-based build"
                    )
                    return None
                return self._setup_repository_workspace(
                    keymap_file, config_file, config.zmk_config_repo
                )

        except Exception as e:
            self._handle_workspace_setup_error("ZMK config", e)
            return None

    def _build_compilation_command(
        self, workspace_path: Path, config: CompilationConfig
    ) -> str:
        """Build west compilation command for ZMK config strategy.

        Uses build.yaml from workspace to generate west build commands
        following GitHub Actions workflow pattern.

        Args:
            workspace_path: Path to workspace directory
            config: Compilation configuration

        Returns:
            str: Complete west command sequence
        """
        zmk_workspace_config = config.zmk_config_repo

        if zmk_workspace_config is None:
            raise BuildError("ZMK config repository configuration is missing")

        # Create workspace parameters
        workspace_params = ZmkWorkspaceParams(
            workspace_path=workspace_path, zmk_config=zmk_workspace_config
        )

        # Use helper functions for command generation
        init_commands = build_zmk_init_commands(workspace_params)

        # Check for build.yaml in workspace config directory
        build_yaml_file_path = workspace_path / zmk_workspace_config.build_yaml_path
        if build_yaml_file_path.exists():
            try:
                # Parse build matrix from build.yaml
                from glovebox.compilation.configuration.build_matrix_resolver import (
                    create_build_matrix_resolver,
                )

                resolver = create_build_matrix_resolver()
                build_matrix = resolver.resolve_from_build_yaml(build_yaml_file_path)

                # Generate west build commands for each target
                build_commands = build_zmk_compilation_commands(
                    build_matrix, workspace_params
                )

            except Exception as e:
                self.logger.warning("Failed to parse build.yaml, using fallback: %s", e)
                build_commands = build_zmk_fallback_commands(
                    workspace_params, config.board_targets
                )
        else:
            # No build.yaml found, use fallback approach
            self.logger.debug("No build.yaml found, using fallback build commands")
            build_commands = build_zmk_fallback_commands(
                workspace_params, config.board_targets
            )

        return " && ".join(init_commands + build_commands)

    def _setup_dynamic_workspace(
        self,
        keymap_file: Path,
        config_file: Path,
        config: CompilationConfig,
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
        # TODO: fix me to get random path
        workspace_path = self._get_dynamic_workspace_path(
            config.zmk_config_repo, keyboard_profile
        )

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
        self,
        keymap_file: Path,
        config_file: Path,
        zmk_workspace_config: "ZmkWorkspaceConfig",
    ) -> Path | None:
        """Setup repository-based ZMK config workspace.

        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            zmk_workspace_config: ZMK workspace configuration

        Returns:
            Path | None: Workspace path if successful
        """
        workspace_path = zmk_workspace_config.workspace_path.host_path

        # Initialize repository workspace
        if self.workspace_manager.initialize_workspace(
            config_repo_config=zmk_workspace_config,
            keymap_file=keymap_file,
            config_file=config_file,
        ):
            return workspace_path

        return None

    def _get_dynamic_workspace_path(
        self,
        zmk_workspace_config: "ZmkWorkspaceConfig | None",
        keyboard_profile: "KeyboardProfile",
    ) -> Path:
        """Get workspace path for dynamic generation.

        Args:
            zmk_workspace_config: ZMK workspace configuration
            keyboard_profile: Keyboard profile

        Returns:
            Path: Dynamic workspace path
        """
        if zmk_workspace_config and zmk_workspace_config.workspace_path.host_path:
            return zmk_workspace_config.workspace_path.host_path

        # Fallback to user-configured workspace location
        return (
            self.user_workspace_config.root_directory
            / f"zmk_config_{keyboard_profile.keyboard_name}"
        )

    def _extract_shield_name(
        self, config: CompilationConfig, keyboard_profile: "KeyboardProfile"
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

    def _validate_strategy_specific(self, config: CompilationConfig) -> bool:
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

        # Log build_root configuration for debugging
        build_root = config.zmk_config_repo.build_root
        if build_root.container_path != "build":
            self.logger.debug(
                "ZMK config custom build root configured: %s",
                config.zmk_config_repo.build_root,
            )
        else:
            self.logger.debug("ZMK config using default build root: build")

        self.logger.debug("ZMK config validation passed")
        return True


def create_zmk_config_service(
    workspace_manager: ZmkConfigWorkspaceManagerProtocol | None = None,
    user_workspace_config: UserWorkspaceConfig | None = None,
    compilation_cache: Any | None = None,
    **base_kwargs: Any,
) -> ZmkConfigCompilationService:
    """Create ZMK config compilation service.

    Args:
        workspace_manager: ZMK config workspace manager
        user_workspace_config: User workspace configuration
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
        user_workspace_config=user_workspace_config,
        **base_kwargs,
    )
