#!/usr/bin/env python3
"""
Protocol-based copy benchmarking framework with strategy pattern.
Provides clean separation between copy strategies and benchmarking logic.
"""

import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import psutil


# ====================
# CORE PROTOCOLS
# ====================


@dataclass
class CopyContext:
    """Context passed to copy strategies with all necessary information."""

    workspace_path: Path
    cache_dir: Path
    components: list[str]
    verbose: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CopyResult:
    """Result returned by copy strategies."""

    total_size: int
    elapsed_time: float
    success: bool
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def speed_mbps(self) -> float:
        """Calculate speed in MB/s."""
        if self.elapsed_time > 0 and self.success:
            return (self.total_size / (1024 * 1024)) / self.elapsed_time
        return 0.0


@runtime_checkable
class CopyStrategyProtocol(Protocol):
    """Protocol defining the interface for copy strategies."""

    @property
    def name(self) -> str:
        """Human-readable name for the strategy."""
        ...

    @property
    def description(self) -> str:
        """Detailed description of the strategy."""
        ...

    def copy(self, context: CopyContext) -> CopyResult:
        """Execute the copy operation and return results."""
        ...

    def validate_prerequisites(self) -> list[str]:
        """Return list of missing prerequisites, empty if all good."""
        ...


class CopyStrategyType(Enum):
    """Categories of copy strategies for organization."""

    BASELINE = "baseline"
    OPTIMIZED = "optimized"
    PARALLEL = "parallel"
    EXPERIMENTAL = "experimental"


# ====================
# STRATEGY REGISTRY
# ====================


class StrategyRegistry:
    """Registry for copy strategies with auto-discovery and filtering."""

    def __init__(self):
        self._strategies: dict[str, CopyStrategyProtocol] = {}
        self._categories: dict[CopyStrategyType, list[str]] = {
            category: [] for category in CopyStrategyType
        }

    def register(
        self,
        strategy: CopyStrategyProtocol,
        category: CopyStrategyType = CopyStrategyType.BASELINE,
    ):
        """Register a copy strategy."""
        strategy_id = (
            strategy.name.lower().replace(" ", "_").replace("(", "").replace(")", "")
        )
        self._strategies[strategy_id] = strategy
        self._categories[category].append(strategy_id)

    def get_strategy(self, strategy_id: str) -> CopyStrategyProtocol | None:
        """Get strategy by ID."""
        return self._strategies.get(strategy_id)

    def list_strategies(self, category: CopyStrategyType | None = None) -> list[str]:
        """List available strategy IDs, optionally filtered by category."""
        if category:
            return self._categories[category].copy()
        return list(self._strategies.keys())

    def list_all_strategies(self) -> dict[str, CopyStrategyProtocol]:
        """Get all registered strategies."""
        return self._strategies.copy()

    def validate_all(self) -> dict[str, list[str]]:
        """Validate all strategies and return missing prerequisites."""
        return {
            strategy_id: strategy.validate_prerequisites()
            for strategy_id, strategy in self._strategies.items()
        }


# Global registry instance
STRATEGY_REGISTRY = StrategyRegistry()


# ====================
# STRATEGY IMPLEMENTATIONS
# ====================


class BaselineShutilStrategy:
    """Standard shutil.copytree baseline strategy."""

    @property
    def name(self) -> str:
        return "Baseline Shutil"

    @property
    def description(self) -> str:
        return "Standard Python shutil.copytree with no optimizations"

    def validate_prerequisites(self) -> list[str]:
        return []  # No special requirements

    def copy(self, context: CopyContext) -> CopyResult:
        start_time = time.time()
        total_size = 0

        try:
            for component in context.components:
                src_component = context.workspace_path / component
                dest_component = context.cache_dir / component

                # Calculate size
                component_size = sum(
                    f.stat().st_size for f in src_component.rglob("*") if f.is_file()
                )
                total_size += component_size

                # Clean destination
                if dest_component.exists():
                    shutil.rmtree(dest_component)

                # Copy
                shutil.copytree(src_component, dest_component)

                if context.verbose:
                    print(
                        f"  Copied {component}: {component_size / (1024 * 1024):.1f} MB"
                    )

            elapsed_time = time.time() - start_time
            return CopyResult(
                total_size=total_size, elapsed_time=elapsed_time, success=True
            )

        except Exception as e:
            elapsed_time = time.time() - start_time
            return CopyResult(
                total_size=total_size,
                elapsed_time=elapsed_time,
                success=False,
                error=str(e),
            )


class BufferedCopyStrategy:
    """Optimized copy with configurable buffer size."""

    def __init__(self, buffer_size_kb: int = 1024):
        self.buffer_size = buffer_size_kb * 1024
        self.buffer_size_kb = buffer_size_kb

    @property
    def name(self) -> str:
        return f"Buffered Copy ({self.buffer_size_kb}KB)"

    @property
    def description(self) -> str:
        return f"Custom buffered copy with {self.buffer_size_kb}KB buffer size"

    def validate_prerequisites(self) -> list[str]:
        return []

    def copy(self, context: CopyContext) -> CopyResult:
        start_time = time.time()
        total_size = 0

        try:
            for component in context.components:
                src_component = context.workspace_path / component
                dest_component = context.cache_dir / component

                component_size = self._copy_component_buffered(
                    src_component, dest_component
                )
                total_size += component_size

                if context.verbose:
                    print(
                        f"  Copied {component} with {self.buffer_size_kb}KB buffer: {component_size / (1024 * 1024):.1f} MB"
                    )

            elapsed_time = time.time() - start_time
            return CopyResult(
                total_size=total_size,
                elapsed_time=elapsed_time,
                success=True,
                metadata={"buffer_size_kb": self.buffer_size_kb},
            )

        except Exception as e:
            elapsed_time = time.time() - start_time
            return CopyResult(
                total_size=total_size,
                elapsed_time=elapsed_time,
                success=False,
                error=str(e),
            )

    def _copy_component_buffered(self, src: Path, dst: Path) -> int:
        """Copy a component with buffered I/O."""
        total_size = 0

        if dst.exists():
            shutil.rmtree(dst)

        for src_file in src.rglob("*"):
            if src_file.is_file():
                rel_path = src_file.relative_to(src)
                dst_file = dst / rel_path
                dst_file.parent.mkdir(parents=True, exist_ok=True)

                with src_file.open("rb") as fsrc, dst_file.open("wb") as fdst:
                    while True:
                        chunk = fsrc.read(self.buffer_size)
                        if not chunk:
                            break
                        fdst.write(chunk)
                        total_size += len(chunk)

                shutil.copystat(src_file, dst_file)

        return total_size


class ParallelCopyStrategy:
    """Parallel copy strategy with configurable worker count."""

    def __init__(
        self, max_workers: int = 3, base_strategy: CopyStrategyProtocol | None = None
    ):
        self.max_workers = max_workers
        self.base_strategy = base_strategy or BaselineShutilStrategy()

    @property
    def name(self) -> str:
        return f"Parallel {self.base_strategy.name} ({self.max_workers} workers)"

    @property
    def description(self) -> str:
        return f"Parallel execution of {self.base_strategy.description} with {self.max_workers} workers"

    def validate_prerequisites(self) -> list[str]:
        return self.base_strategy.validate_prerequisites()

    def copy(self, context: CopyContext) -> CopyResult:
        start_time = time.time()

        def copy_single_component(component: str) -> int:
            single_context = CopyContext(
                workspace_path=context.workspace_path,
                cache_dir=context.cache_dir,
                components=[component],
                verbose=False,  # Avoid thread-unsafe printing
                metadata=context.metadata,
            )
            result = self.base_strategy.copy(single_context)
            if not result.success:
                raise Exception(f"Failed to copy {component}: {result.error}")
            return result.total_size

        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [
                    executor.submit(copy_single_component, comp)
                    for comp in context.components
                ]
                total_size = sum(future.result() for future in as_completed(futures))

            elapsed_time = time.time() - start_time
            return CopyResult(
                total_size=total_size,
                elapsed_time=elapsed_time,
                success=True,
                metadata={"max_workers": self.max_workers},
            )

        except Exception as e:
            elapsed_time = time.time() - start_time
            return CopyResult(
                total_size=0, elapsed_time=elapsed_time, success=False, error=str(e)
            )


class SendfileCopyStrategy:
    """Strategy using sendfile system call for optimization."""

    @property
    def name(self) -> str:
        return "Sendfile Copy"

    @property
    def description(self) -> str:
        return "Copy using sendfile system call (Linux/Unix only)"

    def validate_prerequisites(self) -> list[str]:
        missing = []
        if not hasattr(os, "sendfile"):
            missing.append("sendfile system call not available")
        return missing

    def copy(self, context: CopyContext) -> CopyResult:
        start_time = time.time()
        total_size = 0

        try:
            for component in context.components:
                src_component = context.workspace_path / component
                dest_component = context.cache_dir / component

                component_size = self._copy_component_sendfile(
                    src_component, dest_component
                )
                total_size += component_size

                if context.verbose:
                    print(
                        f"  Copied {component} with sendfile: {component_size / (1024 * 1024):.1f} MB"
                    )

            elapsed_time = time.time() - start_time
            return CopyResult(
                total_size=total_size, elapsed_time=elapsed_time, success=True
            )

        except Exception as e:
            elapsed_time = time.time() - start_time
            return CopyResult(
                total_size=total_size,
                elapsed_time=elapsed_time,
                success=False,
                error=str(e),
            )

    def _copy_component_sendfile(self, src: Path, dst: Path) -> int:
        """Copy component using sendfile."""
        total_size = 0

        if dst.exists():
            shutil.rmtree(dst)

        for src_file in src.rglob("*"):
            if src_file.is_file():
                rel_path = src_file.relative_to(src)
                dst_file = dst / rel_path
                dst_file.parent.mkdir(parents=True, exist_ok=True)

                with src_file.open("rb") as fsrc, dst_file.open("wb") as fdst:
                    file_size = os.fstat(fsrc.fileno()).st_size
                    try:
                        os.sendfile(fdst.fileno(), fsrc.fileno(), 0, file_size)
                        total_size += file_size
                    except OSError:
                        # Fallback to regular copy
                        fsrc.seek(0)
                        shutil.copyfileobj(fsrc, fdst, 1024 * 1024)
                        total_size += file_size

                shutil.copystat(src_file, dst_file)

        return total_size


# ====================
# STRATEGY FACTORY
# ====================


def create_buffer_strategies(buffer_sizes_kb: list[int]) -> list[CopyStrategyProtocol]:
    """Factory function to create multiple buffer strategies."""
    return [BufferedCopyStrategy(size) for size in buffer_sizes_kb]


def create_parallel_strategies(
    base_strategies: list[CopyStrategyProtocol], worker_counts: list[int]
) -> list[CopyStrategyProtocol]:
    """Factory function to create parallel versions of strategies."""
    strategies: list[CopyStrategyProtocol] = []
    for base in base_strategies:
        for workers in worker_counts:
            strategies.append(ParallelCopyStrategy(workers, base))
    return strategies


def register_default_strategies():
    """Register default copy strategies."""
    # Baseline strategies
    STRATEGY_REGISTRY.register(BaselineShutilStrategy(), CopyStrategyType.BASELINE)

    # Optimized strategies
    for buffer_kb in [64, 128, 256, 512, 1024, 2048, 4096]:
        STRATEGY_REGISTRY.register(
            BufferedCopyStrategy(buffer_kb), CopyStrategyType.OPTIMIZED
        )

    # Parallel strategies
    for workers in [2, 3, 4]:
        STRATEGY_REGISTRY.register(
            ParallelCopyStrategy(workers), CopyStrategyType.PARALLEL
        )

    # Experimental strategies
    if hasattr(os, "sendfile"):
        STRATEGY_REGISTRY.register(
            SendfileCopyStrategy(), CopyStrategyType.EXPERIMENTAL
        )
        STRATEGY_REGISTRY.register(
            ParallelCopyStrategy(3, SendfileCopyStrategy()),
            CopyStrategyType.EXPERIMENTAL,
        )


# ====================
# BENCHMARKING FRAMEWORK
# ====================


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs."""

    runs: int = 1
    clear_cache: bool = False
    verbose: bool = False
    limit_components: int | None = None
    categories: list[CopyStrategyType] = field(
        default_factory=lambda: list(CopyStrategyType)
    )
    specific_strategies: list[str] = field(default_factory=list)


class BenchmarkRunner:
    """Main benchmark execution engine."""

    def __init__(self, registry: StrategyRegistry):
        self.registry = registry

    def run_benchmarks(
        self, workspace_path: Path, config: BenchmarkConfig
    ) -> list[dict[str, Any]]:
        """Run benchmarks according to configuration."""
        # Discover components
        components = self._discover_components(workspace_path)
        if config.limit_components:
            components = components[: config.limit_components]

        # Select strategies to run
        strategies = self._select_strategies(config)

        # Validate strategies
        self._validate_strategies(strategies)

        # Execute benchmarks
        all_results = []
        for run in range(config.runs):
            if config.runs > 1:
                print(f"\n{'#' * 60}")
                print(f"RUN {run + 1} of {config.runs}")
                print(f"{'#' * 60}")

            for strategy_id in strategies:
                strategy = self.registry.get_strategy(strategy_id)
                if strategy is None:
                    continue
                result = self._run_single_benchmark(
                    strategy, workspace_path, components, config
                )
                result["run"] = run + 1
                result["strategy_id"] = strategy_id
                all_results.append(result)

        return all_results

    def _discover_components(self, workspace_path: Path) -> list[str]:
        """Discover components to copy."""
        return [d.name for d in workspace_path.iterdir() if d.is_dir()]

    def _select_strategies(self, config: BenchmarkConfig) -> list[str]:
        """Select strategies based on configuration."""
        if config.specific_strategies:
            return config.specific_strategies

        strategies = []
        for category in config.categories:
            strategies.extend(self.registry.list_strategies(category))

        return strategies

    def _validate_strategies(self, strategy_ids: list[str]):
        """Validate selected strategies and warn about issues."""
        for strategy_id in strategy_ids:
            strategy = self.registry.get_strategy(strategy_id)
            if not strategy:
                print(f"⚠ Strategy '{strategy_id}' not found")
                continue

            missing = strategy.validate_prerequisites()
            if missing:
                print(
                    f"⚠ Strategy '{strategy.name}' missing prerequisites: {', '.join(missing)}"
                )

    def _run_single_benchmark(
        self,
        strategy: CopyStrategyProtocol,
        workspace_path: Path,
        components: list[str],
        config: BenchmarkConfig,
    ) -> dict[str, Any]:
        """Run a single benchmark."""
        print(f"\n{'=' * 50}")
        print(f"Testing: {strategy.name}")
        print(f"{'=' * 50}")

        import tempfile

        with tempfile.TemporaryDirectory(
            prefix=f"benchmark_{strategy.name.replace(' ', '_')}_"
        ) as temp_dir:
            cache_dir = Path(temp_dir)

            if config.clear_cache:
                self._clear_cache(temp_dir)

            # Create context
            context = CopyContext(
                workspace_path=workspace_path,
                cache_dir=cache_dir,
                components=components,
                verbose=config.verbose,
            )

            # Monitor resources
            process = psutil.Process()
            memory_before = process.memory_info().rss / (1024 * 1024)

            # Run the strategy
            result = strategy.copy(context)

            # Calculate resource usage
            memory_after = process.memory_info().rss / (1024 * 1024)

            # Format results
            print(f"\nResults for {strategy.name}:")
            print(f"  Success: {'✓' if result.success else '✗'}")
            print(f"  Time: {result.elapsed_time:.2f} seconds")
            print(f"  Total size: {result.total_size / (1024 * 1024 * 1024):.3f} GB")
            print(
                f"  Speed: {result.speed_mbps:.1f} MB/s"
                if result.success
                else "  Speed: N/A"
            )
            print(f"  Memory delta: {memory_after - memory_before:.1f} MB")

            if not result.success:
                print(f"  Error: {result.error}")

            return {
                "strategy_name": strategy.name,
                "success": result.success,
                "time": result.elapsed_time,
                "size": result.total_size,
                "speed_mbps": result.speed_mbps,
                "memory_delta": memory_after - memory_before,
                "error": result.error,
                "metadata": result.metadata,
            }

    def _clear_cache(self, temp_dir: str):
        """Clear system cache if possible."""
        # Implementation from original code
        pass


def print_summary(results: list[dict[str, Any]]):
    """Print benchmark summary."""
    print(f"\n{'=' * 70}")
    print("SUMMARY - SORTED BY PERFORMANCE")
    print(f"{'=' * 70}")

    successful_results = [r for r in results if r["success"]]
    sorted_results = sorted(successful_results, key=lambda x: x["time"])

    print(f"{'Strategy':<35} | {'Time':<10} | {'Speed':<12} | {'Speedup'}")
    print(f"{'-' * 35} | {'-' * 10} | {'-' * 12} | {'-' * 10}")

    baseline_time = None
    baseline_result = next(
        (r for r in sorted_results if "Baseline" in r["strategy_name"]), None
    )
    if baseline_result:
        baseline_time = baseline_result["time"]

    for i, result in enumerate(sorted_results):
        speedup = f"{baseline_time / result['time']:.1f}x" if baseline_time else "N/A"
        prefix = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "  "
        print(
            f"{prefix} {result['strategy_name']:<32} | {result['time']:>6.2f}s   | {result['speed_mbps']:>8.1f} MB/s | {speedup:>8}"
        )


if __name__ == "__main__":
    # Example usage
    register_default_strategies()

    # Show available strategies
    print("Available strategies:")
    for category in CopyStrategyType:
        strategies = STRATEGY_REGISTRY.list_strategies(category)
        if strategies:
            print(f"  {category.value}: {len(strategies)} strategies")
            for s_id in strategies[:3]:  # Show first 3
                strategy = STRATEGY_REGISTRY.get_strategy(s_id)
                if strategy is not None:
                    print(f"    - {strategy.name}")
            if len(strategies) > 3:
                print(f"    ... and {len(strategies) - 3} more")
