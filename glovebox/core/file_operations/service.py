"""Simplified file operations service with embedded strategies."""

import contextlib
import logging
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from glovebox.core.file_operations.models import (
    CopyProgress,
    CopyProgressCallback,
    CopyResult,
)
from glovebox.core.file_operations.protocols import CopyStrategyProtocol
from glovebox.core.structlog_logger import get_struct_logger


class BaselineStrategy:
    """Standard shutil.copytree strategy for baseline performance."""

    def __init__(self) -> None:
        self.logger = get_struct_logger(__name__)

    @property
    def name(self) -> str:
        return "Baseline"

    @property
    def description(self) -> str:
        return "Standard Python shutil.copytree with ignore patterns"

    def validate_prerequisites(self) -> list[str]:
        return []  # No special requirements

    def copy_directory(
        self,
        src: Path,
        dst: Path,
        exclude_git: bool = False,
        progress_callback: CopyProgressCallback | None = None,
        **options: Any,
    ) -> CopyResult:
        """Copy directory using file-by-file approach with progress tracking."""
        start_time = time.time()
        total_size = 0

        try:
            # Check if source exists
            if not src.exists():
                raise FileNotFoundError(f"Source directory does not exist: {src}")

            if not src.is_dir():
                raise NotADirectoryError(f"Source is not a directory: {src}")

            # Remove destination if it exists
            if dst.exists():
                shutil.rmtree(dst)

            # Create destination root directory
            dst.mkdir(parents=True, exist_ok=True)

            # Calculate totals for progress tracking if callback provided
            total_files = 0
            total_bytes = 0
            if progress_callback:
                total_files, total_bytes = self._calculate_totals(src, exclude_git)
                self.logger.debug(
                    "baseline_copy_processing",
                    total_files=total_files,
                    total_mb=total_bytes / (1024 * 1024),
                )

            # Copy files and directories iteratively
            files_processed = 0
            bytes_copied = 0

            for src_item in self._traverse_directory(src):
                rel_path = src_item.relative_to(src)

                # Skip .git items if requested
                if exclude_git and ".git" in rel_path.parts:
                    continue

                dst_item = dst / rel_path

                if src_item.is_dir():
                    # Create directory
                    dst_item.mkdir(parents=True, exist_ok=True)
                elif src_item.is_file():
                    # Create parent directory and copy file
                    dst_item.parent.mkdir(parents=True, exist_ok=True)
                    file_size = self._copy_single_file(src_item, dst_item)
                    total_size += file_size
                    bytes_copied += file_size
                    files_processed += 1

                    # Report progress if callback provided
                    if progress_callback:
                        progress = CopyProgress(
                            files_processed=files_processed,
                            total_files=total_files,
                            bytes_copied=bytes_copied,
                            total_bytes=total_bytes,
                            current_file=src_item.name,
                            component_name="",  # Baseline doesn't have component concept
                        )
                        progress_callback(progress)

            elapsed_time = time.time() - start_time

            self.logger.debug(
                "baseline_copy_completed",
                src=str(src),
                dst=str(dst),
                total_mb=total_size / (1024 * 1024),
                elapsed_time=elapsed_time,
            )

            return CopyResult(
                success=True,
                bytes_copied=total_size,
                elapsed_time=elapsed_time,
                strategy_used=self.name,
            )

        except Exception as e:
            elapsed_time = time.time() - start_time
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("baseline_copy_failed", error=str(e), exc_info=exc_info)
            return CopyResult(
                success=False,
                bytes_copied=total_size,
                elapsed_time=elapsed_time,
                error=str(e),
                strategy_used=self.name,
                files_copied=0,
            )

    def _copy_single_file(self, src_file: Path, dst_file: Path) -> int:
        """Copy a single file with metadata preservation."""
        shutil.copy2(src_file, dst_file)
        return src_file.stat().st_size

    def _traverse_directory(self, directory: Path) -> Any:
        """Fast directory traversal using optimal method."""
        if hasattr(os, "scandir"):
            return self._traverse_with_scandir(directory)
        else:
            return directory.rglob("*")

    def _traverse_with_scandir(self, directory: Path) -> Any:
        """Traverse directory using scandir for better performance."""
        try:
            yield from self._scandir_recursive(directory)
        except (OSError, PermissionError):
            yield from directory.rglob("*")

    def _scandir_recursive(self, directory: Path) -> Any:
        """Recursively traverse directory using os.scandir."""
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    try:
                        entry_path = Path(entry.path)
                        yield entry_path

                        if entry.is_dir():
                            yield from self._scandir_recursive(entry_path)
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass

    def _calculate_totals(self, src: Path, exclude_git: bool) -> tuple[int, int]:
        """Calculate total files and bytes for progress tracking."""
        total_files = 0
        total_bytes = 0

        try:
            for src_item in self._traverse_directory(src):
                if exclude_git and ".git" in src_item.parts:
                    continue

                if src_item.is_file():
                    try:
                        total_files += 1
                        total_bytes += src_item.stat().st_size
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass

        return total_files, total_bytes


class PipelineStrategy:
    """Pipeline copy strategy using component-level parallelism."""

    def __init__(self, max_workers: int = 3, size_calculation_workers: int = 4):
        self.max_workers = max_workers
        self.size_calculation_workers = size_calculation_workers
        self.logger = get_struct_logger(__name__)

    @property
    def name(self) -> str:
        return f"Pipeline ({self.max_workers} copy workers)"

    @property
    def description(self) -> str:
        return (
            f"Two-phase pipeline copy with {self.max_workers} component-level workers"
        )

    def validate_prerequisites(self) -> list[str]:
        return []

    def copy_directory(
        self,
        src: Path,
        dst: Path,
        exclude_git: bool = False,
        progress_callback: CopyProgressCallback | None = None,
        **options: Any,
    ) -> CopyResult:
        """Copy directory using pipeline approach with component-level parallelism."""
        start_time = time.time()
        total_size = 0

        try:
            # Check if source exists
            if not src.exists():
                raise FileNotFoundError(f"Source directory does not exist: {src}")

            if not src.is_dir():
                raise NotADirectoryError(f"Source is not a directory: {src}")

            # Remove destination if it exists
            if dst.exists():
                shutil.rmtree(dst)

            # Detect components (subdirectories of source) and root files
            components = []
            root_files = []
            for item in src.iterdir():
                if item.is_dir():
                    # Skip .git if requested
                    if exclude_git and item.name == ".git":
                        continue
                    components.append(item.name)
                elif item.is_file():
                    # Skip .git-related files if requested
                    if exclude_git and item.name.startswith(".git"):
                        continue
                    root_files.append(item.name)

            if not components and not root_files:
                # Fallback to regular copy if no components or files
                return self._fallback_copy(src, dst, exclude_git, start_time)

            # Create destination root directory only after component check
            dst.mkdir(parents=True, exist_ok=True)

            self.logger.debug(
                "pipeline_copy_detected",
                component_count=len(components),
                root_file_count=len(root_files),
                items=components + root_files,
            )

            # Phase 1: Calculate all sizes in parallel
            with ThreadPoolExecutor(
                max_workers=self.size_calculation_workers
            ) as executor:
                # Submit directory size calculations
                size_futures = {
                    executor.submit(self._get_component_info, src, comp): comp
                    for comp in components
                }

                copy_tasks = []
                # Process directory components
                for future in as_completed(size_futures):
                    component, src_path, size = future.result()
                    if src_path.exists():  # Only add existing components
                        dst_path = dst / component
                        copy_tasks.append((component, src_path, dst_path, size))
                        total_size += size

                # Add root files to copy tasks
                for file_name in root_files:
                    src_file = src / file_name
                    dst_file = dst / file_name
                    if src_file.exists():
                        file_size = src_file.stat().st_size
                        copy_tasks.append((file_name, src_file, dst_file, file_size))
                        total_size += file_size

            # Phase 2: Copy all components and files in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                copy_futures: list[Any] = []

                # Submit directory copy tasks
                for task in copy_tasks:
                    _, src_path, dst_path, _ = task
                    if src_path.is_dir():
                        copy_futures.append(
                            executor.submit(self._copy_component, task, exclude_git)
                        )
                    else:
                        # Handle individual files
                        copy_futures.append(executor.submit(self._copy_file, task))

                copied_total = 0
                completed_tasks = 0
                for future in as_completed(copy_futures):
                    try:
                        copied_size: int = future.result()  # type: ignore[assignment]
                        copied_total += copied_size
                        completed_tasks += 1

                        # Report progress if callback provided
                        if progress_callback:
                            task_name = (
                                copy_tasks[completed_tasks - 1][0]
                                if completed_tasks <= len(copy_tasks)
                                else "component"
                            )
                            progress = CopyProgress(
                                files_processed=completed_tasks,
                                total_files=len(copy_tasks),
                                bytes_copied=copied_total,
                                total_bytes=total_size,
                                current_file=task_name,
                                component_name=task_name,
                            )
                            progress_callback(progress)
                    except Exception as e:
                        self.logger.warning("component_copy_failed", error=str(e))
                        completed_tasks += 1

            elapsed_time = time.time() - start_time

            self.logger.debug(
                "pipeline_copy_completed",
                src=str(src),
                dst=str(dst),
                total_mb=copied_total / (1024 * 1024),
                elapsed_time=elapsed_time,
                component_count=len(copy_tasks),
            )

            return CopyResult(
                success=True,
                bytes_copied=copied_total,
                elapsed_time=elapsed_time,
                strategy_used=self.name,
                files_copied=completed_tasks,
            )

        except Exception as e:
            elapsed_time = time.time() - start_time
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("pipeline_copy_failed", error=str(e), exc_info=exc_info)
            return CopyResult(
                success=False,
                bytes_copied=total_size,
                elapsed_time=elapsed_time,
                error=str(e),
                strategy_used=self.name,
                files_copied=0,
            )

    def _get_component_info(
        self, src_base: Path, component: str
    ) -> tuple[str, Path, int]:
        """Get component information for pipeline copy."""
        src_path = src_base / component
        size = 0

        if src_path.exists() and src_path.is_dir():
            # Use fast scandir-based size calculation
            if hasattr(os, "scandir"):
                _, size = self._scandir_stats(src_path)
            else:
                size = self._calculate_directory_size(src_path)

        return component, src_path, size

    def _copy_component(
        self, task: tuple[str, Path, Path, int], exclude_git: bool
    ) -> int:
        """Copy a single component using shutil.copytree."""
        component, src_path, dst_path, expected_size = task

        if not src_path.exists():
            return 0

        try:
            # Remove destination if exists
            if dst_path.exists():
                shutil.rmtree(dst_path)

            # Define ignore function for git exclusion
            def ignore_patterns(src_dir: str, names: list[str]) -> list[str]:
                """Ignore function for shutil.copytree."""
                ignored = []
                if exclude_git and ".git" in names:
                    ignored.append(".git")
                return ignored

            # Use shutil.copytree for fast directory copying
            shutil.copytree(src_path, dst_path, ignore=ignore_patterns)

            # Return actual copied size
            return self._calculate_directory_size(dst_path)

        except Exception as e:
            self.logger.warning(
                "component_copy_failed", component=component, error=str(e)
            )
            return 0

    def _copy_file(self, task: tuple[str, Path, Path, int]) -> int:
        """Copy a single file for pipeline copy."""
        file_name, src_file, dst_file, expected_size = task

        if not src_file.exists():
            return 0

        try:
            # Remove destination if exists
            if dst_file.exists():
                dst_file.unlink()

            # Copy the file
            shutil.copy2(src_file, dst_file)

            # Return actual copied size
            return dst_file.stat().st_size

        except Exception as e:
            self.logger.warning("file_copy_failed", file_name=file_name, error=str(e))
            return 0

    def _fallback_copy(
        self, src: Path, dst: Path, exclude_git: bool, start_time: float
    ) -> CopyResult:
        """Fallback to baseline copy when no components detected."""
        try:

            def ignore_patterns(src_dir: str, names: list[str]) -> list[str]:
                """Ignore function for shutil.copytree."""
                ignored = []
                if exclude_git and ".git" in names:
                    ignored.append(".git")
                return ignored

            shutil.copytree(src, dst, ignore=ignore_patterns)

            bytes_copied = self._calculate_directory_size(dst)
            elapsed_time = time.time() - start_time

            # Calculate file count for tracking
            file_count, _ = self._fast_directory_stats(dst)

            return CopyResult(
                success=True,
                bytes_copied=bytes_copied,
                elapsed_time=elapsed_time,
                strategy_used=f"{self.name} (fallback)",
                files_copied=file_count,
            )

        except Exception as e:
            elapsed_time = time.time() - start_time
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "pipeline_fallback_copy_failed", error=str(e), exc_info=exc_info
            )
            return CopyResult(
                success=False,
                bytes_copied=0,
                elapsed_time=elapsed_time,
                error=str(e),
                strategy_used=f"{self.name} (fallback)",
                files_copied=0,
            )

    def _calculate_directory_size(self, directory: Path) -> int:
        """Calculate total size of directory in bytes."""
        total = 0
        try:
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    with contextlib.suppress(OSError, PermissionError):
                        total += file_path.stat().st_size
        except (OSError, PermissionError):
            pass
        return total

    def _scandir_stats(self, directory: Path) -> tuple[int, int]:
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

    def _fast_directory_stats(self, directory: Path) -> tuple[int, int]:
        """Get directory stats using fast method.

        This is an alias for _scandir_stats to maintain backwards compatibility
        with existing tests.

        Returns:
            Tuple of (file_count, total_size)
        """
        return self._scandir_stats(directory)


class FileCopyService:
    """Simplified service for optimized file copying with two strategies."""

    def __init__(self, use_pipeline: bool = True, max_workers: int = 3):
        """Initialize the file copy service.

        Args:
            use_pipeline: Whether to use pipeline strategy by default
            max_workers: Number of worker threads for pipeline strategy
        """
        self.use_pipeline = use_pipeline
        self.logger = get_struct_logger(__name__)

        # Initialize strategies
        self.baseline = BaselineStrategy()
        self.pipeline = PipelineStrategy(max_workers=max_workers)

    def copy_directory(
        self,
        src: Path,
        dst: Path,
        exclude_git: bool = False,
        use_pipeline: bool | None = None,
        progress_callback: CopyProgressCallback | None = None,
        **options: Any,
    ) -> CopyResult:
        """Copy directory using specified strategy.

        Args:
            src: Source directory path
            dst: Destination directory path
            exclude_git: Whether to exclude .git directories
            use_pipeline: Override default strategy choice
            progress_callback: Optional callback for progress reporting
            **options: Strategy-specific options

        Returns:
            CopyResult with operation details
        """
        # Determine strategy to use
        strategy_choice = (
            use_pipeline if use_pipeline is not None else self.use_pipeline
        )
        strategy = self.pipeline if strategy_choice else self.baseline

        self.logger.debug(
            "copy_strategy_selected", strategy=strategy.name, src=str(src), dst=str(dst)
        )

        # Execute copy operation
        return strategy.copy_directory(
            src, dst, exclude_git, progress_callback, **options
        )

    def get_strategies(self) -> dict[str, CopyStrategyProtocol]:
        """Get available strategies.

        Returns:
            Dictionary mapping strategy names to strategy instances
        """
        return {
            "baseline": self.baseline,
            "pipeline": self.pipeline,
        }


def create_copy_service(
    use_pipeline: bool = True, max_workers: int = 3
) -> FileCopyService:
    """Create a configured file copy service.

    Args:
        use_pipeline: Whether to use pipeline strategy by default
        max_workers: Number of worker threads for pipeline strategy

    Returns:
        Configured FileCopyService instance
    """
    return FileCopyService(use_pipeline=use_pipeline, max_workers=max_workers)


# Backward compatibility constants
BASELINE = "baseline"
PIPELINE = "pipeline"
