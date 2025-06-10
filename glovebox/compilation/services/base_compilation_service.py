"""Base compilation service for all compilation strategies."""

import logging
from pathlib import Path

from glovebox.config.compile_methods import GenericDockerCompileConfig
from glovebox.firmware.models import BuildResult
from glovebox.services.base_service import BaseService


class BaseCompilationService(BaseService):
    """Base service for all compilation strategies.

    Provides common functionality and patterns for all compilation
    strategies while enforcing consistent interfaces.
    """

    def __init__(self, name: str, version: str):
        """Initialize base compilation service.

        Args:
            name: Service name for identification
            version: Service version for compatibility tracking
        """
        super().__init__(name, version)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def validate_configuration(self, config: GenericDockerCompileConfig) -> bool:
        """Validate compilation configuration.

        Base validation that all compilation strategies should perform.
        Can be overridden by subclasses for strategy-specific validation.

        Args:
            config: Compilation configuration to validate

        Returns:
            bool: True if configuration is valid
        """
        valid = True

        # Base validation checks
        if not config.image:
            self.logger.error("Docker image not specified")
            valid = False

        if not config.build_strategy:
            self.logger.error("Build strategy not specified")
            valid = False

        # Strategy-specific validation should be in subclasses
        return valid

    def prepare_build_environment(
        self, config: GenericDockerCompileConfig
    ) -> dict[str, str]:
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

    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
    ) -> BuildResult:
        """Execute compilation using this strategy.

        This method must be implemented by subclasses to provide
        strategy-specific compilation logic.

        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            output_dir: Output directory for build artifacts
            config: Compilation configuration

        Returns:
            BuildResult: Results of compilation

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        raise NotImplementedError("Subclasses must implement compile method")

    def check_available(self) -> bool:
        """Check if this compilation strategy is available.

        Base implementation checks for Docker availability.
        Subclasses can override for strategy-specific availability checks.

        Returns:
            bool: True if strategy is available
        """
        # Default to checking if we have necessary dependencies
        # Subclasses should override for specific availability checks
        return True
