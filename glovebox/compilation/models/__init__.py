"""Compilation-specific models for build configuration and metadata."""

from glovebox.compilation.models.build_matrix import (
    BuildMatrix,
    BuildTarget,
    BuildTargetConfig,
    BuildYamlConfig,
)
from glovebox.compilation.models.cache_metadata import (
    CacheConfig,
    CacheMetadata,
    CacheValidationResult,
    WorkspaceCacheEntry,
)
from glovebox.compilation.models.compilation_result import (
    BuildMatrixResult,
    CompilationResult,
    StrategyResult,
)
from glovebox.compilation.models.workspace_config import (
    WestWorkspaceConfig,
    WorkspaceConfig,
    ZmkConfigRepoConfig,
)


__all__: list[str] = [
    # Build matrix models
    "BuildMatrix",
    "BuildTarget",
    "BuildTargetConfig",
    "BuildYamlConfig",
    # Workspace models
    "WorkspaceConfig",
    "WestWorkspaceConfig",
    "ZmkConfigRepoConfig",
    # Cache models
    "CacheMetadata",
    "CacheConfig",
    "CacheValidationResult",
    "WorkspaceCacheEntry",
    # Result models
    "CompilationResult",
    "StrategyResult",
    "BuildMatrixResult",
]
