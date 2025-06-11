"""Simplified build service using direct compilation domain services."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Union


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

from glovebox.compilation import create_west_service, create_zmk_config_service
from glovebox.config.compile_methods import GenericDockerCompileConfig
from glovebox.core.errors import BuildError
from glovebox.firmware.models import BuildResult
from glovebox.services.base_service import BaseService


logger = logging.getLogger(__name__)


class BuildService(BaseService):
    """Simplified build service using compilation domain services.

    This service directly uses compilation domain services, eliminating
    the complex method selection and fallback logic.
    """

    def __init__(self, loglevel: str = "INFO"):
        """Initialize the build service.

        Args:
            loglevel: Log level for build operations
        """
        super().__init__(service_name="BuildService", service_version="3.0.0")
        self.loglevel = loglevel
        logger.debug("BuildService v3 initialized with log level: %s", loglevel)

    def compile_firmware(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
        keyboard_profile: Union["KeyboardProfile", None] = None,
        strategy: str = "zmk_config",
    ) -> BuildResult:
        """Compile firmware using specified strategy.

        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            output_dir: Output directory for build artifacts
            config: Compilation configuration
            keyboard_profile: Keyboard profile for dynamic generation
            strategy: Compilation strategy ("zmk_config" or "west")

        Returns:
            BuildResult: Results of compilation

        Raises:
            BuildError: If compilation fails
        """
        logger.info("Starting firmware compilation with %s strategy", strategy)

        try:
            # Create appropriate compilation service based on strategy
            if strategy == "zmk_config":
                service = create_zmk_config_service()
            elif strategy == "west":
                service = create_west_service()
            else:
                raise BuildError(f"Unknown compilation strategy: {strategy}")

            # Execute compilation
            result = service.compile(
                keymap_file=keymap_file,
                config_file=config_file,
                output_dir=output_dir,
                config=config,
                keyboard_profile=keyboard_profile,
            )

            if result.success:
                logger.info("Firmware compilation completed successfully")
            else:
                logger.error("Firmware compilation failed")

            return result

        except Exception as e:
            logger.error("Build service compilation failed: %s", e)
            result = BuildResult(success=False)
            result.add_error(f"Build service error: {e}")
            return result


def create_build_service() -> BuildService:
    """Create build service instance.

    Returns:
        BuildService: Configured build service
    """
    return BuildService()
