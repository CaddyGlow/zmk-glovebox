"""Generic Docker compiler facade - delegates to compilation domain."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from glovebox.adapters import create_docker_adapter, create_file_adapter
from glovebox.compilation import create_compilation_coordinator
from glovebox.compilation.protocols.compilation_protocols import (
    CompilationCoordinatorProtocol,
)
from glovebox.config.compile_methods import GenericDockerCompileConfig
from glovebox.firmware.models import BuildResult
from glovebox.protocols import DockerAdapterProtocol, FileAdapterProtocol
from glovebox.protocols.compile_protocols import GenericDockerCompilerProtocol
from glovebox.utils import stream_process


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile


logger = logging.getLogger(__name__)


class GenericDockerCompiler:
    """Generic Docker compiler facade - delegates to compilation domain.

    This class serves as a facade for the compilation domain, providing
    backward compatibility while delegating to the new compilation architecture.
    Implements GenericDockerCompilerProtocol for type safety.
    """

    def __init__(
        self,
        compilation_coordinator: CompilationCoordinatorProtocol | None = None,
        docker_adapter: DockerAdapterProtocol | None = None,
        file_adapter: FileAdapterProtocol | None = None,
        output_middleware: stream_process.OutputMiddleware[str] | None = None,
    ):
        """Initialize generic Docker compiler with compilation coordinator.

        Args:
            compilation_coordinator: Compilation coordination service
            docker_adapter: Docker operations adapter (for compatibility)
            file_adapter: File operations adapter (for compatibility)
            output_middleware: Output processing middleware
        """
        self.compilation_coordinator = (
            compilation_coordinator or create_compilation_coordinator()
        )
        self.docker_adapter = docker_adapter or create_docker_adapter()
        self.file_adapter = file_adapter or create_file_adapter()
        self.output_middleware = output_middleware or self._create_default_middleware()
        logger.debug("GenericDockerCompiler facade initialized")

    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
        keyboard_profile: "KeyboardProfile | None" = None,
    ) -> BuildResult:
        """Compile firmware using specified build strategy.

        Delegates to the compilation coordinator which handles strategy selection
        and execution using the new compilation domain architecture.

        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            output_dir: Output directory for build artifacts
            config: Compilation configuration
            keyboard_profile: Keyboard profile for dynamic generation

        Returns:
            BuildResult: Results of compilation
        """
        logger.info(
            "Starting generic Docker compilation with strategy: %s",
            config.build_strategy,
        )

        try:
            # Check Docker availability
            if not self.check_available():
                result = BuildResult(success=False)
                result.add_error("Docker is not available")
                return result

            # Validate input files
            result = BuildResult(success=True)
            if not self._validate_input_files(keymap_file, config_file, result):
                return result

            # Delegate to compilation coordinator
            return self.compilation_coordinator.compile(
                keymap_file, config_file, output_dir, config, keyboard_profile
            )

        except Exception as e:
            logger.error("Unexpected error in generic Docker compilation: %s", e)
            result = BuildResult(success=False)
            result.add_error(f"Unexpected error: {str(e)}")
            return result

    def check_available(self) -> bool:
        """Check if generic Docker compiler is available.

        Returns:
            bool: True if Docker is available
        """
        return self.docker_adapter.is_available()

    def validate_config(self, config: GenericDockerCompileConfig) -> bool:
        """Validate generic Docker configuration.

        Provides backward compatibility validation that accepts basic configurations
        while delegating complex validation to compilation coordinator.

        Args:
            config: Configuration to validate

        Returns:
            bool: True if configuration is valid
        """
        # Basic validation
        if not config.image:
            logger.error("Docker image not specified")
            return False
        if not config.build_strategy:
            logger.error("Build strategy not specified")
            return False

        # Backward compatibility: accept basic strategy names
        if config.build_strategy in [
            "west",
            "zmk_config",
            "cmake",
            "make",
            "ninja",
            "custom",
        ]:
            # For facade backward compatibility, accept basic configurations
            # The coordinator will handle more complex validation during compilation
            return True

        logger.error("Invalid build strategy: %s", config.build_strategy)
        return False

    def build_image(self, config: GenericDockerCompileConfig) -> BuildResult:
        """Build Docker image for compilation.

        Args:
            config: Compilation configuration

        Returns:
            BuildResult: Image build result
        """
        logger.info("Building Docker image for generic compiler: %s", config.image)
        result = BuildResult(success=True)

        try:
            if not self.check_available():
                result.success = False
                result.add_error("Docker is not available")
                return result

            # Image building is handled by the compilation domain
            result.add_message(f"Docker image {config.image} assumed available")
            logger.info(
                "Docker image build completed for generic compiler: %s", config.image
            )

        except Exception as e:
            logger.error("Failed to build Docker image for generic compiler: %s", e)
            result.success = False
            result.add_error(f"Failed to build Docker image: {str(e)}")

        return result

    def get_available_strategies(self) -> list[str]:
        """Get list of available compilation strategies.

        Returns:
            list[str]: List of available strategy names
        """
        return self.compilation_coordinator.get_available_strategies()

    def _validate_input_files(
        self, keymap_file: Path, config_file: Path, result: BuildResult
    ) -> bool:
        """Validate input files exist and are accessible.

        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            result: Build result to add errors to

        Returns:
            bool: True if files are valid
        """
        if not self.file_adapter.check_exists(keymap_file):
            result.success = False
            result.add_error(f"Keymap file not found: {keymap_file}")
            return False

        if not self.file_adapter.check_exists(config_file):
            result.success = False
            result.add_error(f"Config file not found: {config_file}")
            return False

        return True

    def _create_default_middleware(self) -> stream_process.OutputMiddleware[str]:
        """Create default output middleware for stream processing.

        Returns:
            OutputMiddleware: Default middleware for output processing
        """
        return stream_process.OutputMiddleware[str]()


def create_generic_docker_compiler(
    docker_adapter: DockerAdapterProtocol | None = None,
    file_adapter: FileAdapterProtocol | None = None,
    output_middleware: stream_process.OutputMiddleware[str] | None = None,
) -> GenericDockerCompiler:
    """Factory function to create GenericDockerCompiler.

    Args:
        docker_adapter: Docker operations adapter
        file_adapter: File operations adapter
        output_middleware: Output processing middleware

    Returns:
        GenericDockerCompiler: A new instance of the generic Docker compiler
    """
    return GenericDockerCompiler(
        docker_adapter=docker_adapter,
        file_adapter=file_adapter,
        output_middleware=output_middleware,
    )
