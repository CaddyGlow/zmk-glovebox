"""West compilation service for ZMK firmware builds."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

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
from glovebox.compilation.protocols.artifact_protocols import (
    ArtifactCollectorProtocol,
)
from glovebox.compilation.protocols.compilation_protocols import (
    CompilationServiceProtocol,
)
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
from glovebox.core.errors import BuildError
from glovebox.firmware.models import BuildResult
from glovebox.protocols import DockerAdapterProtocol
from glovebox.protocols.docker_adapter_protocol import DockerVolume


logger = logging.getLogger(__name__)


class WestCompilationService(BaseCompilationService):
    """West compilation service for ZMK firmware builds.

    Implements the traditional ZMK west workspace build strategy with
    workspace initialization and board-specific compilation.
    """

    def __init__(
        self,
        workspace_manager: WestWorkspaceManagerProtocol | None = None,
        build_matrix_resolver: BuildMatrixResolver | None = None,
        artifact_collector: ArtifactCollectorProtocol | None = None,
        environment_manager: EnvironmentManager | None = None,
        volume_manager: VolumeManager | None = None,
        docker_adapter: DockerAdapterProtocol | None = None,
    ) -> None:
        """Initialize west compilation service.

        Args:
            workspace_manager: West workspace manager
            build_matrix_resolver: Build matrix resolver (not used for west strategy)
            artifact_collector: Artifact collection service
            environment_manager: Environment variable manager
            volume_manager: Docker volume manager
            docker_adapter: Docker adapter for container operations
        """
        super().__init__("west_compilation", "1.0.0")
        self.workspace_manager = workspace_manager or create_west_workspace_manager()
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
        keyboard_profile: "KeyboardProfile | None" = None,
    ) -> BuildResult:
        """Execute west compilation strategy.

        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            output_dir: Output directory for firmware files
            config: Compilation configuration
            keyboard_profile: Keyboard profile (unused for west strategy)

        Returns:
            BuildResult: Compilation results with firmware files

        Raises:
            BuildError: If compilation fails
        """
        logger.info("Starting west build strategy")
        result = BuildResult(success=True)

        try:
            if not self._docker_adapter:
                result.success = False
                result.add_error("Docker adapter not available for west compilation")
                return result

            workspace_path = None

            # Initialize west workspace if configured
            if config.west_workspace:
                workspace_path = Path(config.west_workspace.workspace_path)

                if not self._initialize_workspace(
                    config.west_workspace, keymap_file, config_file
                ):
                    result.success = False
                    result.add_error("Failed to initialize west workspace")
                    return result

            # Prepare build environment for west
            build_env = self._prepare_build_environment(config)

            # Prepare Docker volumes for west workspace
            volumes = self._prepare_build_volumes(
                workspace_path, keymap_file, config_file, output_dir, config
            )

            # Generate west build commands
            build_commands = self._generate_build_commands(config)

            # Execute build commands in Docker container
            west_command = " && ".join(build_commands)
            docker_image = config.image

            # Determine working directory
            work_dir = (
                config.west_workspace.workspace_path
                if config.west_workspace
                else "/zmk-workspace"
            )

            return_code, stdout_lines, stderr_lines = (
                self._docker_adapter.run_container(
                    image=docker_image,
                    command=[
                        "sh",
                        "-c",
                        f"cd {work_dir} && {west_command}",
                    ],
                    volumes=volumes,
                    environment=build_env,
                )
            )

            if return_code != 0:
                error_msg = (
                    "\\n".join(stderr_lines)
                    if stderr_lines
                    else "West compilation failed"
                )
                logger.error(
                    "West compilation failed with exit code %d: %s",
                    return_code,
                    error_msg,
                )
                result.success = False
                result.add_error(
                    f"West compilation failed with exit code {return_code}: {error_msg}"
                )
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
                f"West compilation completed. Generated {firmware_count} firmware files."
            )

            return result

        except Exception as e:
            msg = f"West compilation failed: {e}"
            logger.error(msg)
            result.success = False
            result.add_error(msg)
            return result

    def validate_configuration(self, config: GenericDockerCompileConfig) -> bool:
        """Validate west compilation configuration.

        Args:
            config: Compilation configuration to validate

        Returns:
            bool: True if configuration is valid
        """
        # West strategy doesn't require specific configuration
        # but can optionally use west_workspace configuration
        if config.west_workspace:
            if not config.west_workspace.workspace_path:
                logger.error(
                    "West workspace path is required when workspace is configured"
                )
                return False

            if not config.west_workspace.manifest_url:
                logger.error(
                    "West manifest URL is required when workspace is configured"
                )
                return False

        return True

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
        # West compilation requires Docker adapter
        return self._docker_adapter is not None and self._docker_adapter.is_available()

    def _initialize_workspace(
        self,
        workspace_config: Any,
        keymap_file: Path,
        config_file: Path,
    ) -> bool:
        """Initialize west workspace.

        Args:
            workspace_config: West workspace configuration
            keymap_file: User keymap file
            config_file: User config file

        Returns:
            bool: True if workspace initialized successfully
        """
        return self.workspace_manager.initialize_workspace(
            workspace_config=workspace_config,
            keymap_file=keymap_file,
            config_file=config_file,
        )

    def _prepare_build_environment(
        self, config: GenericDockerCompileConfig
    ) -> dict[str, str]:
        """Prepare build environment variables.

        Args:
            config: Compilation configuration

        Returns:
            dict[str, str]: Environment variables for Docker container
        """
        context = {}

        # Add west-specific environment
        if config.west_workspace:
            context.update(
                {
                    "workspace_path": config.west_workspace.workspace_path,
                    "config_path": config.west_workspace.config_path,
                    "manifest_url": config.west_workspace.manifest_url,
                    "manifest_revision": config.west_workspace.manifest_revision,
                }
            )

        return self.environment_manager.prepare_environment(config, **context)

    def _prepare_build_volumes(
        self,
        workspace_path: Path | None,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
    ) -> list[DockerVolume]:
        """Prepare Docker volumes for build.

        Args:
            workspace_path: Path to west workspace (if any)
            keymap_file: Path to keymap file
            config_file: Path to config file
            output_dir: Output directory for firmware files
            config: Compilation configuration

        Returns:
            list[DockerVolume]: Docker volume mount tuples
        """
        volumes = []

        # Map output directory
        output_dir_abs = output_dir.absolute()
        volumes.append((str(output_dir_abs), "/build"))

        # Use volume templates if provided, otherwise use optimized defaults
        if config.volume_templates:
            # Apply volume templates (this would be expanded based on templates)
            for template in config.volume_templates:
                logger.debug("Applying volume template: %s", template)
                # Parse template and add to volumes
                self._parse_volume_template(template, volumes)
        else:
            # Optimized west workspace volume mapping
            if config.west_workspace and workspace_path:
                config_path = config.west_workspace.config_path
                workspace_path_str = config.west_workspace.workspace_path

                # Map files to west workspace config directory
                keymap_abs = keymap_file.absolute()
                config_abs = config_file.absolute()

                volumes.append(
                    (
                        str(keymap_abs),
                        f"{workspace_path_str}/{config_path}/keymap.keymap:ro",
                    )
                )
                volumes.append(
                    (
                        str(config_abs),
                        f"{workspace_path_str}/{config_path}/config.conf:ro",
                    )
                )

                # Add workspace directory for persistent builds
                workspace_host_path = workspace_path.absolute()
                if workspace_host_path.exists():
                    volumes.append(
                        (str(workspace_host_path), f"{workspace_path_str}:rw")
                    )
                    logger.debug(
                        "Mounted workspace directory: %s",
                        workspace_path_str,
                    )
            else:
                # Default volume mappings without workspace
                keymap_abs = keymap_file.absolute()
                config_abs = config_file.absolute()
                volumes.append(
                    (str(keymap_abs), "/zmk-workspace/config/keymap.keymap:ro")
                )
                volumes.append(
                    (str(config_abs), "/zmk-workspace/config/config.conf:ro")
                )

        return volumes

    def _parse_volume_template(
        self, template: str, volumes: list[DockerVolume]
    ) -> None:
        """Parse volume template string and add to volumes list.

        Args:
            template: Volume template string
            volumes: List to append volumes to
        """
        try:
            # Simple template parsing - format: "host_path:container_path:mode"
            parts = template.split(":")
            if len(parts) >= 2:
                host_path = parts[0]
                container_path = parts[1]
                mode = parts[2] if len(parts) > 2 else "rw"

                # Expand templates like {workspace_path}
                # This could be enhanced to support more template variables
                volumes.append((host_path, f"{container_path}:{mode}"))
                logger.debug(
                    "Parsed volume template: %s -> %s:%s",
                    host_path,
                    container_path,
                    mode,
                )
        except Exception as e:
            logger.warning("Failed to parse volume template '%s': %s", template, e)

    def _generate_build_commands(self, config: GenericDockerCompileConfig) -> list[str]:
        """Generate west build commands.

        Args:
            config: Compilation configuration

        Returns:
            list[str]: List of west build commands
        """
        build_commands = []

        # Build west compilation command
        if config.board_targets:
            # Build for specific board targets
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


def create_west_compilation_service(
    workspace_manager: WestWorkspaceManagerProtocol | None = None,
    build_matrix_resolver: BuildMatrixResolver | None = None,
    artifact_collector: ArtifactCollectorProtocol | None = None,
    environment_manager: EnvironmentManager | None = None,
    volume_manager: VolumeManager | None = None,
    docker_adapter: DockerAdapterProtocol | None = None,
) -> WestCompilationService:
    """Create west compilation service instance.

    Args:
        workspace_manager: West workspace manager
        build_matrix_resolver: Build matrix resolver
        artifact_collector: Artifact collector
        environment_manager: Environment manager
        volume_manager: Volume manager
        docker_adapter: Docker adapter

    Returns:
        WestCompilationService: New service instance
    """
    return WestCompilationService(
        workspace_manager=workspace_manager,
        build_matrix_resolver=build_matrix_resolver,
        artifact_collector=artifact_collector,
        environment_manager=environment_manager,
        volume_manager=volume_manager,
        docker_adapter=docker_adapter,
    )
