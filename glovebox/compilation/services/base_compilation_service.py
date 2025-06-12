"""Base compilation service for all compilation strategies."""

import logging
from abc import abstractmethod
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
from glovebox.compilation.configuration.user_context_manager import (
    UserContextManager,
    create_user_context_manager,
)
from glovebox.compilation.configuration.volume_manager import (
    VolumeManager,
    create_volume_manager,
)

# Artifact collection will be replaced with SimpleArtifactCollector in Phase 3
from glovebox.config.compile_methods import CompilationConfig
from glovebox.core.errors import BuildError
from glovebox.firmware.models import BuildResult
from glovebox.protocols import DockerAdapterProtocol
from glovebox.services.base_service import BaseService


class BaseCompilationService(BaseService):
    """Base service for all compilation strategies.

    Provides common Docker execution logic, environment preparation,
    volume management, artifact collection, and error handling patterns
    shared across all compilation strategies.
    """

    def __init__(
        self,
        name: str,
        version: str,
        build_matrix_resolver: BuildMatrixResolver | None = None,
        artifact_collector: Any
        | None = None,  # Will be SimpleArtifactCollector in Phase 3
        environment_manager: EnvironmentManager | None = None,
        volume_manager: VolumeManager | None = None,
        user_context_manager: UserContextManager | None = None,
        docker_adapter: DockerAdapterProtocol | None = None,
        compilation_cache: Any | None = None,
    ):
        """Initialize base compilation service with common dependencies.

        Args:
            name: Service name for identification
            version: Service version for compatibility tracking
            build_matrix_resolver: Build matrix resolver
            artifact_collector: Artifact collection service
            environment_manager: Environment variable manager
            volume_manager: Docker volume manager
            user_context_manager: User context manager for Docker user mapping
            docker_adapter: Docker adapter for container operations
            compilation_cache: Compilation cache instance
        """
        super().__init__(name, version)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Initialize common dependencies
        self.build_matrix_resolver = (
            build_matrix_resolver or create_build_matrix_resolver()
        )
        self.artifact_collector = artifact_collector  # Will be None until Phase 5
        self.environment_manager = environment_manager or create_environment_manager()
        self.volume_manager = volume_manager or create_volume_manager()
        self.user_context_manager = (
            user_context_manager or create_user_context_manager()
        )

        # Initialize generic cache system
        self.compilation_cache = compilation_cache

        # Docker adapter will be injected from parent coordinator
        self._docker_adapter: DockerAdapterProtocol | None = docker_adapter

    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: CompilationConfig,
        keyboard_profile: "KeyboardProfile | None" = None,
    ) -> BuildResult:
        """Execute compilation using template method pattern.

        Template method that orchestrates the common compilation flow
        while allowing strategy-specific customization through abstract methods.

        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            output_dir: Output directory for build artifacts
            config: Compilation configuration
            keyboard_profile: Keyboard profile for dynamic generation

        Returns:
            BuildResult: Results of compilation

        Raises:
            BuildError: If compilation fails
        """
        self.logger.info(f"Starting {self.service_name} compilation")
        result = BuildResult(success=True)

        try:
            # Step 1: Validate configuration
            if not self._validate_common_config(config, result):
                return result

            if config.zmk_config_repo is None:
                raise BuildError("ZMK config repository configuration is missing")

            # Step 2: Setup workspace (strategy-specific)
            workspace_path = self._setup_workspace(
                keymap_file, config_file, config, keyboard_profile
            )
            if not workspace_path:
                result.success = False
                result.add_error("Failed to setup workspace")
                return result

            # Step 3: Execute Docker compilation (common logic)
            if not self._execute_docker_compilation(
                workspace_path, output_dir, config, result
            ):
                return result

            # Step 4: Collect artifacts (common logic)
            firmware_files = self._collect_firmware_artifacts(
                workspace_path, output_dir
            )
            if not self._validate_artifacts(firmware_files, result):
                return result

            # Step 5: Store results and prepare response
            result.output_files = firmware_files
            firmware_count = self._count_firmware_files(firmware_files)
            result.add_message(
                f"{self.service_name} compilation completed. "
                f"Generated {firmware_count} firmware files."
            )

            return result

        except Exception as e:
            msg = f"{self.service_name} compilation failed: {e}"
            self.logger.error(msg)
            result.success = False
            result.add_error(msg)
            return result

    @abstractmethod
    def _setup_workspace(
        self,
        keymap_file: Path,
        config_file: Path,
        config: CompilationConfig,
        keyboard_profile: "KeyboardProfile | None" = None,
    ) -> Path | None:
        """Setup workspace for compilation (strategy-specific).

        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            config: Compilation configuration
            keyboard_profile: Keyboard profile for dynamic generation

        Returns:
            Path | None: Workspace path if successful, None if failed
        """
        pass

    @abstractmethod
    def _build_compilation_command(
        self, workspace_path: Path, config: CompilationConfig
    ) -> str:
        """Build compilation command for this strategy.

        Args:
            workspace_path: Path to workspace directory
            config: Compilation configuration

        Returns:
            str: Complete compilation command to execute
        """
        pass

    def validate_config(self, config: CompilationConfig) -> bool:
        """Validate compilation configuration.

        Calls both common validation and strategy-specific validation.

        Args:
            config: Compilation configuration to validate

        Returns:
            bool: True if configuration is valid
        """
        # Base validation checks
        if not self._validate_common_requirements(config):
            return False

        # Strategy-specific validation
        return self._validate_strategy_specific(config)

    def _validate_common_requirements(self, config: CompilationConfig) -> bool:
        """Validate common configuration requirements.

        Args:
            config: Compilation configuration to validate

        Returns:
            bool: True if common requirements are met
        """
        if not config.image:
            self.logger.error("Docker image not specified")
            return False

        return True

    @abstractmethod
    def _validate_strategy_specific(self, config: CompilationConfig) -> bool:
        """Validate strategy-specific configuration requirements.

        Args:
            config: Compilation configuration to validate

        Returns:
            bool: True if strategy-specific requirements are met
        """
        pass

    def check_available(self) -> bool:
        """Check if this compilation strategy is available.

        Base implementation checks for Docker availability.
        Subclasses can override for strategy-specific availability checks.

        Returns:
            bool: True if strategy is available
        """
        # Default to checking if we have necessary dependencies
        # Subclasses should override for specific availability checks
        return self._docker_adapter is not None

    def set_docker_adapter(self, docker_adapter: DockerAdapterProtocol) -> None:
        """Set Docker adapter for compilation operations.

        Args:
            docker_adapter: Docker adapter instance
        """
        self._docker_adapter = docker_adapter

    def _validate_common_config(
        self, config: CompilationConfig, result: BuildResult
    ) -> bool:
        """Validate common configuration requirements.

        Args:
            config: Compilation configuration
            result: Build result to store errors

        Returns:
            bool: True if configuration is valid
        """
        if not self._docker_adapter:
            result.success = False
            result.add_error("Docker adapter not available for compilation")
            return False

        if not self.validate_config(config):
            result.success = False
            result.add_error("Configuration validation failed")
            return False

        return True

    def _execute_docker_compilation(
        self,
        workspace_path: Path,
        output_dir: Path,
        config: CompilationConfig,
        result: BuildResult,
    ) -> bool:
        """Execute Docker compilation using common patterns.

        Args:
            workspace_path: Path to workspace directory
            output_dir: Output directory for artifacts
            config: Compilation configuration
            result: Build result to store errors

        Returns:
            bool: True if compilation succeeded
        """
        try:
            # Prepare build environment
            build_env = self._prepare_build_environment(config)

            # Prepare Docker volumes (single workspace strategy)
            volumes = self._prepare_build_volumes(workspace_path, config)

            # Get compilation command from strategy
            compilation_command = self._build_compilation_command(
                workspace_path, config
            )

            # Get user context for Docker volume permissions
            user_context = self.user_context_manager.get_user_context(
                enable_user_mapping=config.docker_user.enable_user_mapping,
                detect_automatically=config.docker_user.detect_user_automatically,
            )

            # Update environment for Docker user mapping if enabled
            if user_context and user_context.should_use_user_mapping():
                build_env = self.environment_manager.prepare_docker_environment(
                    config,
                    user_context=user_context,
                    user_mapping_enabled=True,
                    workspace_path=str(workspace_path),
                )

            # Execute Docker container
            if not self._docker_adapter:
                raise BuildError("Docker adapter not available")

            return_code, stdout_lines, stderr_lines = (
                self._docker_adapter.run_container(
                    image=config.image,
                    command=["sh", "-c", compilation_command],
                    volumes=volumes,
                    environment=build_env,
                    user_context=user_context,
                )
            )

            if return_code != 0:
                error_msg = (
                    "\n".join(stderr_lines) if stderr_lines else "Compilation failed"
                )
                self.logger.error(
                    "Compilation failed with exit code %d: %s",
                    return_code,
                    error_msg,
                )
                result.success = False
                result.add_error(
                    f"Compilation failed with exit code {return_code}: {error_msg}"
                )
                return False

            return True

        except Exception as e:
            self.logger.error("Docker compilation execution failed: %s", e)
            result.success = False
            result.add_error(f"Docker compilation execution failed: {e}")
            return False

    def _prepare_build_environment(self, config: CompilationConfig) -> dict[str, str]:
        """Prepare build environment variables for compilation.

        Base environment preparation that all strategies can use.
        Can be extended by subclasses for strategy-specific environment.

        Args:
            config: Compilation configuration

        Returns:
            dict[str, str]: Environment variables for build
        """
        import multiprocessing

        # Start with custom environment template
        build_env = dict(config.environment_template)

        # Add common build environment variables
        build_env.setdefault("JOBS", str(multiprocessing.cpu_count()))
        build_env.setdefault("BUILD_TYPE", "Release")

        self.logger.debug("Prepared base build environment: %s", build_env)
        return build_env

    def _prepare_build_volumes(
        self,
        workspace_path: Path,
        config: CompilationConfig,
    ) -> list[tuple[str, str]]:
        """Prepare Docker volumes for compilation using single workspace volume strategy.

        Simplified volume strategy: only mounts workspace volume to Docker container.
        Artifacts are extracted from workspace post-execution using build matrix.

        Args:
            workspace_path: Path to workspace directory
            config: Compilation configuration

        Returns:
            list[tuple[str, str]]: Docker volumes for compilation (host_path, container_path)
        """
        volumes = []

        # Single workspace volume only - mount at /workspace for consistent path
        volumes.append((str(workspace_path.resolve()), "/workspace"))

        # Add custom volume templates (if specified by user)
        for volume_template in config.volume_templates:
            # Parse volume template (format: host_path:container_path)
            parts = volume_template.split(":")
            if len(parts) >= 2:
                host_path = parts[0]
                container_path = parts[1]
                volumes.append((host_path, container_path))

        self.logger.debug(
            "Prepared %d Docker volumes (single workspace strategy)", len(volumes)
        )
        return volumes

    def _collect_firmware_artifacts(
        self, workspace_path: Path, output_dir: Path
    ) -> Any:
        """Collect firmware artifacts from workspace and output directories.

        Args:
            workspace_path: Path to workspace directory
            output_dir: Output directory for artifacts

        Returns:
            Any: Firmware files collection (will be properly typed in Phase 2)
        """
        # Use new SimpleArtifactCollector with ZMK GitHub Actions conventions
        if not self.artifact_collector:
            from glovebox.compilation.artifacts import create_simple_artifact_collector

            collector = create_simple_artifact_collector()

            # Collect and copy artifacts using ZMK build matrix
            output_files = collector.collect_and_copy(
                workspace_path=workspace_path, output_dir=output_dir
            )

            return output_files

        # Use the protocol method when artifact collector is implemented
        firmware_files, output_files = self.artifact_collector.collect_artifacts(
            output_dir
        )

        self.logger.debug(
            "Collected firmware artifacts: main=%s, left=%s, right=%s",
            output_files.main_uf2 if output_files else None,
            output_files.left_uf2 if output_files else None,
            output_files.right_uf2 if output_files else None,
        )

        return output_files

    def _validate_artifacts(self, firmware_files: Any, result: BuildResult) -> bool:
        """Validate collected artifacts.

        Args:
            firmware_files: Collected firmware files
            result: Build result to store errors

        Returns:
            bool: True if artifacts are valid
        """
        if not firmware_files or not (
            firmware_files.main_uf2
            or firmware_files.left_uf2
            or firmware_files.right_uf2
        ):
            result.success = False
            result.add_error("No firmware files generated")
            return False

        return True

    def _count_firmware_files(self, firmware_files: Any) -> int:
        """Count the number of firmware files generated.

        Args:
            firmware_files: Collected firmware files

        Returns:
            int: Number of firmware files
        """
        count = 0
        if firmware_files.main_uf2:
            count += 1
        if firmware_files.left_uf2:
            count += 1
        if firmware_files.right_uf2:
            count += 1
        return count

    def _extract_board_name(self, config: CompilationConfig) -> str:
        """Extract board name from compilation configuration.

        Common logic for extracting board name from config.

        Args:
            config: Compilation configuration

        Returns:
            str: Board name for compilation
        """
        # Use board targets from config
        if config.board_targets and len(config.board_targets) > 0:
            return config.board_targets[0]

        # Default board for most ZMK keyboards
        return "nice_nano_v2"

    def _handle_workspace_setup_error(self, operation: str, error: Exception) -> None:
        """Common error handling for workspace setup failures.

        Args:
            operation: Description of the operation that failed
            error: The exception that occurred
        """
        self.logger.error("Failed to setup %s workspace: %s", operation, error)
