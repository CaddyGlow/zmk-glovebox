"""Tests for FileCopyService simplified interface."""

import logging
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from glovebox.core.file_operations.service import FileCopyService, create_copy_service


class TestFileCopyService:
    """Test FileCopyService implementation."""

    def test_service_creation_with_defaults(self):
        """Test service creation with default settings."""
        service = FileCopyService()
        assert service.use_pipeline  # Default is pipeline

        strategies = service.get_strategies()
        assert "baseline" in strategies
        assert "pipeline" in strategies

    def test_service_creation_with_custom_settings(self):
        """Test service creation with custom settings."""
        service = FileCopyService(use_pipeline=False, max_workers=8)
        assert not service.use_pipeline

    def test_factory_function(self):
        """Test create_copy_service factory function."""
        service = create_copy_service(use_pipeline=True, max_workers=4)
        assert isinstance(service, FileCopyService)
        assert service.use_pipeline

    def test_copy_directory_basic(self, tmp_path):
        """Test basic directory copy operation."""
        service = FileCopyService()

        # Create source directory with files
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file1.txt").write_text("content1")
        (src_dir / "file2.txt").write_text("content2")

        dst_dir = tmp_path / "destination"

        # Execute copy
        result = service.copy_directory(src_dir, dst_dir)

        # Verify result
        assert result.success is True
        assert result.files_copied > 0
        assert result.duration > 0
        assert result.error is None

        # Verify files copied
        assert (dst_dir / "file1.txt").read_text() == "content1"
        assert (dst_dir / "file2.txt").read_text() == "content2"

    def test_copy_directory_with_strategy_override(self, tmp_path):
        """Test copy with strategy override."""
        service = FileCopyService(use_pipeline=True)  # Default to pipeline

        # Create source directory
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("content")

        dst_dir = tmp_path / "destination"

        # Copy with baseline strategy override
        result = service.copy_directory(src_dir, dst_dir, use_pipeline=False)

        assert result.success is True
        assert (dst_dir / "file.txt").read_text() == "content"

    def test_copy_directory_with_git_exclusion(self, tmp_path):
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
        result = service.copy_directory(src_dir, dst_dir, exclude_git=True)

        assert result.success is True
        assert (dst_dir / "file.txt").exists()
        assert not (dst_dir / ".git").exists()

    def test_copy_directory_nonexistent_source(self, tmp_path):
        """Test copy from nonexistent source."""
        service = FileCopyService()

        src_dir = tmp_path / "nonexistent"
        dst_dir = tmp_path / "destination"

        result = service.copy_directory(src_dir, dst_dir)

        assert result.success is False
        assert result.error is not None
        assert result.files_copied == 0

    def test_get_strategies(self):
        """Test getting available strategies."""
        service = FileCopyService()
        strategies = service.get_strategies()

        assert isinstance(strategies, dict)
        assert "baseline" in strategies
        assert "pipeline" in strategies
