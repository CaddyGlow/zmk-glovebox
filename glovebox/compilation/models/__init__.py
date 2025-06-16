"""Compilation-specific models for build configuration and metadata."""

from glovebox.compilation.models.build_matrix import (
    BuildMatrix,
    BuildTarget,
)
from glovebox.compilation.models.compilation_config import (
    CacheConfig,
    CompilationConfig,
    CompilationConfigUnion,
    DockerUserConfig,
    MoergoCompilationConfig,
    ZmkCompilationConfig,
    ZmkWorkspaceConfig,
)
from glovebox.compilation.models.west_config import (
    WestCommandsConfig,
    WestDefaults,
    WestManifest,
    WestManifestConfig,
    WestProject,
    WestRemote,
    WestSelf,
)


__all__: list[str] = [
    # Build matrix models
    "BuildMatrix",
    "BuildTarget",
    # Compilation configuration models
    "CompilationConfig",
    "ZmkCompilationConfig",
    "MoergoCompilationConfig",
    "CompilationConfigUnion",
    "DockerUserConfig",
    "CacheConfig",
    "ZmkWorkspaceConfig",
    # West configuration models
    "WestCommandsConfig",
    "WestDefaults",
    "WestManifest",
    "WestManifestConfig",
    "WestProject",
    "WestRemote",
    "WestSelf",
]
