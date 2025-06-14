"""Base strategy classes and protocols for firmware compilation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from glovebox.config.compile_methods import DockerCompilationConfig
from glovebox.config.profile import KeyboardProfile


@dataclass
class CompilationParams:
    """Compilation parameters from CLI."""

    keymap_file: Path
    kconfig_file: Path
    output_dir: Path  # Always resolved to a default by CLI before reaching strategies
    branch: str | None
    repo: str | None
    jobs: int | None
    verbose: bool | None
    no_cache: bool | None
    docker_uid: int | None
    docker_gid: int | None
    docker_username: str | None
    docker_home: str | None
    docker_container_home: str | None
    no_docker_user_mapping: bool | None
    board_targets: str | None
    preserve_workspace: bool | None
    force_cleanup: bool | None
    clear_cache: bool | None


class CompilationStrategyProtocol(Protocol):
    """Protocol for compilation strategies."""

    @property
    def name(self) -> str:
        """Strategy name."""
        ...

    def supports_profile(self, profile: KeyboardProfile) -> bool:
        """Check if strategy supports the given profile."""
        ...

    def extract_docker_image(self, profile: KeyboardProfile) -> str:
        """Extract Docker image from profile."""
        ...

    def build_config(
        self, params: CompilationParams, profile: KeyboardProfile
    ) -> DockerCompilationConfig:
        """Build compilation configuration."""
        ...

    def get_service_name(self) -> str:
        """Get the compilation service name."""
        ...


class BaseCompilationStrategy(ABC):
    """Base implementation for compilation strategies."""

    def __init__(self, name: str) -> None:
        """Initialize base strategy.

        Args:
            name: Strategy name
        """
        self._name = name

    @property
    def name(self) -> str:
        """Strategy name."""
        return self._name

    @abstractmethod
    def supports_profile(self, profile: KeyboardProfile) -> bool:
        """Check if strategy supports the given profile.

        Args:
            profile: Keyboard profile to check

        Returns:
            bool: True if strategy supports this profile
        """
        ...

    @abstractmethod
    def extract_docker_image(self, profile: KeyboardProfile) -> str:
        """Extract Docker image from profile.

        Args:
            profile: Keyboard profile

        Returns:
            str: Docker image name
        """
        ...

    @abstractmethod
    def build_config(
        self, params: CompilationParams, profile: KeyboardProfile
    ) -> DockerCompilationConfig:
        """Build compilation configuration.

        Args:
            params: Compilation parameters from CLI
            profile: Keyboard profile

        Returns:
            DockerCompilationConfig: Configuration for compilation
        """
        ...

    @abstractmethod
    def get_service_name(self) -> str:
        """Get the compilation service name.

        Returns:
            str: Service name for this strategy
        """
        ...

    def _get_default_docker_image(self, profile: KeyboardProfile) -> str:
        """Get default Docker image for a profile.

        Args:
            profile: Keyboard profile

        Returns:
            str: Default Docker image
        """
        # Standard ZMK image as fallback
        return "zmkfirmware/zmk-build-arm:stable"

    def _validate_params(self, params: CompilationParams) -> None:
        """Validate compilation parameters.

        Args:
            params: Parameters to validate

        Raises:
            ValueError: If parameters are invalid
        """
        if not params.keymap_file.exists():
            raise ValueError(f"Keymap file not found: {params.keymap_file}")

        if not params.kconfig_file.exists():
            raise ValueError(f"Kconfig file not found: {params.kconfig_file}")

        if not params.output_dir.parent.exists():
            raise ValueError(
                f"Output directory parent not found: {params.output_dir.parent}"
            )
