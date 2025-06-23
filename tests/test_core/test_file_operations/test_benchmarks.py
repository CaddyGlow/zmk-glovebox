"""Tests for file operations benchmarking system."""

import logging
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from glovebox.core.file_operations.benchmarks import (
    BenchmarkResult,
    FileOperationsBenchmark,
    create_benchmark_runner,
)
from glovebox.core.file_operations.enums import CopyStrategy


class TestBenchmarkResult:
    """Test benchmark result data class."""

    def test_benchmark_result_creation(self):
        """Test benchmark result creation."""
        result = BenchmarkResult(
            operation="test_op",
            method="test_method",
            duration=1.5,
            file_count=100,
            total_size=1024 * 1024,  # 1MB
            throughput_mbps=0.667,
        )

        assert result.operation == "test_op"
        assert result.method == "test_method"
        assert result.duration == 1.5
        assert result.file_count == 100
        assert result.total_size == 1024 * 1024
        assert result.throughput_mbps == 0.667
        assert result.errors is None

    def test_speed_summary_mbps(self):
        """Test speed summary in MB/s."""
        result = BenchmarkResult(
            operation="test",
            method="test",
            duration=1.0,
            file_count=1,
            total_size=1024,
            throughput_mbps=100.5,
        )

        assert result.speed_summary == "100.5 MB/s"

    def test_speed_summary_gbps(self):
        """Test speed summary in GB/s."""
        result = BenchmarkResult(
            operation="test",
            method="test",
            duration=1.0,
            file_count=1,
            total_size=1024,
            throughput_mbps=2048.0,  # 2 GB/s
        )

        assert result.speed_summary == "2.0 GB/s"

    def test_benchmark_result_with_errors(self):
        """Test benchmark result with errors."""
        result = BenchmarkResult(
            operation="failed_op",
            method="failed_method",
            duration=0.5,
            file_count=0,
            total_size=0,
            throughput_mbps=0,
            errors=["File not found", "Permission denied"],
        )

        assert result.errors == ["File not found", "Permission denied"]


class TestFileOperationsBenchmark:
    """Test file operations benchmark suite."""

    @pytest.fixture
    def benchmark(self):
        """Create benchmark instance."""
        logger = Mock(spec=logging.Logger)
        return FileOperationsBenchmark(logger)

    @pytest.fixture
    def test_workspace(self, tmp_path):
        """Create test workspace structure."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create ZMK-like structure
        for component in ["zmk", "zephyr", "modules", ".west"]:
            comp_dir = workspace / component
            comp_dir.mkdir()

            # Add some files
            (comp_dir / "main.c").write_text(f"/* {component} main file */")
            (comp_dir / "config.h").write_text(f"// {component} config")

            # Add subdirectory
            sub_dir = comp_dir / "src"
            sub_dir.mkdir()
            (sub_dir / "util.c").write_text(f"/* {component} utility */")

        return workspace

    def test_benchmark_creation(self):
        """Test benchmark instance creation."""
        benchmark = FileOperationsBenchmark()
        assert benchmark.logger is not None

    def test_create_benchmark_runner(self):
        """Test factory function."""
        logger = Mock(spec=logging.Logger)
        benchmark = create_benchmark_runner(logger)
        assert isinstance(benchmark, FileOperationsBenchmark)
        assert benchmark.logger == logger

    def test_benchmark_directory_traversal_rglob(self, benchmark, test_workspace):
        """Test directory traversal benchmark includes rglob."""
        results = benchmark.benchmark_directory_traversal(test_workspace, iterations=1)

        # Should have rglob among the results
        assert len(results) >= 1
        rglob_results = [r for r in results if r.method == "rglob"]
        assert len(rglob_results) >= 1

        result = rglob_results[0]
        assert result.operation == "directory_traversal"
        assert result.method == "rglob"
        assert result.file_count > 0
        assert result.total_size > 0
        assert result.duration > 0

    def test_benchmark_directory_traversal_both_methods(
        self, benchmark, test_workspace
    ):
        """Test directory traversal with all methods."""
        results = benchmark.benchmark_directory_traversal(test_workspace, iterations=1)

        # Should have results for all available methods (scandir, walk, listdir, rglob)
        assert len(results) >= 2
        methods = [result.method for result in results]
        assert "rglob" in methods

        # Should have at least one other method (os.walk, os.scandir, or os.listdir)
        other_methods = [m for m in methods if m != "rglob"]
        assert len(other_methods) >= 1

    def test_benchmark_directory_traversal_nonexistent(self, benchmark, tmp_path):
        """Test traversal benchmark with nonexistent directory."""
        nonexistent = tmp_path / "nonexistent"
        results = benchmark.benchmark_directory_traversal(nonexistent)

        assert len(results) == 0

    def test_benchmark_copy_strategies(self, benchmark, test_workspace, tmp_path):
        """Test copy strategy benchmarking."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch(
            "glovebox.core.file_operations.benchmarks.create_copy_service"
        ) as mock_create:
            mock_service = Mock()
            mock_service.copy_directory.return_value = Mock(
                success=True,
                bytes_copied=1024,
                elapsed_time=0.5,
                speed_mbps=2.0,
                error=None,
            )
            mock_create.return_value = mock_service

            results = benchmark.benchmark_copy_strategies(
                test_workspace,
                output_dir,
                strategies=[CopyStrategy.BASELINE, CopyStrategy.BUFFERED],
            )

        assert len(results) == 2
        for result in results:
            assert result.operation == "copy_directory"
            assert result.method in ["baseline", "buffered"]

    def test_benchmark_copy_strategies_with_failure(
        self, benchmark, test_workspace, tmp_path
    ):
        """Test copy strategy benchmark with failure."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch(
            "glovebox.core.file_operations.benchmarks.create_copy_service"
        ) as mock_create:
            mock_service = Mock()
            mock_service.copy_directory.return_value = Mock(
                success=False,
                bytes_copied=0,
                elapsed_time=0.1,
                speed_mbps=0,
                error="Simulated failure",
            )
            mock_create.return_value = mock_service

            results = benchmark.benchmark_copy_strategies(
                test_workspace, output_dir, strategies=[CopyStrategy.BASELINE]
            )

        assert len(results) == 1
        result = results[0]
        assert result.errors == ["Simulated failure"]

    def test_benchmark_parallel_workers(self, benchmark, test_workspace, tmp_path):
        """Test parallel worker count benchmarking."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch(
            "glovebox.core.file_operations.service.FileCopyService"
        ) as mock_service_class:
            mock_service = Mock()
            mock_service.copy_directory.return_value = Mock(
                success=True,
                bytes_copied=2048,
                elapsed_time=1.0,
                speed_mbps=2.0,
                error=None,
            )
            mock_service_class.return_value = mock_service

            results = benchmark.benchmark_parallel_workers(
                test_workspace, output_dir, worker_counts=[2, 4]
            )

        assert len(results) == 2
        for result in results:
            assert result.operation == "parallel_copy"
            assert "workers" in result.method

    def test_pipeline_copy_benchmark(self, benchmark, test_workspace, tmp_path):
        """Test pipeline copy benchmark."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        result = benchmark.pipeline_copy_benchmark(
            test_workspace, cache_dir, components=["zmk", "zephyr"]
        )

        assert result.operation == "pipeline_copy"
        assert result.method == "two_phase_parallel"
        assert result.duration > 0

    def test_get_component_info(self, benchmark, test_workspace):
        """Test component info extraction."""
        component, src_path, size = benchmark._get_component_info(test_workspace, "zmk")

        assert component == "zmk"
        assert src_path == test_workspace / "zmk"
        assert size > 0

    def test_get_component_info_nonexistent(self, benchmark, test_workspace):
        """Test component info for nonexistent component."""
        component, src_path, size = benchmark._get_component_info(
            test_workspace, "nonexistent"
        )

        assert component == "nonexistent"
        assert src_path == test_workspace / "nonexistent"
        assert size == 0

    def test_copy_component(self, benchmark, test_workspace, tmp_path):
        """Test component copying."""
        src_path = test_workspace / "zmk"
        dst_path = tmp_path / "zmk_copy"
        expected_size = 1000

        task = ("zmk", src_path, dst_path, expected_size)
        copied_size = benchmark._copy_component(task)

        assert copied_size == expected_size
        assert dst_path.exists()
        assert (dst_path / "main.c").exists()

    def test_copy_component_nonexistent(self, benchmark, tmp_path):
        """Test copying nonexistent component."""
        src_path = tmp_path / "nonexistent"
        dst_path = tmp_path / "copy"

        task = ("nonexistent", src_path, dst_path, 100)
        copied_size = benchmark._copy_component(task)

        assert copied_size == 0
        assert not dst_path.exists()

    def test_copy_component_with_git_exclusion(self, benchmark, tmp_path):
        """Test component copying excludes .git directories."""
        src_path = tmp_path / "component"
        src_path.mkdir()
        (src_path / "file.txt").write_text("content")

        git_dir = src_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config")

        dst_path = tmp_path / "copy"
        task = ("component", src_path, dst_path, 100)

        copied_size = benchmark._copy_component(task)

        assert copied_size == 100
        assert (dst_path / "file.txt").exists()
        assert not (dst_path / ".git").exists()

    def test_count_files(self, benchmark, test_workspace):
        """Test file counting."""
        count = benchmark._count_files(test_workspace)
        assert count > 0

    def test_count_files_nonexistent(self, benchmark, tmp_path):
        """Test file counting on nonexistent directory."""
        count = benchmark._count_files(tmp_path / "nonexistent")
        assert count == 0

    def test_run_comprehensive_benchmark(self, benchmark, test_workspace, tmp_path):
        """Test comprehensive benchmark suite."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Mock various components to speed up test
        with (
            patch.object(benchmark, "benchmark_directory_traversal") as mock_traversal,
            patch.object(benchmark, "benchmark_copy_strategies") as mock_copy,
            patch.object(benchmark, "benchmark_parallel_workers") as mock_workers,
            patch.object(benchmark, "pipeline_copy_benchmark") as mock_pipeline,
        ):
            mock_traversal.return_value = [
                BenchmarkResult("traversal", "rglob", 0.1, 10, 1024, 10.0)
            ]
            mock_copy.return_value = [
                BenchmarkResult("copy", "baseline", 0.5, 10, 1024, 2.0)
            ]
            mock_workers.return_value = [
                BenchmarkResult("parallel", "4_workers", 0.3, 10, 1024, 3.0)
            ]
            mock_pipeline.return_value = BenchmarkResult(
                "pipeline", "two_phase", 0.4, 10, 1024, 2.5
            )

            results = benchmark.run_comprehensive_benchmark(
                test_workspace, output_dir, verbose=False
            )

        assert "traversal" in results
        assert "copy_strategies" in results
        assert "parallel_workers" in results
        assert "pipeline" in results

        # Verify all mocks were called
        mock_traversal.assert_called_once()
        mock_copy.assert_called_once()
        mock_workers.assert_called_once()
        mock_pipeline.assert_called_once()

    def test_print_methods_do_not_crash(self, benchmark, capsys):
        """Test that print methods handle empty results gracefully."""
        # Test with empty results
        benchmark._print_traversal_results([])
        benchmark._print_copy_results([])
        benchmark._print_worker_results([])
        benchmark._print_pipeline_results([])

        # Should not crash and produce minimal output
        captured = capsys.readouterr()
        assert len(captured.out) == 0  # Empty results should produce no output

    def test_print_traversal_results(self, benchmark, capsys):
        """Test traversal results printing."""
        results = [
            BenchmarkResult("traversal", "rglob", 1.0, 100, 1024 * 1024, 1.0),
            BenchmarkResult("traversal", "os.walk", 0.8, 100, 1024 * 1024, 1.25),
        ]

        benchmark._print_traversal_results(results)
        captured = capsys.readouterr()

        assert "rglob" in captured.out
        assert "os.walk" in captured.out
        assert "1.0 MB/s" in captured.out

    def test_print_copy_results(self, benchmark, capsys):
        """Test copy results printing."""
        results = [
            BenchmarkResult("copy", "baseline", 1.0, 50, 512 * 1024, 0.5),
            BenchmarkResult(
                "copy", "buffered", 0.8, 50, 512 * 1024, 0.625, errors=["Error"]
            ),
        ]

        benchmark._print_copy_results(results)
        captured = capsys.readouterr()

        assert "baseline" in captured.out
        assert "buffered" in captured.out
        assert "SUCCESS" in captured.out
        assert "FAILED" in captured.out

    def test_print_worker_results(self, benchmark, capsys):
        """Test worker results printing."""
        results = [
            BenchmarkResult(
                "parallel", "parallel_2_workers", 1.0, 50, 1024 * 1024, 1.0
            ),
            BenchmarkResult(
                "parallel", "parallel_4_workers", 0.6, 50, 1024 * 1024, 1.67
            ),
        ]

        benchmark._print_worker_results(results)
        captured = capsys.readouterr()

        assert "2" in captured.out  # Worker count
        assert "4" in captured.out  # Worker count
        assert "SUCCESS" in captured.out

    def test_print_pipeline_results(self, benchmark, capsys):
        """Test pipeline results printing."""
        results = [
            BenchmarkResult(
                "pipeline",
                "two_phase_parallel",
                2.0,
                200,
                2 * 1024 * 1024 * 1024,
                1000.0,
            )
        ]

        benchmark._print_pipeline_results(results)
        captured = capsys.readouterr()

        assert "Pipeline Copy" in captured.out
        assert "2.00 GB" in captured.out
        assert "SUCCESS" in captured.out

    def test_benchmark_with_real_directory_structure(self, benchmark, tmp_path):
        """Test benchmark with real directory structure (integration test)."""
        # Create a more realistic directory structure
        workspace = tmp_path / "real_workspace"
        workspace.mkdir()

        # Create nested structure with various file sizes
        for component in ["app", "lib", "test"]:
            comp_dir = workspace / component
            comp_dir.mkdir()

            # Create files of different sizes
            (comp_dir / "small.txt").write_text("small")
            (comp_dir / "medium.txt").write_text("medium " * 100)
            (comp_dir / "large.txt").write_text("large " * 1000)

            # Create nested directories
            nested = comp_dir / "nested" / "deep"
            nested.mkdir(parents=True)
            (nested / "deep_file.txt").write_text("deep content")

        # Run traversal benchmark
        results = benchmark.benchmark_directory_traversal(workspace, iterations=1)

        # Should have at least one result
        assert len(results) >= 1

        # All results should be successful
        for result in results:
            assert result.file_count > 0
            assert result.total_size > 0
            assert result.duration >= 0

    def test_benchmark_handles_permission_errors(self, benchmark, tmp_path):
        """Test benchmark gracefully handles permission errors."""
        # Create directory structure
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "file.txt").write_text("content")

        # Mock stat to raise permission error only for specific stat calls, not directory.exists()
        original_stat = Path.stat

        def mock_stat_with_selective_error(self, follow_symlinks=True):
            # Allow directory.exists() to work, but fail on file stat calls
            if str(self).endswith("file.txt"):
                raise PermissionError("Access denied")
            return original_stat(self, follow_symlinks=follow_symlinks)

        with patch.object(Path, "stat", mock_stat_with_selective_error):
            results = benchmark.benchmark_directory_traversal(workspace, iterations=1)

        # Should still complete without crashing
        assert len(results) >= 1
        # Files might not be counted due to permission errors, but benchmark should complete
        for result in results:
            assert result.duration >= 0
