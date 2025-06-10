"""Compilation coordinator service for orchestrating build strategies."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.adapters import create_docker_adapter
from glovebox.compilation.protocols.compilation_protocols import (
    CompilationCoordinatorProtocol,
    CompilationServiceProtocol,
)
from glovebox.compilation.services.base_compilation_service import (
    BaseCompilationService,
)
from glovebox.config.compile_methods import GenericDockerCompileConfig
from glovebox.core.errors import BuildError
from glovebox.firmware.models import BuildResult
from glovebox.protocols import DockerAdapterProtocol


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile


logger = logging.getLogger(__name__)


class CompilationCoordinator(BaseCompilationService):
    """Compilation coordinator for orchestrating different build strategies.

    Manages multiple compilation services and selects the appropriate strategy
    based on the compilation configuration.
    """

    def __init__(
        self,
        compilation_services: dict[str, CompilationServiceProtocol] | None = None,
        docker_adapter: DockerAdapterProtocol | None = None,
    ) -> None:
        """Initialize compilation coordinator.

        Args:
            compilation_services: Dictionary of strategy name to service
            docker_adapter: Docker adapter for container operations
        """
        super().__init__("compilation_coordinator", "1.0.0")
        self.compilation_services = compilation_services or {}
        self.docker_adapter = docker_adapter or create_docker_adapter()

    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
        keyboard_profile: "KeyboardProfile | None" = None,
    ) -> BuildResult:
        """Coordinate compilation using appropriate strategy.

        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            output_dir: Output directory for build artifacts
            config: Compilation configuration
            keyboard_profile: Keyboard profile for dynamic generation

        Returns:
            BuildResult: Results of compilation

        Raises:
            BuildError: If compilation fails or no suitable strategy found
        """
        logger.info("Starting compilation coordination")

        try:
            # Select compilation strategy based on configuration
            strategy_name = self._select_compilation_strategy(config)
            if not strategy_name:
                raise BuildError("No suitable compilation strategy found")

            compilation_service = self.compilation_services.get(strategy_name)
            if not compilation_service:
                raise BuildError(f"Compilation service '{strategy_name}' not available")

            logger.info("Using compilation strategy: %s", strategy_name)

            # Inject Docker adapter into service if it supports it
            self._inject_docker_adapter(compilation_service)

            # Execute compilation using selected strategy
            result = compilation_service.compile(
                keymap_file, config_file, output_dir, config, keyboard_profile
            )

            if result.success:
                logger.info(
                    "Compilation completed successfully using %s", strategy_name
                )
            else:
                logger.error("Compilation failed using %s", strategy_name)

            return result

        except Exception as e:
            msg = f"Compilation coordination failed: {e}"
            logger.error(msg)
            result = BuildResult(success=False)
            result.add_error(msg)
            return result

    def validate_config(self, config: GenericDockerCompileConfig) -> bool:
        """Validate configuration across all strategies.

        Args:
            config: Compilation configuration to validate

        Returns:
            bool: True if configuration is valid for at least one strategy
        """
        # Check if any strategy can handle this configuration
        strategy_name = self._select_compilation_strategy(config)
        if not strategy_name:
            logger.error(
                "No compilation strategy can handle the provided configuration"
            )
            return False

        compilation_service = self.compilation_services.get(strategy_name)
        if not compilation_service:
            logger.error(
                "Selected compilation service '%s' is not available", strategy_name
            )
            return False

        return compilation_service.validate_config(config)

    def check_available(self) -> bool:
        """Check if compilation coordinator is available.

        Returns:
            bool: True if at least one compilation strategy is available
        """
        if not self.docker_adapter.is_available():
            logger.debug("Docker adapter not available")
            return False

        # Check if any compilation service is available
        for service in self.compilation_services.values():
            if service.check_available():
                return True

        logger.debug("No compilation services are available")
        return False

    def get_available_strategies(self) -> list[str]:
        """Get list of available compilation strategies.

        Returns:
            list[str]: List of available strategy names
        """
        available_strategies = []
        for strategy_name, service in self.compilation_services.items():
            if service.check_available():
                available_strategies.append(strategy_name)

        logger.debug("Available compilation strategies: %s", available_strategies)
        return available_strategies

    def add_compilation_service(
        self, strategy_name: str, service: CompilationServiceProtocol
    ) -> None:
        """Add a compilation service for a specific strategy.

        Args:
            strategy_name: Name of the compilation strategy
            service: Compilation service instance
        """
        self.compilation_services[strategy_name] = service
        logger.debug("Added compilation service: %s", strategy_name)

    def _select_compilation_strategy(
        self, config: GenericDockerCompileConfig
    ) -> str | None:
        """Select appropriate compilation strategy based on configuration.

        Args:
            config: Compilation configuration

        Returns:
            str | None: Selected strategy name or None if none suitable
        """
        logger.debug(
            "Selecting compilation strategy for config with build_strategy: %s",
            config.build_strategy,
        )
        logger.debug("Available services: %s", list(self.compilation_services.keys()))

        # Strategy selection priority order
        strategy_priorities = [
            ("zmk_config", self._is_zmk_config_strategy),
            ("west", self._is_west_strategy),
            ("cmake", self._is_cmake_strategy),
        ]

        for strategy_name, strategy_check in strategy_priorities:
            logger.debug("Checking strategy: %s", strategy_name)

            strategy_matches = strategy_check(config)
            logger.debug(
                "  Strategy %s matches config: %s", strategy_name, strategy_matches
            )

            if strategy_matches and strategy_name in self.compilation_services:
                service = self.compilation_services[strategy_name]

                # Inject Docker adapter before checking availability
                self._inject_docker_adapter(service)

                service_available = service.check_available()
                logger.debug(
                    "  Service %s available: %s", strategy_name, service_available
                )

                if service_available:
                    config_valid = service.validate_config(config)
                    logger.debug(
                        "  Config valid for %s: %s", strategy_name, config_valid
                    )

                    if config_valid:
                        logger.debug("Selected compilation strategy: %s", strategy_name)
                        return strategy_name

        logger.warning("No suitable compilation strategy found for configuration")
        return None

    def _is_zmk_config_strategy(self, config: GenericDockerCompileConfig) -> bool:
        """Check if configuration indicates ZMK config strategy.

        Args:
            config: Compilation configuration

        Returns:
            bool: True if ZMK config strategy should be used
        """
        # ZMK config strategy if zmk_config_repo is configured
        # OR if build_strategy explicitly requests "zmk_config"
        return bool(config.zmk_config_repo) or config.build_strategy == "zmk_config"

    def _is_west_strategy(self, config: GenericDockerCompileConfig) -> bool:
        """Check if configuration indicates west strategy.

        Args:
            config: Compilation configuration

        Returns:
            bool: True if west strategy should be used
        """
        return bool(config.west_workspace)

    def _is_cmake_strategy(self, config: GenericDockerCompileConfig) -> bool:
        """Check if configuration indicates cmake strategy.

        Args:
            config: Compilation configuration

        Returns:
            bool: True if cmake strategy should be used
        """
        # Default fallback strategy
        return True

    def _inject_docker_adapter(self, service: CompilationServiceProtocol) -> None:
        """Inject Docker adapter into compilation service if supported.

        Args:
            service: Compilation service to inject adapter into
        """
        if hasattr(service, "set_docker_adapter"):
            service.set_docker_adapter(self.docker_adapter)
            logger.debug("Injected Docker adapter into compilation service")


def create_compilation_coordinator(
    compilation_services: dict[str, CompilationServiceProtocol] | None = None,
    docker_adapter: DockerAdapterProtocol | None = None,
) -> CompilationCoordinator:
    """Create compilation coordinator instance.

    Args:
        compilation_services: Dictionary of strategy name to service
        docker_adapter: Docker adapter for container operations

    Returns:
        CompilationCoordinator: New compilation coordinator instance
    """
    return CompilationCoordinator(compilation_services, docker_adapter)
