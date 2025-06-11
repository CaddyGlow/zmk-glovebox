"""Protocol definitions for compilation methods."""

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, Union, runtime_checkable

from glovebox.config.compile_methods import (
    CompilationConfig,
    CompileMethodConfig,
    DockerCompileConfig,
)
from glovebox.firmware.models import BuildResult


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile


@runtime_checkable
class CompilerProtocol(Protocol):
    """Generic compiler interface."""

    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: CompileMethodConfig,
        keyboard_profile: Union["KeyboardProfile", None] = None,
    ) -> BuildResult:
        """Compile firmware using this method."""
        ...

    def check_available(self) -> bool:
        """Check if this compiler is available."""
        ...

    def validate_config(self, config: CompileMethodConfig) -> bool:
        """Validate method-specific configuration."""
        ...


@runtime_checkable
class DockerCompilerProtocol(Protocol):
    """Docker-specific compiler interface."""

    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: DockerCompileConfig,  # Type-specific config
    ) -> BuildResult:
        """Compile firmware using Docker."""
        ...

    def build_image(self, config: DockerCompileConfig) -> BuildResult:
        """Build Docker image for compilation."""
        ...

    def validate_config(self, config: DockerCompileConfig) -> bool:
        """Validate Docker-specific configuration."""
        ...


@runtime_checkable
class GenericDockerCompilerProtocol(Protocol):
    """Protocol for generic Docker compiler facade.

    This protocol defines the public interface for the generic Docker compiler
    facade that delegates to the compilation domain.
    """

    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: CompilationConfig,
    ) -> BuildResult:
        """Compile firmware using generic Docker method."""
        ...

    def build_image(self, config: CompilationConfig) -> BuildResult:
        """Build Docker image for compilation."""
        ...

    def check_available(self) -> bool:
        """Check if generic Docker compiler is available."""
        ...

    def validate_config(self, config: CompilationConfig) -> bool:
        """Validate generic Docker configuration."""
        ...

    def get_available_strategies(self) -> list[str]:
        """Get list of available compilation strategies."""
        ...


__all__ = [
    "CompilerProtocol",
    "DockerCompilerProtocol",
    "GenericDockerCompilerProtocol",
]
