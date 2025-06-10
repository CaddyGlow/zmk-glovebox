"""Generic Docker compiler with pluggable build strategies."""

import logging
import multiprocessing
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

from glovebox.adapters.docker_adapter import create_docker_adapter
from glovebox.adapters.file_adapter import create_file_adapter
from glovebox.config.compile_methods import (
    GenericDockerCompileConfig,
    WestWorkspaceConfig,
)
from glovebox.core.errors import BuildError
from glovebox.firmware.models import BuildResult, FirmwareOutputFiles
from glovebox.protocols import DockerAdapterProtocol, FileAdapterProtocol
from glovebox.protocols.compile_protocols import GenericDockerCompilerProtocol
from glovebox.protocols.docker_adapter_protocol import DockerVolume
from glovebox.utils import stream_process


logger = logging.getLogger(__name__)


class GenericDockerCompiler:
    """Generic Docker compiler with pluggable build strategies.

    Implements GenericDockerCompilerProtocol for type safety.
    """

    def __init__(
        self,
        docker_adapter: DockerAdapterProtocol | None = None,
        file_adapter: FileAdapterProtocol | None = None,
        output_middleware: stream_process.OutputMiddleware[str] | None = None,
    ):
        """Initialize generic Docker compiler with dependencies."""
        self.docker_adapter = docker_adapter or create_docker_adapter()
        self.file_adapter = file_adapter or create_file_adapter()
        self.output_middleware = output_middleware or self._create_default_middleware()
        logger.debug("GenericDockerCompiler initialized")

    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
    ) -> BuildResult:
        """Compile firmware using generic Docker method with build strategies."""
        logger.info(
            "Starting generic Docker compilation with strategy: %s",
            config.build_strategy,
        )
        result = BuildResult(success=True)

        try:
            # Check Docker availability
            if not self.check_available():
                result.success = False
                result.add_error("Docker is not available")
                return result

            # Validate input files and configuration
            if not self._validate_input_files(keymap_file, config_file, result):
                return result

            if not self.validate_config(config):
                result.success = False
                result.add_error("Configuration validation failed")
                return result

            # Execute build strategy
            if config.build_strategy == "west":
                return self._execute_west_strategy(
                    keymap_file, config_file, output_dir, config
                )
            elif config.build_strategy == "cmake":
                return self._execute_cmake_strategy(
                    keymap_file, config_file, output_dir, config
                )
            else:
                result.success = False
                result.add_error(f"Unsupported build strategy: {config.build_strategy}")
                return result

        except BuildError as e:
            logger.error("Generic Docker compilation failed: %s", e)
            result.success = False
            result.add_error(f"Generic Docker compilation failed: {str(e)}")
        except Exception as e:
            logger.error("Unexpected error in generic Docker compilation: %s", e)
            result.success = False
            result.add_error(f"Unexpected error: {str(e)}")

        return result

    def check_available(self) -> bool:
        """Check if generic Docker compiler is available."""
        return self.docker_adapter.is_available()

    def validate_config(self, config: GenericDockerCompileConfig) -> bool:
        """Validate generic Docker configuration."""
        if not config.image:
            logger.error("Docker image not specified")
            return False
        if not config.build_strategy:
            logger.error("Build strategy not specified")
            return False
        if config.build_strategy not in ["west", "cmake", "make", "ninja", "custom"]:
            logger.error("Invalid build strategy: %s", config.build_strategy)
            return False
        return True

    def build_image(self, config: GenericDockerCompileConfig) -> BuildResult:
        """Build Docker image for compilation."""
        logger.info("Building Docker image for generic compiler: %s", config.image)
        result = BuildResult(success=True)

        try:
            if not self.check_available():
                result.success = False
                result.add_error("Docker is not available")
                return result

            # For now, assume image building is handled externally
            # This could be extended to build custom images
            result.add_message(f"Docker image {config.image} assumed available")
            logger.info(
                "Docker image build completed for generic compiler: %s", config.image
            )

        except Exception as e:
            logger.error("Failed to build Docker image for generic compiler: %s", e)
            result.success = False
            result.add_error(f"Failed to build Docker image: {str(e)}")

        return result

    def initialize_workspace(self, config: GenericDockerCompileConfig) -> bool:
        """Initialize build workspace (west, cmake, etc.)."""
        logger.debug("Initializing workspace for strategy: %s", config.build_strategy)

        if config.build_strategy == "west" and config.west_workspace:
            return self.manage_west_workspace(config.west_workspace)

        # For other strategies, initialization is handled in strategy execution
        return True

    def execute_build_strategy(self, strategy: str, commands: list[str]) -> BuildResult:
        """Execute build using specified strategy."""
        logger.info("Executing build strategy: %s", strategy)
        result = BuildResult(success=True)

        # This is a generic method that can be called by specific strategy implementations
        # For now, it's a placeholder for custom command execution
        try:
            for command in commands:
                logger.debug("Executing command: %s", command)
                # Commands would be executed in the Docker context

        except Exception as e:
            logger.error("Build strategy execution failed: %s", e)
            result.success = False
            result.add_error(f"Build strategy execution failed: {str(e)}")

        return result

    def manage_west_workspace(self, workspace_config: WestWorkspaceConfig) -> bool:
        """Manage ZMK west workspace lifecycle."""
        logger.debug("Managing west workspace: %s", workspace_config.workspace_path)

        try:
            # Execute west commands inside Docker container
            for command in workspace_config.west_commands:
                logger.debug("Executing west command: %s", command)

                # Build command environment
                env = {
                    "WEST_WORKSPACE": workspace_config.workspace_path,
                    "MANIFEST_URL": workspace_config.manifest_url,
                    "MANIFEST_REVISION": workspace_config.manifest_revision,
                }

                # Prepare volumes for west workspace
                volumes = [
                    (workspace_config.workspace_path, workspace_config.workspace_path),
                ]

                # Execute west command in Docker container
                return_code, stdout_lines, stderr_lines = (
                    self.docker_adapter.run_container(
                        image="zmkfirmware/zmk-build-arm:stable",  # Default ZMK image
                        command=["sh", "-c", command],
                        volumes=volumes,
                        environment=env,
                        middleware=self.output_middleware,
                    )
                )

                if return_code != 0:
                    error_msg = (
                        "\\n".join(stderr_lines)
                        if stderr_lines
                        else f"Command failed: {command}"
                    )
                    logger.error("West command failed: %s", error_msg)
                    return False

            logger.info(
                "West workspace initialized successfully: %s",
                workspace_config.manifest_url,
            )
            return True

        except Exception as e:
            logger.error("Failed to manage west workspace: %s", e)
            return False

    def cache_workspace(self, workspace_path: Path) -> bool:
        """Cache workspace for reuse."""
        logger.debug("Caching workspace: %s", workspace_path)

        try:
            # Create cache directory if it doesn't exist
            cache_dir = workspace_path.parent / ".glovebox_cache"
            if not self.file_adapter.check_exists(cache_dir):
                self.file_adapter.create_directory(cache_dir)
                logger.debug("Created cache directory: %s", cache_dir)

            # Create workspace metadata for cache validation
            workspace_metadata = {
                "workspace_path": str(workspace_path),
                "cached_at": str(Path.cwd()),
                "west_modules": self._get_west_modules(workspace_path),
            }

            # Write metadata to cache
            metadata_file = cache_dir / f"{workspace_path.name}_metadata.json"
            import json

            metadata_json = json.dumps(workspace_metadata, indent=2)
            self.file_adapter.write_text(metadata_file, metadata_json)

            logger.info("Workspace cached successfully: %s", workspace_path)
            return True

        except Exception as e:
            logger.error("Failed to cache workspace: %s", e)
            return False

    def _get_west_modules(self, workspace_path: Path) -> list[str]:
        """Get list of west modules in workspace."""
        try:
            west_config = workspace_path / ".west" / "config"
            if self.file_adapter.check_exists(west_config):
                # Parse west config to get module information
                config_content = self.file_adapter.read_text(west_config)
                logger.debug(
                    "Found west config with %d characters", len(config_content)
                )
                # Simple module detection - could be enhanced
                return ["zmk"]  # Default module
            return []
        except Exception as e:
            logger.debug("Could not read west modules: %s", e)
            return []

    def _execute_west_strategy(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
    ) -> BuildResult:
        """Execute ZMK west workspace build strategy."""
        logger.info("Executing west build strategy")
        result = BuildResult(success=True)

        try:
            # Initialize west workspace if configured
            if config.west_workspace and not self._initialize_west_workspace(
                config.west_workspace, keymap_file, config_file
            ):
                result.success = False
                result.add_error("Failed to initialize west workspace")
                return result

            # Prepare build environment for west
            build_env = self._prepare_west_environment(config)

            # Prepare volumes for west workspace
            volumes = self._prepare_west_volumes(
                keymap_file, config_file, output_dir, config
            )

            # Build west compilation command
            if config.board_targets:
                # Build for specific board targets
                build_commands = []
                for board in config.board_targets:
                    build_commands.append(
                        f"west build -p always -b {board} -d build/{board}"
                    )
                west_command = " && ".join(build_commands)
            else:
                # Default build command
                west_command = "west build -p always"

            # Add any custom build commands
            if config.build_commands:
                west_command = " && ".join([west_command] + config.build_commands)

            # Run Docker compilation with west commands
            docker_image = f"{config.image}"
            return_code, stdout_lines, stderr_lines = self.docker_adapter.run_container(
                image=docker_image,
                command=[
                    "sh",
                    "-c",
                    f"cd {config.west_workspace.workspace_path if config.west_workspace else '/zmk-workspace'} && {west_command}",
                ],
                volumes=volumes,
                environment=build_env,
                middleware=self.output_middleware,
            )

            if return_code != 0:
                error_msg = (
                    "\\n".join(stderr_lines)
                    if stderr_lines
                    else "West compilation failed"
                )
                result.success = False
                result.add_error(
                    f"West compilation failed with exit code {return_code}: {error_msg}"
                )
                return result

            # Find and collect firmware files
            firmware_files, output_files = self._find_firmware_files(output_dir)

            if not firmware_files:
                result.success = False
                result.add_error("No firmware files generated")
                return result

            # Store results
            result.output_files = output_files
            result.add_message(
                f"West compilation completed. Generated {len(firmware_files)} firmware files."
            )

            for firmware_file in firmware_files:
                result.add_message(f"Firmware file: {firmware_file}")

            logger.info(
                "West compilation completed successfully with %d files",
                len(firmware_files),
            )

        except Exception as e:
            logger.error("West strategy execution failed: %s", e)
            result.success = False
            result.add_error(f"West strategy execution failed: {str(e)}")

        return result

    def _execute_cmake_strategy(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
    ) -> BuildResult:
        """Execute CMake build strategy."""
        logger.info("Executing CMake build strategy")
        result = BuildResult(success=True)

        try:
            # Prepare build environment for CMake
            build_env = self._prepare_cmake_environment(config)

            # Prepare volumes for CMake build
            volumes = self._prepare_cmake_volumes(keymap_file, config_file, output_dir)

            # Run Docker compilation with CMake commands
            docker_image = f"{config.image}"
            return_code, stdout_lines, stderr_lines = self.docker_adapter.run_container(
                image=docker_image,
                volumes=volumes,
                environment=build_env,
                middleware=self.output_middleware,
            )

            if return_code != 0:
                error_msg = (
                    "\\n".join(stderr_lines)
                    if stderr_lines
                    else "CMake compilation failed"
                )
                result.success = False
                result.add_error(
                    f"CMake compilation failed with exit code {return_code}: {error_msg}"
                )
                return result

            # Find and collect firmware files
            firmware_files, output_files = self._find_firmware_files(output_dir)

            if not firmware_files:
                result.success = False
                result.add_error("No firmware files generated")
                return result

            # Store results
            result.output_files = output_files
            result.add_message(
                f"CMake compilation completed. Generated {len(firmware_files)} firmware files."
            )

            logger.info(
                "CMake compilation completed successfully with %d files",
                len(firmware_files),
            )

        except Exception as e:
            logger.error("CMake strategy execution failed: %s", e)
            result.success = False
            result.add_error(f"CMake strategy execution failed: {str(e)}")

        return result

    def _initialize_west_workspace(
        self,
        workspace_config: WestWorkspaceConfig,
        keymap_file: Path,
        config_file: Path,
    ) -> bool:
        """Initialize ZMK west workspace in Docker container."""
        logger.debug("Initializing west workspace")

        try:
            # Create workspace directory if it doesn't exist
            workspace_path = Path(workspace_config.workspace_path)
            if not self.file_adapter.check_exists(workspace_path):
                self.file_adapter.create_directory(workspace_path)
                logger.debug("Created workspace directory: %s", workspace_path)

            # Create config directory inside workspace
            config_dir = workspace_path / workspace_config.config_path
            if not self.file_adapter.check_exists(config_dir):
                self.file_adapter.create_directory(config_dir)
                logger.debug("Created config directory: %s", config_dir)

            # Copy keymap and config files to workspace
            try:
                workspace_keymap = config_dir / "keymap.keymap"
                workspace_config_file = config_dir / "config.conf"

                # Use file adapter to copy files
                keymap_content = self.file_adapter.read_text(keymap_file)
                config_content = self.file_adapter.read_text(config_file)

                self.file_adapter.write_text(workspace_keymap, keymap_content)
                self.file_adapter.write_text(workspace_config_file, config_content)

                logger.debug("Copied files to workspace config directory")

            except Exception as e:
                logger.warning("Failed to copy files to workspace: %s", e)
                # Continue with initialization even if file copy fails

            # Initialize west workspace using Docker
            init_commands = [
                f"cd {workspace_config.workspace_path}",
                f"west init -m {workspace_config.manifest_url} --mr {workspace_config.manifest_revision}",
                "west update",
            ]

            # Add any additional west commands from config
            init_commands.extend(workspace_config.west_commands)

            # Execute initialization commands
            full_command = " && ".join(init_commands)

            env = {
                "WEST_WORKSPACE": workspace_config.workspace_path,
                "MANIFEST_URL": workspace_config.manifest_url,
                "MANIFEST_REVISION": workspace_config.manifest_revision,
            }

            volumes = [
                (str(workspace_path.absolute()), workspace_config.workspace_path),
            ]

            return_code, stdout_lines, stderr_lines = self.docker_adapter.run_container(
                image="zmkfirmware/zmk-build-arm:stable",
                command=["sh", "-c", full_command],
                volumes=volumes,
                environment=env,
                middleware=self.output_middleware,
            )

            if return_code != 0:
                error_msg = (
                    "\\n".join(stderr_lines)
                    if stderr_lines
                    else "West initialization failed"
                )
                logger.error("West workspace initialization failed: %s", error_msg)
                return False

            logger.info("West workspace initialized successfully")
            return True

        except Exception as e:
            logger.error("Failed to initialize west workspace: %s", e)
            return False

    def _prepare_west_environment(
        self, config: GenericDockerCompileConfig
    ) -> dict[str, str]:
        """Prepare build environment variables for west strategy."""
        build_env = {}

        # Start with any custom environment template
        build_env.update(config.environment_template)

        # Add west-specific environment
        if config.west_workspace:
            build_env.update(
                {
                    "WEST_WORKSPACE": config.west_workspace.workspace_path,
                    "ZMK_CONFIG": f"{config.west_workspace.workspace_path}/{config.west_workspace.config_path}",
                }
            )

        # Add any additional environment variables
        build_env.setdefault("JOBS", str(multiprocessing.cpu_count()))

        logger.debug("West build environment: %s", build_env)
        return build_env

    def _prepare_cmake_environment(
        self, config: GenericDockerCompileConfig
    ) -> dict[str, str]:
        """Prepare build environment variables for CMake strategy."""
        build_env = {}

        # Start with any custom environment template
        build_env.update(config.environment_template)

        # Add CMake-specific environment
        build_env.update(
            {
                "CMAKE_BUILD_TYPE": "Release",
                "JOBS": str(multiprocessing.cpu_count()),
            }
        )

        logger.debug("CMake build environment: %s", build_env)
        return build_env

    def _prepare_west_volumes(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
    ) -> list[DockerVolume]:
        """Prepare Docker volume mappings for west strategy."""
        volumes = []

        # Map output directory
        output_dir_abs = output_dir.absolute()
        volumes.append((str(output_dir_abs), "/build"))

        # Use volume templates if provided, otherwise use defaults
        if config.volume_templates:
            # Apply volume templates (this would be expanded based on templates)
            for template in config.volume_templates:
                logger.debug("Applying volume template: %s", template)
        else:
            # Default west workspace volume mapping
            if config.west_workspace:
                # Map files to west workspace config directory
                keymap_abs = keymap_file.absolute()
                config_abs = config_file.absolute()
                workspace_path = config.west_workspace.workspace_path
                config_path = config.west_workspace.config_path

                volumes.append(
                    (
                        str(keymap_abs),
                        f"{workspace_path}/{config_path}/keymap.keymap:ro",
                    )
                )
                volumes.append(
                    (str(config_abs), f"{workspace_path}/{config_path}/config.conf:ro")
                )

        return volumes

    def _prepare_cmake_volumes(
        self, keymap_file: Path, config_file: Path, output_dir: Path
    ) -> list[DockerVolume]:
        """Prepare Docker volume mappings for CMake strategy."""
        volumes = []

        # Map output directory
        output_dir_abs = output_dir.absolute()
        volumes.append((str(output_dir_abs), "/build"))

        # Map keymap and config files
        keymap_abs = keymap_file.absolute()
        config_abs = config_file.absolute()
        volumes.append((str(keymap_abs), "/build/keymap.keymap:ro"))
        volumes.append((str(config_abs), "/build/config.conf:ro"))

        return volumes

    def _find_firmware_files(
        self, output_dir: Path
    ) -> tuple[list[Path], FirmwareOutputFiles]:
        """Find firmware files in output directory."""
        firmware_files = []
        output_files = FirmwareOutputFiles(output_dir=output_dir)

        try:
            # Check if output directory exists
            if not self.file_adapter.check_exists(output_dir):
                logger.warning("Output directory does not exist: %s", output_dir)
                return [], output_files

            # Look for .uf2 files in the base output directory
            files = self.file_adapter.list_files(output_dir, "*.uf2")
            firmware_files.extend(files)

            # The first .uf2 file found is considered the main firmware
            if files and not output_files.main_uf2:
                output_files.main_uf2 = files[0]

            # Check west build output directories
            build_dir = output_dir / "build"
            if self.file_adapter.check_exists(build_dir) and self.file_adapter.is_dir(
                build_dir
            ):
                logger.debug("Checking west build directory: %s", build_dir)

                # Check for board-specific build directories
                build_subdirs = self.file_adapter.list_directory(build_dir)
                for subdir in build_subdirs:
                    if self.file_adapter.is_dir(subdir):
                        # Look for zephyr/zmk.uf2 in build directories
                        zephyr_dir = subdir / "zephyr"
                        if self.file_adapter.check_exists(zephyr_dir):
                            zmk_uf2 = zephyr_dir / "zmk.uf2"
                            if self.file_adapter.check_exists(zmk_uf2):
                                firmware_files.append(zmk_uf2)
                                if not output_files.main_uf2:
                                    output_files.main_uf2 = zmk_uf2
                                logger.debug("Found west build firmware: %s", zmk_uf2)

            # Check for subdirectories with firmware files (legacy support)
            subdirs = self.file_adapter.list_directory(output_dir)
            for subdir in subdirs:
                if self.file_adapter.is_dir(subdir) and subdir.name != "build":
                    subdir_files = self.file_adapter.list_files(subdir, "*.uf2")
                    firmware_files.extend(subdir_files)

            logger.debug(
                "Found %d firmware files in %s", len(firmware_files), output_dir
            )

        except Exception as e:
            logger.error("Failed to list firmware files in %s: %s", output_dir, str(e))

        return firmware_files, output_files

    def _validate_input_files(
        self, keymap_file: Path, config_file: Path, result: BuildResult
    ) -> bool:
        """Validate input files exist."""
        if not self.file_adapter.check_exists(
            keymap_file
        ) or not self.file_adapter.is_file(keymap_file):
            result.success = False
            result.add_error(f"Keymap file not found: {keymap_file}")
            return False

        if not self.file_adapter.check_exists(
            config_file
        ) or not self.file_adapter.is_file(config_file):
            result.success = False
            result.add_error(f"Config file not found: {config_file}")
            return False

        return True

    @staticmethod
    def _create_default_middleware() -> stream_process.OutputMiddleware[str]:
        """Create default output middleware for build process."""

        class BuildOutputMiddleware(stream_process.OutputMiddleware[str]):
            def __init__(self) -> None:
                self.collected_data: list[tuple[str, str]] = []

            def process(self, line: str, stream_type: str) -> str:
                # Print with color based on stream type
                if stream_type == "stdout":
                    print(f"\\033[92m{line}\\033[0m")  # Green for stdout
                else:
                    print(f"\\033[91m{line}\\033[0m")  # Red for stderr

                # Store additional metadata
                self.collected_data.append((stream_type, line))

                # Return the processed line
                return line

        return BuildOutputMiddleware()


def create_generic_docker_compiler(
    docker_adapter: DockerAdapterProtocol | None = None,
    file_adapter: FileAdapterProtocol | None = None,
    output_middleware: stream_process.OutputMiddleware[str] | None = None,
) -> GenericDockerCompiler:
    """Create a GenericDockerCompiler instance with dependency injection."""
    return GenericDockerCompiler(
        docker_adapter=docker_adapter,
        file_adapter=file_adapter,
        output_middleware=output_middleware,
    )
