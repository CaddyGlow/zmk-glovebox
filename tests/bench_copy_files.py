#!/usr/bin/env python3
"""
Enhanced benchmark script with buffer size optimization testing.
Usage: python benchmark_copy_files.py /path/to/test/directory
"""

import argparse
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import psutil


# ====================
# CACHE CLEARING UTILITIES
# ====================


def clear_disk_cache():
    """Clear disk cache (Linux only)"""
    try:
        subprocess.run(["sync"], check=True)
        try:
            with open("/proc/sys/vm/drop_caches", "w") as f:
                f.write("3")
            print("  ✓ Cleared disk cache")
            return True
        except PermissionError:
            print(
                "  ⚠ Cannot clear disk cache (need sudo), results may be affected by caching"
            )
            return False
    except Exception as e:
        print(f"  ⚠ Could not clear cache: {e}")
        return False


def create_large_dummy_files(temp_dir, size_mb=1500):
    """Create large dummy files to pollute cache"""
    try:
        dummy_dir = Path(temp_dir) / "cache_polluter"
        dummy_dir.mkdir(exist_ok=True)

        for i in range(5):
            dummy_file = dummy_dir / f"dummy_{i}.dat"
            with open(dummy_file, "wb") as f:
                chunk = b"0" * (1024 * 1024)  # 1MB chunk
                for _ in range(size_mb):
                    f.write(chunk)

        print(f"  ✓ Created {size_mb * 5}MB of cache pollution files")
        return True
    except Exception as e:
        print(f"  ⚠ Could not create cache pollution: {e}")
        return False


# ====================
# OPTIMIZED COPY FUNCTIONS WITH BUFFER TUNING
# ====================


def optimized_copy_with_buffer(src, dst, buffer_size=1024 * 1024):
    """Copy with custom buffer size"""
    total_size = 0

    def copy_file_buffered(src_file, dst_file):
        nonlocal total_size
        os.makedirs(dst_file.parent, exist_ok=True)

        with open(src_file, "rb") as fsrc, open(dst_file, "wb") as fdst:
            while True:
                chunk = fsrc.read(buffer_size)
                if not chunk:
                    break
                fdst.write(chunk)
                total_size += len(chunk)

        # Copy metadata
        shutil.copystat(src_file, dst_file)

    # Walk and copy
    for src_file in src.rglob("*"):
        if src_file.is_file():
            rel_path = src_file.relative_to(src)
            dst_file = dst / rel_path
            copy_file_buffered(src_file, dst_file)

    return total_size


def sendfile_copy_with_buffer(src, dst):
    """Use sendfile for faster copying on Unix systems"""
    total_size = 0

    def copy_file_sendfile(src_file, dst_file):
        nonlocal total_size
        os.makedirs(dst_file.parent, exist_ok=True)

        # Use sendfile if available (Linux/Unix)
        if hasattr(os, "sendfile"):
            with open(src_file, "rb") as fsrc, open(dst_file, "wb") as fdst:
                file_size = os.fstat(fsrc.fileno()).st_size
                try:
                    os.sendfile(fdst.fileno(), fsrc.fileno(), 0, file_size)
                    total_size += file_size
                except OSError:
                    # Fallback if sendfile fails
                    fsrc.seek(0)
                    shutil.copyfileobj(fsrc, fdst, 1024 * 1024)
                    total_size += file_size
        else:
            # Fallback to regular copy
            shutil.copy2(src_file, dst_file)
            total_size += src_file.stat().st_size

        shutil.copystat(src_file, dst_file)

    for src_file in src.rglob("*"):
        if src_file.is_file():
            rel_path = src_file.relative_to(src)
            dst_file = dst / rel_path
            copy_file_sendfile(src_file, dst_file)

    return total_size


# ====================
# BUFFER SIZE TESTING METHODS
# ====================


def create_buffer_test_method(buffer_size, method_name=""):
    """Create a copy method with specific buffer size"""

    def buffer_test_copy(
        workspace_path, level_cache_dir, detected_components, verbose=False
    ):
        total_size = 0

        for component in detected_components:
            src_component = workspace_path / component
            dest_component = level_cache_dir / component

            if dest_component.exists():
                shutil.rmtree(dest_component)

            component_size = optimized_copy_with_buffer(
                src_component, dest_component, buffer_size
            )
            total_size += component_size

            if verbose:
                print(
                    f"  Copied {component} with {buffer_size // 1024}KB buffer: {component_size / (1024 * 1024):.1f} MB"
                )

        return total_size

    return buffer_test_copy


def create_parallel_buffer_test_method(buffer_size, workers=3):
    """Create a parallel copy method with specific buffer size"""

    def parallel_buffer_copy(
        workspace_path, level_cache_dir, detected_components, verbose=False
    ):
        def copy_component_buffered(component):
            src_component = workspace_path / component
            dest_component = level_cache_dir / component

            if dest_component.exists():
                shutil.rmtree(dest_component)

            return optimized_copy_with_buffer(
                src_component, dest_component, buffer_size
            )

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(copy_component_buffered, comp)
                for comp in detected_components
            ]
            total_size = sum(future.result() for future in as_completed(futures))

        return total_size

    return parallel_buffer_copy


def sendfile_parallel_copy(
    workspace_path, level_cache_dir, detected_components, verbose=False
):
    """Parallel copy using sendfile optimization"""

    def copy_component_sendfile(component):
        src_component = workspace_path / component
        dest_component = level_cache_dir / component

        if dest_component.exists():
            shutil.rmtree(dest_component)

        return sendfile_copy_with_buffer(src_component, dest_component)

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(copy_component_sendfile, comp)
            for comp in detected_components
        ]
        total_size = sum(future.result() for future in as_completed(futures))

    return total_size


# ====================
# ORIGINAL METHODS (from previous script)
# ====================


def get_dir_size_psutil(path):
    """Fast directory size using psutil"""
    total = 0
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += get_dir_size_psutil(entry.path)
    except (OSError, PermissionError):
        pass
    return total


def get_component_info(args):
    """Get size and prepare for copy"""
    workspace_path, component = args
    src_path = workspace_path / component

    def get_size_fast(path):
        total = 0
        try:
            with os.scandir(path) as entries:
                for entry in entries:
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat().st_size
                    elif entry.is_dir(follow_symlinks=False):
                        total += get_size_fast(entry.path)
        except (OSError, PermissionError):
            pass
        return total

    size = get_size_fast(src_path)
    return component, src_path, size


def copy_component(args):
    """Copy single component"""
    component, src_path, dst_path, size = args

    if dst_path.exists():
        shutil.rmtree(dst_path)

    shutil.copytree(src_path, dst_path)
    return size


def option2_pipeline_copy(
    workspace_path, level_cache_dir, detected_components, verbose=False
):
    """Option 2: Simpler Pipeline with psutil"""
    total_size = 0

    # Phase 1: Calculate all sizes in parallel
    if verbose:
        print("  Phase 1: Calculating sizes...")

    with ThreadPoolExecutor(max_workers=4) as executor:
        size_futures = {
            executor.submit(get_component_info, (workspace_path, comp)): comp
            for comp in detected_components
        }

        copy_tasks = []
        for future in as_completed(size_futures):
            component, src_path, size = future.result()
            dst_path = level_cache_dir / component
            copy_tasks.append((component, src_path, dst_path, size))
            total_size += size

    if verbose:
        print(f"  Will copy {total_size / (1024 * 1024 * 1024):.2f} GB")
        print("  Phase 2: Copying files...")

    # Phase 2: Copy all components in parallel
    with ThreadPoolExecutor(max_workers=3) as executor:
        copy_futures = [executor.submit(copy_component, task) for task in copy_tasks]

        for future in as_completed(copy_futures):
            copied_size = future.result()
            if verbose:
                print(f"  Copied {copied_size / (1024 * 1024):.1f} MB")

    return total_size


def parallel_shutil_copy(
    workspace_path, level_cache_dir, detected_components, verbose=False
):
    """Parallel version of standard shutil.copytree"""

    def copy_single_component(component):
        src_component = workspace_path / component
        dest_component = level_cache_dir / component

        component_size = sum(
            f.stat().st_size for f in src_component.rglob("*") if f.is_file()
        )

        if dest_component.exists():
            shutil.rmtree(dest_component)
        shutil.copytree(src_component, dest_component)

        if verbose:
            print(f"  Copied {component}: {component_size / (1024 * 1024):.1f} MB")

        return component_size

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(copy_single_component, comp) for comp in detected_components
        ]
        total_size = sum(future.result() for future in as_completed(futures))

    return total_size


# ====================
# BENCHMARKING FRAMEWORK
# ====================


def get_subdirectories(path):
    """Get all subdirectories in a path"""
    path = Path(path)
    return [d.name for d in path.iterdir() if d.is_dir()]


def run_benchmark(
    method_name,
    method_func,
    workspace_path,
    detected_components,
    clear_cache=False,
    verbose=False,
):
    """Run a single benchmark"""
    print(f"\n{'=' * 50}")
    print(f"Testing: {method_name}")
    print(f"{'=' * 50}")

    with tempfile.TemporaryDirectory(
        prefix=f"benchmark_{method_name.replace(' ', '_').replace('(', '').replace(')', '')}_"
    ) as temp_dir:
        level_cache_dir = Path(temp_dir)

        if verbose:
            print(f"Temp directory: {temp_dir}")
            print(f"Components to copy: {len(detected_components)}")

        if clear_cache:
            clear_disk_cache()
            create_large_dummy_files(temp_dir, size_mb=200)
            time.sleep(0.5)

        process = psutil.Process()
        cpu_before = process.cpu_percent()
        memory_before = process.memory_info().rss / (1024 * 1024)

        start_time = time.time()
        try:
            total_size = method_func(
                workspace_path, level_cache_dir, detected_components, verbose
            )
            end_time = time.time()
            success = True
        except Exception as e:
            end_time = time.time()
            total_size = 0
            success = False
            print(f"ERROR: {e}")
            import traceback

            if verbose:
                traceback.print_exc()

        cpu_after = process.cpu_percent()
        memory_after = process.memory_info().rss / (1024 * 1024)
        elapsed_time = end_time - start_time

        print(f"\nResults for {method_name}:")
        print(f"  Success: {'✓' if success else '✗'}")
        print(f"  Time: {elapsed_time:.2f} seconds")
        print(f"  Total size: {total_size / (1024 * 1024 * 1024):.3f} GB")
        if elapsed_time > 0 and success:
            print(f"  Speed: {(total_size / (1024 * 1024)) / elapsed_time:.1f} MB/s")
        else:
            print("  Speed: N/A")
        print(f"  Memory delta: {memory_after - memory_before:.1f} MB")

        return {
            "method": method_name,
            "success": success,
            "time": elapsed_time,
            "size": total_size,
            "speed_mbps": (total_size / (1024 * 1024)) / elapsed_time
            if elapsed_time > 0 and success
            else 0,
            "memory_delta": memory_after - memory_before,
        }


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark different copy methods with buffer optimization"
    )
    parser.add_argument("path", help="Path to directory to copy from")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--runs", "-r", type=int, default=1, help="Number of runs per method"
    )
    parser.add_argument(
        "--methods",
        "-m",
        nargs="+",
        choices=["baseline", "parallel", "option2", "buffer-test", "sendfile", "all"],
        default=["all"],
        help="Methods to test",
    )
    parser.add_argument(
        "--limit", "-l", type=int, help="Limit number of components to copy"
    )
    parser.add_argument(
        "--clear-cache",
        "-c",
        action="store_true",
        help="Try to clear disk cache between tests",
    )
    parser.add_argument(
        "--buffer-sizes",
        "-b",
        nargs="+",
        type=int,
        default=[64, 128, 256, 512, 1024, 2048, 4096],
        help="Buffer sizes to test in KB (default: 64 128 256 512 1024 2048 4096)",
    )

    args = parser.parse_args()

    workspace_path = Path(args.path)
    if not workspace_path.exists():
        print(f"Error: Path {workspace_path} does not exist")
        sys.exit(1)

    detected_components = get_subdirectories(workspace_path)
    if not detected_components:
        print(f"Error: No subdirectories found in {workspace_path}")
        sys.exit(1)

    if args.limit:
        detected_components = detected_components[: args.limit]
        print(f"Limited to first {len(detected_components)} components for testing")

    print("Benchmark Configuration:")
    print(f"  Source path: {workspace_path}")
    print(f"  Components found: {len(detected_components)}")
    print(
        f"  Components: {', '.join(detected_components[:5])}"
        + (
            f" ... and {len(detected_components) - 5} more"
            if len(detected_components) > 5
            else ""
        )
    )
    print(f"  Runs per method: {args.runs}")
    print(f"  Clear cache: {'Yes' if args.clear_cache else 'No'}")
    if "buffer-test" in args.methods or "all" in args.methods:
        print(
            f"  Buffer sizes to test: {', '.join(f'{b}KB' for b in args.buffer_sizes)}"
        )

    # Define base methods
    base_methods = {
        "parallel": ("Parallel shutil (baseline)", parallel_shutil_copy),
        "option2": ("Option 2 (Pipeline)", option2_pipeline_copy),
        "sendfile": ("Sendfile parallel", sendfile_parallel_copy),
    }

    methods_to_run = {}

    # Determine which methods to run
    if "all" in args.methods:
        methods_to_run.update(base_methods)
        # Add buffer tests
        for buffer_kb in args.buffer_sizes:
            buffer_bytes = buffer_kb * 1024
            methods_to_run[f"buffer_{buffer_kb}kb"] = (
                f"Buffer {buffer_kb}KB",
                create_buffer_test_method(buffer_bytes),
            )
            methods_to_run[f"parallel_buffer_{buffer_kb}kb"] = (
                f"Parallel Buffer {buffer_kb}KB",
                create_parallel_buffer_test_method(buffer_bytes),
            )
    else:
        if "baseline" in args.methods or "parallel" in args.methods:
            methods_to_run["parallel"] = base_methods["parallel"]
        if "option2" in args.methods:
            methods_to_run["option2"] = base_methods["option2"]
        if "sendfile" in args.methods:
            methods_to_run["sendfile"] = base_methods["sendfile"]
        if "buffer-test" in args.methods:
            for buffer_kb in args.buffer_sizes:
                buffer_bytes = buffer_kb * 1024
                methods_to_run[f"buffer_{buffer_kb}kb"] = (
                    f"Buffer {buffer_kb}KB",
                    create_buffer_test_method(buffer_bytes),
                )
                methods_to_run[f"parallel_buffer_{buffer_kb}kb"] = (
                    f"Parallel Buffer {buffer_kb}KB",
                    create_parallel_buffer_test_method(buffer_bytes),
                )

    # Run benchmarks
    all_results = []

    for run in range(args.runs):
        if args.runs > 1:
            print(f"\n{'#' * 60}")
            print(f"RUN {run + 1} of {args.runs}")
            print(f"{'#' * 60}")

        for _method_key, (method_name, method_func) in methods_to_run.items():
            result = run_benchmark(
                method_name,
                method_func,
                workspace_path,
                detected_components,
                args.clear_cache,
                args.verbose,
            )
            result["run"] = run + 1
            all_results.append(result)
            time.sleep(1)

    # Summary
    print(f"\n{'=' * 70}")
    print("SUMMARY - SORTED BY PERFORMANCE")
    print(f"{'=' * 70}")

    successful_results = [r for r in all_results if r["success"]]
    sorted_results = sorted(successful_results, key=lambda x: x["time"])

    print(f"{'Method':<35} | {'Time':<10} | {'Speed':<12} | {'Speedup'}")
    print(f"{'-' * 35} | {'-' * 10} | {'-' * 12} | {'-' * 10}")

    baseline_time = None
    baseline_result = next(
        (r for r in sorted_results if "Parallel shutil" in r["method"]), None
    )
    if baseline_result:
        baseline_time = baseline_result["time"]

    for i, result in enumerate(sorted_results):
        if baseline_time:
            speedup = f"{baseline_time / result['time']:.1f}x"
        else:
            speedup = "N/A"

        # Highlight top 3 results
        prefix = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "  "
        print(
            f"{prefix} {result['method']:<32} | {result['time']:>6.2f}s   | {result['speed_mbps']:>8.1f} MB/s | {speedup:>8}"
        )

    # Show failed methods
    failed_results = [r for r in all_results if not r["success"]]
    for result in failed_results:
        print(f"❌ {result['method']:<32} | {'FAILED':<10} | {'N/A':<12} | {'N/A'}")

    if successful_results:
        best_result = sorted_results[0]
        print(
            f"\n🏆 Fastest method: {best_result['method']} ({best_result['time']:.2f}s)"
        )

        if baseline_result:
            improvement = (
                (baseline_result["time"] - best_result["time"])
                / baseline_result["time"]
                * 100
            )
            print(
                f"📈 Improvement over baseline: {improvement:.1f}% faster ({baseline_result['time'] / best_result['time']:.1f}x speedup)"
            )

        # Show optimal buffer size if buffer tests were run
        buffer_results = [r for r in sorted_results if "Buffer" in r["method"]]
        if buffer_results:
            best_buffer = buffer_results[0]
            print(
                f"🎯 Optimal buffer size: {best_buffer['method']} ({best_buffer['speed_mbps']:.1f} MB/s)"
            )

    else:
        print("\n❌ No successful runs completed")


if __name__ == "__main__":
    main()
