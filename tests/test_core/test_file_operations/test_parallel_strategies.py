"""Tests for parallel file copy strategies."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.core.file_operations import PipelineStrategy


class TestPipelineStrategy:
    """Test pipeline copy strategy implementation."""

    @pytest.fixture
    def strategy(self):
        """Create pipeline copy strategy with test configuration."""
        return PipelineStrategy(max_workers=2)

    @pytest.fixture
    def test_directory_structure(self, tmp_path):
        """Create test directory structure with multiple files."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()

        # Create multiple files of different sizes
        (src_dir / "small.txt").write_text("small content")
        (src_dir / "medium.txt").write_text("medium content " * 100)
        (src_dir / "large.txt").write_text("large content " * 1000)

        # Create subdirectory with files
        sub_dir = src_dir / "subdir"
        sub_dir.mkdir()
        (sub_dir / "nested.txt").write_text("nested content")

        # Create empty directory
        empty_dir = src_dir / "empty"
        empty_dir.mkdir()

        return src_dir

    def test_strategy_properties(self, strategy):
        """Test strategy properties."""
        assert strategy.name == "Pipeline (2 copy workers)"
        assert strategy.max_workers == 2

    def test_copy_directory_success(self, strategy, test_directory_structure, tmp_path):
        """Test successful directory copy."""
        dst_dir = tmp_path / "destination"

        result = strategy.copy_directory(test_directory_structure, dst_dir)

        assert result.success is True
        assert result.strategy_used == "Pipeline (2 copy workers)"
        assert result.bytes_copied > 0
        assert result.duration > 0
        assert result.error is None

        # Verify files were copied
        assert (dst_dir / "small.txt").read_text() == "small content"
        assert (dst_dir / "subdir" / "nested.txt").read_text() == "nested content"
        assert (dst_dir / "empty").is_dir()

    def test_copy_directory_with_git_exclusion(self, strategy, tmp_path):
        """Test git directory exclusion."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()

        # Create regular file and .git directory
        (src_dir / "regular.txt").write_text("regular content")
        git_dir = src_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config")

        dst_dir = tmp_path / "destination"

        result = strategy.copy_directory(src_dir, dst_dir, exclude_git=True)

        assert result.success is True
        assert (dst_dir / "regular.txt").exists()
        assert not (dst_dir / ".git").exists()

    def test_copy_directory_with_git_inclusion(self, strategy, tmp_path):
        """Test git directory inclusion."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()

        # Create regular file and .git directory
        (src_dir / "regular.txt").write_text("regular content")
        git_dir = src_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config")

        dst_dir = tmp_path / "destination"

        result = strategy.copy_directory(src_dir, dst_dir, exclude_git=False)

        assert result.success is True
        assert (dst_dir / "regular.txt").exists()
        assert (dst_dir / ".git" / "config").read_text() == "git config"

    def test_copy_directory_nonexistent_source(self, strategy, tmp_path):
        """Test copying from nonexistent source."""
        src_dir = tmp_path / "nonexistent"
        dst_dir = tmp_path / "destination"

        result = strategy.copy_directory(src_dir, dst_dir)

        assert result.success is False
        assert result.error is not None
        assert result.files_copied == 0

    def test_single_worker_mode(self, tmp_path):
        """Test pipeline strategy with single worker."""
        single_worker_strategy = PipelineStrategy(max_workers=1)

        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("single worker test")

        dst_dir = tmp_path / "destination"

        result = single_worker_strategy.copy_directory(src_dir, dst_dir)

        assert result.success is True
        assert result.strategy_used is not None
        assert "1 copy workers" in result.strategy_used
        assert (dst_dir / "file.txt").read_text() == "single worker test"
