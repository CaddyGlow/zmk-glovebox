#!/usr/bin/env python3
"""Demo script for file operations benchmarking.

This script demonstrates the comprehensive benchmarking capabilities
of the file operations module with multithreading and performance optimization.
"""

import logging
import tempfile
from pathlib import Path

import pytest

from glovebox.core.file_operations import create_benchmark_runner


def create_test_workspace(base_path: Path, size_mb: int = 10) -> Path:
    """Create a test workspace with sample files for benchmarking.

    Args:
        base_path: Base directory to create workspace in
        size_mb: Approximate size in MB to create

    Returns:
        Path to created workspace
    """
    workspace = base_path / "test_workspace"
    workspace.mkdir(exist_ok=True)

    # Create ZMK-style directory structure
    components = ["zmk", "zephyr", "modules", ".west"]

    for component in components:
        comp_dir = workspace / component
        comp_dir.mkdir(exist_ok=True)

        # Create subdirectories and files
        for i in range(3):
            sub_dir = comp_dir / f"subdir_{i}"
            sub_dir.mkdir(exist_ok=True)

            # Create files with some content
            for j in range(5):
                file_path = sub_dir / f"file_{j}.txt"
                # Create files with approximately size_mb/20 MB each
                content_size = (
                    size_mb * 1024 * 1024
                ) // 60  # Distribute across ~60 files
                content = "x" * max(1024, content_size)  # At least 1KB per file
                file_path.write_text(content)

    return workspace


def test_comprehensive_file_operations_benchmark(
    tmp_path, workspace_path_override=None
):
    """Comprehensive test of file operations benchmarking system.

    Args:
        tmp_path: Temporary directory for test isolation
        workspace_path_override: Optional existing workspace path to use instead of creating one
    """
    # Enable logging to see benchmark progress
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("\n" + "=" * 60)
    print("FILE OPERATIONS BENCHMARK DEMO")
    print("=" * 60)

    # Use provided workspace or create test workspace
    if workspace_path_override:
        workspace_path = Path(workspace_path_override)
        print(f"\n1. Using provided workspace: {workspace_path}")
        if not workspace_path.exists():
            raise ValueError(
                f"Provided workspace path does not exist: {workspace_path}"
            )
    else:
        print("\n1. Creating test workspace...")
        workspace_path = create_test_workspace(
            tmp_path, size_mb=100
        )  # Reasonable size for tests
        print(f"   Created workspace: {workspace_path}")

    output_dir = tmp_path / "benchmark_output"
    print(f"   Output dir: {output_dir}")

    # Create benchmark runner
    benchmark = create_benchmark_runner()

    print("\n2. Running comprehensive benchmark suite...")
    print("   This will test:")
    print("   - Directory traversal (rglob vs psutil)")
    print("   - Copy strategies (baseline, buffered, parallel, sendfile)")
    print("   - Parallel worker scaling (1, 2, 4, 8 threads)")
    print("   - Pipeline copy approach (two-phase parallel)")

    # Run comprehensive benchmark
    results = benchmark.run_comprehensive_benchmark(
        workspace_path=workspace_path, output_dir=output_dir, verbose=True
    )

    print("\n3. Benchmark Results Summary:")
    print("-" * 40)

    for category, result_list in results.items():
        print(f"\n{category.upper()}:")
        for result in result_list:
            status = "SUCCESS" if not result.errors else f"FAILED: {result.errors[0]}"
            print(
                f"  {result.method:<20} {result.duration:>6.2f}s  {result.speed_summary:>10}  {status}"
            )

    # Verify we got results
    assert "traversal" in results
    assert "copy_strategies" in results
    assert "parallel_workers" in results
    assert "pipeline" in results

    # At least one result per category
    assert len(results["traversal"]) >= 1
    assert len(results["copy_strategies"]) >= 1
    assert len(results["parallel_workers"]) >= 1
    assert len(results["pipeline"]) == 1

    print("\n4. Individual Benchmark Examples:")
    print("-" * 40)

    # Example 1: Just directory traversal
    print("\nDirectory Traversal Benchmark (rglob vs psutil):")
    traversal_results = benchmark.benchmark_directory_traversal(
        workspace_path, iterations=2
    )
    for result in traversal_results:
        print(
            f"  {result.method}: {result.duration:.3f}s, {result.file_count} files, {result.speed_summary}"
        )

    # Example 2: Pipeline copy (matches user's example)
    print("\nPipeline Copy Benchmark (two-phase parallel):")
    pipeline_result = benchmark.pipeline_copy_benchmark(
        workspace_path=workspace_path,
        cache_dir=output_dir / "pipeline_test",
        components=["zmk", "zephyr", "modules"],
    )
    print(
        f"  Pipeline: {pipeline_result.duration:.3f}s, {pipeline_result.file_count} files, {pipeline_result.speed_summary}"
    )

    print("\n" + "=" * 60)
    print("BENCHMARK DEMO COMPLETED SUCCESSFULLY!")
    print("=" * 60)


def test_pipeline_copy_example(workspace_path_override=None):
    """Example showing the pipeline copy approach similar to user's option2_pipeline_copy.

    Args:
        workspace_path_override: Optional existing workspace path to use instead of creating one
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Use provided workspace or create test workspace
        if workspace_path_override:
            workspace_path = Path(workspace_path_override)
            if not workspace_path.exists():
                raise ValueError(
                    f"Provided workspace path does not exist: {workspace_path}"
                )
        else:
            workspace_path = create_test_workspace(tmp_path, size_mb=2)

        cache_dir = tmp_path / "pipeline_cache"

        # Create benchmark runner
        benchmark = create_benchmark_runner()

        print("\nPipeline Copy Example (like option2_pipeline_copy):")
        print("-" * 50)

        # Run pipeline benchmark
        result = benchmark.pipeline_copy_benchmark(
            workspace_path=workspace_path,
            cache_dir=cache_dir,
            components=["zmk", "zephyr", "modules", ".west"],
        )

        print(f"Total time: {result.duration:.2f}s")
        print(f"Files copied: {result.file_count}")
        print(f"Total size: {result.total_size / (1024**2):.1f} MB")
        print(f"Throughput: {result.speed_summary}")
        print(f"Status: {'SUCCESS' if not result.errors else 'FAILED'}")

        # Verify cache was created
        assert cache_dir.exists()
        assert result.file_count > 0
        assert result.total_size > 0
        assert result.duration > 0


if __name__ == "__main__":
    """Run demo when executed directly."""
    import sys
    import tempfile

    # Check for optional workspace path argument
    workspace_path = None
    if len(sys.argv) > 1:
        workspace_path = sys.argv[1]
        print(f"Using provided workspace: {workspace_path}")
    else:
        print("No workspace path provided, will create test workspace")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        print("Running comprehensive benchmark...")
        test_comprehensive_file_operations_benchmark(tmp_path, workspace_path)

        print("\nRunning individual pipeline example...")
        test_pipeline_copy_example(workspace_path)
