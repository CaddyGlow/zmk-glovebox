"""ZMK config compilation service implementation."""

import logging
import tempfile
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
from glovebox.config.compile_methods import CompilationConfig
from glovebox.config.models.workspace import UserWorkspaceConfig


if TYPE_CHECKING:
    from glovebox.compilation.models.build_matrix import BuildMatrix
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
        # Import build matrix resolver
        from glovebox.compilation.configuration.build_matrix_resolver import (
            create_build_matrix_resolver,
        )

        # Initialize commands with workspace setup
        commands = [
            "cd /workspace",  # Ensure we're in the workspace
            "rm -rf .west build",  # Remove existing west workspace and build dirs
            "west init -l config",  # Initialize west workspace with config
            "west update",  # Download dependencies
            "west zephyr-export",  # Export Zephyr build environment
        ]

        # Check for build.yaml in workspace config directory
        build_yaml_path = workspace_path / "build.yaml"
        if build_yaml_path.exists():
            try:
                # Parse build matrix from build.yaml
                resolver = create_build_matrix_resolver()
                build_matrix = resolver.resolve_from_build_yaml(build_yaml_path)

                # Generate west build commands for each target
                build_commands = self._generate_build_commands_from_matrix(build_matrix)
                commands.extend(build_commands)

            except Exception as e:
                self.logger.warning("Failed to parse build.yaml, using fallback: %s", e)
                commands.extend(self._generate_fallback_build_commands(config))
        else:
            # No build.yaml found, use fallback approach
            self.logger.debug("No build.yaml found, using fallback build commands")
            commands.extend(self._generate_fallback_build_commands(config))

        return " && ".join(commands)

    def _generate_build_commands_from_matrix(
        self, build_matrix: "BuildMatrix"
    ) -> list[str]:
        """Generate west build commands from build matrix.

        Creates build commands following GitHub Actions workflow pattern
        with proper build directories and CMake arguments.

        Args:
            build_matrix: Resolved build matrix from build.yaml

        Returns:
            list[str]: West build commands for each target
        """

        commands = []

        for target in build_matrix.targets:
            # Generate build directory name
            build_dir = Path("build") / f"{target.artifact_name or target.board}"
            if target.shield:
                build_dir = Path("build") / f"{target.shield}-{target.board}"

            # Build west command with GitHub Actions workflow parameters
            west_cmd = f"west build -s zmk/app -b {target.board} -d {build_dir}"

            # Add CMake arguments
            cmake_args = ["-DZMK_CONFIG=/workspace/config"]

            # Add shield if specified
            if target.shield:
                cmake_args.append(f"-DSHIELD={target.shield}")

            # Add target-specific cmake args
            if target.cmake_args:
                cmake_args.extend(target.cmake_args)

            # Add snippet if specified
            if target.snippet:
                cmake_args.append(f"-DZMK_EXTRA_MODULES={target.snippet}")

            # Combine command with cmake args
            if cmake_args:
                west_cmd += f" -- {' '.join(cmake_args)}"

            commands.append(west_cmd)
            self.logger.debug(
                "Generated build command for %s: %s", target.artifact_name, west_cmd
            )

        return commands

    def _generate_fallback_build_commands(self, config: CompilationConfig) -> list[str]:
        """Generate fallback build commands when build.yaml is not available.

        Uses configuration to generate basic west build commands.

        Args:
            config: Compilation configuration

        Returns:
            list[str]: Fallback west build commands
        """
        commands = []
        board_name = self._extract_board_name(config)

        # Generate basic build command
        west_cmd = f"west build -s zmk/app -b {board_name} -d build"
        cmake_args = ["-DZMK_CONFIG=/workspace/config"]

        # Add board targets as shields if available
        if config.board_targets and len(config.board_targets) > 1:
            # Multiple board targets - generate commands for each
            for board_target in config.board_targets:
                build_dir = f"build_{board_target}"
                target_cmd = f"west build -s zmk/app -b {board_target} -d {build_dir}"
                target_cmd += f" -- {' '.join(cmake_args)}"
                commands.append(target_cmd)
        else:
            # Single board target
            west_cmd += f" -- {' '.join(cmake_args)}"
            commands.append(west_cmd)

        return commands

    def _should_use_dynamic_generation(
        self,
        config: CompilationConfig,
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
        self, keymap_file: Path, config_file: Path, config: CompilationConfig
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
        self, config: CompilationConfig, keyboard_profile: "KeyboardProfile"
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

    def _extract_board_name(self, config: CompilationConfig) -> str:
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

    def validate_config(self, config: CompilationConfig) -> bool:
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
