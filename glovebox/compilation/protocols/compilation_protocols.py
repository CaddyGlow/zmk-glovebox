"""Compilation service protocols."""

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from glovebox.config.compile_methods import CompilationConfig
from glovebox.firmware.models import BuildResult


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile


@runtime_checkable
class CompilationServiceProtocol(Protocol):
    """Protocol for compilation strategy services."""

    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: CompilationConfig,
        keyboard_profile: "KeyboardProfile | None" = None,
    ) -> BuildResult:
        """Execute compilation using this strategy.

        Args:
            keymap_file: Path to keymap file
            config_file: Path to config file
            output_dir: Output directory for build artifacts
            config: Compilation configuration
            keyboard_profile: Keyboard profile for dynamic generation

        Returns:
            BuildResult: Results of compilation
        """
        ...

    def validate_config(self, config: CompilationConfig) -> bool:
        """Validate configuration for this compilation strategy.

        Args:
            config: Compilation configuration to validate

        Returns:
            bool: True if configuration is valid
        """
        ...

    def check_available(self) -> bool:
        """Check if this compilation strategy is available.

        Returns:
            bool: True if strategy is available
        """
        ...


@runtime_checkable
class CompilationCoordinatorProtocol(Protocol):
    """Protocol for compilation coordination service."""

    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: CompilationConfig,
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
        """
        ...

    def validate_config(self, config: CompilationConfig) -> bool:
        """Validate configuration across all strategies.

        Args:
            config: Compilation configuration to validate

        Returns:
            bool: True if configuration is valid
        """
        ...

    def get_available_strategies(self) -> list[str]:
        """Get list of available compilation strategies.

        Returns:
            list[str]: List of available strategy names
        """
        ...
