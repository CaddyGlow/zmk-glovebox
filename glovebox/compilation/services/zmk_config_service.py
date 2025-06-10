"""ZMK config compilation service following GitHub Actions workflow pattern."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.compilation.configuration.build_matrix_resolver import (
    BuildMatrixResolver,
    create_build_matrix_resolver,
)
from glovebox.compilation.configuration.environment_manager import (
    EnvironmentManager,
    create_environment_manager,
)
from glovebox.compilation.configuration.volume_manager import (
    VolumeManager,
    create_volume_manager,
)
from glovebox.compilation.generation.zmk_config_generator import (
    ZmkConfigContentGenerator,
    create_zmk_config_content_generator,
)
from glovebox.compilation.models.build_matrix import BuildMatrix, BuildTarget
from glovebox.compilation.protocols.artifact_protocols import (
    ArtifactCollectorProtocol,
)
from glovebox.compilation.protocols.compilation_protocols import (
    CompilationServiceProtocol,
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
from glovebox.config.compile_methods import GenericDockerCompileConfig
from glovebox.core.errors import BuildError


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
from glovebox.firmware.models import BuildResult
from glovebox.protocols import DockerAdapterProtocol
from glovebox.protocols.docker_adapter_protocol import DockerVolume


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
        build_matrix_resolver: BuildMatrixResolver | None = None,
        artifact_collector: ArtifactCollectorProtocol | None = None,
        environment_manager: EnvironmentManager | None = None,
        volume_manager: VolumeManager | None = None,
        docker_adapter: DockerAdapterProtocol | None = None,
        content_generator: ZmkConfigContentGenerator | None = None,
    ) -> None:
        """Initialize ZMK config compilation service.

        Args:
            workspace_manager: ZMK config workspace manager
            build_matrix_resolver: Build matrix resolver for build.yaml
            artifact_collector: Artifact collection service
            environment_manager: Environment variable manager
            volume_manager: Docker volume manager
            docker_adapter: Docker adapter for container operations
            content_generator: ZMK config content generator for dynamic workspaces
        """
        super().__init__("zmk_config_compilation", "1.0.0")
        self.workspace_manager = (
            workspace_manager or create_zmk_config_workspace_manager()
        )
        self.build_matrix_resolver = (
            build_matrix_resolver or create_build_matrix_resolver()
        )
        self.artifact_collector = artifact_collector  # Will be None until Phase 5
        self.environment_manager = environment_manager or create_environment_manager()
        self.volume_manager = volume_manager or create_volume_manager()
        self.content_generator = (
            content_generator or create_zmk_config_content_generator()
        )

        # Docker adapter will be injected from parent coordinator
        self._docker_adapter: DockerAdapterProtocol | None = docker_adapter

    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
        keyboard_profile: "KeyboardProfile | None" = None,
    ) -> BuildResult:
        """Execute ZMK config compilation using GitHub Actions pattern.

        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            output_dir: Output directory for firmware files
            config: Compilation configuration
            keyboard_profile: Keyboard profile for dynamic generation

        Returns:
            BuildResult: Compilation results with firmware files

        Raises:
            BuildError: If compilation fails
        """
        logger.info("Starting ZMK config compilation")
        result = BuildResult(success=True)

        try:
            # Handle dynamic generation or repository-based configuration
            if self._should_use_dynamic_generation(config, keyboard_profile):
                # Use dynamic generation mode
                workspace_path = self._get_dynamic_workspace_path(
                    config, keyboard_profile
                )

                if not self._initialize_dynamic_workspace(
                    workspace_path, keymap_file, config_file, keyboard_profile, config
                ):
                    result.success = False
                    result.add_error("Failed to generate dynamic ZMK config workspace")
                    return result

                # Create minimal config for dynamic mode
                config_repo_config = self._create_dynamic_config(workspace_path)
            else:
                # Use repository-based configuration
                if not self._validate_zmk_config(config, result):
                    return result

                config_repo_config = config.zmk_config_repo
                if not config_repo_config:
                    result.success = False
                    result.add_error("ZMK config repository configuration is missing")
                    return result
                workspace_path = Path(config_repo_config.workspace_path)

                # Initialize repository workspace
                if not self._initialize_workspace(
                    config_repo_config, keymap_file, config_file
                ):
                    result.success = False
                    result.add_error("Failed to initialize ZMK config workspace")
                    return result

            # Resolve build matrix from build.yaml
            build_matrix = self._resolve_build_matrix(
                workspace_path, config_repo_config
            )

            # Execute compilation using build matrix
            if not self._execute_build_matrix(
                build_matrix, workspace_path, output_dir, config, config_repo_config
            ):
                result.success = False
                result.add_error("Build matrix execution failed")
                return result

            # Collect and validate artifacts
            firmware_files = self._collect_firmware_artifacts(output_dir)
            if not firmware_files or not (
                firmware_files.main_uf2
                or firmware_files.left_uf2
                or firmware_files.right_uf2
            ):
                result.success = False
                result.add_error("No firmware files generated")
                return result

            # Store results
            result.output_files = firmware_files

            # Count the actual firmware files
            firmware_count = 0
            if firmware_files.main_uf2:
                firmware_count += 1
            if firmware_files.left_uf2:
                firmware_count += 1
            if firmware_files.right_uf2:
                firmware_count += 1

            result.add_message(
                f"ZMK config compilation completed. Generated {firmware_count} firmware files."
            )

            return result

        except Exception as e:
            msg = f"ZMK config compilation failed: {e}"
            logger.error(msg)
            result.success = False
            result.add_error(msg)
            return result

    def validate_configuration(self, config: GenericDockerCompileConfig) -> bool:
        """Validate ZMK config compilation configuration.

        Args:
            config: Compilation configuration to validate

        Returns:
            bool: True if configuration is valid
        """
        if not config.zmk_config_repo:
            logger.error("ZMK config repository configuration is required")
            return False

        config_repo = config.zmk_config_repo

        if not config_repo.config_repo_url:
            logger.error("ZMK config repository URL is required")
            return False

        if not config_repo.workspace_path:
            logger.error("ZMK config workspace path is required")
            return False

        return True

    def _validate_zmk_config(
        self, config: GenericDockerCompileConfig, result: BuildResult
    ) -> bool:
        """Validate ZMK config repository configuration.

        Args:
            config: Compilation configuration
            result: Build result to store errors

        Returns:
            bool: True if configuration is valid
        """
        if not config.zmk_config_repo:
            result.add_error(
                "ZMK config repository configuration is required for zmk_config strategy"
            )
            return False

        return self.validate_configuration(config)

    def validate_config(self, config: GenericDockerCompileConfig) -> bool:
        """Validate configuration for this compilation strategy.

        Args:
            config: Compilation configuration to validate

        Returns:
            bool: True if configuration is valid
        """
        return self.validate_configuration(config)

    def check_available(self) -> bool:
        """Check if this compilation strategy is available.

        Returns:
            bool: True if strategy is available
        """
        # ZMK config compilation requires Docker adapter
        return self._docker_adapter is not None and self._docker_adapter.is_available()

    def _initialize_workspace(
        self,
        config_repo_config: Any,
        keymap_file: Path,
        config_file: Path,
    ) -> bool:
        """Initialize ZMK config workspace.

        Args:
            config_repo_config: ZMK config repository configuration
            keymap_file: User keymap file
            config_file: User config file

        Returns:
            bool: True if workspace initialized successfully
        """
        return self.workspace_manager.initialize_workspace(
            config_repo_config=config_repo_config,
            keymap_file=keymap_file,
            config_file=config_file,
        )

    def _resolve_build_matrix(
        self, workspace_path: Path, config_repo_config: Any
    ) -> BuildMatrix:
        """Resolve build matrix from build.yaml file.

        Args:
            workspace_path: Path to ZMK config workspace
            config_repo_config: ZMK config repository configuration

        Returns:
            BuildMatrix: Resolved build matrix
        """
        build_yaml_path = workspace_path / config_repo_config.build_yaml_path
        return self.build_matrix_resolver.resolve_from_build_yaml(build_yaml_path)

    def _execute_build_matrix(
        self,
        build_matrix: BuildMatrix,
        workspace_path: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
        config_repo_config: Any,
    ) -> bool:
        """Execute build matrix using Docker containers.

        Args:
            build_matrix: Build matrix with targets
            workspace_path: Path to ZMK config workspace
            output_dir: Output directory for firmware files
            config: Compilation configuration
            config_repo_config: ZMK config repository configuration

        Returns:
            bool: True if build matrix executed successfully
        """
        if not self._docker_adapter:
            logger.error("Docker adapter not available for compilation")
            return False

        # Generate build commands from build matrix
        build_commands = self._generate_build_commands(build_matrix, config)

        # Prepare build environment
        build_env = self._prepare_build_environment(config, config_repo_config)

        # Prepare Docker volumes (we need the original keymap/config files from compile method)
        # For now, use empty Path() as placeholders - this will be properly injected in integration
        volumes = self._prepare_build_volumes(
            workspace_path, output_dir, config, Path(), Path()
        )

        # Execute build commands in Docker container
        west_command = " && ".join(build_commands)
        docker_image = config.image

        return_code, stdout_lines, stderr_lines = self._docker_adapter.run_container(
            image=docker_image,
            command=[
                "sh",
                "-c",
                f"cd {config_repo_config.workspace_path} && {west_command}",
            ],
            volumes=volumes,
            environment=build_env,
        )

        if return_code != 0:
            error_msg = (
                "\n".join(stderr_lines)
                if stderr_lines
                else "ZMK config compilation failed"
            )
            logger.error(
                "ZMK config compilation failed with exit code %d: %s",
                return_code,
                error_msg,
            )
            return False

        return True

    def _generate_build_commands(
        self, build_matrix: BuildMatrix, config: GenericDockerCompileConfig
    ) -> list[str]:
        """Generate west build commands from build matrix.

        Args:
            build_matrix: Build matrix with targets
            config: Compilation configuration

        Returns:
            list[str]: List of west build commands
        """
        build_commands = []

        if build_matrix.targets:
            # Use targets from build.yaml
            for target in build_matrix.targets:
                command = self._generate_target_command(target)
                build_commands.append(command)
        elif config.board_targets:
            # Use board targets from config
            for board in config.board_targets:
                build_commands.append(
                    f"west build -p always -b {board} -d build/{board}"
                )
        else:
            # Default build command
            build_commands.append("west build -p always")

        # Add any custom build commands
        if config.build_commands:
            build_commands.extend(config.build_commands)

        return build_commands

    def _generate_target_command(self, target: BuildTarget) -> str:
        """Generate west build command for a specific target.

        Args:
            target: Build target configuration

        Returns:
            str: West build command
        """
        board_arg = target.board
        shield_arg = f" -- -DSHIELD={target.shield}" if target.shield else ""

        artifact_name = (
            target.artifact_name or f"{target.board}_{target.shield}"
            if target.shield
            else target.board
        )

        return (
            f"west build -p always -b {board_arg} -d build/{artifact_name}{shield_arg}"
        )

    def _prepare_build_environment(
        self, config: GenericDockerCompileConfig, config_repo_config: Any
    ) -> dict[str, str]:
        """Prepare build environment variables.

        Args:
            config: Compilation configuration
            config_repo_config: ZMK config repository configuration

        Returns:
            dict[str, str]: Environment variables for Docker container
        """
        context = {
            "workspace_path": config_repo_config.workspace_path,
            "config_repo_url": config_repo_config.config_repo_url,
            "config_repo_revision": config_repo_config.config_repo_revision,
        }

        return self.environment_manager.prepare_environment(config, **context)

    def _prepare_build_volumes(
        self,
        workspace_path: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
        keymap_file: Path,
        config_file: Path,
    ) -> list[DockerVolume]:
        """Prepare Docker volumes for build.

        Args:
            workspace_path: Path to ZMK config workspace
            output_dir: Output directory for firmware files
            config: Compilation configuration
            keymap_file: Path to keymap file
            config_file: Path to config file

        Returns:
            list[DockerVolume]: Docker volume mount tuples
        """
        # For now, create basic volume mapping manually
        # This will use the VolumeManager properly in integration
        return [
            (str(workspace_path), str(workspace_path)),
            (str(output_dir), str(output_dir)),
        ]

    def _collect_firmware_artifacts(self, output_dir: Path) -> Any:
        """Collect firmware artifacts from output directory.

        Args:
            output_dir: Output directory to scan

        Returns:
            FirmwareOutputFiles: Collected firmware files
        """
        if not self.artifact_collector:
            # Fallback implementation until Phase 5
            from glovebox.firmware.models import FirmwareOutputFiles

            return FirmwareOutputFiles(output_dir=output_dir)

        # Use the protocol method when artifact collector is implemented
        firmware_files, output_files = self.artifact_collector.collect_artifacts(
            output_dir
        )
        return output_files

    def set_docker_adapter(self, docker_adapter: DockerAdapterProtocol) -> None:
        """Set Docker adapter for compilation operations.

        Args:
            docker_adapter: Docker adapter instance
        """
        self._docker_adapter = docker_adapter

    def _should_use_dynamic_generation(
        self,
        config: GenericDockerCompileConfig,
        keyboard_profile: "KeyboardProfile | None",
    ) -> bool:
        """Determine if should use dynamic generation instead of repository.

        Args:
            config: Compilation configuration
            keyboard_profile: Keyboard profile (required for dynamic generation)

        Returns:
            bool: True if should use dynamic generation
        """
        # Use dynamic generation if:
        # 1. No zmk_config_repo configured, OR
        # 2. zmk_config_repo.config_repo_url is not set/empty, AND
        # 3. keyboard_profile is available for dynamic generation

        if not keyboard_profile:
            return False

        if not config.zmk_config_repo:
            return True

        repo_url = config.zmk_config_repo.config_repo_url
        return not repo_url or repo_url.strip() == ""

    def _get_dynamic_workspace_path(
        self,
        config: GenericDockerCompileConfig,
        keyboard_profile: "KeyboardProfile | None",
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

        # Default dynamic workspace path
        keyboard_name = (
            keyboard_profile.keyboard_name if keyboard_profile else "keyboard"
        )
        return Path.home() / f".glovebox/dynamic-zmk-config/{keyboard_name}"

    def _initialize_dynamic_workspace(
        self,
        workspace_path: Path,
        keymap_file: Path,
        config_file: Path,
        keyboard_profile: "KeyboardProfile | None",
        config: GenericDockerCompileConfig,
    ) -> bool:
        """Initialize dynamic ZMK config workspace.

        Args:
            workspace_path: Path to workspace directory
            keymap_file: Source keymap file
            config_file: Source config file
            keyboard_profile: Keyboard profile for configuration
            config: Compilation configuration

        Returns:
            bool: True if workspace initialized successfully
        """
        if not keyboard_profile:
            logger.error("Keyboard profile required for dynamic workspace generation")
            return False

        try:
            # Extract shield name from config or keyboard profile
            shield_name = self._extract_shield_name(config, keyboard_profile)

            # Generate workspace content using content generator
            return self.content_generator.generate_config_workspace(
                workspace_path=workspace_path,
                keymap_file=keymap_file,
                config_file=config_file,
                keyboard_profile=keyboard_profile,
                shield_name=shield_name,
                board_name=self._extract_board_name(config),
            )

        except Exception as e:
            logger.error("Failed to initialize dynamic workspace: %s", e)
            return False

    def _extract_shield_name(
        self, config: GenericDockerCompileConfig, keyboard_profile: "KeyboardProfile"
    ) -> str:
        """Extract shield name from configuration or profile.

        Args:
            config: Compilation configuration
            keyboard_profile: Keyboard profile

        Returns:
            str: Shield name for builds
        """
        # Try to extract from build commands first
        if config.build_commands:
            for command in config.build_commands:
                if "-DSHIELD=" in command:
                    # Extract shield name from command like: -DSHIELD=corne_left
                    shield_part = command.split("-DSHIELD=")[1].split()[0]
                    # Remove _left/_right suffix to get base shield name
                    base_shield = shield_part.replace("_left", "").replace("_right", "")
                    return base_shield

        # Fallback to keyboard name from profile
        return keyboard_profile.keyboard_name

    def _extract_board_name(self, config: GenericDockerCompileConfig) -> str:
        """Extract board name from configuration.

        Args:
            config: Compilation configuration

        Returns:
            str: Board name for builds
        """
        # Try board_targets first
        if config.board_targets:
            return config.board_targets[0]

        # Try to extract from build commands
        if config.build_commands:
            for command in config.build_commands:
                if "-b " in command:
                    # Extract board from command like: west build -b nice_nano_v2
                    parts = command.split("-b ")
                    if len(parts) > 1:
                        board = parts[1].split()[0]
                        return board

        # Default to nice_nano_v2
        return "nice_nano_v2"

    def _create_dynamic_config(self, workspace_path: Path) -> Any:
        """Create minimal config object for dynamic mode.

        Args:
            workspace_path: Path to dynamic workspace

        Returns:
            Dynamic config object with required attributes
        """

        # Create a simple object with required attributes for the rest of the compilation
        class DynamicConfig:
            def __init__(self, workspace_path: Path):
                self.workspace_path = str(workspace_path)
                self.config_path = "config"
                self.build_yaml_path = "build.yaml"
                self.config_repo_url = f"dynamic://{workspace_path}"
                self.config_repo_revision = "dynamic"

        return DynamicConfig(workspace_path)


def create_zmk_config_service(
    workspace_manager: ZmkConfigWorkspaceManagerProtocol | None = None,
    build_matrix_resolver: BuildMatrixResolver | None = None,
    artifact_collector: ArtifactCollectorProtocol | None = None,
    environment_manager: EnvironmentManager | None = None,
    volume_manager: VolumeManager | None = None,
    docker_adapter: DockerAdapterProtocol | None = None,
    content_generator: ZmkConfigContentGenerator | None = None,
) -> ZmkConfigCompilationService:
    """Create ZMK config compilation service instance.

    Args:
        workspace_manager: ZMK config workspace manager
        build_matrix_resolver: Build matrix resolver
        artifact_collector: Artifact collector
        environment_manager: Environment manager
        volume_manager: Volume manager
        docker_adapter: Docker adapter
        content_generator: ZMK config content generator

    Returns:
        ZmkConfigCompilationService: New service instance
    """
    return ZmkConfigCompilationService(
        workspace_manager=workspace_manager,
        build_matrix_resolver=build_matrix_resolver,
        artifact_collector=artifact_collector,
        environment_manager=environment_manager,
        volume_manager=volume_manager,
        docker_adapter=docker_adapter,
        content_generator=content_generator,
    )
