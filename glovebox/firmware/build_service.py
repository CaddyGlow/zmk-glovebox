"""Refactored build service using multi-method architecture."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Union


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

from glovebox.config.compile_methods import (
    CompileMethodConfig,
    DockerCompileConfig,
    GenericDockerCompileConfig,
)
from glovebox.core.errors import BuildError
from glovebox.firmware.method_selector import select_compiler_with_fallback
from glovebox.firmware.models import BuildResult
from glovebox.firmware.options import BuildServiceCompileOpts
from glovebox.services.base_service import BaseService


logger = logging.getLogger(__name__)


class BuildService(BaseService):
    """Refactored build service using multi-method architecture.

    This service uses the method selection system to choose appropriate
    compilation methods with automatic fallbacks.
    """

    def __init__(self, loglevel: str = "INFO"):
        """Initialize the build service.

        Args:
            loglevel: Log level for build operations
        """
        super().__init__(service_name="BuildService", service_version="2.0.0")
        self.loglevel = loglevel
        logger.debug("BuildService v2 initialized with log level: %s", loglevel)

    def compile_from_files(
        self,
        keymap_file_path: Path,
        kconfig_file_path: Path,
        output_dir: Path,
        keyboard_profile: Union["KeyboardProfile", None] = None,
        branch: str = "main",
        repo: str = "moergo-sc/zmk",
        jobs: int | None = None,
        verbose: bool = False,
        docker_user_overrides: dict[str, str | int | None] | None = None,
    ) -> BuildResult:
        """Compile firmware from specific files using method selection.

        Args:
            keymap_file_path: Path to the keymap (.keymap) file
            kconfig_file_path: Path to the kconfig (.conf) file
            output_dir: Directory where build artifacts will be stored
            keyboard_profile: KeyboardProfile with build configuration
            branch: Git branch to use for ZMK (default: main)
            repo: Git repository to use for ZMK (default: moergo-sc/zmk)
            jobs: Number of parallel jobs (default: auto-detect)
            verbose: Enable verbose output
            docker_user_overrides: Docker user context manual overrides from CLI

        Returns:
            BuildResult with success status and firmware file paths
        """
        logger.info("Starting firmware build from files")
        result = BuildResult(success=True)

        try:
            # Create build options
            build_opts = BuildServiceCompileOpts(
                keymap_path=keymap_file_path,
                kconfig_path=kconfig_file_path,
                output_dir=output_dir,
                branch=branch,
                repo=repo,
                jobs=jobs,
                verbose=verbose,
                docker_user_overrides=docker_user_overrides,
            )

            # Use the main compile method
            return self.compile(build_opts, keyboard_profile)

        except Exception as e:
            logger.error("Failed to prepare build: %s", e)
            result.success = False
            result.add_error(f"Build preparation failed: {str(e)}")
            return result

    def compile(
        self,
        opts: BuildServiceCompileOpts,
        keyboard_profile: Union["KeyboardProfile", None] = None,
    ) -> BuildResult:
        """Compile firmware using method selection with fallbacks.

        Args:
            opts: Build configuration options
            keyboard_profile: KeyboardProfile with method configurations

        Returns:
            BuildResult with success status and firmware file paths
        """
        logger.info("Starting firmware compilation using method selection")
        result = BuildResult(success=True)

        try:
            # Get compilation method configs from profile or use defaults
            compile_configs = self._get_compile_method_configs(keyboard_profile, opts)

            # Select the best available compiler with fallbacks
            compiler = select_compiler_with_fallback(
                compile_configs,
                # Pass any additional dependencies here
            )

            logger.info("Selected compiler method: %s", type(compiler).__name__)

            # Compile using the selected method
            return compiler.compile(
                keymap_file=opts.keymap_path,
                config_file=opts.kconfig_path,
                output_dir=opts.output_dir,
                config=compile_configs[0],  # Use the primary config
                keyboard_profile=keyboard_profile,
            )

        except Exception as e:
            logger.error("Compilation failed: %s", e)
            result.success = False
            result.add_error(f"Compilation failed: {str(e)}")
            return result

    def _get_compile_method_configs(
        self,
        keyboard_profile: Union["KeyboardProfile", None],
        opts: BuildServiceCompileOpts,
    ) -> list[CompileMethodConfig]:
        """Get compilation method configurations from profile or defaults.

        Args:
            keyboard_profile: KeyboardProfile with method configurations (optional)
            opts: Build options for fallback values

        Returns:
            List of compilation method configurations to try
        """
        if (
            keyboard_profile
            and hasattr(keyboard_profile.keyboard_config, "compile_methods")
            and keyboard_profile.keyboard_config.compile_methods
        ):
            # Use profile's compile method configurations
            return list(keyboard_profile.keyboard_config.compile_methods)

        # Fallback: Create default Docker configuration
        logger.debug("No profile compile methods, using default Docker configuration")

        # Create default Docker compile config from build options
        docker_image = "moergo-zmk-build:latest"
        repository = opts.repo
        branch = opts.branch
        jobs = opts.jobs

        # Create default Docker compile config
        default_config = DockerCompileConfig(
            image=docker_image,
            repository=repository,
            branch=branch,
            jobs=jobs,
        )

        return [default_config]


def create_build_service(loglevel: str = "INFO") -> BuildService:
    """Create a BuildService instance with the multi-method architecture.

    Args:
        loglevel: Log level for build operations

    Returns:
        Configured BuildService instance
    """
    return BuildService(loglevel=loglevel)
