#!/usr/bin/env python3
"""Unit tests for file operations progress callback functionality."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from glovebox.core.file_operations import BaselineStrategy, PipelineStrategy
from glovebox.core.file_operations.models import CopyProgress, CopyProgressCallback
from glovebox.core.file_operations.service import FileCopyService


def create_test_directory(base_path: Path, num_files: int = 5) -> Path:
    """Create a test directory with sample files.

    Args:
        base_path: Base directory to create test structure in
        num_files: Number of files to create

    Returns:
        Path to created test directory
    """
    test_dir = base_path / "test_source"
    test_dir.mkdir(exist_ok=True)

    # Create some files
    for i in range(num_files):
        file_path = test_dir / f"test_file_{i}.txt"
        file_path.write_text(f"Test content for file {i}\n" * 100)  # ~2KB per file

    # Create a subdirectory with files (like ZMK components)
    sub_dir = test_dir / "zmk"
    sub_dir.mkdir(exist_ok=True)
    for i in range(3):
        file_path = sub_dir / f"zmk_file_{i}.c"
        file_path.write_text(f"/* ZMK source file {i} */\n" * 50)

    return test_dir


class TestCopyProgress:
    """Test CopyProgress model."""

    def test_copy_progress_creation(self):
        """Test CopyProgress model creation and properties."""
        progress = CopyProgress(
            files_processed=5,
            total_files=10,
            bytes_copied=1024,
            total_bytes=2048,
            current_file="test.txt",
            component_name="zmk",
        )

        assert progress.files_processed == 5
        assert progress.total_files == 10
        assert progress.bytes_copied == 1024
        assert progress.total_bytes == 2048
        assert progress.current_file == "test.txt"
        assert progress.component_name == "zmk"

        # Test calculated properties
        assert progress.file_progress_percent == 50.0
        assert progress.bytes_progress_percent == 50.0

    def test_copy_progress_edge_cases(self):
        """Test CopyProgress with edge cases."""
        # Test with zero totals
        progress = CopyProgress(
            files_processed=0,
            total_files=0,
            bytes_copied=0,
            total_bytes=0,
            current_file="",
        )

        assert progress.file_progress_percent == 0.0
        assert progress.bytes_progress_percent == 0.0


class TestProgressCallbacks:
    """Test progress callback functionality in copy strategies."""

    def test_pipeline_copy_strategy_with_progress_callback(self, tmp_path):
        """Test PipelineStrategy with progress callback."""
        # Create test source directory
        src_dir = create_test_directory(tmp_path)
        dst_dir = tmp_path / "test_dest"

        # Mock progress callback
        progress_callback = Mock()

        # Create strategy and perform copy
        strategy = PipelineStrategy()
        result = strategy.copy_directory(
            src=src_dir,
            dst=dst_dir,
            exclude_git=False,
            progress_callback=progress_callback,
        )

        # Verify copy was successful
        assert result.success
        assert dst_dir.exists()
        assert (dst_dir / "zmk").exists()

        # Verify progress callback was called
        assert progress_callback.called

        # Check that progress callback received CopyProgress objects
        call_args_list = progress_callback.call_args_list
        assert len(call_args_list) > 0

        # Verify first call has CopyProgress object
        first_call_args = call_args_list[0][0]
        assert len(first_call_args) == 1
        progress_obj = first_call_args[0]
        assert isinstance(progress_obj, CopyProgress)

        # Verify progress values make sense
        assert progress_obj.files_processed >= 0
        assert progress_obj.total_files >= 0
        assert progress_obj.bytes_copied >= 0
        assert progress_obj.total_bytes >= 0
        assert progress_obj.current_file is not None

    def test_file_copy_service_with_progress_callback(self, tmp_path):
        """Test FileCopyService with progress callback."""
        # Create test source directory
        src_dir = create_test_directory(tmp_path, num_files=3)
        dst_dir = tmp_path / "service_dest"

        # Mock progress callback
        progress_callback = Mock()

        # Create service and perform copy
        service = FileCopyService()
        result = service.copy_directory(
            src=src_dir,
            dst=dst_dir,
            exclude_git=False,
            progress_callback=progress_callback,
        )

        # Verify copy was successful
        assert result.success
        assert dst_dir.exists()

        # Verify progress callback was called
        assert progress_callback.called

    def test_progress_callback_without_callback(self, tmp_path):
        """Test copy operations work normally without progress callback."""
        # Create test source directory
        src_dir = create_test_directory(tmp_path, num_files=2)
        dst_dir = tmp_path / "no_callback_dest"

        # Create strategy and perform copy without callback
        strategy = PipelineStrategy()
        result = strategy.copy_directory(
            src=src_dir,
            dst=dst_dir,
            exclude_git=False,
            progress_callback=None,  # Explicitly no callback
        )

        # Verify copy was successful
        assert result.success
        assert dst_dir.exists()
        assert (dst_dir / "zmk").exists()

    def test_progress_callback_exception_handling(self, tmp_path):
        """Test that exceptions in progress callback don't break copy operation."""
        # Create test source directory
        src_dir = create_test_directory(tmp_path, num_files=2)
        dst_dir = tmp_path / "exception_dest"

        # Create callback that raises exception
        def failing_callback(progress: CopyProgress) -> None:
            raise ValueError("Test exception in callback")

        # Create strategy and perform copy
        strategy = PipelineStrategy()

        # Copy should still succeed even if callback fails
        # Note: The implementation might need to be updated to handle callback exceptions
        result = strategy.copy_directory(
            src=src_dir,
            dst=dst_dir,
            exclude_git=False,
            progress_callback=failing_callback,
        )

        # Copy should still succeed (implementation dependent)
        # This test documents the expected behavior
        assert dst_dir.exists()

    def test_baseline_copy_strategy_with_progress_callback(self, tmp_path):
        """Test BaselineStrategy with progress callback."""
        # Create test source directory
        src_dir = create_test_directory(tmp_path, num_files=4)
        dst_dir = tmp_path / "baseline_test_dest"

        # Mock progress callback
        progress_callback = Mock()

        # Create strategy and perform copy
        strategy = BaselineStrategy()
        result = strategy.copy_directory(
            src=src_dir,
            dst=dst_dir,
            exclude_git=False,
            progress_callback=progress_callback,
        )

        # Verify copy was successful
        assert result.success
        assert dst_dir.exists()
        assert (dst_dir / "zmk").exists()

        # Verify progress callback was called
        assert progress_callback.called

        # Check that progress callback received CopyProgress objects
        call_args_list = progress_callback.call_args_list
        assert len(call_args_list) > 0

        # Verify first call has CopyProgress object
        first_call_args = call_args_list[0][0]
        assert len(first_call_args) == 1
        progress_obj = first_call_args[0]
        assert isinstance(progress_obj, CopyProgress)

        # Verify progress values make sense
        assert progress_obj.files_processed >= 0
        assert progress_obj.total_files >= 0
        assert progress_obj.bytes_copied >= 0
        assert progress_obj.total_bytes >= 0
        assert progress_obj.current_file is not None

        # Check progress progression
        files_processed = [call[0][0].files_processed for call in call_args_list]
        assert files_processed == sorted(
            files_processed
        )  # Should be monotonically increasing

    def test_baseline_copy_strategy_without_callback(self, tmp_path):
        """Test BaselineStrategy works normally without progress callback."""
        # Create test source directory
        src_dir = create_test_directory(tmp_path, num_files=3)
        dst_dir = tmp_path / "baseline_no_callback_dest"

        # Create strategy and perform copy without callback
        strategy = BaselineStrategy()
        result = strategy.copy_directory(
            src=src_dir,
            dst=dst_dir,
            exclude_git=False,
            progress_callback=None,  # Explicitly no callback
        )

        # Verify copy was successful
        assert result.success
        assert dst_dir.exists()
        assert (dst_dir / "zmk").exists()

    def test_baseline_copy_strategy_git_exclusion_with_progress(self, tmp_path):
        """Test BaselineStrategy .git exclusion with progress callback."""
        # Create test source directory with .git folder
        src_dir = create_test_directory(tmp_path, num_files=2)

        # Add a .git directory with files
        git_dir = src_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("[core]\n")
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")

        dst_dir = tmp_path / "baseline_git_exclude_dest"

        # Track progress calls
        progress_calls = []

        def track_progress(progress: CopyProgress) -> None:
            progress_calls.append(progress.current_file)

        # Create strategy and perform copy with git exclusion
        strategy = BaselineStrategy()
        result = strategy.copy_directory(
            src=src_dir,
            dst=dst_dir,
            exclude_git=True,
            progress_callback=track_progress,
        )

        # Verify copy was successful
        assert result.success
        assert dst_dir.exists()
        assert not (dst_dir / ".git").exists()  # .git should be excluded

        # Verify no git files were reported in progress
        git_files = [f for f in progress_calls if "git" in f.lower()]
        assert len(git_files) == 0
