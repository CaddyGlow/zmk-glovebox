import logging
import shutil
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from glovebox.core.file_operations.models import CopyProgress, CopyResult
from glovebox.core.structlog_logger import get_struct_logger


logger = get_struct_logger(__name__)


class FastPipelineCopyStrategy:
    """Fast pipeline copy with minimal overhead."""

    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers
        self.logger = get_struct_logger(__name__)

    @property
    def name(self) -> str:
        return f"Fast Pipeline ({self.max_workers} workers)"

    def copy_directory(
        self,
        src: Path,
        dst: Path,
        exclude_git: bool = False,
        progress_callback: Callable[[CopyProgress], None] | None = None,
        **options: Any,
    ) -> CopyResult:
        """Copy directory with minimal overhead pipeline."""
        start_time = time.time()

        try:
            if not src.exists() or not src.is_dir():
                raise FileNotFoundError(f"Source directory invalid: {src}")

            if dst.exists():
                shutil.rmtree(dst)
            dst.mkdir(parents=True, exist_ok=True)

            # Quick component detection - no size calculation
            components = []
            root_files = []

            for item in src.iterdir():
                if item.is_dir() and not (exclude_git and item.name == ".git"):
                    components.append(item)
                elif item.is_file() and not (
                    exclude_git and item.name.startswith(".git")
                ):
                    root_files.append(item)

            # Simple task list - just paths
            tasks = [
                (comp, src, dst, True) for comp in components
            ]  # (path, src_base, dst_base, is_dir)
            tasks.extend([(f, src, dst, False) for f in root_files])

            if not tasks:
                return self._fallback_copy(src, dst, exclude_git, start_time)

            self.logger.debug(
                f"Fast pipeline: {len(components)} dirs, {len(root_files)} files"
            )

            # Single-phase parallel execution
            copied_total = 0
            completed = 0

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks immediately
                futures = [
                    executor.submit(self._copy_item, task, exclude_git)
                    for task in tasks
                ]

                for future in as_completed(futures):
                    try:
                        bytes_copied = future.result()
                        copied_total += bytes_copied
                        completed += 1

                        if progress_callback:
                            progress = CopyProgress(
                                files_processed=completed,
                                total_files=len(tasks),
                                bytes_copied=copied_total,
                                total_bytes=0,  # Don't calculate total - it's slow
                                current_file=f"item_{completed}",
                                component_name=f"item_{completed}",
                            )
                            progress_callback(progress)

                    except Exception as e:
                        self.logger.warning(f"Copy failed: {e}")
                        completed += 1

            elapsed_time = time.time() - start_time

            return CopyResult(
                success=True,
                bytes_copied=copied_total,
                elapsed_time=elapsed_time,
                strategy_used=self.name,
            )

        except Exception as e:
            elapsed_time = time.time() - start_time
            self.logger.error(f"Fast pipeline failed: {e}")
            return CopyResult(
                success=False,
                bytes_copied=0,
                elapsed_time=elapsed_time,
                error=str(e),
                strategy_used=self.name,
            )

    def _copy_item(self, task: tuple[Path, Path, Path, bool], exclude_git: bool) -> int:
        """Copy a single item (file or directory)."""
        item_path, src_base, dst_base, is_dir = task

        try:
            if is_dir:
                # Directory copy
                src_path = item_path
                dst_path = dst_base / item_path.name

                if dst_path.exists():
                    shutil.rmtree(dst_path)

                def ignore_git(src_dir: str, names: list[str]) -> list[str]:
                    return [".git"] if exclude_git and ".git" in names else []

                shutil.copytree(src_path, dst_path, ignore=ignore_git)
                return self._quick_size(dst_path)
            else:
                # File copy
                src_file = item_path
                dst_file = dst_base / item_path.name

                if dst_file.exists():
                    dst_file.unlink()

                shutil.copy2(src_file, dst_file)
                return dst_file.stat().st_size

        except Exception as e:
            self.logger.warning(f"Failed to copy {item_path.name}: {e}")
            return 0

    def _quick_size(self, path: Path) -> int:
        """Quick size estimation without full traversal."""
        try:
            if path.is_file():
                return path.stat().st_size

            # For directories, just sample a few files for rough estimate
            total = 0
            count = 0
            for item in path.rglob("*"):
                if item.is_file() and count < 100:  # Sample only first 100 files
                    try:
                        total += item.stat().st_size
                        count += 1
                    except OSError:
                        pass
                elif count >= 100:
                    break
            return total
        except OSError:
            return 0

    def _fallback_copy(
        self, src: Path, dst: Path, exclude_git: bool, start_time: float
    ) -> CopyResult:
        """Simple fallback copy."""
        try:

            def ignore_git(src_dir: str, names: list[str]) -> list[str]:
                return [".git"] if exclude_git and ".git" in names else []

            shutil.copytree(src, dst, ignore=ignore_git)
            bytes_copied = self._quick_size(dst)
            elapsed_time = time.time() - start_time

            return CopyResult(
                success=True,
                bytes_copied=bytes_copied,
                elapsed_time=elapsed_time,
                strategy_used=f"{self.name} (fallback)",
            )
        except Exception as e:
            elapsed_time = time.time() - start_time
            return CopyResult(
                success=False,
                bytes_copied=0,
                elapsed_time=elapsed_time,
                error=str(e),
                strategy_used=f"{self.name} (fallback)",
            )
