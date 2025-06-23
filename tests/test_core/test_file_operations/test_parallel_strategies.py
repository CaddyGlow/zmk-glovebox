"""Tests for parallel file copy strategies."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.core.file_operations import CopyStrategy
from glovebox.core.file_operations.strategies import ParallelCopyStrategy


class TestParallelCopyStrategy:
    """Test parallel copy strategy implementation."""

    @pytest.fixture
    def strategy(self):
        """Create parallel copy strategy with test configuration."""
        return ParallelCopyStrategy(max_workers=2, buffer_size_kb=512)

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
        assert strategy.name == "Parallel (2 threads, 512KB)"
        assert (
            "Multithreaded copy with 2 workers and 512KB buffer" in strategy.description
        )
        assert strategy.max_workers == 2
        assert strategy.buffer_size_kb == 512
        assert strategy.buffer_size == 512 * 1024

    def test_validate_prerequisites(self, strategy):
        """Test prerequisite validation."""
        missing = strategy.validate_prerequisites()
        assert missing == []  # No prerequisites for parallel strategy

    def test_copy_directory_success(self, strategy, test_directory_structure, tmp_path):
        """Test successful directory copy."""
        dst_dir = tmp_path / "destination"

        result = strategy.copy_directory(test_directory_structure, dst_dir)

        assert result.success is True
        assert result.strategy_used == "Parallel (2 threads, 512KB)"
        assert result.bytes_copied > 0
        assert result.elapsed_time > 0
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

    def test_copy_directory_existing_destination(
        self, strategy, test_directory_structure, tmp_path
    ):
        """Test copying to existing destination."""
        dst_dir = tmp_path / "destination"
        dst_dir.mkdir()
        (dst_dir / "existing.txt").write_text("existing content")

        result = strategy.copy_directory(test_directory_structure, dst_dir)

        assert result.success is True
        # Existing content should be removed
        assert not (dst_dir / "existing.txt").exists()
        # New content should be present
        assert (dst_dir / "small.txt").exists()

    def test_copy_directory_nonexistent_source(self, strategy, tmp_path):
        """Test copying from nonexistent source."""
        src_dir = tmp_path / "nonexistent"
        dst_dir = tmp_path / "destination"

        result = strategy.copy_directory(src_dir, dst_dir)

        assert result.success is False
        assert result.error is not None
        assert result.bytes_copied == 0

    def test_copy_file_buffered(self, strategy, tmp_path):
        """Test individual file copy with buffering."""
        src_file = tmp_path / "source.txt"
        src_file.write_text("test content for buffered copy")

        dst_file = tmp_path / "destination.txt"

        size = strategy._copy_file_buffered(src_file, dst_file)

        assert size > 0
        assert dst_file.read_text() == "test content for buffered copy"
        assert dst_file.stat().st_size == src_file.stat().st_size

    def test_copy_file_buffered_with_subdirectory(self, strategy, tmp_path):
        """Test file copy creates parent directories."""
        src_file = tmp_path / "source.txt"
        src_file.write_text("test content")

        dst_file = tmp_path / "subdir" / "nested" / "destination.txt"

        size = strategy._copy_file_buffered(src_file, dst_file)

        assert size > 0
        assert dst_file.exists()
        assert dst_file.read_text() == "test content"

    def test_traverse_directory_fallback(self, strategy, test_directory_structure):
        """Test directory traversal with rglob fallback."""
        with patch(
            "glovebox.core.file_operations.strategies.hasattr", return_value=False
        ):
            items = list(strategy._traverse_directory(test_directory_structure))

        # Should find all files and directories
        paths = [item.name for item in items]
        assert "small.txt" in paths
        assert "subdir" in paths
        assert "nested.txt" in paths

    def test_traverse_directory_with_scandir(self, strategy, test_directory_structure):
        """Test directory traversal with scandir."""
        items = list(strategy._traverse_directory(test_directory_structure))

        # Should find all files and directories
        paths = [item.name for item in items]
        assert "small.txt" in paths
        assert "subdir" in paths
        assert "nested.txt" in paths

    def test_fast_directory_stats_fallback(self, strategy, test_directory_structure):
        """Test directory stats with rglob fallback."""
        with patch(
            "glovebox.core.file_operations.strategies.hasattr", return_value=False
        ):
            file_count, total_size = strategy._fast_directory_stats(
                test_directory_structure
            )

        assert file_count > 0
        assert total_size > 0

    def test_fast_directory_stats_with_scandir(
        self, strategy, test_directory_structure
    ):
        """Test directory stats with scandir."""
        file_count, total_size = strategy._fast_directory_stats(
            test_directory_structure
        )

        assert file_count > 0
        assert total_size > 0

    def test_copy_directory_handles_file_errors(self, strategy, tmp_path):
        """Test handling of individual file copy errors."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()

        # Create some files
        (src_dir / "good1.txt").write_text("good content 1")
        (src_dir / "good2.txt").write_text("good content 2")

        dst_dir = tmp_path / "destination"

        # Mock _copy_file_buffered to simulate some failures
        original_copy = strategy._copy_file_buffered

        def mock_copy(src_file, dst_file):
            if "good1" in str(src_file):
                raise OSError("Simulated file error")
            return original_copy(src_file, dst_file)

        strategy._copy_file_buffered = mock_copy

        result = strategy.copy_directory(src_dir, dst_dir)

        # Should still succeed overall despite individual file failures
        assert result.success is True
        # Should have copied at least one file
        assert (dst_dir / "good2.txt").exists()

    def test_thread_safety_simulation(self, strategy, tmp_path):
        """Test thread safety by simulating concurrent operations."""
        import threading
        import time

        src_dir = tmp_path / "source"
        src_dir.mkdir()

        # Create multiple files
        for i in range(10):
            (src_dir / f"file_{i}.txt").write_text(f"content {i}")

        results = []
        errors = []

        def copy_operation(thread_id):
            try:
                dst_dir = tmp_path / f"destination_{thread_id}"
                result = strategy.copy_directory(src_dir, dst_dir)
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Run multiple copy operations concurrently
        threads = []
        for i in range(3):
            thread = threading.Thread(target=copy_operation, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All operations should succeed
        assert len(errors) == 0
        assert len(results) == 3
        assert all(result.success for result in results)

    def test_large_buffer_handling(self, tmp_path):
        """Test strategy with large buffer size."""
        # Create strategy with very large buffer
        large_buffer_strategy = ParallelCopyStrategy(max_workers=2, buffer_size_kb=8192)

        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "large_file.txt").write_text("X" * 10000)  # 10KB file

        dst_dir = tmp_path / "destination"

        result = large_buffer_strategy.copy_directory(src_dir, dst_dir)

        assert result.success is True
        assert (dst_dir / "large_file.txt").stat().st_size == 10000

    def test_single_worker_mode(self, tmp_path):
        """Test parallel strategy with single worker."""
        single_worker_strategy = ParallelCopyStrategy(max_workers=1, buffer_size_kb=512)

        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("single worker test")

        dst_dir = tmp_path / "destination"

        result = single_worker_strategy.copy_directory(src_dir, dst_dir)

        assert result.success is True
        assert "1 threads" in result.strategy_used
        assert (dst_dir / "file.txt").read_text() == "single worker test"

    def test_many_workers_mode(self, tmp_path):
        """Test parallel strategy with many workers."""
        many_workers_strategy = ParallelCopyStrategy(max_workers=16, buffer_size_kb=512)

        src_dir = tmp_path / "source"
        src_dir.mkdir()

        # Create many small files to utilize workers
        for i in range(20):
            (src_dir / f"file_{i:02d}.txt").write_text(f"content {i}")

        dst_dir = tmp_path / "destination"

        result = many_workers_strategy.copy_directory(src_dir, dst_dir)

        assert result.success is True
        assert "16 threads" in result.strategy_used

        # Verify all files copied
        for i in range(20):
            assert (dst_dir / f"file_{i:02d}.txt").read_text() == f"content {i}"
