"""Implementation of file copy strategies."""

# os.scandir is available in Python 3.5+ (our minimum version)
import contextlib
import logging
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .models import CopyResult
from .protocols import CopyStrategyProtocol


class BaselineCopyStrategy:
    """Standard shutil.copytree strategy for baseline performance."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    @property
    def name(self) -> str:
        return "Baseline"

    @property
    def description(self) -> str:
        return "Standard Python shutil.copytree with ignore patterns"

    def validate_prerequisites(self) -> list[str]:
        return []  # No special requirements

    def copy_directory(
        self, src: Path, dst: Path, exclude_git: bool = False, **options: Any
    ) -> CopyResult:
        """Copy directory using standard shutil.copytree."""
        start_time = time.time()

        try:

            def ignore_patterns(src_dir: str, names: list[str]) -> list[str]:
                """Ignore function for shutil.copytree."""
                ignored = []
                if exclude_git and ".git" in names:
                    ignored.append(".git")
                return ignored

            # Remove destination if it exists
            if dst.exists():
                shutil.rmtree(dst)

            # Copy with ignore patterns
            shutil.copytree(src, dst, ignore=ignore_patterns)

            # Calculate size
            bytes_copied = self._calculate_directory_size(dst)
            elapsed_time = time.time() - start_time

            self.logger.debug(
                "Baseline copy completed: %s -> %s (%.1f MB in %.2f seconds)",
                src,
                dst,
                bytes_copied / (1024 * 1024),
                elapsed_time,
            )

            return CopyResult(
                success=True,
                bytes_copied=bytes_copied,
                elapsed_time=elapsed_time,
                strategy_used=self.name,
            )

        except Exception as e:
            elapsed_time = time.time() - start_time
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Baseline copy failed: %s", e, exc_info=exc_info)
            return CopyResult(
                success=False,
                bytes_copied=0,
                elapsed_time=elapsed_time,
                error=str(e),
                strategy_used=self.name,
            )

    def _calculate_directory_size(self, directory: Path) -> int:
        """Calculate total size of directory in bytes."""
        total = 0
        try:
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    total += file_path.stat().st_size
        except (OSError, PermissionError):
            pass
        return total


class BufferedCopyStrategy:
    """Optimized copy with configurable buffer size."""

    def __init__(self, buffer_size_kb: int = 1024):
        self.buffer_size = buffer_size_kb * 1024
        self.buffer_size_kb = buffer_size_kb
        self.logger = logging.getLogger(__name__)

    @property
    def name(self) -> str:
        return f"Buffered ({self.buffer_size_kb}KB)"

    @property
    def description(self) -> str:
        return f"Custom buffered copy with {self.buffer_size_kb}KB buffer size"

    def validate_prerequisites(self) -> list[str]:
        return []

    def copy_directory(
        self, src: Path, dst: Path, exclude_git: bool = False, **options: Any
    ) -> CopyResult:
        """Copy directory using custom buffered I/O."""
        start_time = time.time()
        total_size = 0

        try:
            # Remove destination if it exists
            if dst.exists():
                shutil.rmtree(dst)

            # Create destination root directory
            dst.mkdir(parents=True, exist_ok=True)

            # Copy files and directories with buffered I/O
            for src_item in src.rglob("*"):
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
                    file_size = self._copy_file_buffered(src_item, dst_item)
                    total_size += file_size

            elapsed_time = time.time() - start_time

            self.logger.debug(
                "Buffered copy completed: %s -> %s (%.1f MB in %.2f seconds, %dKB buffer)",
                src,
                dst,
                total_size / (1024 * 1024),
                elapsed_time,
                self.buffer_size_kb,
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
            self.logger.error("Buffered copy failed: %s", e, exc_info=exc_info)
            return CopyResult(
                success=False,
                bytes_copied=total_size,
                elapsed_time=elapsed_time,
                error=str(e),
                strategy_used=self.name,
            )

    def _copy_file_buffered(self, src_file: Path, dst_file: Path) -> int:
        """Copy a single file with buffered I/O."""
        total_size = 0

        with src_file.open("rb") as fsrc, dst_file.open("wb") as fdst:
            while True:
                chunk = fsrc.read(self.buffer_size)
                if not chunk:
                    break
                fdst.write(chunk)
                total_size += len(chunk)

        # Copy metadata
        shutil.copystat(src_file, dst_file)
        return total_size


class SendfileCopyStrategy:
    """Strategy using sendfile system call for Linux/Unix optimization."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    @property
    def name(self) -> str:
        return "Sendfile"

    @property
    def description(self) -> str:
        return "Copy using sendfile system call (Linux/Unix only)"

    def validate_prerequisites(self) -> list[str]:
        missing = []
        if not hasattr(os, "sendfile"):
            missing.append("sendfile system call not available")
        return missing

    def copy_directory(
        self, src: Path, dst: Path, exclude_git: bool = False, **options: Any
    ) -> CopyResult:
        """Copy directory using sendfile system call."""
        start_time = time.time()
        total_size = 0

        try:
            # Remove destination if it exists
            if dst.exists():
                shutil.rmtree(dst)

            # Create destination root directory
            dst.mkdir(parents=True, exist_ok=True)

            # Copy files and directories with sendfile
            for src_item in src.rglob("*"):
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
                    file_size = self._copy_file_sendfile(src_item, dst_item)
                    total_size += file_size

            elapsed_time = time.time() - start_time

            self.logger.debug(
                "Sendfile copy completed: %s -> %s (%.1f MB in %.2f seconds)",
                src,
                dst,
                total_size / (1024 * 1024),
                elapsed_time,
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
            self.logger.error("Sendfile copy failed: %s", e, exc_info=exc_info)
            return CopyResult(
                success=False,
                bytes_copied=total_size,
                elapsed_time=elapsed_time,
                error=str(e),
                strategy_used=self.name,
            )

    def _copy_file_sendfile(self, src_file: Path, dst_file: Path) -> int:
        """Copy a single file using sendfile."""
        with src_file.open("rb") as fsrc, dst_file.open("wb") as fdst:
            file_size = os.fstat(fsrc.fileno()).st_size
            try:
                os.sendfile(fdst.fileno(), fsrc.fileno(), 0, file_size)
            except OSError:
                # Fallback to regular copy
                fsrc.seek(0)
                shutil.copyfileobj(fsrc, fdst, 1024 * 1024)

        # Copy metadata
        shutil.copystat(src_file, dst_file)
        return file_size


class ParallelCopyStrategy:
    """Multithreaded copy strategy for maximum performance."""

    def __init__(self, max_workers: int = 4, buffer_size_kb: int = 1024):
        self.max_workers = max_workers
        self.buffer_size = buffer_size_kb * 1024
        self.buffer_size_kb = buffer_size_kb
        self.logger = logging.getLogger(__name__)

    @property
    def name(self) -> str:
        return f"Parallel ({self.max_workers} threads, {self.buffer_size_kb}KB)"

    @property
    def description(self) -> str:
        return f"Multithreaded copy with {self.max_workers} workers and {self.buffer_size_kb}KB buffer"

    def validate_prerequisites(self) -> list[str]:
        return []

    def copy_directory(
        self, src: Path, dst: Path, exclude_git: bool = False, **options: Any
    ) -> CopyResult:
        """Copy directory using multithreaded approach."""
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

            # Collect all files to copy
            files_to_copy = []
            dirs_to_create = []

            for src_item in self._traverse_directory(src):
                rel_path = src_item.relative_to(src)

                # Skip .git items if requested
                if exclude_git and ".git" in rel_path.parts:
                    continue

                dst_item = dst / rel_path

                if src_item.is_dir():
                    dirs_to_create.append(dst_item)
                elif src_item.is_file():
                    files_to_copy.append((src_item, dst_item))

            # Create all directories first
            for dir_path in dirs_to_create:
                dir_path.mkdir(parents=True, exist_ok=True)

            # Copy files in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all copy tasks
                future_to_file = {
                    executor.submit(self._copy_file_buffered, src_file, dst_file): (
                        src_file,
                        dst_file,
                    )
                    for src_file, dst_file in files_to_copy
                }

                # Collect results
                for future in as_completed(future_to_file):
                    src_file, dst_file = future_to_file[future]
                    try:
                        file_size = future.result()
                        total_size += file_size
                    except Exception as e:
                        self.logger.warning("Failed to copy file %s: %s", src_file, e)

            elapsed_time = time.time() - start_time

            self.logger.debug(
                "Parallel copy completed: %s -> %s (%.1f MB in %.2f seconds, %d workers)",
                src,
                dst,
                total_size / (1024 * 1024),
                elapsed_time,
                self.max_workers,
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
            self.logger.error("Parallel copy failed: %s", e, exc_info=exc_info)
            return CopyResult(
                success=False,
                bytes_copied=total_size,
                elapsed_time=elapsed_time,
                error=str(e),
                strategy_used=self.name,
            )

    def _copy_file_buffered(self, src_file: Path, dst_file: Path) -> int:
        """Copy a single file with buffered I/O (thread-safe)."""
        total_size = 0

        # Ensure parent directory exists
        dst_file.parent.mkdir(parents=True, exist_ok=True)

        with src_file.open("rb") as fsrc, dst_file.open("wb") as fdst:
            while True:
                chunk = fsrc.read(self.buffer_size)
                if not chunk:
                    break
                fdst.write(chunk)
                total_size += len(chunk)

        # Copy metadata
        shutil.copystat(src_file, dst_file)
        return total_size

    def _traverse_directory(self, directory: Path) -> Any:
        """Fast directory traversal using optimal method."""
        if hasattr(os, "scandir"):
            return self._traverse_with_scandir(directory)
        else:
            return directory.rglob("*")

    def _traverse_with_scandir(self, directory: Path) -> Any:
        """Traverse directory using scandir for better performance."""
        try:
            # Use os.scandir for maximum performance (2.5x faster than rglob)
            yield from self._scandir_recursive(directory)
        except (OSError, PermissionError):
            # Fallback to rglob if scandir approach fails
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

    def _fast_directory_stats(self, directory: Path) -> tuple[int, int]:
        """Get quick statistics about directory contents."""
        file_count = 0
        total_size = 0

        try:
            if hasattr(os, "scandir"):
                # Use os.scandir for maximum speed (2.5x faster than rglob)
                file_count, total_size = self._scandir_stats(directory)
            else:
                # Fallback to rglob
                for item in directory.rglob("*"):
                    if item.is_file():
                        file_count += 1
                        with contextlib.suppress(OSError, PermissionError):
                            total_size += item.stat().st_size
        except (OSError, PermissionError):
            pass

        return file_count, total_size

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


class PipelineCopyStrategy:
    """Pipeline copy strategy using component-level parallelism."""

    def __init__(self, max_workers: int = 3, size_calculation_workers: int = 4):
        self.max_workers = max_workers
        self.size_calculation_workers = size_calculation_workers
        self.logger = logging.getLogger(__name__)

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
        self, src: Path, dst: Path, exclude_git: bool = False, **options: Any
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
                "Pipeline copy detected %d components and %d root files: %s",
                len(components),
                len(root_files),
                components + root_files,
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
                for future in as_completed(copy_futures):
                    try:
                        copied_size: int = future.result()  # type: ignore[assignment]
                        copied_total += copied_size
                    except Exception as e:
                        self.logger.warning("Component/file copy failed: %s", e)

            elapsed_time = time.time() - start_time

            self.logger.debug(
                "Pipeline copy completed: %s -> %s (%.1f MB in %.2f seconds, %d components)",
                src,
                dst,
                copied_total / (1024 * 1024),
                elapsed_time,
                len(copy_tasks),
            )

            return CopyResult(
                success=True,
                bytes_copied=copied_total,
                elapsed_time=elapsed_time,
                strategy_used=self.name,
            )

        except Exception as e:
            elapsed_time = time.time() - start_time
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Pipeline copy failed: %s", e, exc_info=exc_info)
            return CopyResult(
                success=False,
                bytes_copied=total_size,
                elapsed_time=elapsed_time,
                error=str(e),
                strategy_used=self.name,
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
            self.logger.warning("Failed to copy component %s: %s", component, e)
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
            self.logger.warning("Failed to copy file %s: %s", file_name, e)
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

            return CopyResult(
                success=True,
                bytes_copied=bytes_copied,
                elapsed_time=elapsed_time,
                strategy_used=f"{self.name} (fallback)",
            )

        except Exception as e:
            elapsed_time = time.time() - start_time
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Pipeline fallback copy failed: %s", e, exc_info=exc_info)
            return CopyResult(
                success=False,
                bytes_copied=0,
                elapsed_time=elapsed_time,
                error=str(e),
                strategy_used=f"{self.name} (fallback)",
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

    def _fast_directory_stats(self, directory: Path) -> tuple[int, int]:
        """Get quick statistics about directory contents."""
        file_count = 0
        total_size = 0

        try:
            if hasattr(os, "scandir"):
                # Use os.scandir for maximum speed (2.5x faster than rglob)
                file_count, total_size = self._scandir_stats(directory)
            else:
                # Fallback to rglob
                for item in directory.rglob("*"):
                    if item.is_file():
                        file_count += 1
                        with contextlib.suppress(OSError, PermissionError):
                            total_size += item.stat().st_size
        except (OSError, PermissionError):
            pass

        return file_count, total_size

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
