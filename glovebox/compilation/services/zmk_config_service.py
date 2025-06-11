"""ZMK config compilation service following GitHub Actions workflow pattern."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.compilation.artifacts.firmware_scanner import (
    FirmwareScanner,
    create_firmware_scanner,
)
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
from glovebox.protocols import FileAdapterProtocol


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
        user_context_manager: UserContextManager | None = None,
        docker_adapter: DockerAdapterProtocol | None = None,
        content_generator: ZmkConfigContentGenerator | None = None,
        firmware_scanner: FirmwareScanner | None = None,
        file_adapter: FileAdapterProtocol | None = None,
    ) -> None:
        """Initialize ZMK config compilation service.

        Args:
            workspace_manager: ZMK config workspace manager
            build_matrix_resolver: Build matrix resolver for build.yaml
            artifact_collector: Artifact collection service
            environment_manager: Environment variable manager
            volume_manager: Docker volume manager
            user_context_manager: User context manager for Docker user mapping
            docker_adapter: Docker adapter for container operations
            content_generator: ZMK config content generator for dynamic workspaces
            firmware_scanner: Firmware scanner for workspace and output scanning
            file_adapter: File operations adapter
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
        self.user_context_manager = (
            user_context_manager or create_user_context_manager()
        )
        self.content_generator = (
            content_generator or create_zmk_config_content_generator()
        )
        self.firmware_scanner = firmware_scanner or create_firmware_scanner()

        # File adapter for file operations
        from glovebox.adapters import create_file_adapter

        self.file_adapter = file_adapter or create_file_adapter()

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

            # Collect and validate artifacts using enhanced workspace scanning
            firmware_files = self._collect_firmware_artifacts(
                workspace_path, output_dir
            )
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

        # For dynamic generation, config_repo_url can be empty
        repo_url = config_repo.config_repo_url
        is_dynamic_mode = not repo_url or repo_url.strip() == ""

        if not is_dynamic_mode and not config_repo.config_repo_url:
            logger.error("ZMK config repository URL is required for repository mode")
            return False

        if not config_repo.workspace_path:
            logger.error("ZMK config workspace path is required")
            return False

        logger.debug("ZMK config validation passed (dynamic mode: %s)", is_dynamic_mode)
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

        # Get user context for Docker volume permissions
        user_context = self.user_context_manager.get_user_context(
            enable_user_mapping=config.enable_user_mapping,
            detect_automatically=config.detect_user_automatically,
        )

        # Update environment for Docker user mapping if enabled
        if user_context and user_context.should_use_user_mapping():
            # Prepare context for environment preparation
            context = {
                "workspace_path": config_repo_config.workspace_path,
                "config_path": config_repo_config.config_path,
                "build_yaml_path": config_repo_config.build_yaml_path,
            }

            build_env = self.environment_manager.prepare_docker_environment(
                config, user_mapping_enabled=True, **context
            )

        return_code, stdout_lines, stderr_lines = self._docker_adapter.run_container(
            image=docker_image,
            command=[
                "sh",
                "-c",
                f"cd {config_repo_config.workspace_path} && {west_command}",
            ],
            volumes=volumes,
            environment=build_env,
            user_context=user_context,
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
        """Generate complete west command sequence including initialization.

        Args:
            build_matrix: Build matrix with targets
            config: Compilation configuration

        Returns:
            list[str]: List of west commands including initialization and build
        """
        build_commands = []

        # Add west initialization commands first
        if config.zmk_config_repo and config.zmk_config_repo.west_commands:
            build_commands.extend(config.zmk_config_repo.west_commands)
            logger.debug(
                "Added west initialization commands: %s",
                config.zmk_config_repo.west_commands,
            )

        # Add west zephyr-export command (required after west update)
        build_commands.append("west zephyr-export")
        logger.debug("Added west zephyr-export command")

        # Add build commands
        if build_matrix.targets:
            # Use targets from build.yaml
            for target in build_matrix.targets:
                command = self._generate_target_command(target)
                build_commands.append(command)
        elif config.board_targets:
            # Use board targets from config
            for board in config.board_targets:
                build_commands.append(
                    f"west build -s zmk/app -p always -b {board} -d build/{board}"
                )
        else:
            # Default build command
            build_commands.append("west build -s zmk/app -p always")

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

        return f"west build -s zmk/app -p always -b {board_arg} -d build/{artifact_name}{shield_arg}"

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
        # Ensure absolute paths for Docker volume mounting
        workspace_abs = workspace_path.resolve()
        output_abs = output_dir.resolve()

        logger.debug("Mounting workspace: %s -> %s", workspace_abs, workspace_abs)
        logger.debug("Mounting output: %s -> %s", output_abs, output_abs)

        return [
            (str(workspace_abs), str(workspace_abs)),
            (str(output_abs), str(output_abs)),
        ]

    def _collect_firmware_artifacts(
        self, workspace_path: Path, output_dir: Path
    ) -> Any:
        """Collect firmware artifacts from workspace and output directories.

        Uses enhanced scanning to find firmware files in both workspace build
        directories (where ZMK config compilation generates them) and output
        directories (where they may be copied).

        Args:
            workspace_path: Path to compilation workspace
            output_dir: Output directory to scan

        Returns:
            FirmwareOutputFiles: Collected firmware files
        """
        logger.info(
            "Collecting firmware artifacts from workspace and output directories"
        )
        logger.debug("Workspace path: %s", workspace_path)
        logger.debug("Output directory: %s", output_dir)

        if not self.artifact_collector:
            # Enhanced fallback implementation using firmware scanner
            from glovebox.firmware.models import FirmwareOutputFiles

            # Use the enhanced firmware scanner to scan both directories
            firmware_files = self.firmware_scanner.scan_workspace_and_output(
                workspace_path, output_dir
            )

            if not firmware_files:
                logger.warning(
                    "No firmware files found in workspace (%s) or output (%s)",
                    workspace_path,
                    output_dir,
                )
                return FirmwareOutputFiles(output_dir=output_dir)

            # Organize files into structured output
            output_files = self._organize_firmware_files(firmware_files, output_dir)
            logger.info(
                "Collected %d firmware files: main=%s, left=%s, right=%s",
                len(firmware_files),
                output_files.main_uf2,
                output_files.left_uf2,
                output_files.right_uf2,
            )

            return output_files

        # Use the protocol method when artifact collector is implemented
        firmware_files, output_files = self.artifact_collector.collect_artifacts(
            output_dir
        )
        return output_files

    def _organize_firmware_files(
        self, firmware_files: list[Path], output_dir: Path
    ) -> Any:
        """Organize firmware files into structured output.

        Copies firmware files from workspace to output directory and captures
        additional build artifacts like devicetree files and build logs.

        Args:
            firmware_files: List of collected firmware files
            output_dir: Base output directory

        Returns:
            FirmwareOutputFiles: Structured output files with copied firmware
        """
        import shutil
        from datetime import datetime

        from glovebox.firmware.models import FirmwareOutputFiles

        output_files = FirmwareOutputFiles(output_dir=output_dir)

        if not firmware_files:
            return output_files

        # Create timestamped output directory for this build
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        build_output_dir = output_dir / f"build-{timestamp}"

        # Use injected FileAdapter for directory creation
        self.file_adapter.create_directory(build_output_dir)
        if not self.file_adapter.check_exists(build_output_dir):
            logger.error(
                "Failed to create build output directory: %s", build_output_dir
            )
            # Use output_dir directly as fallback
            build_output_dir = output_dir
        else:
            logger.info("Created build output directory: %s", build_output_dir)

        # Process and copy each firmware file
        for firmware_file in firmware_files:
            # Check the build directory name (e.g., glove80_lh, glove80_rh)
            build_dir = firmware_file.parent.parent.name.lower()
            parent_dir = firmware_file.parent.name.lower()
            filename = firmware_file.name.lower()

            # Determine target filename based on board type
            copied_file = None
            if any(pattern in build_dir for pattern in ["_lh", "_left"]):
                target_filename = f"{build_dir}_left.uf2"
                copied_file = self._copy_firmware_and_artifacts(
                    firmware_file, build_output_dir, target_filename, "left"
                )
                output_files.left_uf2 = copied_file
                logger.debug(
                    "Copied left hand firmware: %s -> %s", firmware_file, copied_file
                )
            elif any(pattern in build_dir for pattern in ["_rh", "_right"]):
                target_filename = f"{build_dir}_right.uf2"
                copied_file = self._copy_firmware_and_artifacts(
                    firmware_file, build_output_dir, target_filename, "right"
                )
                output_files.right_uf2 = copied_file
                logger.debug(
                    "Copied right hand firmware: %s -> %s", firmware_file, copied_file
                )
            # Check parent directory patterns
            elif any(pattern in parent_dir for pattern in ["lh", "lf", "left"]):
                target_filename = f"{parent_dir}_left.uf2"
                copied_file = self._copy_firmware_and_artifacts(
                    firmware_file, build_output_dir, target_filename, "left"
                )
                output_files.left_uf2 = copied_file
                logger.debug(
                    "Copied left hand firmware from parent dir: %s -> %s",
                    firmware_file,
                    copied_file,
                )
            elif any(pattern in parent_dir for pattern in ["rh", "rf", "right"]):
                target_filename = f"{parent_dir}_right.uf2"
                copied_file = self._copy_firmware_and_artifacts(
                    firmware_file, build_output_dir, target_filename, "right"
                )
                output_files.right_uf2 = copied_file
                logger.debug(
                    "Copied right hand firmware from parent dir: %s -> %s",
                    firmware_file,
                    copied_file,
                )
            # Check filename patterns or fallback to main
            elif any(pattern in filename for pattern in ["left", "_lh", "_lf"]):
                target_filename = f"{firmware_file.stem}_left.uf2"
                copied_file = self._copy_firmware_and_artifacts(
                    firmware_file, build_output_dir, target_filename, "left"
                )
                output_files.left_uf2 = copied_file
                logger.debug(
                    "Copied left hand firmware from filename: %s -> %s",
                    firmware_file,
                    copied_file,
                )
            elif any(pattern in filename for pattern in ["right", "_rh", "_rf"]):
                target_filename = f"{firmware_file.stem}_right.uf2"
                copied_file = self._copy_firmware_and_artifacts(
                    firmware_file, build_output_dir, target_filename, "right"
                )
                output_files.right_uf2 = copied_file
                logger.debug(
                    "Copied right hand firmware from filename: %s -> %s",
                    firmware_file,
                    copied_file,
                )
            else:
                # Fallback to main firmware file
                target_filename = f"{firmware_file.stem}.uf2"
                copied_file = self._copy_firmware_and_artifacts(
                    firmware_file, build_output_dir, target_filename, "main"
                )
                if not output_files.main_uf2:
                    output_files.main_uf2 = copied_file
                logger.debug(
                    "Copied main firmware: %s -> %s", firmware_file, copied_file
                )

        # If we identified left/right split files, clear the main_uf2 for cleaner output
        if output_files.left_uf2 and output_files.right_uf2:
            output_files.main_uf2 = None
            logger.debug("Split keyboard detected - cleared main firmware file")

        logger.info(
            "Organized and copied firmware files: main=%s, left=%s, right=%s",
            output_files.main_uf2,
            output_files.left_uf2,
            output_files.right_uf2,
        )

        return output_files

    def _copy_firmware_and_artifacts(
        self, firmware_file: Path, output_dir: Path, target_filename: str, side: str
    ) -> Path:
        """Copy firmware file and capture additional build artifacts.

        Following GitHub Actions pattern, captures firmware, devicetree files,
        and build logs from the ZMK build workspace.

        Args:
            firmware_file: Source firmware file path
            output_dir: Target output directory
            target_filename: Target filename for the firmware
            side: Board side identifier (left, right, main)

        Returns:
            Path: Path to copied firmware file
        """
        # Copy main firmware file using injected FileAdapter
        target_firmware = output_dir / target_filename
        try:
            self.file_adapter.copy_file(firmware_file, target_firmware)
            logger.debug("Copied firmware: %s -> %s", firmware_file, target_firmware)
        except Exception as e:
            logger.error(
                "Failed to copy firmware %s -> %s: %s",
                firmware_file,
                target_firmware,
                e,
            )
            return firmware_file  # Return original path if copy fails

        # Capture additional artifacts from the build directory
        build_dir = firmware_file.parent  # e.g., .../build/glove80_lh/zephyr/
        artifacts_dir = output_dir / f"{side}_artifacts"
        self.file_adapter.create_directory(artifacts_dir)

        # Capture devicetree files (following GitHub Actions pattern)
        self._capture_devicetree_files(build_dir, artifacts_dir, side)

        # Capture build information and logs
        self._capture_build_artifacts(build_dir, artifacts_dir, side)

        return target_firmware

    def _capture_devicetree_files(
        self, build_dir: Path, artifacts_dir: Path, side: str
    ) -> None:
        """Capture devicetree files following GitHub Actions pattern.

        Captures zephyr.dts and zephyr.dts.pre files as shown in the GitHub Actions workflow.

        Args:
            build_dir: ZMK build directory (e.g., build/glove80_lh/zephyr/)
            artifacts_dir: Artifacts output directory
            side: Board side identifier
        """
        devicetree_content = []

        # Check for zephyr.dts (primary devicetree file)
        zephyr_dts = build_dir / "zephyr.dts"
        if self.file_adapter.check_exists(zephyr_dts):
            content = self.file_adapter.read_text(zephyr_dts)
            if content:
                devicetree_content.append(
                    f"=== {side.upper()} HAND DEVICETREE (zephyr.dts) ===\n"
                )
                devicetree_content.append(content)
                logger.debug("Captured devicetree file: %s", zephyr_dts)
            else:
                logger.warning("Failed to read devicetree file %s", zephyr_dts)

        # Check for zephyr.dts.pre (preprocessed devicetree file)
        zephyr_dts_pre = build_dir / "zephyr.dts.pre"
        if self.file_adapter.check_exists(zephyr_dts_pre):
            content = self.file_adapter.read_text(zephyr_dts_pre)
            if content:
                devicetree_content.append(
                    f"\n=== {side.upper()} HAND DEVICETREE PREPROCESSED (zephyr.dts.pre) ===\n"
                )
                devicetree_content.append(content)
                logger.debug(
                    "Captured preprocessed devicetree file: %s", zephyr_dts_pre
                )
            else:
                logger.warning(
                    "Failed to read preprocessed devicetree file %s", zephyr_dts_pre
                )

        # Write combined devicetree information using FileAdapter
        devicetree_output = artifacts_dir / f"{side}_devicetree.txt"
        if devicetree_content:
            combined_content = "".join(devicetree_content)
            try:
                self.file_adapter.write_text(devicetree_output, combined_content)
                logger.info("Saved devicetree information: %s", devicetree_output)
            except Exception as e:
                logger.error(
                    "Failed to save devicetree information %s: %s", devicetree_output, e
                )
        else:
            # No devicetree output found
            try:
                self.file_adapter.write_text(devicetree_output, "No Devicetree output")
                logger.debug("No devicetree files found for %s", side)
            except Exception as e:
                logger.warning(
                    "Failed to write no-devicetree marker %s: %s", devicetree_output, e
                )

    def _capture_build_artifacts(
        self, build_dir: Path, artifacts_dir: Path, side: str
    ) -> None:
        """Capture additional build artifacts and information.

        Captures build logs, configuration files, and other useful artifacts
        from the ZMK build process.

        Args:
            build_dir: ZMK build directory (e.g., build/glove80_lh/zephyr/)
            artifacts_dir: Artifacts output directory
            side: Board side identifier
        """
        # Capture build configuration (.config file)
        config_file = build_dir / ".config"
        if self.file_adapter.check_exists(config_file):
            target_config = artifacts_dir / f"{side}_build.config"
            try:
                self.file_adapter.copy_file(config_file, target_config)
                logger.debug("Captured build config: %s", target_config)
            except Exception as e:
                logger.warning("Failed to capture build config %s: %s", config_file, e)

        # Capture autoconf.h (generated configuration header)
        autoconf_h = build_dir / "include" / "generated" / "autoconf.h"
        if self.file_adapter.check_exists(autoconf_h):
            target_autoconf = artifacts_dir / f"{side}_autoconf.h"
            try:
                self.file_adapter.copy_file(autoconf_h, target_autoconf)
                logger.debug("Captured autoconf.h: %s", target_autoconf)
            except Exception as e:
                logger.warning("Failed to capture autoconf.h %s: %s", autoconf_h, e)

        # Capture devicetree_generated.h
        devicetree_h = build_dir / "include" / "generated" / "devicetree_generated.h"
        if self.file_adapter.check_exists(devicetree_h):
            target_devicetree_h = artifacts_dir / f"{side}_devicetree_generated.h"
            try:
                self.file_adapter.copy_file(devicetree_h, target_devicetree_h)
                logger.debug("Captured devicetree_generated.h: %s", target_devicetree_h)
            except Exception as e:
                logger.warning(
                    "Failed to capture devicetree_generated.h %s: %s", devicetree_h, e
                )

        # Look for additional firmware files (bin, hex, elf)
        additional_files = ["zmk.bin", "zmk.hex", "zmk.elf"]
        for filename in additional_files:
            source_file = build_dir / filename
            if self.file_adapter.check_exists(source_file):
                target_file = artifacts_dir / f"{side}_{filename}"
                try:
                    self.file_adapter.copy_file(source_file, target_file)
                    logger.debug("Captured additional firmware file: %s", target_file)
                except Exception as e:
                    logger.warning(
                        "Failed to capture %s %s: %s", filename, source_file, e
                    )

        logger.info("Captured build artifacts for %s hand", side)

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
    user_context_manager: UserContextManager | None = None,
    docker_adapter: DockerAdapterProtocol | None = None,
    content_generator: ZmkConfigContentGenerator | None = None,
    firmware_scanner: FirmwareScanner | None = None,
    file_adapter: FileAdapterProtocol | None = None,
) -> ZmkConfigCompilationService:
    """Create ZMK config compilation service instance.

    Args:
        workspace_manager: ZMK config workspace manager
        build_matrix_resolver: Build matrix resolver
        artifact_collector: Artifact collector
        environment_manager: Environment manager
        volume_manager: Volume manager
        user_context_manager: User context manager for Docker user mapping
        docker_adapter: Docker adapter
        content_generator: ZMK config content generator
        firmware_scanner: Firmware scanner for enhanced artifact collection
        file_adapter: File operations adapter

    Returns:
        ZmkConfigCompilationService: New service instance
    """
    return ZmkConfigCompilationService(
        workspace_manager=workspace_manager,
        build_matrix_resolver=build_matrix_resolver,
        artifact_collector=artifact_collector,
        environment_manager=environment_manager,
        volume_manager=volume_manager,
        user_context_manager=user_context_manager,
        docker_adapter=docker_adapter,
        content_generator=content_generator,
        firmware_scanner=firmware_scanner,
        file_adapter=file_adapter,
    )
