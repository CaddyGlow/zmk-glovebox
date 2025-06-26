#!/usr/bin/env python3
"""Integration tests for workspace cache service with progress tracking."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from glovebox.compilation.cache.workspace_cache_service import ZmkWorkspaceCacheService
from glovebox.core.file_operations.models import CopyProgress


def create_mock_zmk_workspace(base_path: Path) -> Path:
    """Create a mock ZMK workspace for testing.

    Args:
        base_path: Base directory to create workspace in

    Returns:
        Path to created workspace
    """
    workspace = base_path / "mock_zmk_workspace"
    workspace.mkdir(exist_ok=True)

    # Create ZMK-style components
    components = ["zmk", "zephyr", "modules", ".west"]

    for component in components:
        comp_dir = workspace / component
        comp_dir.mkdir(exist_ok=True)

        # Create some files in each component
        for i in range(3):
            file_path = comp_dir / f"{component}_file_{i}.txt"
            content = f"Mock {component} content {i}\n" * 50  # ~1.5KB per file
            file_path.write_text(content)

        # Create subdirectories
        if component == "zmk":
            app_dir = comp_dir / "app"
            app_dir.mkdir(exist_ok=True)
            (app_dir / "main.c").write_text("/* Mock ZMK main */\n" * 100)

    return workspace


@pytest.fixture
def mock_user_config():
    """Create a mock user config for testing."""
    config = Mock()
    config._config.cache_path = Path(tempfile.mkdtemp())
    config._config.cache_ttls.get_workspace_ttls.return_value = {
        "repo": 86400,
        "repo_branch": 3600,
        "base": 86400,
        "branch": 3600,
        "full": 1800,
        "build": 600,
    }
    return config


@pytest.fixture
def mock_cache_manager():
    """Create a mock cache manager for testing."""
    cache_manager = Mock()
    cache_manager.set.return_value = True
    cache_manager.get.return_value = None
    cache_manager.delete.return_value = True
    cache_manager.keys.return_value = []
    return cache_manager


@pytest.fixture
def mock_metrics():
    """Create a mock metrics protocol for testing."""
    metrics = Mock()
    metrics.set_context.return_value = None
    metrics.time_operation.return_value.__enter__ = Mock(return_value=None)
    metrics.time_operation.return_value.__exit__ = Mock(return_value=None)
    return metrics


class TestWorkspaceCacheWithProgress:
    """Test workspace cache service with progress tracking."""

    def test_inject_existing_workspace_with_progress(
        self, tmp_path, mock_user_config, mock_cache_manager, mock_metrics
    ):
        """Test injecting existing workspace with progress callback."""
        # Create mock workspace
        workspace_path = create_mock_zmk_workspace(tmp_path)

        # Mock progress callback
        progress_callback = Mock()

        # Create workspace cache service
        service = ZmkWorkspaceCacheService(
            user_config=mock_user_config,
            cache_manager=mock_cache_manager,
            session_metrics=mock_metrics,
        )

        # Inject workspace with progress tracking
        result = service.inject_existing_workspace(
            workspace_path=workspace_path,
            repository="test/repo",
            branch="main",
            progress_callback=progress_callback,
        )

        # Verify result
        assert result.success
        assert result.metadata is not None
        assert result.metadata.repository == "test/repo"
        assert result.metadata.branch == "main"

        # Verify progress callback was called
        assert progress_callback.called

        # Check progress callback calls
        call_args_list = progress_callback.call_args_list
        assert len(call_args_list) > 0

        # Verify progress objects
        for call_args in call_args_list:
            progress_obj = call_args[0][0]
            assert isinstance(progress_obj, CopyProgress)
            assert progress_obj.component_name != ""  # Should have component info

    def test_cache_workspace_repo_only_with_progress(
        self, tmp_path, mock_user_config, mock_cache_manager, mock_metrics
    ):
        """Test caching workspace (repo-only) with progress callback."""
        # Create mock workspace
        workspace_path = create_mock_zmk_workspace(tmp_path)

        # Mock progress callback
        progress_callback = Mock()

        # Create workspace cache service
        service = ZmkWorkspaceCacheService(
            user_config=mock_user_config,
            cache_manager=mock_cache_manager,
            session_metrics=mock_metrics,
        )

        # Cache workspace with progress tracking
        result = service.cache_workspace_repo_only(
            workspace_path=workspace_path,
            repository="test/repo",
            progress_callback=progress_callback,
        )

        # Verify result
        assert result.success
        assert progress_callback.called

    def test_cache_workspace_repo_branch_with_progress(
        self, tmp_path, mock_user_config, mock_cache_manager, mock_metrics
    ):
        """Test caching workspace (repo+branch) with progress callback."""
        # Create mock workspace
        workspace_path = create_mock_zmk_workspace(tmp_path)

        # Mock progress callback
        progress_callback = Mock()

        # Create workspace cache service
        service = ZmkWorkspaceCacheService(
            user_config=mock_user_config,
            cache_manager=mock_cache_manager,
            session_metrics=mock_metrics,
        )

        # Cache workspace with progress tracking
        result = service.cache_workspace_repo_branch(
            workspace_path=workspace_path,
            repository="test/repo",
            branch="feature-branch",
            progress_callback=progress_callback,
        )

        # Verify result
        assert result.success
        assert progress_callback.called

    def test_workspace_caching_without_progress_callback(
        self, tmp_path, mock_user_config, mock_cache_manager, mock_metrics
    ):
        """Test workspace caching works without progress callback."""
        # Create mock workspace
        workspace_path = create_mock_zmk_workspace(tmp_path)

        # Create workspace cache service
        service = ZmkWorkspaceCacheService(
            user_config=mock_user_config,
            cache_manager=mock_cache_manager,
            session_metrics=mock_metrics,
        )

        # Cache workspace without progress callback
        result = service.inject_existing_workspace(
            workspace_path=workspace_path,
            repository="test/repo",
            branch="main",
            progress_callback=None,  # Explicitly no callback
        )

        # Verify result
        assert result.success

    def test_progress_callback_component_information(
        self, tmp_path, mock_user_config, mock_cache_manager, mock_metrics
    ):
        """Test that progress callback receives component-level information."""
        # Create mock workspace
        workspace_path = create_mock_zmk_workspace(tmp_path)

        # Track progress calls
        progress_calls = []

        def track_progress(progress: CopyProgress) -> None:
            progress_calls.append(
                {
                    "component_name": progress.component_name,
                    "current_file": progress.current_file,
                    "files_processed": progress.files_processed,
                    "total_files": progress.total_files,
                }
            )

        # Create workspace cache service
        service = ZmkWorkspaceCacheService(
            user_config=mock_user_config,
            cache_manager=mock_cache_manager,
            session_metrics=mock_metrics,
        )

        # Cache workspace with progress tracking
        result = service.inject_existing_workspace(
            workspace_path=workspace_path,
            repository="test/repo",
            branch="main",
            progress_callback=track_progress,
        )

        # Verify result
        assert result.success

        # Verify we got progress calls with component information
        assert len(progress_calls) > 0

        # Check that we have component-level information
        component_names = [call["component_name"] for call in progress_calls]
        assert any("zmk" in name for name in component_names)
        assert any(
            "(" in name and "/" in name for name in component_names
        )  # Component (X/Y) format

        # Verify progress makes sense
        for call in progress_calls:
            assert call["files_processed"] >= 0
            assert call["total_files"] >= 0
            assert call["current_file"] is not None
