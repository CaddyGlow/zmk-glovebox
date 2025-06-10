"""Test model imports and exports."""

import pytest


def test_compilation_models_import():
    """Test that all compilation models can be imported from the models package."""
    from glovebox.compilation.models import (
        BuildMatrix,
        BuildMatrixResult,
        BuildTarget,
        BuildTargetConfig,
        BuildYamlConfig,
        CacheConfig,
        CacheMetadata,
        CacheValidationResult,
        CompilationResult,
        StrategyResult,
        WestWorkspaceConfig,
        WorkspaceCacheEntry,
        WorkspaceConfig,
        ZmkConfigRepoConfig,
    )

    # Test that all imports are successful
    models = [
        BuildMatrix,
        BuildTarget,
        BuildTargetConfig,
        BuildYamlConfig,
        WorkspaceConfig,
        WestWorkspaceConfig,
        ZmkConfigRepoConfig,
        CacheMetadata,
        CacheConfig,
        CacheValidationResult,
        WorkspaceCacheEntry,
        CompilationResult,
        StrategyResult,
        BuildMatrixResult,
    ]

    for model in models:
        assert model is not None


def test_build_matrix_models_import():
    """Test that build matrix models can be imported directly."""
    from glovebox.compilation.models.build_matrix import (
        BuildMatrix,
        BuildTarget,
        BuildTargetConfig,
        BuildYamlConfig,
    )

    assert BuildMatrix is not None
    assert BuildTarget is not None
    assert BuildTargetConfig is not None
    assert BuildYamlConfig is not None


def test_workspace_config_models_import():
    """Test that workspace config models can be imported directly."""
    from glovebox.compilation.models.workspace_config import (
        WestWorkspaceConfig,
        WorkspaceConfig,
        ZmkConfigRepoConfig,
        expand_path_variables,
    )

    assert WestWorkspaceConfig is not None
    assert WorkspaceConfig is not None
    assert ZmkConfigRepoConfig is not None
    assert callable(expand_path_variables)


def test_cache_metadata_models_import():
    """Test that cache metadata models can be imported directly."""
    from glovebox.compilation.models.cache_metadata import (
        CacheConfig,
        CacheMetadata,
        CacheValidationResult,
        WorkspaceCacheEntry,
    )

    assert CacheMetadata is not None
    assert CacheConfig is not None
    assert CacheValidationResult is not None
    assert WorkspaceCacheEntry is not None


def test_compilation_result_models_import():
    """Test that compilation result models can be imported directly."""
    from glovebox.compilation.models.compilation_result import (
        BuildMatrixResult,
        CompilationResult,
        StrategyResult,
    )

    assert CompilationResult is not None
    assert StrategyResult is not None
    assert BuildMatrixResult is not None
