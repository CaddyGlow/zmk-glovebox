"""Tests for file copy service."""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.core.file_operations import CopyStrategy
from glovebox.core.file_operations.service import FileCopyService, create_copy_service


class TestFileCopyService:
    """Test FileCopyService functionality."""

    def test_service_initialization_with_defaults(self):
        """Test service initialization with default parameters."""
        service = FileCopyService()

        assert service.default_strategy == CopyStrategy.BASELINE
        assert service.buffer_size_kb == 1024
        assert CopyStrategy.BASELINE in service.list_available_strategies()
        assert CopyStrategy.BUFFERED in service.list_available_strategies()

    def test_service_initialization_with_custom_params(self):
        """Test service initialization with custom parameters."""
        service = FileCopyService(
            default_strategy=CopyStrategy.BUFFERED, buffer_size_kb=2048, max_workers=8
        )

        assert service.default_strategy == CopyStrategy.BUFFERED
        assert service.buffer_size_kb == 2048
        assert service.max_workers == 8

    def test_list_available_strategies(self):
        """Test listing available strategies."""
        service = FileCopyService()
        strategies = service.list_available_strategies()

        assert CopyStrategy.BASELINE in strategies
        assert CopyStrategy.BUFFERED in strategies
        assert CopyStrategy.PARALLEL in strategies

        # sendfile only available on supported systems
        if hasattr(os, "sendfile"):
            assert CopyStrategy.SENDFILE in strategies
        else:
            assert CopyStrategy.SENDFILE not in strategies

    def test_get_strategy_info(self):
        """Test getting strategy information."""
        service = FileCopyService()

        # Test baseline strategy info
        info = service.get_strategy_info(CopyStrategy.BASELINE)
        assert info is not None
        assert info["name"] == "Baseline"
        assert info["available"] is True
        assert info["prerequisites"] == []

        # Test non-existent strategy
        info = service.get_strategy_info("nonexistent")
        assert info is None

    def test_successful_directory_copy_with_baseline(self, tmp_path):
        """Test successful directory copy using baseline strategy."""
        service = FileCopyService()

        # Create source directory
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file1.txt").write_text("content1")
        (src_dir / "subdir").mkdir()
        (src_dir / "subdir" / "file2.txt").write_text("content2")

        dst_dir = tmp_path / "destination"

        # Copy using explicit baseline strategy
        result = service.copy_directory(
            src_dir, dst_dir, strategy=CopyStrategy.BASELINE
        )

        assert result.success is True
        assert result.bytes_copied > 0
        assert result.strategy_used == "Baseline"
        assert (dst_dir / "file1.txt").read_text() == "content1"
        assert (dst_dir / "subdir" / "file2.txt").read_text() == "content2"

    def test_copy_with_git_exclusion(self, tmp_path):
        """Test copy with git exclusion."""
        service = FileCopyService()

        # Create source with .git directory
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("content")
        git_dir = src_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config")

        dst_dir = tmp_path / "destination"

        # Copy excluding .git
        result = service.copy_directory(
            src_dir, dst_dir, exclude_git=True, strategy=CopyStrategy.BASELINE
        )

        assert result.success is True
        assert (dst_dir / "file.txt").exists()
        assert not (dst_dir / ".git").exists()

    def test_copy_with_git_inclusion(self, tmp_path):
        """Test copy with git inclusion."""
        service = FileCopyService()

        # Create source with .git directory
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("content")
        git_dir = src_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config")

        dst_dir = tmp_path / "destination"

        # Copy including .git
        result = service.copy_directory(
            src_dir, dst_dir, exclude_git=False, strategy=CopyStrategy.BASELINE
        )

        assert result.success is True
        assert (dst_dir / "file.txt").exists()
        assert (dst_dir / ".git" / "config").exists()

    def test_auto_strategy_selection(self, tmp_path):
        """Test automatic strategy selection."""
        service = FileCopyService(default_strategy=CopyStrategy.BASELINE)

        # Create small directory (should use baseline or buffered)
        small_dir = tmp_path / "small"
        small_dir.mkdir()
        (small_dir / "small.txt").write_text("small content")

        dst_dir = tmp_path / "destination"

        result = service.copy_directory(small_dir, dst_dir)

        assert result.success is True
        assert result.strategy_used in ["Baseline", "Buffered (1024KB)", "Sendfile"]

    def test_strategy_fallback_on_missing_prerequisites(self, tmp_path):
        """Test fallback to baseline when strategy prerequisites are missing."""
        service = FileCopyService()

        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("content")

        dst_dir = tmp_path / "destination"

        # Mock sendfile strategy to have missing prerequisites
        original_sendfile_strategy = service._strategies.get(CopyStrategy.SENDFILE)
        if original_sendfile_strategy:
            with patch.object(
                original_sendfile_strategy,
                "validate_prerequisites",
                return_value=["missing_feature"],
            ):
                result = service.copy_directory(
                    src_dir, dst_dir, strategy=CopyStrategy.SENDFILE
                )
        else:
            # If sendfile not available, just test with baseline
            result = service.copy_directory(
                src_dir, dst_dir, strategy=CopyStrategy.BASELINE
            )

        assert result.success is True
        assert result.strategy_used == "Baseline"  # Fallback

    def test_copy_failure_handling(self, tmp_path):
        """Test copy failure handling."""
        service = FileCopyService()

        # Non-existent source
        src_dir = tmp_path / "nonexistent"
        dst_dir = tmp_path / "destination"

        result = service.copy_directory(src_dir, dst_dir)

        assert result.success is False
        assert result.error is not None
        assert result.bytes_copied == 0

    def test_buffered_strategy_with_custom_buffer_size(self, tmp_path):
        """Test buffered strategy uses custom buffer size."""
        service = FileCopyService(buffer_size_kb=2048)

        # Check that buffered strategy uses custom buffer size
        buffered_info = service.get_strategy_info(CopyStrategy.BUFFERED)
        assert "2048KB" in buffered_info["name"]

        # Test actual copy operation
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("content" * 1000)

        dst_dir = tmp_path / "destination"

        result = service.copy_directory(
            src_dir, dst_dir, strategy=CopyStrategy.BUFFERED
        )

        assert result.success is True
        assert "2048KB" in result.strategy_used


class TestCreateCopyService:
    """Test create_copy_service factory function."""

    def test_create_service_without_config(self):
        """Test creating service without user configuration."""
        service = create_copy_service()

        assert isinstance(service, FileCopyService)
        assert service.default_strategy == CopyStrategy.BASELINE
        assert service.buffer_size_kb == 1024

    def test_create_service_with_none_config(self):
        """Test creating service with None configuration."""
        service = create_copy_service(None)

        assert isinstance(service, FileCopyService)
        assert service.default_strategy == CopyStrategy.BASELINE
        assert service.buffer_size_kb == 1024

    def test_create_service_with_mock_config(self):
        """Test creating service with mock user configuration."""
        # Create mock user config
        mock_config = Mock()
        mock_config._config = Mock()
        mock_config._config.copy_strategy = CopyStrategy.BUFFERED
        mock_config._config.copy_buffer_size_kb = 2048
        mock_config._config.copy_max_workers = 8

        service = create_copy_service(mock_config)

        assert service.default_strategy == CopyStrategy.BUFFERED
        assert service.buffer_size_kb == 2048
        assert service.max_workers == 8

    def test_create_service_with_partial_config(self):
        """Test creating service with partial configuration."""
        # Config with only copy_strategy
        mock_config = Mock()
        mock_config._config = Mock()
        mock_config._config.copy_strategy = CopyStrategy.SENDFILE
        # No copy_buffer_size_kb attribute

        service = create_copy_service(mock_config)

        assert service.default_strategy == CopyStrategy.SENDFILE
        assert service.buffer_size_kb == 1024  # Default
        assert service.max_workers == 4  # Default

    def test_create_service_with_invalid_config_object(self):
        """Test creating service with invalid config object."""
        # Config without _config attribute
        mock_config = Mock(spec=[])  # Empty spec, no _config

        service = create_copy_service(mock_config)

        # Should fall back to defaults
        assert service.default_strategy == CopyStrategy.BASELINE
        assert service.buffer_size_kb == 1024
        assert service.max_workers == 4


class TestServiceIntegration:
    """Test service integration scenarios."""

    def test_service_handles_large_directory_auto_selection(self, tmp_path):
        """Test service handles large directory with auto selection."""
        service = FileCopyService(default_strategy=CopyStrategy.BASELINE)

        # Create directory with larger content
        src_dir = tmp_path / "large_source"
        src_dir.mkdir()

        # Create multiple files to increase size
        for i in range(10):
            (src_dir / f"file_{i}.txt").write_text("content " * 10000)

        dst_dir = tmp_path / "large_destination"

        result = service.copy_directory(src_dir, dst_dir)

        assert result.success is True
        assert result.bytes_copied > 0
        assert result.elapsed_time > 0

        # Verify all files copied
        for i in range(10):
            assert (dst_dir / f"file_{i}.txt").exists()

    def test_service_preserves_directory_structure(self, tmp_path):
        """Test service preserves complex directory structure."""
        service = FileCopyService()

        # Create complex directory structure
        src_dir = tmp_path / "complex_source"
        src_dir.mkdir()

        # Multiple levels of subdirectories
        (src_dir / "level1").mkdir()
        (src_dir / "level1" / "level2").mkdir()
        (src_dir / "level1" / "level2" / "file.txt").write_text("deep content")
        (src_dir / "level1" / "file1.txt").write_text("content1")
        (src_dir / "root_file.txt").write_text("root content")

        dst_dir = tmp_path / "complex_destination"

        result = service.copy_directory(
            src_dir, dst_dir, strategy=CopyStrategy.BASELINE
        )

        assert result.success is True

        # Verify directory structure preserved
        assert (dst_dir / "root_file.txt").read_text() == "root content"
        assert (dst_dir / "level1" / "file1.txt").read_text() == "content1"
        assert (
            dst_dir / "level1" / "level2" / "file.txt"
        ).read_text() == "deep content"

    def test_service_handles_concurrent_access_patterns(self, tmp_path):
        """Test service handles patterns that might occur during concurrent access."""
        service = FileCopyService()

        # Create source directory
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("original content")

        # First copy
        dst_dir1 = tmp_path / "dest1"
        result1 = service.copy_directory(src_dir, dst_dir1)

        # Modify source
        (src_dir / "file.txt").write_text("modified content")
        (src_dir / "new_file.txt").write_text("new content")

        # Second copy should get the new state
        dst_dir2 = tmp_path / "dest2"
        result2 = service.copy_directory(src_dir, dst_dir2)

        assert result1.success is True
        assert result2.success is True

        # First destination should have original content
        assert (dst_dir1 / "file.txt").read_text() == "original content"
        assert not (dst_dir1 / "new_file.txt").exists()

        # Second destination should have modified content
        assert (dst_dir2 / "file.txt").read_text() == "modified content"
        assert (dst_dir2 / "new_file.txt").read_text() == "new content"

    def test_parallel_strategy_execution(self, tmp_path):
        """Test parallel strategy execution."""
        service = FileCopyService(max_workers=2)

        # Create source directory with multiple files
        src_dir = tmp_path / "source"
        src_dir.mkdir()

        for i in range(5):
            (src_dir / f"file_{i}.txt").write_text(f"content {i}")

        dst_dir = tmp_path / "destination"

        result = service.copy_directory(
            src_dir, dst_dir, strategy=CopyStrategy.PARALLEL
        )

        assert result.success is True
        assert "Parallel" in result.strategy_used
        assert "2 threads" in result.strategy_used

        # Verify all files copied
        for i in range(5):
            assert (dst_dir / f"file_{i}.txt").read_text() == f"content {i}"

    def test_auto_strategy_selection_priority(self, tmp_path):
        """Test auto strategy selection follows priority order."""
        service = FileCopyService(default_strategy=CopyStrategy.BASELINE)

        # Create a small directory (should select baseline for small dirs)
        small_dir = tmp_path / "small"
        small_dir.mkdir()
        (small_dir / "small_file.txt").write_text("small content")

        dst_dir = tmp_path / "destination"

        result = service.copy_directory(small_dir, dst_dir)

        assert result.success is True
        # For small directories, should fall back to baseline
        # (parallel/sendfile strategies return False for small dirs)

    def test_parallel_strategy_with_different_worker_counts(self, tmp_path):
        """Test parallel strategy with different worker counts."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()

        # Create multiple files
        for i in range(10):
            (src_dir / f"file_{i}.txt").write_text(f"content {i}")

        # Test with 1 worker
        service1 = FileCopyService(max_workers=1)
        dst_dir1 = tmp_path / "dest1"
        result1 = service1.copy_directory(
            src_dir, dst_dir1, strategy=CopyStrategy.PARALLEL
        )

        # Test with 4 workers
        service4 = FileCopyService(max_workers=4)
        dst_dir4 = tmp_path / "dest4"
        result4 = service4.copy_directory(
            src_dir, dst_dir4, strategy=CopyStrategy.PARALLEL
        )

        assert result1.success is True
        assert result4.success is True
        assert "1 threads" in result1.strategy_used
        assert "4 threads" in result4.strategy_used

        # Verify content copied correctly in both cases
        for i in range(10):
            assert (dst_dir1 / f"file_{i}.txt").read_text() == f"content {i}"
            assert (dst_dir4 / f"file_{i}.txt").read_text() == f"content {i}"

    def test_get_parallel_strategy_info(self):
        """Test getting parallel strategy information."""
        service = FileCopyService(max_workers=8, buffer_size_kb=2048)

        info = service.get_strategy_info(CopyStrategy.PARALLEL)
        assert info is not None
        assert "Parallel" in info["name"]
        assert "8 threads" in info["name"]
        assert "2048KB" in info["name"]
        assert info["available"] is True
        assert info["prerequisites"] == []
