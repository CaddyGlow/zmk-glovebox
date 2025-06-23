"""Tests for file copy strategies."""

import os
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.core.file_operations import CopyStrategy
from glovebox.core.file_operations.strategies import (
    BaselineCopyStrategy,
    BufferedCopyStrategy,
    SendfileCopyStrategy,
)


class TestBaselineCopyStrategy:
    """Test baseline copy strategy."""

    def test_strategy_properties(self):
        """Test strategy properties."""
        strategy = BaselineCopyStrategy()

        assert strategy.name == "Baseline"
        assert "shutil.copytree" in strategy.description
        assert strategy.validate_prerequisites() == []

    def test_successful_copy(self, tmp_path):
        """Test successful directory copy."""
        strategy = BaselineCopyStrategy()

        # Create source directory with files
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file1.txt").write_text("content1")
        (src_dir / "subdir").mkdir()
        (src_dir / "subdir" / "file2.txt").write_text("content2")

        # Create destination
        dst_dir = tmp_path / "destination"

        # Execute copy
        result = strategy.copy_directory(src_dir, dst_dir)

        # Verify result
        assert result.success is True
        assert result.bytes_copied > 0
        assert result.elapsed_time > 0
        assert result.strategy_used == "Baseline"
        assert result.error is None

        # Verify files copied
        assert (dst_dir / "file1.txt").read_text() == "content1"
        assert (dst_dir / "subdir" / "file2.txt").read_text() == "content2"

    def test_copy_with_git_exclusion(self, tmp_path):
        """Test copy with .git directory exclusion."""
        strategy = BaselineCopyStrategy()

        # Create source with .git directory
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("content")
        git_dir = src_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config")

        dst_dir = tmp_path / "destination"

        # Copy excluding .git
        result = strategy.copy_directory(src_dir, dst_dir, exclude_git=True)

        assert result.success is True
        assert (dst_dir / "file.txt").exists()
        assert not (dst_dir / ".git").exists()

    def test_copy_including_git(self, tmp_path):
        """Test copy including .git directory."""
        strategy = BaselineCopyStrategy()

        # Create source with .git directory
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("content")
        git_dir = src_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config")

        dst_dir = tmp_path / "destination"

        # Copy including .git
        result = strategy.copy_directory(src_dir, dst_dir, exclude_git=False)

        assert result.success is True
        assert (dst_dir / "file.txt").exists()
        assert (dst_dir / ".git" / "config").exists()

    def test_copy_overwrites_existing(self, tmp_path):
        """Test copy overwrites existing destination."""
        strategy = BaselineCopyStrategy()

        # Create source
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("new content")

        # Create existing destination
        dst_dir = tmp_path / "destination"
        dst_dir.mkdir()
        (dst_dir / "file.txt").write_text("old content")

        # Execute copy
        result = strategy.copy_directory(src_dir, dst_dir)

        assert result.success is True
        assert (dst_dir / "file.txt").read_text() == "new content"

    def test_copy_failure(self, tmp_path):
        """Test copy failure handling."""
        strategy = BaselineCopyStrategy()

        # Non-existent source
        src_dir = tmp_path / "nonexistent"
        dst_dir = tmp_path / "destination"

        result = strategy.copy_directory(src_dir, dst_dir)

        assert result.success is False
        assert result.error is not None
        assert result.bytes_copied == 0
        assert result.strategy_used == "Baseline"


class TestBufferedCopyStrategy:
    """Test buffered copy strategy."""

    def test_strategy_properties(self):
        """Test strategy properties."""
        strategy = BufferedCopyStrategy(buffer_size_kb=512)

        assert strategy.name == "Buffered (512KB)"
        assert "512KB buffer" in strategy.description
        assert strategy.validate_prerequisites() == []
        assert strategy.buffer_size == 512 * 1024

    def test_successful_buffered_copy(self, tmp_path):
        """Test successful buffered copy operation."""
        strategy = BufferedCopyStrategy(buffer_size_kb=64)

        # Create source with multiple files
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file1.txt").write_text("content1" * 1000)
        (src_dir / "subdir").mkdir()
        (src_dir / "subdir" / "file2.txt").write_text("content2" * 1000)

        dst_dir = tmp_path / "destination"

        # Execute buffered copy
        result = strategy.copy_directory(src_dir, dst_dir)

        assert result.success is True
        assert result.bytes_copied > 0
        assert result.strategy_used == "Buffered (64KB)"

        # Verify files copied correctly
        assert (dst_dir / "file1.txt").read_text() == "content1" * 1000
        assert (dst_dir / "subdir" / "file2.txt").read_text() == "content2" * 1000

    def test_git_exclusion_in_buffered_copy(self, tmp_path):
        """Test git exclusion in buffered copy."""
        strategy = BufferedCopyStrategy()

        # Create source with .git in subdirectory
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("content")
        subdir = src_dir / "subdir"
        subdir.mkdir()
        git_file = subdir / ".git" / "config"
        git_file.parent.mkdir()
        git_file.write_text("git config")

        dst_dir = tmp_path / "destination"

        # Copy excluding .git
        result = strategy.copy_directory(src_dir, dst_dir, exclude_git=True)

        assert result.success is True
        assert (dst_dir / "file.txt").exists()
        assert (dst_dir / "subdir").exists()
        assert not (dst_dir / "subdir" / ".git").exists()


class TestSendfileCopyStrategy:
    """Test sendfile copy strategy."""

    def test_strategy_properties(self):
        """Test strategy properties."""
        strategy = SendfileCopyStrategy()

        assert strategy.name == "Sendfile"
        assert "sendfile" in strategy.description

    def test_prerequisites_when_sendfile_available(self):
        """Test prerequisites when sendfile is available."""
        strategy = SendfileCopyStrategy()

        if hasattr(os, "sendfile"):
            assert strategy.validate_prerequisites() == []
        else:
            prereqs = strategy.validate_prerequisites()
            assert len(prereqs) > 0
            assert "sendfile" in prereqs[0]

    @pytest.mark.skipif(not hasattr(os, "sendfile"), reason="sendfile not available")
    def test_successful_sendfile_copy(self, tmp_path):
        """Test successful sendfile copy operation."""
        strategy = SendfileCopyStrategy()

        # Create source
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("test content")

        dst_dir = tmp_path / "destination"

        # Execute sendfile copy
        result = strategy.copy_directory(src_dir, dst_dir)

        assert result.success is True
        assert result.bytes_copied > 0
        assert result.strategy_used == "Sendfile"
        assert (dst_dir / "file.txt").read_text() == "test content"

    @pytest.mark.skipif(not hasattr(os, "sendfile"), reason="sendfile not available")
    def test_sendfile_with_fallback(self, tmp_path):
        """Test sendfile with fallback to regular copy."""
        strategy = SendfileCopyStrategy()

        # Create source
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("content")

        dst_dir = tmp_path / "destination"

        # Mock sendfile to raise OSError for fallback testing
        with patch("os.sendfile", side_effect=OSError("Mocked sendfile error")):
            result = strategy.copy_directory(src_dir, dst_dir)

            # Should still succeed with fallback
            assert result.success is True
            assert (dst_dir / "file.txt").read_text() == "content"


class TestStrategyIntegration:
    """Test strategy integration and common patterns."""

    def test_all_strategies_handle_empty_directory(self, tmp_path):
        """Test all strategies handle empty directory correctly."""
        strategies = [
            BaselineCopyStrategy(),
            BufferedCopyStrategy(),
        ]

        if hasattr(os, "sendfile"):
            strategies.append(SendfileCopyStrategy())

        # Create empty source directory
        src_dir = tmp_path / "empty_source"
        src_dir.mkdir()

        for i, strategy in enumerate(strategies):
            dst_dir = tmp_path / f"empty_dest_{i}"

            result = strategy.copy_directory(src_dir, dst_dir)

            assert result.success is True
            assert dst_dir.exists()
            assert dst_dir.is_dir()
            assert list(dst_dir.iterdir()) == []

    def test_all_strategies_preserve_file_metadata(self, tmp_path):
        """Test all strategies preserve file metadata."""
        strategies = [
            BaselineCopyStrategy(),
            BufferedCopyStrategy(),
        ]

        if hasattr(os, "sendfile"):
            strategies.append(SendfileCopyStrategy())

        # Create source with specific permissions
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        src_file = src_dir / "test.txt"
        src_file.write_text("content")
        src_file.chmod(0o644)

        original_stat = src_file.stat()

        for i, strategy in enumerate(strategies):
            dst_dir = tmp_path / f"dest_{i}"

            result = strategy.copy_directory(src_dir, dst_dir)

            assert result.success is True

            dst_file = dst_dir / "test.txt"
            assert dst_file.exists()

            # Check that some metadata is preserved (at least modification time)
            dst_stat = dst_file.stat()
            assert abs(dst_stat.st_mtime - original_stat.st_mtime) < 1.0
