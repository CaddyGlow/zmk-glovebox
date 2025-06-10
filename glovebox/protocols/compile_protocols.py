"""Protocol definitions for compilation methods."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from glovebox.config.compile_methods import (
    BuildYamlConfig,
    CompileMethodConfig,
    DockerCompileConfig,
    GenericDockerCompileConfig,
    WestWorkspaceConfig,
    ZmkConfigRepoConfig,
)
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


@runtime_checkable
class GenericDockerCompilerProtocol(Protocol):
    """Protocol for generic Docker compiler with build strategies."""

    # Include all methods from DockerCompilerProtocol
    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: GenericDockerCompileConfig,
    ) -> BuildResult:
        """Compile firmware using generic Docker method."""
        ...

    def build_image(self, config: GenericDockerCompileConfig) -> BuildResult:
        """Build Docker image for compilation."""
        ...

    def check_available(self) -> bool:
        """Check if generic Docker compiler is available."""
        ...

    def validate_config(self, config: GenericDockerCompileConfig) -> bool:
        """Validate generic Docker configuration."""
        ...

    # New methods specific to generic Docker compiler
    def initialize_workspace(self, config: GenericDockerCompileConfig) -> bool:
        """Initialize build workspace (west, cmake, etc.)."""
        ...

    def execute_build_strategy(self, strategy: str, commands: list[str]) -> BuildResult:
        """Execute build using specified strategy."""
        ...

    def manage_west_workspace(self, workspace_config: WestWorkspaceConfig) -> bool:
        """Manage ZMK west workspace lifecycle."""
        ...

    def manage_zmk_config_repo(self, config_repo_config: ZmkConfigRepoConfig) -> bool:
        """Manage ZMK config repository workspace lifecycle."""
        ...

    def parse_build_yaml(self, build_yaml_path: Path) -> BuildYamlConfig:
        """Parse build.yaml configuration file."""
        ...

    def cache_workspace(self, workspace_path: Path) -> bool:
        """Cache workspace for reuse."""
        ...


__all__ = [
    "CompilerProtocol",
    "DockerCompilerProtocol",
    "GenericDockerCompilerProtocol",
]
