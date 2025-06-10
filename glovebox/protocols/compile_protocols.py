"""Protocol definitions for compilation methods."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from glovebox.config.compile_methods import CompileMethodConfig, DockerCompileConfig
from glovebox.firmware.models import BuildResult


@runtime_checkable
class CompilerProtocol(Protocol):
    """Generic compiler interface."""

    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: CompileMethodConfig,
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
