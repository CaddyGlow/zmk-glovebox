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
    ZmkConfigGenerationParams,
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
from glovebox.config.compile_methods import ZmkCompilationConfig
from glovebox.config.models.keyboard import CompileMethodConfigUnion
from glovebox.config.models.workspace import UserWorkspaceConfig
from glovebox.core.errors import BuildError
from glovebox.models.docker_path import DockerPath


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
        config: CompileMethodConfigUnion,
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
            if not isinstance(config, ZmkCompilationConfig):
                raise BuildError("Invalid compilation configuration")

            logger.debug("Preparing ZMK config workspace: %r", config)
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
            workspace_path = config.workspace.workspace_path.host_path
            build_path = config.workspace.build_root.host_path
            config_path = config.workspace.config_path.host_path

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
                raise BuildError("Not implemented")
                # if not config.zmk_config_repo:
                #     self.logger.error(
                #         "ZMK config repository configuration is missing for repository-based build"
                #     )
                #     return None
                # return self._setup_repository_workspace(
                #     keymap_file, config_file, config.zmk_config_repo
                # )

        except Exception as e:
            self._handle_workspace_setup_error("ZMK config", e)
            return None

    def _build_compilation_command(
        self, workspace_path: Path, config: CompileMethodConfigUnion
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
        if not isinstance(config, ZmkCompilationConfig):
            raise BuildError("Invalid compilation configuration")

        # Create workspace parameters
        workspace_params = ZmkWorkspaceParams(
            workspace_path=workspace_path, zmk_config=config.workspace
        )

        # Use helper functions for command generation
        init_commands = build_zmk_init_commands(workspace_params)

        # Check for build.yaml in workspace config directory
        build_yaml_file_path = workspace_path / config.workspace.build_matrix_file
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
                    workspace_params, [config.build_config.get_board_name()]
                )
        else:
            # No build.yaml found, use fallback approach
            self.logger.debug("No build.yaml found, using fallback build commands")
            build_commands = build_zmk_fallback_commands(
                workspace_params, [config.build_config.get_board_name()]
            )

        return " && ".join(init_commands + build_commands)

    def _setup_dynamic_workspace(
        self,
        keymap_file: Path,
        config_file: Path,
        config: CompileMethodConfigUnion,
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
        if not isinstance(config, ZmkCompilationConfig):
            raise BuildError("Invalid compilation configuration")

        # Generate host workspace path for dynamic mode
        workspace_path = self._get_dynamic_workspace_path(
            config.workspace, keyboard_profile
        )

        # Get ZMK workspace config with configured Docker paths
        zmk_workspace_config = config.workspace

        # Create consolidated generation parameters using existing DockerPath objects
        generation_params = ZmkConfigGenerationParams(
            workspace_path=workspace_path,
            keymap_file=keymap_file,
            config_file=config_file,
            keyboard_profile=keyboard_profile,
            workspace_docker_path=zmk_workspace_config.workspace_path,
            config_docker_path=zmk_workspace_config.config_path,
            build_docker_path=zmk_workspace_config.build_root,
            shield_name="placeholder",
            board_name=config.build_config.get_board_name(),
        )

        # Initialize dynamic workspace with consolidated parameters
        if self.workspace_manager.initialize_dynamic_workspace(generation_params):
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

    def _validate_strategy_specific(self, config: CompileMethodConfigUnion) -> bool:
        """Validate ZMK config strategy-specific configuration requirements.

        Args:
            config: Compilation configuration to validate

        Returns:
            bool: True if strategy-specific requirements are met
        """
        if not isinstance(config, ZmkCompilationConfig):
            self.logger.error("Invalid configuration type for ZMK config strategy")
            return False

        # ZMK config strategy specific validation
        workspace_config = config.workspace
        if not workspace_config:
            self.logger.error("ZMK workspace configuration is required")
            return False

        return True

    def _prepare_build_volumes(
        self,
        workspace_path: Path,
        config: CompileMethodConfigUnion,
    ) -> list[tuple[str, str]]:
        """Prepare Docker volumes for Moergo compilation.

        Args:
            workspace_path: Path to workspace directory
            config: Compilation configuration

        Returns:
            list[tuple[str, str]]: Docker volumes for compilation
        """
        if not isinstance(config, ZmkCompilationConfig):
            raise BuildError("Invalid compilation configuration")

        volumes = []

        if config.workspace.workspace_path.host_path:
            volumes.append(config.workspace.workspace_path.vol())
        if config.workspace.build_root.host_path:
            volumes.append(config.workspace.build_root.vol())
        if config.workspace.config_path.host_path:
            volumes.append(config.workspace.config_path.vol())

        self.logger.debug("Prepared %d Docker volumes for Moergo build", len(volumes))
        return volumes


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
