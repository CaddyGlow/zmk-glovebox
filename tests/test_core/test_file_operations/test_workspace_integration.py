"""Integration tests for file operations with workspace cache service."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from glovebox.compilation.cache.workspace_cache_service import ZmkWorkspaceCacheService
from glovebox.core.cache_v2.cache_manager import CacheManager
from glovebox.core.file_operations import CopyStrategy


class TestWorkspaceCacheIntegration:
    """Test integration of file operations with workspace cache service."""

    @pytest.fixture
    def mock_user_config(self):
        """Create mock user config with copy settings."""
        config = Mock()
        config._config = Mock()
        config._config.copy_strategy = CopyStrategy.BASELINE
        config._config.copy_buffer_size_kb = 512
        config._config.cache_path = Path("/tmp/test_cache")

        # Mock cache TTL configuration
        config._config.cache_ttls = Mock()
        config._config.cache_ttls.get_workspace_ttls = Mock(
            return_value={"repo": 86400, "repo_branch": 3600}
        )

        return config

    @pytest.fixture
    def mock_cache_manager(self):
        """Create mock cache manager."""
        manager = Mock(spec=CacheManager)
        manager.get.return_value = None  # No cached data by default
        manager.set.return_value = True
        manager.delete.return_value = True
        manager.keys.return_value = []
        return manager

    @pytest.fixture
    def workspace_service(self, mock_user_config, mock_cache_manager):
        """Create workspace cache service with mocked dependencies."""
        return ZmkWorkspaceCacheService(mock_user_config, mock_cache_manager)

    def test_workspace_service_initializes_copy_service(
        self, workspace_service, mock_user_config
    ):
        """Test workspace service properly initializes copy service."""
        # The service should have a copy_service attribute
        assert hasattr(workspace_service, "copy_service")
        assert workspace_service.copy_service is not None

        # Copy service should be configured from user config
        assert workspace_service.copy_service.default_strategy == CopyStrategy.BASELINE
        assert workspace_service.copy_service.buffer_size_kb == 512

    def test_copy_directory_uses_copy_service(self, workspace_service, tmp_path):
        """Test that _copy_directory uses the copy service."""
        # Create source directory
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("test content")
        (src_dir / ".git").mkdir()
        (src_dir / ".git" / "config").write_text("git config")

        dst_dir = tmp_path / "destination"

        # Test copy with git exclusion
        workspace_service._copy_directory(src_dir, dst_dir, include_git=False)

        # Verify copy was successful
        assert dst_dir.exists()
        assert (dst_dir / "file.txt").read_text() == "test content"
        assert not (dst_dir / ".git").exists()

    def test_copy_directory_with_git_inclusion(self, workspace_service, tmp_path):
        """Test copy directory includes git when requested."""
        # Create source directory with .git
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("test content")
        (src_dir / ".git").mkdir()
        (src_dir / ".git" / "config").write_text("git config")

        dst_dir = tmp_path / "destination"

        # Test copy with git inclusion
        workspace_service._copy_directory(src_dir, dst_dir, include_git=True)

        # Verify git directory was included
        assert dst_dir.exists()
        assert (dst_dir / "file.txt").read_text() == "test content"
        assert (dst_dir / ".git" / "config").read_text() == "git config"

    def test_copy_directory_handles_failure(self, workspace_service, tmp_path):
        """Test copy directory handles copy failures."""
        # Non-existent source directory
        src_dir = tmp_path / "nonexistent"
        dst_dir = tmp_path / "destination"

        # Should raise RuntimeError when copy fails
        with pytest.raises(RuntimeError, match="Copy operation failed"):
            workspace_service._copy_directory(src_dir, dst_dir, include_git=False)

    def test_workspace_caching_with_optimized_copy(
        self, workspace_service, tmp_path, mock_cache_manager
    ):
        """Test full workspace caching flow with optimized copy."""
        # Create mock workspace structure
        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()

        # Create ZMK workspace components
        for component in ["zmk", "zephyr", "modules", ".west"]:
            comp_dir = workspace_dir / component
            comp_dir.mkdir()
            (comp_dir / "test_file.txt").write_text(f"{component} content")

            # Add .git to some components
            if component in ["zmk", "zephyr"]:
                git_dir = comp_dir / ".git"
                git_dir.mkdir()
                (git_dir / "config").write_text(f"{component} git config")

        # Mock cache directory creation
        cache_base = tmp_path / "cache"
        workspace_service.get_cache_directory = Mock(return_value=cache_base)

        # Import the actual enum we need
        from glovebox.config.models.cache import CacheLevel

        # Test workspace caching (repo-only, includes .git)
        result = workspace_service._cache_workspace_internal(
            workspace_path=workspace_dir,
            repository="zmkfirmware/zmk",
            branch=None,
            cache_level=CacheLevel.REPO,
            include_git=True,
        )

        assert result.success is True
        assert result.workspace_path is not None

        # Verify components were copied
        cached_workspace = result.workspace_path
        for component in ["zmk", "zephyr", "modules", ".west"]:
            assert (cached_workspace / component / "test_file.txt").exists()
            content = (cached_workspace / component / "test_file.txt").read_text()
            assert content == f"{component} content"

    def test_workspace_caching_excludes_git_when_requested(
        self, workspace_service, tmp_path, mock_cache_manager
    ):
        """Test workspace caching excludes .git when requested."""
        # Create workspace with .git directories
        workspace_dir = tmp_path / "workspace"
        workspace_dir.mkdir()

        zmk_dir = workspace_dir / "zmk"
        zmk_dir.mkdir()
        (zmk_dir / "file.txt").write_text("zmk content")
        git_dir = zmk_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config")

        # Mock cache directory
        cache_base = tmp_path / "cache"
        workspace_service.get_cache_directory = Mock(return_value=cache_base)

        # Import the actual enum we need
        from glovebox.config.models.cache import CacheLevel

        # Test workspace caching (repo+branch, excludes .git)
        result = workspace_service._cache_workspace_internal(
            workspace_path=workspace_dir,
            repository="zmkfirmware/zmk",
            branch="main",
            cache_level=CacheLevel.REPO_BRANCH,
            include_git=False,
        )

        assert result.success is True

        # Verify .git was excluded
        cached_workspace = result.workspace_path
        assert (cached_workspace / "zmk" / "file.txt").exists()
        assert not (cached_workspace / "zmk" / ".git").exists()

    def test_copy_service_strategy_selection_in_workspace_cache(self, tmp_path):
        """Test copy service strategy selection in real workspace scenario."""
        # Create user config with specific strategy
        config = Mock()
        config._config = Mock()
        config._config.copy_strategy = CopyStrategy.BUFFERED
        config._config.copy_buffer_size_kb = 2048
        config._config.cache_path = tmp_path / "cache"
        config._config.cache_ttls = Mock()
        config._config.cache_ttls.get_workspace_ttls = Mock(
            return_value={"repo": 86400}
        )

        cache_manager = Mock(spec=CacheManager)
        cache_manager.get.return_value = None
        cache_manager.set.return_value = True

        service = ZmkWorkspaceCacheService(config, cache_manager)

        # Verify copy service uses configured strategy
        assert service.copy_service.default_strategy == CopyStrategy.BUFFERED
        assert service.copy_service.buffer_size_kb == 2048

        # Verify buffered strategy is available and configured correctly
        strategy_info = service.copy_service.get_strategy_info(CopyStrategy.BUFFERED)
        assert strategy_info is not None
        assert "2048KB" in strategy_info["name"]

    def test_workspace_cache_performance_logging(
        self, workspace_service, tmp_path, caplog
    ):
        """Test that performance information is logged during copy operations."""
        import logging

        # Set debug logging to capture copy performance logs
        caplog.set_level(logging.DEBUG)

        # Create source directory
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("test content" * 1000)  # Larger content

        dst_dir = tmp_path / "destination"

        # Perform copy operation
        workspace_service._copy_directory(src_dir, dst_dir, include_git=False)

        # Verify performance logging occurred
        log_messages = [
            record.message
            for record in caplog.records
            if record.levelno == logging.DEBUG
        ]
        performance_logs = [
            msg
            for msg in log_messages
            if "copy completed using strategy" in msg.lower()
        ]

        assert len(performance_logs) > 0

        # Performance log should include strategy, size, time, and speed
        perf_log = performance_logs[0]
        assert "MB" in perf_log  # Size information
        assert "seconds" in perf_log  # Time information
        assert "MB/s" in perf_log  # Speed information

    def test_workspace_cache_error_handling_with_copy_service(
        self, workspace_service, tmp_path
    ):
        """Test error handling when copy service fails."""
        # Test with non-existent source directory (should fail)
        src_dir = tmp_path / "nonexistent_source"
        dst_dir = tmp_path / "destination"

        # This should raise RuntimeError due to copy failure
        with pytest.raises(RuntimeError, match="Copy operation failed"):
            workspace_service._copy_directory(src_dir, dst_dir, include_git=False)
