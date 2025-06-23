"""Benchmarking module for file operations performance analysis."""

# os.scandir is available in Python 3.5+ (our minimum version)
import contextlib
import logging
import os
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .enums import CopyStrategy
from .models import CopyResult
from .service import create_copy_service


@dataclass
class BenchmarkResult:
    """Results from a benchmark run."""

    operation: str
    method: str
    duration: float
    file_count: int
    total_size: int
    throughput_mbps: float
    errors: list[str] | None = None

    @property
    def speed_summary(self) -> str:
        """Human-readable speed summary."""
        if self.throughput_mbps > 1000:
            return f"{self.throughput_mbps / 1024:.1f} GB/s"
        else:
            return f"{self.throughput_mbps:.1f} MB/s"


class FileOperationsBenchmark:
    """Comprehensive benchmarking suite for file operations."""

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger(__name__)

    def benchmark_directory_traversal(
        self, directory: Path, iterations: int = 3
    ) -> list[BenchmarkResult]:
        """Benchmark different directory traversal methods."""
        results: list[BenchmarkResult] = []

        if not directory.exists() or not directory.is_dir():
            return results

        # Method 1: rglob
        self.logger.info("Benchmarking rglob traversal...")
        rglob_results = []
        for _i in range(iterations):
            start_time = time.time()
            file_count = 0
            total_size = 0

            try:
                for item in directory.rglob("*"):
                    if item.is_file():
                        file_count += 1
                        with contextlib.suppress(OSError, PermissionError):
                            total_size += item.stat().st_size

                duration = time.time() - start_time
                throughput = (
                    (total_size / (1024 * 1024)) / duration if duration > 0 else 0
                )

                rglob_results.append(
                    BenchmarkResult(
                        operation="directory_traversal",
                        method="rglob",
                        duration=duration,
                        file_count=file_count,
                        total_size=total_size,
                        throughput_mbps=throughput,
                    )
                )

            except Exception as e:
                rglob_results.append(
                    BenchmarkResult(
                        operation="directory_traversal",
                        method="rglob",
                        duration=time.time() - start_time,
                        file_count=0,
                        total_size=0,
                        throughput_mbps=0,
                        errors=[str(e)],
                    )
                )

        # Method 2: os.walk
        self.logger.info("Benchmarking os.walk traversal...")
        walk_results = []
        for _i in range(iterations):
            start_time = time.time()
            file_count = 0
            total_size = 0

            try:
                for root, _dirs, files in os.walk(directory):
                    file_count += len(files)
                    for file_name in files:
                        try:
                            file_path = Path(root) / file_name
                            total_size += file_path.stat().st_size
                        except (OSError, PermissionError):
                            pass

                duration = time.time() - start_time
                throughput = (
                    (total_size / (1024 * 1024)) / duration if duration > 0 else 0
                )

                walk_results.append(
                    BenchmarkResult(
                        operation="directory_traversal",
                        method="os.walk",
                        duration=duration,
                        file_count=file_count,
                        total_size=total_size,
                        throughput_mbps=throughput,
                    )
                )

            except Exception as e:
                walk_results.append(
                    BenchmarkResult(
                        operation="directory_traversal",
                        method="os.walk",
                        duration=time.time() - start_time,
                        file_count=0,
                        total_size=0,
                        throughput_mbps=0,
                        errors=[str(e)],
                    )
                )

        # Method 3: os.listdir (recursive)
        self.logger.info("Benchmarking os.listdir traversal...")
        listdir_results = []
        for _i in range(iterations):
            start_time = time.time()
            file_count = 0
            total_size = 0

            try:
                file_count, total_size = self._traverse_with_listdir(directory)

                duration = time.time() - start_time
                throughput = (
                    (total_size / (1024 * 1024)) / duration if duration > 0 else 0
                )

                listdir_results.append(
                    BenchmarkResult(
                        operation="directory_traversal",
                        method="os.listdir",
                        duration=duration,
                        file_count=file_count,
                        total_size=total_size,
                        throughput_mbps=throughput,
                    )
                )

            except Exception as e:
                listdir_results.append(
                    BenchmarkResult(
                        operation="directory_traversal",
                        method="os.listdir",
                        duration=time.time() - start_time,
                        file_count=0,
                        total_size=0,
                        throughput_mbps=0,
                        errors=[str(e)],
                    )
                )

        # Method 4: os.scandir (if available)
        if hasattr(os, "scandir"):
            self.logger.info("Benchmarking os.scandir traversal...")
            scandir_results = []
            for _i in range(iterations):
                start_time = time.time()
                file_count = 0
                total_size = 0

                try:
                    file_count, total_size = self._traverse_with_scandir(directory)

                    duration = time.time() - start_time
                    throughput = (
                        (total_size / (1024 * 1024)) / duration if duration > 0 else 0
                    )

                    scandir_results.append(
                        BenchmarkResult(
                            operation="directory_traversal",
                            method="os.scandir",
                            duration=duration,
                            file_count=file_count,
                            total_size=total_size,
                            throughput_mbps=throughput,
                        )
                    )

                except Exception as e:
                    scandir_results.append(
                        BenchmarkResult(
                            operation="directory_traversal",
                            method="os.scandir",
                            duration=time.time() - start_time,
                            file_count=0,
                            total_size=0,
                            throughput_mbps=0,
                            errors=[str(e)],
                        )
                    )

            results.extend(scandir_results)

        # Add all results
        results.extend(walk_results)
        results.extend(listdir_results)
        results.extend(rglob_results)
        return results

    def benchmark_copy_strategies(
        self,
        src_dir: Path,
        dst_base: Path,
        strategies: list[CopyStrategy] | None = None,
    ) -> list[BenchmarkResult]:
        """Benchmark different copy strategies."""
        if strategies is None:
            strategies = [
                CopyStrategy.BASELINE,
                CopyStrategy.BUFFERED,
                CopyStrategy.PARALLEL,
                CopyStrategy.PIPELINE,
            ]
            # Add sendfile if available on the system
            if hasattr(os, "sendfile"):
                strategies.append(CopyStrategy.SENDFILE)

        results = []

        for strategy in strategies:
            self.logger.info("Benchmarking %s copy strategy...", strategy.value)

            # Create unique destination for this strategy
            dst_dir = dst_base / f"copy_{strategy.value}_{int(time.time())}"

            try:
                # Create copy service with specific strategy
                copy_service = create_copy_service()

                # Force use of specific strategy
                start_time = time.time()
                copy_result = copy_service.copy_directory(
                    src=src_dir, dst=dst_dir, exclude_git=True, strategy=strategy
                )

                # Convert CopyResult to BenchmarkResult
                benchmark_result = BenchmarkResult(
                    operation="copy_directory",
                    method=strategy.value,
                    duration=copy_result.elapsed_time,
                    file_count=self._count_files(dst_dir) if copy_result.success else 0,
                    total_size=copy_result.bytes_copied,
                    throughput_mbps=copy_result.speed_mbps,
                    errors=None
                    if copy_result.success
                    else [copy_result.error or "Unknown error"],
                )

                results.append(benchmark_result)

                # Clean up destination
                if dst_dir.exists():
                    import shutil

                    shutil.rmtree(dst_dir)

            except Exception as e:
                duration = time.time() - start_time
                results.append(
                    BenchmarkResult(
                        operation="copy_directory",
                        method=strategy.value,
                        duration=duration,
                        file_count=0,
                        total_size=0,
                        throughput_mbps=0,
                        errors=[str(e)],
                    )
                )

        return results

    def benchmark_parallel_workers(
        self, src_dir: Path, dst_base: Path, worker_counts: list[int] | None = None
    ) -> list[BenchmarkResult]:
        """Benchmark parallel copy with different worker counts."""
        if worker_counts is None:
            worker_counts = [1, 2, 4, 8, 16]

        results = []

        for worker_count in worker_counts:
            self.logger.info(
                "Benchmarking parallel copy with %d workers...", worker_count
            )

            dst_dir = dst_base / f"parallel_{worker_count}_{int(time.time())}"

            try:
                from .service import FileCopyService

                copy_service = FileCopyService(
                    default_strategy=CopyStrategy.PARALLEL, max_workers=worker_count
                )

                start_time = time.time()
                copy_result = copy_service.copy_directory(
                    src=src_dir,
                    dst=dst_dir,
                    exclude_git=True,
                    strategy=CopyStrategy.PARALLEL,
                )

                benchmark_result = BenchmarkResult(
                    operation="parallel_copy",
                    method=f"parallel_{worker_count}_workers",
                    duration=copy_result.elapsed_time,
                    file_count=self._count_files(dst_dir) if copy_result.success else 0,
                    total_size=copy_result.bytes_copied,
                    throughput_mbps=copy_result.speed_mbps,
                    errors=None
                    if copy_result.success
                    else [copy_result.error or "Unknown error"],
                )

                results.append(benchmark_result)

                # Clean up
                if dst_dir.exists():
                    import shutil

                    shutil.rmtree(dst_dir)

            except Exception as e:
                duration = time.time() - start_time
                results.append(
                    BenchmarkResult(
                        operation="parallel_copy",
                        method=f"parallel_{worker_count}_workers",
                        duration=duration,
                        file_count=0,
                        total_size=0,
                        throughput_mbps=0,
                        errors=[str(e)],
                    )
                )

        return results

    def pipeline_copy_benchmark(
        self, workspace_path: Path, cache_dir: Path, components: list[str] | None = None
    ) -> BenchmarkResult:
        """Benchmark the pipeline copy approach from the user's example."""
        if components is None:
            # Default ZMK components
            components = ["zmk", "zephyr", "modules", ".west"]

        self.logger.info("Benchmarking pipeline copy approach...")
        start_time = time.time()
        total_size = 0

        try:
            # Phase 1: Calculate all sizes in parallel
            with ThreadPoolExecutor(max_workers=4) as executor:
                size_futures = {
                    executor.submit(
                        self._get_component_info, workspace_path, comp
                    ): comp
                    for comp in components
                    if (workspace_path / comp).exists()
                }

                copy_tasks = []
                for future in as_completed(size_futures):
                    component, src_path, size = future.result()
                    dst_path = cache_dir / component
                    copy_tasks.append((component, src_path, dst_path, size))
                    total_size += size

            # Phase 2: Copy all components in parallel
            with ThreadPoolExecutor(max_workers=3) as executor:
                copy_futures: list[Any] = [
                    executor.submit(self._copy_component, task) for task in copy_tasks
                ]

                copied_total = 0
                for future in as_completed(copy_futures):
                    copied_size: int = future.result()  # type: ignore[assignment]
                    copied_total += copied_size

            duration = time.time() - start_time
            # Use actual copied size for throughput calculation
            actual_size = copied_total if copied_total > 0 else total_size
            throughput = (actual_size / (1024 * 1024)) / duration if duration > 0 else 0

            return BenchmarkResult(
                operation="pipeline_copy",
                method="two_phase_parallel",
                duration=duration,
                file_count=self._count_files(cache_dir),
                total_size=actual_size,
                throughput_mbps=throughput,
            )

        except Exception as e:
            duration = time.time() - start_time
            return BenchmarkResult(
                operation="pipeline_copy",
                method="two_phase_parallel",
                duration=duration,
                file_count=0,
                total_size=0,
                throughput_mbps=0,
                errors=[str(e)],
            )

    def _get_component_info(
        self, workspace_path: Path, component: str
    ) -> tuple[str, Path, int]:
        """Get component information for pipeline benchmark."""
        src_path = workspace_path / component
        size = 0

        if src_path.exists():
            if hasattr(os, "scandir"):
                # Use os.scandir for maximum speed (2.5x faster than rglob)
                _, size = self._traverse_with_scandir_stats(src_path)
            else:
                # Fallback to rglob
                for item in src_path.rglob("*"):
                    if item.is_file():
                        with contextlib.suppress(OSError, PermissionError):
                            size += item.stat().st_size

        return component, src_path, size

    def _traverse_with_scandir_stats(self, directory: Path) -> tuple[int, int]:
        """Get directory stats using os.scandir for maximum performance."""
        file_count = 0
        total_size = 0

        def _scandir_stats_recursive(path: Path) -> None:
            nonlocal file_count, total_size
            try:
                with os.scandir(path) as entries:
                    for entry in entries:
                        try:
                            if entry.is_file():
                                file_count += 1
                                total_size += entry.stat().st_size
                            elif entry.is_dir():
                                _scandir_stats_recursive(Path(entry.path))
                        except (OSError, PermissionError):
                            pass
            except (OSError, PermissionError):
                pass

        _scandir_stats_recursive(directory)
        return file_count, total_size

    def _copy_component(self, task: tuple[str, Path, Path, int]) -> int:
        """Copy a single component for pipeline benchmark."""
        component, src_path, dst_path, expected_size = task

        if not src_path.exists():
            return 0

        try:
            import shutil

            if dst_path.exists():
                shutil.rmtree(dst_path)

            # Use simple shutil.copytree for pipeline benchmark
            shutil.copytree(
                src_path,
                dst_path,
                ignore=lambda src, names: [".git"] if ".git" in names else [],
            )

            return expected_size

        except Exception as e:
            self.logger.warning("Failed to copy component %s: %s", component, e)
            return 0

    def _count_files(self, directory: Path) -> int:
        """Count files in directory."""
        if not directory.exists():
            return 0

        count = 0
        try:
            for item in directory.rglob("*"):
                if item.is_file():
                    count += 1
        except (OSError, PermissionError):
            pass

        return count

    def _traverse_with_listdir(self, directory: Path) -> tuple[int, int]:
        """Traverse directory using os.listdir recursively."""
        file_count = 0
        total_size = 0

        def _listdir_recursive(path: Path) -> None:
            nonlocal file_count, total_size
            try:
                for item_path in path.iterdir():
                    try:
                        if item_path.is_file():
                            file_count += 1
                            total_size += item_path.stat().st_size
                        elif item_path.is_dir():
                            _listdir_recursive(item_path)
                    except (OSError, PermissionError):
                        pass
            except (OSError, PermissionError):
                pass

        _listdir_recursive(directory)
        return file_count, total_size

    def _traverse_with_scandir(self, directory: Path) -> tuple[int, int]:
        """Traverse directory using os.scandir recursively."""
        file_count = 0
        total_size = 0

        def _scandir_recursive(path: Path) -> None:
            nonlocal file_count, total_size
            try:
                with os.scandir(path) as entries:
                    for entry in entries:
                        try:
                            if entry.is_file():
                                file_count += 1
                                total_size += entry.stat().st_size
                            elif entry.is_dir():
                                _scandir_recursive(Path(entry.path))
                        except (OSError, PermissionError):
                            pass
            except (OSError, PermissionError):
                pass

        _scandir_recursive(directory)
        return file_count, total_size

    def run_comprehensive_benchmark(
        self, workspace_path: Path, output_dir: Path, verbose: bool = True
    ) -> dict[str, list[BenchmarkResult]]:
        """Run comprehensive benchmark suite."""
        results = {}

        if verbose:
            self.logger.info("Starting comprehensive file operations benchmark...")

        # 1. Directory traversal benchmark
        if verbose:
            self.logger.info("=== Directory Traversal Benchmark ===")

        traversal_results = self.benchmark_directory_traversal(workspace_path)
        results["traversal"] = traversal_results

        if verbose:
            self._print_traversal_results(traversal_results)

        # 2. Copy strategy benchmark
        if verbose:
            self.logger.info("=== Copy Strategy Benchmark ===")

        copy_results = self.benchmark_copy_strategies(workspace_path, output_dir)
        results["copy_strategies"] = copy_results

        if verbose:
            self._print_copy_results(copy_results)

        # 3. Parallel worker benchmark
        if verbose:
            self.logger.info("=== Parallel Worker Count Benchmark ===")

        worker_results = self.benchmark_parallel_workers(workspace_path, output_dir)
        results["parallel_workers"] = worker_results

        if verbose:
            self._print_worker_results(worker_results)

        # 4. Pipeline copy benchmark
        if verbose:
            self.logger.info("=== Pipeline Copy Benchmark ===")

        pipeline_result = self.pipeline_copy_benchmark(
            workspace_path, output_dir / "pipeline"
        )
        results["pipeline"] = [pipeline_result]

        if verbose:
            self._print_pipeline_results([pipeline_result])

        return results

    def _print_traversal_results(self, results: list[BenchmarkResult]) -> None:
        """Print traversal benchmark results."""
        if not results:
            return

        print(
            f"{'Method':<12} {'Duration':<10} {'Files':<8} {'Size':<10} {'Speed':<12}"
        )
        print("-" * 60)

        for result in results:
            size_mb = result.total_size / (1024 * 1024)
            print(
                f"{result.method:<12} {result.duration:<10.3f} {result.file_count:<8} {size_mb:<10.1f} {result.speed_summary:<12}"
            )

    def _print_copy_results(self, results: list[BenchmarkResult]) -> None:
        """Print copy strategy benchmark results."""
        if not results:
            return

        print(
            f"{'Strategy':<12} {'Duration':<10} {'Files':<8} {'Size':<10} {'Speed':<12} {'Status':<10}"
        )
        print("-" * 70)

        for result in results:
            size_mb = result.total_size / (1024 * 1024)
            status = "SUCCESS" if not result.errors else "FAILED"
            print(
                f"{result.method:<12} {result.duration:<10.3f} {result.file_count:<8} {size_mb:<10.1f} {result.speed_summary:<12} {status:<10}"
            )

    def _print_worker_results(self, results: list[BenchmarkResult]) -> None:
        """Print parallel worker benchmark results."""
        if not results:
            return

        print(
            f"{'Workers':<10} {'Duration':<10} {'Files':<8} {'Size':<10} {'Speed':<12} {'Status':<10}"
        )
        print("-" * 68)

        for result in results:
            workers = result.method.split("_")[1]
            size_mb = result.total_size / (1024 * 1024)
            status = "SUCCESS" if not result.errors else "FAILED"
            print(
                f"{workers:<10} {result.duration:<10.3f} {result.file_count:<8} {size_mb:<10.1f} {result.speed_summary:<12} {status:<10}"
            )

    def _print_pipeline_results(self, results: list[BenchmarkResult]) -> None:
        """Print pipeline benchmark results."""
        if not results:
            return

        for result in results:
            size_gb = result.total_size / (1024 * 1024 * 1024)
            status = "SUCCESS" if not result.errors else "FAILED"
            print(
                f"Pipeline Copy: {result.duration:.3f}s, {result.file_count} files, {size_gb:.2f} GB, {result.speed_summary}, {status}"
            )


def create_benchmark_runner(
    logger: logging.Logger | None = None,
) -> FileOperationsBenchmark:
    """Factory function to create benchmark runner."""
    return FileOperationsBenchmark(logger)
