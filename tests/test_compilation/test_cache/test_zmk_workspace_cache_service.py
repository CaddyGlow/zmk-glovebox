"""Tests for the simplified ZmkWorkspaceCacheService."""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from glovebox.compilation.cache.models import (
    WorkspaceCacheMetadata,
    WorkspaceCacheResult,
)
from glovebox.compilation.cache.workspace_cache_service import ZmkWorkspaceCacheService
from glovebox.config.models.cache import CacheLevel
from glovebox.config.user_config import UserConfig
from glovebox.core.cache.cache_manager import CacheManager


class TestZmkWorkspaceCacheServiceSimplified:
    """Test suite for simplified ZmkWorkspaceCacheService."""

    def _create_metadata(
        self,
        workspace_path: Path,
        repository: str,
        branch: str | None = None,
        cache_level: CacheLevel = CacheLevel.REPO,
        commit_hash: str | None = "abc123",
        created_at: datetime | None = None,
        last_accessed: datetime | None = None,
        keymap_hash: str | None = "keymap_hash",
        config_hash: str | None = "config_hash",
        auto_detected: bool = False,
        auto_detected_source: str | None = None,
        build_id: str | None = "build_123",
        build_profile: str | None = "test_profile",
        cached_components: list[str] | None = None,
        size_bytes: int | None = 1024,
        notes: str | None = "test metadata",
    ) -> WorkspaceCacheMetadata:
        """Helper to create WorkspaceCacheMetadata with required fields."""
        if created_at is None:
            created_at = datetime.now()
        if last_accessed is None:
            last_accessed = datetime.now()
        if cached_components is None:
            cached_components = ["zmk", "zephyr"]

        return WorkspaceCacheMetadata(
            workspace_path=workspace_path,
            repository=repository,
            branch=branch,
            cache_level=cache_level,
            commit_hash=commit_hash,
            created_at=created_at,
            last_accessed=last_accessed,
            keymap_hash=keymap_hash,
            config_hash=config_hash,
            auto_detected=auto_detected,
            auto_detected_source=auto_detected_source,
            build_id=build_id,
            build_profile=build_profile,
            cached_components=cached_components,
            size_bytes=size_bytes,
            notes=notes,
        )

    @pytest.fixture
    def mock_cache_manager(self) -> Mock:
        """Create a mock cache manager."""
        return Mock(spec=CacheManager)

        # Removed mock_user_config fixture - now using isolated_config from conftest.py

    @pytest.fixture
    def service(
        self, isolated_config: UserConfig, mock_cache_manager: Mock, session_metrics
    ) -> ZmkWorkspaceCacheService:
        """Create ZmkWorkspaceCacheService instance."""
        return ZmkWorkspaceCacheService(
            isolated_config, mock_cache_manager, session_metrics
        )

    @pytest.fixture
    def sample_workspace(self, tmp_path: Path) -> Path:
        """Create a sample ZMK workspace directory."""
        workspace = tmp_path / "sample_workspace"
        workspace.mkdir()

        # Create ZMK workspace structure
        zmk_dir = workspace / "zmk"
        zmk_dir.mkdir()
        (zmk_dir / "CMakeLists.txt").write_text("# ZMK CMake")

        # Create .git directory (should be preserved for repo-only caching)
        git_dir = zmk_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("[core]\nrepositoryformatversion = 0\n")
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")

        zephyr_dir = workspace / "zephyr"
        zephyr_dir.mkdir()
        (zephyr_dir / "VERSION").write_text("VERSION_MAJOR = 3\n")

        modules_dir = workspace / "modules"
        modules_dir.mkdir()
        (modules_dir / "hal" / "nordic").mkdir(parents=True)

        return workspace

    def test_generate_cache_key_repo_only(self, service: ZmkWorkspaceCacheService):
        """Test cache key generation for repo-only caching."""
        cache_key = service._generate_cache_key("zmkfirmware/zmk", None)

        assert cache_key.startswith("workspace_repo_")

        # Test deterministic generation
        cache_key2 = service._generate_cache_key("zmkfirmware/zmk", None)
        assert cache_key == cache_key2

    def test_generate_cache_key_repo_branch(self, service: ZmkWorkspaceCacheService):
        """Test cache key generation for repo+branch caching."""
        cache_key = service._generate_cache_key("zmkfirmware/zmk", "main")

        assert cache_key.startswith("workspace_repo_branch_")

        # Test deterministic generation
        cache_key2 = service._generate_cache_key("zmkfirmware/zmk", "main")
        assert cache_key == cache_key2

        # Test different from repo-only
        repo_only_key = service._generate_cache_key("zmkfirmware/zmk", None)
        assert cache_key != repo_only_key

    def test_cache_workspace_repo_only_success(
        self,
        service: ZmkWorkspaceCacheService,
        sample_workspace: Path,
        mock_cache_manager: Mock,
        tmp_path: Path,
    ):
        """Test successful repo-only workspace caching (includes .git folders)."""
        repository = "zmkfirmware/zmk"
        mock_cache_manager.set.return_value = True

        result = service.cache_workspace_repo_only(sample_workspace, repository)

        assert result.success is True
        assert result.workspace_path is not None
        assert result.metadata is not None
        assert result.metadata.repository == repository
        assert result.metadata.branch is None
        assert result.metadata.cache_level == CacheLevel.REPO

        # Verify cache manager was called with repo TTL
        mock_cache_manager.set.assert_called_once()
        call_args = mock_cache_manager.set.call_args
        assert call_args[1]["ttl"] == 7 * 24 * 3600  # 7 days

    def test_cache_workspace_repo_branch_success(
        self,
        service: ZmkWorkspaceCacheService,
        sample_workspace: Path,
        mock_cache_manager: Mock,
        tmp_path: Path,
    ):
        """Test successful repo+branch workspace caching (excludes .git folders)."""
        repository = "zmkfirmware/zmk"
        branch = "main"
        mock_cache_manager.set.return_value = True

        result = service.cache_workspace_repo_branch(
            sample_workspace, repository, branch
        )

        assert result.success is True
        assert result.workspace_path is not None
        assert result.metadata is not None
        assert result.metadata.repository == repository
        assert result.metadata.branch == branch
        assert result.metadata.cache_level == CacheLevel.REPO_BRANCH

        # Verify cache manager was called with repo+branch TTL
        mock_cache_manager.set.assert_called_once()
        call_args = mock_cache_manager.set.call_args
        assert call_args[1]["ttl"] == 24 * 3600  # 1 day

    def test_cache_workspace_nonexistent_directory(
        self,
        service: ZmkWorkspaceCacheService,
        tmp_path: Path,
        mock_cache_manager: Mock,
    ):
        """Test caching with non-existent workspace directory."""
        nonexistent_dir = tmp_path / "nonexistent"
        repository = "zmkfirmware/zmk"

        result = service.cache_workspace_repo_only(nonexistent_dir, repository)

        assert result.success is False
        assert (
            result.error_message is not None
            and "does not exist" in result.error_message
        )
        mock_cache_manager.set.assert_not_called()

    def test_get_cached_workspace_repo_only_hit(
        self,
        service: ZmkWorkspaceCacheService,
        mock_cache_manager: Mock,
        tmp_path: Path,
    ):
        """Test cache hit for repo-only workspace."""
        repository = "zmkfirmware/zmk"
        cached_workspace_dir = tmp_path / "cached_workspace"
        cached_workspace_dir.mkdir()

        # Mock cache hit
        metadata = self._create_metadata(
            workspace_path=cached_workspace_dir,
            repository=repository,
            branch=None,
            cache_level=CacheLevel.REPO,
        )
        mock_cache_manager.get.return_value = metadata.to_cache_value()

        result = service.get_cached_workspace(repository, None)

        assert result.success is True
        assert result.workspace_path == cached_workspace_dir
        assert result.metadata is not None
        assert result.metadata.repository == repository
        assert result.metadata.branch is None

    def test_get_cached_workspace_repo_branch_hit(
        self,
        service: ZmkWorkspaceCacheService,
        mock_cache_manager: Mock,
        tmp_path: Path,
    ):
        """Test cache hit for repo+branch workspace."""
        repository = "zmkfirmware/zmk"
        branch = "main"
        cached_workspace_dir = tmp_path / "cached_workspace"
        cached_workspace_dir.mkdir()

        # Mock cache hit
        metadata = self._create_metadata(
            workspace_path=cached_workspace_dir,
            repository=repository,
            branch=branch,
            cache_level=CacheLevel.REPO_BRANCH,
        )
        mock_cache_manager.get.return_value = metadata.to_cache_value()

        result = service.get_cached_workspace(repository, branch)

        assert result.success is True
        assert result.workspace_path == cached_workspace_dir
        assert result.metadata is not None
        assert result.metadata.repository == repository
        assert result.metadata.branch == branch

    def test_get_cached_workspace_miss(
        self, service: ZmkWorkspaceCacheService, mock_cache_manager: Mock
    ):
        """Test cache miss scenario."""
        repository = "zmkfirmware/zmk"
        branch = "main"
        mock_cache_manager.get.return_value = None

        result = service.get_cached_workspace(repository, branch)

        assert result.success is False
        assert (
            result.error_message is not None
            and "No cached workspace found" in result.error_message
        )

    def test_get_cached_workspace_stale_entry(
        self,
        service: ZmkWorkspaceCacheService,
        mock_cache_manager: Mock,
        tmp_path: Path,
    ):
        """Test handling of stale cache entries."""
        repository = "zmkfirmware/zmk"
        branch = "main"
        nonexistent_path = tmp_path / "nonexistent_workspace"

        # Mock cache hit with non-existent path
        metadata = self._create_metadata(
            workspace_path=nonexistent_path,
            repository=repository,
            branch=branch,
            cache_level=CacheLevel.REPO_BRANCH,
        )
        mock_cache_manager.get.return_value = metadata.to_cache_value()

        result = service.get_cached_workspace(repository, branch)

        assert result.success is False
        assert (
            result.error_message is not None
            and "no longer exists" in result.error_message
        )
        # Should clean up stale entry
        mock_cache_manager.delete.assert_called_once()

    def test_inject_existing_workspace_repo_only(
        self,
        service: ZmkWorkspaceCacheService,
        sample_workspace: Path,
        mock_cache_manager: Mock,
    ):
        """Test injecting existing workspace for repo-only caching."""
        repository = "zmkfirmware/zmk"
        mock_cache_manager.set.return_value = True

        result = service.inject_existing_workspace(sample_workspace, repository, None)

        assert result.success is True
        assert result.metadata is not None
        assert result.metadata.repository == repository
        assert result.metadata.branch is None
        assert result.metadata.cache_level == CacheLevel.REPO

    def test_inject_existing_workspace_repo_branch(
        self,
        service: ZmkWorkspaceCacheService,
        sample_workspace: Path,
        mock_cache_manager: Mock,
    ):
        """Test injecting existing workspace for repo+branch caching."""
        repository = "zmkfirmware/zmk"
        branch = "main"
        mock_cache_manager.set.return_value = True

        result = service.inject_existing_workspace(sample_workspace, repository, branch)

        assert result.success is True
        assert result.metadata is not None
        assert result.metadata.repository == repository
        assert result.metadata.branch == branch
        assert result.metadata.cache_level == CacheLevel.REPO_BRANCH

    def test_delete_cached_workspace_repo_only(
        self,
        service: ZmkWorkspaceCacheService,
        mock_cache_manager: Mock,
        tmp_path: Path,
    ):
        """Test deleting repo-only cached workspace."""
        repository = "zmkfirmware/zmk"
        cached_workspace_dir = tmp_path / "cached_workspace"
        cached_workspace_dir.mkdir()

        # Mock cache data
        metadata = self._create_metadata(
            workspace_path=cached_workspace_dir,
            repository=repository,
            branch=None,
            cache_level=CacheLevel.REPO,
        )
        mock_cache_manager.get.return_value = metadata.to_cache_value()
        mock_cache_manager.delete.return_value = True

        result = service.delete_cached_workspace(repository, None)

        assert result is True
        mock_cache_manager.delete.assert_called_once()
        assert not cached_workspace_dir.exists()  # Directory should be removed

    def test_delete_cached_workspace_repo_branch(
        self,
        service: ZmkWorkspaceCacheService,
        mock_cache_manager: Mock,
        tmp_path: Path,
    ):
        """Test deleting repo+branch cached workspace."""
        repository = "zmkfirmware/zmk"
        branch = "main"
        cached_workspace_dir = tmp_path / "cached_workspace"
        cached_workspace_dir.mkdir()

        # Mock cache data
        metadata = self._create_metadata(
            workspace_path=cached_workspace_dir,
            repository=repository,
            branch=branch,
            cache_level=CacheLevel.REPO_BRANCH,
        )
        mock_cache_manager.get.return_value = metadata.to_cache_value()
        mock_cache_manager.delete.return_value = True

        result = service.delete_cached_workspace(repository, branch)

        assert result is True
        mock_cache_manager.delete.assert_called_once()
        assert not cached_workspace_dir.exists()  # Directory should be removed

    def test_list_cached_workspaces(
        self,
        service: ZmkWorkspaceCacheService,
        mock_cache_manager: Mock,
        tmp_path: Path,
    ):
        """Test listing cached workspaces."""
        # Mock cache keys
        mock_cache_manager.keys.return_value = [
            "workspace_repo_key1",
            "workspace_repo_branch_key2",
            "other_cache_key",  # Should be filtered out
        ]

        # Create workspace directories for the test
        workspace1_path = tmp_path / "workspace1"
        workspace1_path.mkdir()
        workspace2_path = tmp_path / "workspace2"
        workspace2_path.mkdir()

        # Mock cache data
        metadata1 = self._create_metadata(
            workspace_path=workspace1_path,
            repository="zmkfirmware/zmk",
            branch=None,
            cache_level=CacheLevel.REPO,
        )
        metadata2 = self._create_metadata(
            workspace_path=workspace2_path,
            repository="zmkfirmware/zmk",
            branch="main",
            cache_level=CacheLevel.REPO_BRANCH,
        )

        mock_cache_manager.get.side_effect = [
            metadata1.to_cache_value(),
            metadata2.to_cache_value(),
        ]

        workspaces = service.list_cached_workspaces()

        assert len(workspaces) == 2
        assert all(ws.repository == "zmkfirmware/zmk" for ws in workspaces)

    def test_cleanup_stale_entries(
        self,
        service: ZmkWorkspaceCacheService,
        mock_cache_manager: Mock,
        tmp_path: Path,
    ):
        """Test cleanup of stale cache entries."""
        # Create workspaces for age-based cleanup test (not existence-based)
        workspace1 = tmp_path / "workspace1"
        workspace1.mkdir()
        workspace2 = tmp_path / "workspace2"
        workspace2.mkdir()  # Create both workspaces so they pass existence check

        # Create metadata with different ages (using datetime manipulation)
        from datetime import datetime, timedelta

        old_time = datetime.now() - timedelta(
            hours=8 * 24
        )  # Older than default 7 days (168h)
        recent_time = datetime.now() - timedelta(hours=1)  # Recent

        metadata1 = self._create_metadata(
            workspace_path=workspace1,
            repository="zmkfirmware/zmk",
            branch=None,
            cache_level=CacheLevel.REPO,
            created_at=recent_time,
            last_accessed=recent_time,
        )
        metadata2 = self._create_metadata(
            workspace_path=workspace2,
            repository="zmkfirmware/zmk",
            branch="main",
            cache_level=CacheLevel.REPO_BRANCH,
            created_at=old_time,
            last_accessed=old_time,
        )

        # Generate actual cache keys that match what the service will generate
        cache_key1 = service._generate_cache_key("zmkfirmware/zmk", None)
        cache_key2 = service._generate_cache_key("zmkfirmware/zmk", "main")

        mock_cache_manager.keys.return_value = [
            cache_key1,
            cache_key2,
        ]
        mock_cache_manager.get.side_effect = [
            metadata1.to_cache_value(),
            metadata2.to_cache_value(),
            metadata2.to_cache_value(),  # For the delete operation
        ]
        mock_cache_manager.delete.return_value = True  # Mock successful deletion

        cleaned_count = service.cleanup_stale_entries()

        assert cleaned_count == 1  # Only one stale entry should be cleaned
        mock_cache_manager.delete.assert_called_once_with(cache_key2)

    def test_workspace_copying_excludes_git_for_repo_branch(
        self,
        service: ZmkWorkspaceCacheService,
        sample_workspace: Path,
        mock_cache_manager: Mock,
        tmp_path: Path,
    ):
        """Test that repo+branch caching excludes .git folders."""
        repository = "zmkfirmware/zmk"
        branch = "main"
        mock_cache_manager.set.return_value = True

        # Mock the cache directory to a known location for verification
        cache_dir = tmp_path / "cache_test"
        cache_dir.mkdir(parents=True, exist_ok=True)
        with patch.object(service, "get_cache_directory", return_value=cache_dir):
            result = service.cache_workspace_repo_branch(
                sample_workspace, repository, branch
            )

            assert result.success is True

            # Verify that .git folders were not copied
            assert result.workspace_path is not None
            cached_zmk_dir = result.workspace_path / "zmk"
            assert cached_zmk_dir.exists()
            assert (cached_zmk_dir / "CMakeLists.txt").exists()  # Regular files copied
            assert not (cached_zmk_dir / ".git").exists()  # .git folder excluded

    def test_workspace_copying_includes_git_for_repo_only(
        self,
        service: ZmkWorkspaceCacheService,
        sample_workspace: Path,
        mock_cache_manager: Mock,
        tmp_path: Path,
    ):
        """Test that repo-only caching includes .git folders."""
        repository = "zmkfirmware/zmk"
        mock_cache_manager.set.return_value = True

        # Mock the cache directory to a known location for verification
        cache_dir = tmp_path / "cache_test"
        cache_dir.mkdir(parents=True, exist_ok=True)
        with patch.object(service, "get_cache_directory", return_value=cache_dir):
            result = service.cache_workspace_repo_only(sample_workspace, repository)

            assert result.success is True

            # Verify that .git folders were copied
            assert result.workspace_path is not None
            cached_zmk_dir = result.workspace_path / "zmk"
            assert cached_zmk_dir.exists()
            assert (cached_zmk_dir / "CMakeLists.txt").exists()  # Regular files copied
            assert (cached_zmk_dir / ".git").exists()  # .git folder included
            assert (cached_zmk_dir / ".git" / "config").exists()  # .git contents copied

    def test_integration_cache_and_retrieve_repo_only(
        self,
        isolated_config: UserConfig,
        isolated_cache_environment: dict[str, Any],
        sample_workspace: Path,
        session_metrics,
    ):
        """Integration test: cache a repo-only workspace and retrieve it."""
        # Use real cache manager for integration test
        from glovebox.core.cache import create_default_cache

        cache_manager = create_default_cache(tag="workspace_test")
        service = ZmkWorkspaceCacheService(
            isolated_config, cache_manager, session_metrics
        )

        repository = "zmkfirmware/zmk"

        # Cache the workspace
        cache_result = service.cache_workspace_repo_only(sample_workspace, repository)
        assert cache_result.success is True

        # Retrieve the cached workspace
        retrieved_result = service.get_cached_workspace(repository, None)
        assert retrieved_result.success is True
        assert retrieved_result.workspace_path is not None
        assert retrieved_result.workspace_path.exists()
        assert (retrieved_result.workspace_path / "zmk").exists()
        assert (
            retrieved_result.workspace_path / "zmk" / ".git"
        ).exists()  # .git preserved

    def test_integration_cache_and_retrieve_repo_branch(
        self,
        isolated_config: UserConfig,
        isolated_cache_environment: dict[str, Any],
        sample_workspace: Path,
        session_metrics,
    ):
        """Integration test: cache a repo+branch workspace and retrieve it."""
        # Use real cache manager for integration test
        from glovebox.core.cache import create_default_cache

        cache_manager = create_default_cache(tag="workspace_test")
        service = ZmkWorkspaceCacheService(
            isolated_config, cache_manager, session_metrics
        )

        repository = "zmkfirmware/zmk"
        branch = "main"

        # Cache the workspace
        cache_result = service.cache_workspace_repo_branch(
            sample_workspace, repository, branch
        )
        assert cache_result.success is True

        # Retrieve the cached workspace
        retrieved_result = service.get_cached_workspace(repository, branch)
        assert retrieved_result.success is True
        assert retrieved_result.workspace_path is not None
        assert retrieved_result.workspace_path.exists()
        assert (retrieved_result.workspace_path / "zmk").exists()
        assert not (
            retrieved_result.workspace_path / "zmk" / ".git"
        ).exists()  # .git excluded
