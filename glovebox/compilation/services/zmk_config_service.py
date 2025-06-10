"""ZMK config compilation service following GitHub Actions workflow pattern."""

import logging
from pathlib import Path
from typing import Any

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
    ) -> None:
        """Initialize ZMK config compilation service.

        Args:
            workspace_manager: ZMK config workspace manager
            build_matrix_resolver: Build matrix resolver for build.yaml
            artifact_collector: Artifact collection service
            environment_manager: Environment variable manager
            volume_manager: Docker volume manager
            docker_adapter: Docker adapter for container operations
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

        # Docker adapter will be injected from parent coordinator
        self._docker_adapter: DockerAdapterProtocol | None = docker_adapter

    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
    ) -> BuildResult:
        """Execute ZMK config compilation using GitHub Actions pattern.

        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            output_dir: Output directory for firmware files
            config: Compilation configuration

        Returns:
            BuildResult: Compilation results with firmware files

        Raises:
            BuildError: If compilation fails
        """
        logger.info("Starting ZMK config compilation")
        result = BuildResult(success=True)

        try:
            # Validate ZMK config repository configuration
            if not self._validate_zmk_config(config, result):
                return result

            config_repo_config = config.zmk_config_repo
            if not config_repo_config:
                result.success = False
                result.add_error("ZMK config repository configuration is missing")
                return result
            workspace_path = Path(config_repo_config.workspace_path)

            # Initialize ZMK config workspace
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


def create_zmk_config_service(
    workspace_manager: ZmkConfigWorkspaceManagerProtocol | None = None,
    build_matrix_resolver: BuildMatrixResolver | None = None,
    artifact_collector: ArtifactCollectorProtocol | None = None,
    environment_manager: EnvironmentManager | None = None,
    volume_manager: VolumeManager | None = None,
    docker_adapter: DockerAdapterProtocol | None = None,
) -> ZmkConfigCompilationService:
    """Create ZMK config compilation service instance.

    Args:
        workspace_manager: ZMK config workspace manager
        build_matrix_resolver: Build matrix resolver
        artifact_collector: Artifact collector
        environment_manager: Environment manager
        volume_manager: Volume manager
        docker_adapter: Docker adapter

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
    )
