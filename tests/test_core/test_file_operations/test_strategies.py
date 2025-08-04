"""Tests for file copy strategies."""

from glovebox.core.file_operations import (
    BaselineStrategy,
    PipelineStrategy,
)


class TestBaselineStrategy:
    """Test baseline copy strategy."""

    def test_strategy_properties(self):
        """Test strategy properties."""
        strategy = BaselineStrategy()

        assert strategy.name == "Baseline"
        assert "shutil.copytree" in strategy.description
        assert strategy.validate_prerequisites() == []

    def test_successful_copy(self, tmp_path):
        """Test successful directory copy."""
        strategy = BaselineStrategy()

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
        strategy = BaselineStrategy()

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
        strategy = BaselineStrategy()

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
        strategy = BaselineStrategy()

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
        strategy = BaselineStrategy()

        # Non-existent source
        src_dir = tmp_path / "nonexistent"
        dst_dir = tmp_path / "destination"

        result = strategy.copy_directory(src_dir, dst_dir)

        assert result.success is False
        assert result.error is not None
        assert result.bytes_copied == 0
        assert result.strategy_used == "Baseline"


class TestStrategyIntegration:
    """Test strategy integration and common patterns."""

    def test_baseline_strategy_handles_empty_directory(self, tmp_path):
        """Test baseline strategy handles empty directory correctly."""
        strategy = BaselineStrategy()

        # Create empty source directory
        src_dir = tmp_path / "empty_source"
        src_dir.mkdir()

        dst_dir = tmp_path / "empty_dest"

        result = strategy.copy_directory(src_dir, dst_dir)

        assert result.success is True
        assert dst_dir.exists()
        assert dst_dir.is_dir()
        assert list(dst_dir.iterdir()) == []

    def test_pipeline_strategy_handles_empty_directory(self, tmp_path):
        """Test pipeline strategy handles empty directory correctly."""
        strategy = PipelineStrategy()

        # Create empty source directory
        src_dir = tmp_path / "empty_source"
        src_dir.mkdir()

        dst_dir = tmp_path / "empty_dest"

        result = strategy.copy_directory(src_dir, dst_dir)

        assert result.success is True
        assert dst_dir.exists()
        assert dst_dir.is_dir()
        assert list(dst_dir.iterdir()) == []

    def test_baseline_strategy_preserves_file_metadata(self, tmp_path):
        """Test baseline strategy preserves file metadata."""
        strategy = BaselineStrategy()

        # Create source with specific permissions
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        src_file = src_dir / "test.txt"
        src_file.write_text("content")
        src_file.chmod(0o644)

        original_stat = src_file.stat()

        dst_dir = tmp_path / "dest"

        result = strategy.copy_directory(src_dir, dst_dir)

        assert result.success is True

        dst_file = dst_dir / "test.txt"
        assert dst_file.exists()

        # Check that some metadata is preserved (at least modification time)
        dst_stat = dst_file.stat()
        assert abs(dst_stat.st_mtime - original_stat.st_mtime) < 1.0
