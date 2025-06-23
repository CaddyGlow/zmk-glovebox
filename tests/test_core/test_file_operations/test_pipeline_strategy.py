"""Tests for pipeline copy strategy implementation."""

import os
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.core.file_operations import CopyStrategy
from glovebox.core.file_operations.strategies import PipelineCopyStrategy


class TestPipelineCopyStrategy:
    """Test pipeline copy strategy implementation."""

    @pytest.fixture
    def strategy(self):
        """Create pipeline copy strategy with test configuration."""
        return PipelineCopyStrategy(max_workers=2, size_calculation_workers=3)

    @pytest.fixture
    def workspace_structure(self, tmp_path):
        """Create ZMK-like workspace structure with multiple components."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create typical ZMK components
        components = ["zmk", "zephyr", "modules", ".west", "app", "boards"]

        for component in components:
            comp_dir = workspace / component
            comp_dir.mkdir()

            # Add files of different sizes
            (comp_dir / "small.txt").write_text(f"{component} small content")
            (comp_dir / "medium.txt").write_text(f"{component} medium content " * 50)
            (comp_dir / "large.txt").write_text(f"{component} large content " * 200)

            # Add nested structure
            nested_dir = comp_dir / "src" / "deep"
            nested_dir.mkdir(parents=True)
            (nested_dir / "nested.c").write_text(f"/* {component} nested file */")
            (nested_dir / "nested.h").write_text(f"// {component} header")

            # Add empty subdirectory
            empty_dir = comp_dir / "empty"
            empty_dir.mkdir()

        return workspace

    @pytest.fixture
    def simple_structure(self, tmp_path):
        """Create simple directory structure without components."""
        simple_dir = tmp_path / "simple"
        simple_dir.mkdir()

        # Just a few files without component structure
        (simple_dir / "file1.txt").write_text("content 1")
        (simple_dir / "file2.txt").write_text("content 2")

        return simple_dir

    def test_strategy_properties(self, strategy):
        """Test strategy properties."""
        assert strategy.name == "Pipeline (2 copy workers)"
        assert (
            "Two-phase pipeline copy with 2 component-level workers"
            in strategy.description
        )
        assert strategy.max_workers == 2
        assert strategy.size_calculation_workers == 3

    def test_validate_prerequisites(self, strategy):
        """Test prerequisite validation."""
        missing = strategy.validate_prerequisites()
        assert missing == []  # No prerequisites for pipeline strategy

    def test_copy_directory_workspace_success(
        self, strategy, workspace_structure, tmp_path
    ):
        """Test successful workspace directory copy."""
        dst_dir = tmp_path / "destination"

        result = strategy.copy_directory(workspace_structure, dst_dir)

        assert result.success is True
        assert result.strategy_used == "Pipeline (2 copy workers)"
        assert result.bytes_copied > 0
        assert result.elapsed_time > 0
        assert result.error is None

        # Verify all components were copied
        for component in ["zmk", "zephyr", "modules", ".west", "app", "boards"]:
            comp_dir = dst_dir / component
            assert comp_dir.exists()
            assert (comp_dir / "small.txt").exists()
            assert (comp_dir / "src" / "deep" / "nested.c").exists()
            assert (comp_dir / "empty").is_dir()

    def test_copy_directory_simple_fallback(self, strategy, simple_structure, tmp_path):
        """Test fallback copy for simple directory structure."""
        dst_dir = tmp_path / "destination"

        result = strategy.copy_directory(simple_structure, dst_dir)

        assert result.success is True
        assert result.bytes_copied > 0

        # Verify files were copied
        assert (dst_dir / "file1.txt").read_text() == "content 1"
        assert (dst_dir / "file2.txt").read_text() == "content 2"

    def test_copy_directory_with_git_exclusion(self, strategy, tmp_path):
        """Test git directory exclusion."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()

        # Create component with .git directory
        comp_dir = src_dir / "component"
        comp_dir.mkdir()
        (comp_dir / "regular.txt").write_text("regular content")

        git_dir = comp_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config")

        # Create .git at root level
        root_git = src_dir / ".git"
        root_git.mkdir()
        (root_git / "HEAD").write_text("ref: refs/heads/main")

        dst_dir = tmp_path / "destination"

        result = strategy.copy_directory(src_dir, dst_dir, exclude_git=True)

        assert result.success is True
        assert (dst_dir / "component" / "regular.txt").exists()
        assert not (dst_dir / "component" / ".git").exists()
        assert not (dst_dir / ".git").exists()

    def test_copy_directory_with_git_inclusion(self, strategy, tmp_path):
        """Test git directory inclusion."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()

        # Create component with .git directory
        comp_dir = src_dir / "component"
        comp_dir.mkdir()
        (comp_dir / "regular.txt").write_text("regular content")

        git_dir = comp_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config")

        dst_dir = tmp_path / "destination"

        result = strategy.copy_directory(src_dir, dst_dir, exclude_git=False)

        assert result.success is True
        assert (dst_dir / "component" / "regular.txt").exists()
        assert (dst_dir / "component" / ".git" / "config").read_text() == "git config"

    def test_copy_directory_existing_destination(
        self, strategy, workspace_structure, tmp_path
    ):
        """Test copying to existing destination."""
        dst_dir = tmp_path / "destination"
        dst_dir.mkdir()
        (dst_dir / "existing.txt").write_text("existing content")

        result = strategy.copy_directory(workspace_structure, dst_dir)

        assert result.success is True
        # Existing content should be removed
        assert not (dst_dir / "existing.txt").exists()
        # New content should be present
        assert (dst_dir / "zmk").exists()

    def test_copy_directory_nonexistent_source(self, strategy, tmp_path):
        """Test copying from nonexistent source."""
        src_dir = tmp_path / "nonexistent"
        dst_dir = tmp_path / "destination"

        result = strategy.copy_directory(src_dir, dst_dir)

        assert result.success is False
        assert result.error is not None
        assert "does not exist" in result.error
        assert result.bytes_copied == 0

    def test_copy_directory_file_as_source(self, strategy, tmp_path):
        """Test copying when source is a file, not directory."""
        src_file = tmp_path / "source.txt"
        src_file.write_text("file content")
        dst_dir = tmp_path / "destination"

        result = strategy.copy_directory(src_file, dst_dir)

        assert result.success is False
        assert result.error is not None
        assert "not a directory" in result.error

    def test_get_component_info(self, strategy, workspace_structure):
        """Test component info extraction."""
        component, src_path, size = strategy._get_component_info(
            workspace_structure, "zmk"
        )

        assert component == "zmk"
        assert src_path == workspace_structure / "zmk"
        assert size > 0

    def test_get_component_info_nonexistent(self, strategy, workspace_structure):
        """Test component info for nonexistent component."""
        component, src_path, size = strategy._get_component_info(
            workspace_structure, "nonexistent"
        )

        assert component == "nonexistent"
        assert src_path == workspace_structure / "nonexistent"
        assert size == 0

    def test_copy_component_success(self, strategy, tmp_path):
        """Test successful component copying."""
        # Create source component
        src_comp = tmp_path / "source_comp"
        src_comp.mkdir()
        (src_comp / "file1.txt").write_text("content 1")
        (src_comp / "file2.txt").write_text("content 2")

        sub_dir = src_comp / "subdir"
        sub_dir.mkdir()
        (sub_dir / "nested.txt").write_text("nested content")

        dst_comp = tmp_path / "dest_comp"
        expected_size = 1000

        task = ("test_comp", src_comp, dst_comp, expected_size)
        copied_size = strategy._copy_component(task, exclude_git=False)

        assert copied_size > 0
        assert dst_comp.exists()
        assert (dst_comp / "file1.txt").read_text() == "content 1"
        assert (dst_comp / "subdir" / "nested.txt").read_text() == "nested content"

    def test_copy_component_with_git_exclusion(self, strategy, tmp_path):
        """Test component copying with git exclusion."""
        # Create source component with .git
        src_comp = tmp_path / "source_comp"
        src_comp.mkdir()
        (src_comp / "regular.txt").write_text("regular content")

        git_dir = src_comp / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config")

        dst_comp = tmp_path / "dest_comp"
        task = ("test_comp", src_comp, dst_comp, 100)

        copied_size = strategy._copy_component(task, exclude_git=True)

        assert copied_size > 0
        assert (dst_comp / "regular.txt").exists()
        assert not (dst_comp / ".git").exists()

    def test_copy_component_nonexistent(self, strategy, tmp_path):
        """Test copying nonexistent component."""
        src_comp = tmp_path / "nonexistent"
        dst_comp = tmp_path / "dest_comp"

        task = ("nonexistent", src_comp, dst_comp, 100)
        copied_size = strategy._copy_component(task, exclude_git=False)

        assert copied_size == 0
        assert not dst_comp.exists()

    def test_copy_component_handles_errors(self, strategy, tmp_path):
        """Test component copying handles errors gracefully."""
        # Create source component
        src_comp = tmp_path / "source_comp"
        src_comp.mkdir()
        (src_comp / "file.txt").write_text("content")

        # Create destination that will cause conflict
        dst_comp = tmp_path / "dest_comp"
        dst_comp.write_text("this is a file, not a directory")

        task = ("test_comp", src_comp, dst_comp, 100)

        # Mock shutil.copytree to raise an exception
        with patch("shutil.copytree", side_effect=OSError("Permission denied")):
            copied_size = strategy._copy_component(task, exclude_git=False)

        assert copied_size == 0

    def test_fallback_copy_success(self, strategy, simple_structure, tmp_path):
        """Test fallback copy operation."""
        dst_dir = tmp_path / "destination"
        start_time = 1000.0

        result = strategy._fallback_copy(
            simple_structure, dst_dir, exclude_git=False, start_time=start_time
        )

        assert result.success is True
        assert "(fallback)" in result.strategy_used
        assert result.bytes_copied > 0
        assert (dst_dir / "file1.txt").exists()

    def test_fallback_copy_with_git_exclusion(self, strategy, tmp_path):
        """Test fallback copy with git exclusion."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        (src_dir / "regular.txt").write_text("regular")

        git_dir = src_dir / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config")

        dst_dir = tmp_path / "destination"
        start_time = 1000.0

        result = strategy._fallback_copy(
            src_dir, dst_dir, exclude_git=True, start_time=start_time
        )

        assert result.success is True
        assert (dst_dir / "regular.txt").exists()
        assert not (dst_dir / ".git").exists()

    def test_fallback_copy_handles_errors(self, strategy, tmp_path):
        """Test fallback copy handles errors."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        dst_dir = tmp_path / "destination"
        start_time = 1000.0

        # Mock shutil.copytree to raise an exception
        with patch("shutil.copytree", side_effect=OSError("Operation failed")):
            result = strategy._fallback_copy(
                src_dir, dst_dir, exclude_git=False, start_time=start_time
            )

        assert result.success is False
        assert result.error is not None
        assert "Operation failed" in result.error

    def test_fast_directory_stats_with_scandir(self, strategy, workspace_structure):
        """Test directory stats using scandir."""
        file_count, total_size = strategy._fast_directory_stats(workspace_structure)

        assert file_count > 0
        assert total_size > 0

    def test_fast_directory_stats_fallback(self, strategy, workspace_structure):
        """Test directory stats with rglob fallback."""
        with patch(
            "glovebox.core.file_operations.strategies.hasattr", return_value=False
        ):
            file_count, total_size = strategy._fast_directory_stats(workspace_structure)

        assert file_count > 0
        assert total_size > 0

    def test_scandir_stats_recursive(self, strategy, workspace_structure):
        """Test scandir stats calculation."""
        file_count, total_size = strategy._scandir_stats(workspace_structure)

        assert file_count > 0
        assert total_size > 0

    def test_calculate_directory_size(self, strategy, workspace_structure):
        """Test directory size calculation."""
        size = strategy._calculate_directory_size(workspace_structure)
        assert size > 0

    def test_calculate_directory_size_nonexistent(self, strategy, tmp_path):
        """Test directory size calculation for nonexistent directory."""
        nonexistent = tmp_path / "nonexistent"
        size = strategy._calculate_directory_size(nonexistent)
        assert size == 0

    def test_parallel_component_copying(self, strategy, tmp_path):
        """Test parallel component copying behavior."""
        # Create multiple components
        src_dir = tmp_path / "source"
        src_dir.mkdir()

        components = ["comp1", "comp2", "comp3", "comp4"]
        for comp in components:
            comp_dir = src_dir / comp
            comp_dir.mkdir()
            (comp_dir / "file.txt").write_text(f"{comp} content")

        dst_dir = tmp_path / "destination"

        result = strategy.copy_directory(src_dir, dst_dir)

        assert result.success is True
        # Verify all components copied
        for comp in components:
            assert (dst_dir / comp / "file.txt").read_text() == f"{comp} content"

    def test_component_copy_error_handling(self, strategy, tmp_path):
        """Test handling of individual component copy errors."""
        # Create source with multiple components
        src_dir = tmp_path / "source"
        src_dir.mkdir()

        # Create normal component
        good_comp = src_dir / "good_comp"
        good_comp.mkdir()
        (good_comp / "file.txt").write_text("good content")

        # Create component that will cause error
        bad_comp = src_dir / "bad_comp"
        bad_comp.mkdir()
        (bad_comp / "file.txt").write_text("bad content")

        dst_dir = tmp_path / "destination"

        # Mock _copy_component to simulate failure for bad_comp
        original_copy = strategy._copy_component

        def mock_copy(task, exclude_git):
            component, src_path, dst_path, expected_size = task
            if "bad_comp" in str(src_path):
                raise OSError("Simulated component error")
            return original_copy(task, exclude_git)

        strategy._copy_component = mock_copy

        result = strategy.copy_directory(src_dir, dst_dir)

        # Should still succeed overall despite individual component failure
        assert result.success is True
        # Good component should be copied
        assert (dst_dir / "good_comp" / "file.txt").exists()

    def test_empty_workspace_handling(self, strategy, tmp_path):
        """Test handling of empty workspace."""
        src_dir = tmp_path / "empty_workspace"
        src_dir.mkdir()
        # No components, completely empty

        dst_dir = tmp_path / "destination"

        result = strategy.copy_directory(src_dir, dst_dir)

        # Should succeed (empty directory copy)
        assert result.success is True

    def test_single_file_component(self, strategy, tmp_path):
        """Test workspace with single file instead of directory."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()

        # Create file instead of component directory
        (src_dir / "single_file.txt").write_text("single file content")

        dst_dir = tmp_path / "destination"

        result = strategy.copy_directory(src_dir, dst_dir)

        # Should handle gracefully (no directories to process as components)
        assert result.success is True
        assert (dst_dir / "single_file.txt").read_text() == "single file content"

    def test_large_component_count(self, strategy, tmp_path):
        """Test performance with many components."""
        # Create strategy with more workers for this test
        large_strategy = PipelineCopyStrategy(max_workers=4, size_calculation_workers=6)

        src_dir = tmp_path / "source"
        src_dir.mkdir()

        # Create many components
        for i in range(20):
            comp_dir = src_dir / f"component_{i:02d}"
            comp_dir.mkdir()
            (comp_dir / "file.txt").write_text(f"component {i} content")

        dst_dir = tmp_path / "destination"

        result = large_strategy.copy_directory(src_dir, dst_dir)

        assert result.success is True
        # Verify all components copied
        for i in range(20):
            assert (dst_dir / f"component_{i:02d}" / "file.txt").exists()

    def test_mixed_component_sizes(self, strategy, tmp_path):
        """Test with components of varying sizes."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()

        # Small component
        small_comp = src_dir / "small"
        small_comp.mkdir()
        (small_comp / "tiny.txt").write_text("small")

        # Medium component
        medium_comp = src_dir / "medium"
        medium_comp.mkdir()
        (medium_comp / "medium.txt").write_text("medium content " * 100)

        # Large component
        large_comp = src_dir / "large"
        large_comp.mkdir()
        (large_comp / "large.txt").write_text("large content " * 1000)

        dst_dir = tmp_path / "destination"

        result = strategy.copy_directory(src_dir, dst_dir)

        assert result.success is True
        assert result.bytes_copied > 0
        # All components should be copied regardless of size
        assert (dst_dir / "small" / "tiny.txt").exists()
        assert (dst_dir / "medium" / "medium.txt").exists()
        assert (dst_dir / "large" / "large.txt").exists()

    def test_permission_error_handling(self, strategy, tmp_path):
        """Test handling of permission errors during size calculation."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()

        comp_dir = src_dir / "component"
        comp_dir.mkdir()
        (comp_dir / "file.txt").write_text("content")

        # Mock os.scandir to raise permission error
        with patch("os.scandir", side_effect=PermissionError("Access denied")):
            file_count, total_size = strategy._fast_directory_stats(src_dir)

        # Should handle gracefully and return 0 values
        assert file_count == 0
        assert total_size == 0

    def test_different_worker_configurations(self, tmp_path):
        """Test strategy with different worker configurations."""
        # Test minimal workers
        minimal_strategy = PipelineCopyStrategy(
            max_workers=1, size_calculation_workers=1
        )

        # Test many workers
        many_workers_strategy = PipelineCopyStrategy(
            max_workers=8, size_calculation_workers=12
        )

        # Create test workspace
        src_dir = tmp_path / "source"
        src_dir.mkdir()

        for i in range(3):
            comp_dir = src_dir / f"comp_{i}"
            comp_dir.mkdir()
            (comp_dir / "file.txt").write_text(f"content {i}")

        # Test both configurations
        for strategy_name, strategy in [
            ("minimal", minimal_strategy),
            ("many", many_workers_strategy),
        ]:
            dst_dir = tmp_path / f"destination_{strategy_name}"

            result = strategy.copy_directory(src_dir, dst_dir)

            assert result.success is True
            for i in range(3):
                assert (dst_dir / f"comp_{i}" / "file.txt").exists()
