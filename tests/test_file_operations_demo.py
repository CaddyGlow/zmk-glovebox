#!/usr/bin/env python3
"""Demo script for file operations benchmarking.

This script demonstrates the comprehensive benchmarking capabilities
of the file operations module with multithreading and performance optimization.
"""

import logging
import tempfile
from pathlib import Path

import pytest

from glovebox.core.file_operations import create_copy_service


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
    """Comprehensive test of file operations using simplified interface.

    Args:
        tmp_path: Temporary directory for test isolation
        workspace_path_override: Optional existing workspace path to use instead of creating one
    """
    # Enable logging to see copy progress
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("\n" + "=" * 60)
    print("FILE OPERATIONS DEMO")
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

    output_dir = tmp_path / "copy_output"
    print(f"   Output dir: {output_dir}")

    # Create file copy service
    copy_service = create_copy_service()

    print("\n2. Running file copy operations...")
    print("   This will test:")
    print("   - Baseline copy strategy")
    print("   - Pipeline copy strategy")

    # Test baseline strategy
    baseline_output = output_dir / "baseline"
    result = copy_service.copy_directory(
        src=workspace_path, dst=baseline_output, use_pipeline=False, exclude_git=True
    )

    print("\n3. Baseline Copy Results:")
    print("-" * 40)
    print(f"  Success: {result.success}")
    print(f"  Bytes copied: {result.bytes_copied}")
    print(f"  Total size: {result.bytes_copied / (1024**2):.1f} MB")
    print(f"  Duration: {result.elapsed_time:.2f}s")

    # Test pipeline strategy
    pipeline_output = output_dir / "pipeline"
    result = copy_service.copy_directory(
        src=workspace_path, dst=pipeline_output, use_pipeline=True, exclude_git=True
    )

    print("\n4. Pipeline Copy Results:")
    print("-" * 40)
    print(f"  Success: {result.success}")
    print(f"  Bytes copied: {result.bytes_copied}")
    print(f"  Total size: {result.bytes_copied / (1024**2):.1f} MB")
    print(f"  Duration: {result.elapsed_time:.2f}s")

    # Verify results
    assert result.success
    assert baseline_output.exists()
    assert pipeline_output.exists()
    assert result.bytes_copied > 0

    print("\n" + "=" * 60)
    print("FILE OPERATIONS DEMO COMPLETED SUCCESSFULLY!")
    print("=" * 60)


def test_pipeline_copy_example(workspace_path_override=None):
    """Example showing the pipeline copy approach using simplified interface.

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

        # Create copy service with pipeline strategy
        copy_service = create_copy_service(use_pipeline=True)

        print("\nPipeline Copy Example:")
        print("-" * 50)

        # Run pipeline copy
        result = copy_service.copy_directory(
            src=workspace_path, dst=cache_dir, use_pipeline=True, exclude_git=True
        )

        print(f"Total time: {result.elapsed_time:.2f}s")
        print(f"Bytes copied: {result.bytes_copied}")
        print(f"Total size: {result.bytes_copied / (1024**2):.1f} MB")
        if result.elapsed_time > 0:
            throughput = result.bytes_copied / (1024**2) / result.elapsed_time
            print(f"Throughput: {throughput:.1f} MB/s")
        print(f"Status: {'SUCCESS' if result.success else 'FAILED'}")

        # Verify cache was created
        assert cache_dir.exists()
        assert result.bytes_copied > 0
        assert result.elapsed_time > 0


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
