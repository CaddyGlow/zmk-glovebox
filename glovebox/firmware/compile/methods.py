"""Compiler method implementations."""

import logging
import multiprocessing
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

from glovebox.adapters.docker_adapter import create_docker_adapter
from glovebox.adapters.file_adapter import create_file_adapter
from glovebox.config.compile_methods import (
    DockerCompileConfig,
    GenericDockerCompileConfig,
    WestWorkspaceConfig,
)
from glovebox.core.errors import BuildError
from glovebox.firmware.models import BuildResult, FirmwareOutputFiles
from glovebox.protocols import DockerAdapterProtocol, FileAdapterProtocol
from glovebox.protocols.compile_protocols import (
    CompilerProtocol,
    DockerCompilerProtocol,
    GenericDockerCompilerProtocol,
)
from glovebox.protocols.docker_adapter_protocol import DockerVolume
from glovebox.utils import stream_process


logger = logging.getLogger(__name__)


class DockerCompiler:
    """Docker-based firmware compiler implementation.

    Implements CompilerProtocol for type safety.
    """

    def __init__(
        self,
        docker_adapter: DockerAdapterProtocol | None = None,
        file_adapter: FileAdapterProtocol | None = None,
        output_middleware: stream_process.OutputMiddleware[str] | None = None,
    ):
        """Initialize Docker compiler with dependencies."""
        self.docker_adapter = docker_adapter or create_docker_adapter()
        self.file_adapter = file_adapter or create_file_adapter()
        self.output_middleware = output_middleware or self._create_default_middleware()
        logger.debug("DockerCompiler initialized")

    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: DockerCompileConfig,
    ) -> BuildResult:
        """Compile firmware using Docker method."""
        logger.info("Starting Docker compilation")
        result = BuildResult(success=True)

        try:
            # Check Docker availability
            if not self.check_available():
                result.success = False
                result.add_error("Docker is not available")
                return result

            # Validate input files
            if not self._validate_input_files(keymap_file, config_file, result):
                return result

            # Prepare build environment
            build_env = self._prepare_build_environment(config)

            # Run Docker compilation
            docker_image = f"{config.image}"
            return_code, stdout_lines, stderr_lines = self.docker_adapter.run_container(
                image=docker_image,
                volumes=self._prepare_volumes(keymap_file, config_file, output_dir),
                environment=build_env,
                middleware=self.output_middleware,
            )

            if return_code != 0:
                error_msg = (
                    "\n".join(stderr_lines)
                    if stderr_lines
                    else "Docker compilation failed"
                )
                result.success = False
                result.add_error(
                    f"Compilation failed with exit code {return_code}: {error_msg}"
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
                f"Docker compilation completed. Generated {len(firmware_files)} firmware files."
            )

            for firmware_file in firmware_files:
                result.add_message(f"Firmware file: {firmware_file}")

            logger.info(
                "Docker compilation completed successfully with %d files",
                len(firmware_files),
            )

        except BuildError as e:
            logger.error("Docker compilation failed: %s", e)
            result.success = False
            result.add_error(f"Docker compilation failed: {str(e)}")
        except Exception as e:
            logger.error("Unexpected error in Docker compilation: %s", e)
            result.success = False
            result.add_error(f"Unexpected error: {str(e)}")

        return result

    def check_available(self) -> bool:
        """Check if Docker compiler is available."""
        return self.docker_adapter.is_available()

    def validate_config(self, config: DockerCompileConfig) -> bool:
        """Validate Docker-specific configuration."""
        if not config.image:
            logger.error("Docker image not specified")
            return False
        if not config.repository:
            logger.error("Repository not specified")
            return False
        if not config.branch:
            logger.error("Branch not specified")
            return False
        return True

    def build_image(self, config: DockerCompileConfig) -> BuildResult:
        """Build Docker image for compilation."""
        logger.info("Building Docker image: %s", config.image)
        result = BuildResult(success=True)

        try:
            if not self.check_available():
                result.success = False
                result.add_error("Docker is not available")
                return result

            # For now, assume image building is handled externally
            # This could be extended to build custom images
            result.add_message(f"Docker image {config.image} assumed available")
            logger.info("Docker image build completed: %s", config.image)

        except Exception as e:
            logger.error("Failed to build Docker image: %s", e)
            result.success = False
            result.add_error(f"Failed to build Docker image: {str(e)}")

        return result

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

    def _prepare_build_environment(self, config: DockerCompileConfig) -> dict[str, str]:
        """Prepare build environment variables."""
        build_env = {
            "ZMK_CONFIG": "/zmk-config",
            "REPO": config.repository,
            "BRANCH": config.branch,
            "JOBS": str(
                config.jobs if config.jobs is not None else multiprocessing.cpu_count()
            ),
        }

        logger.debug("Build environment: %s", build_env)
        return build_env

    def _prepare_volumes(
        self, keymap_file: Path, config_file: Path, output_dir: Path
    ) -> list[DockerVolume]:
        """Prepare Docker volume mappings."""
        volumes = []

        # Map output directory
        output_dir_abs = output_dir.absolute()
        volumes.append((str(output_dir_abs), "/build"))

        # Map keymap file to expected location
        keymap_abs = keymap_file.absolute()
        volumes.append((str(keymap_abs), "/build/glove80.keymap:ro"))

        # Map config file to expected location
        config_abs = config_file.absolute()
        volumes.append((str(config_abs), "/build/glove80.conf:ro"))

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

            # Check artifacts directory
            artifacts_dir = output_dir / "artifacts"
            if self.file_adapter.check_exists(
                artifacts_dir
            ) and self.file_adapter.is_dir(artifacts_dir):
                output_files.artifacts_dir = artifacts_dir

                # Get all subdirectories in artifacts
                build_dirs = self.file_adapter.list_directory(artifacts_dir)
                for build_dir in build_dirs:
                    if not self.file_adapter.is_dir(build_dir):
                        continue

                    # Look for glove80.uf2 in the build directory
                    glove_uf2 = build_dir / "glove80.uf2"
                    if self.file_adapter.check_exists(glove_uf2):
                        firmware_files.append(glove_uf2)
                        if not output_files.main_uf2:
                            output_files.main_uf2 = glove_uf2

                    # Check lf and rh subdirectories for zmk.uf2
                    left_side_dir = build_dir / "lf"
                    right_side_dir = build_dir / "rh"

                    # Check left hand
                    if self.file_adapter.check_exists(
                        left_side_dir
                    ) and self.file_adapter.is_dir(left_side_dir):
                        left_uf2 = left_side_dir / "zmk.uf2"
                        if self.file_adapter.check_exists(left_uf2):
                            firmware_files.append(left_uf2)
                            output_files.left_uf2 = left_uf2

                    # Check right hand
                    if self.file_adapter.check_exists(
                        right_side_dir
                    ) and self.file_adapter.is_dir(right_side_dir):
                        right_uf2 = right_side_dir / "zmk.uf2"
                        if self.file_adapter.check_exists(right_uf2):
                            firmware_files.append(right_uf2)
                            output_files.right_uf2 = right_uf2

            logger.debug(
                "Found %d firmware files in %s", len(firmware_files), output_dir
            )

        except Exception as e:
            logger.error("Failed to list firmware files in %s: %s", output_dir, str(e))

        return firmware_files, output_files

    @staticmethod
    def _create_default_middleware() -> stream_process.OutputMiddleware[str]:
        """Create default output middleware for build process."""

        class BuildOutputMiddleware(stream_process.OutputMiddleware[str]):
            def __init__(self) -> None:
                self.collected_data: list[tuple[str, str]] = []

            def process(self, line: str, stream_type: str) -> str:
                # Print with color based on stream type
                if stream_type == "stdout":
                    print(f"\033[92m{line}\033[0m")  # Green for stdout
                else:
                    print(f"\033[91m{line}\033[0m")  # Red for stderr

                # Store additional metadata
                self.collected_data.append((stream_type, line))

                # Return the processed line
                return line

        return BuildOutputMiddleware()


def create_docker_compiler(
    docker_adapter: DockerAdapterProtocol | None = None,
    file_adapter: FileAdapterProtocol | None = None,
    output_middleware: stream_process.OutputMiddleware[str] | None = None,
) -> DockerCompiler:
    """Create a DockerCompiler instance with dependency injection."""
    return DockerCompiler(
        docker_adapter=docker_adapter,
        file_adapter=file_adapter,
        output_middleware=output_middleware,
    )
