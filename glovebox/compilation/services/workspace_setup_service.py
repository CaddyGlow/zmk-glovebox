"""ZMK workspace setup service for compilation operations."""

import logging
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from glovebox.compilation.models import ZmkCompilationConfig
from glovebox.compilation.models.west_config import (
    WestManifest,
    WestManifestConfig,
)
from glovebox.core.errors import CompilationError
from glovebox.core.file_operations import (
    CompilationProgress,
    CompilationProgressCallback,
    CopyProgress,
    CopyProgressCallback,
    FileCopyService,
    create_copy_service,
)
from glovebox.protocols import FileAdapterProtocol, MetricsProtocol


if TYPE_CHECKING:
    from glovebox.protocols.progress_coordinator_protocol import (
        ProgressCoordinatorProtocol,
    )


class WorkspaceSetupService:
    """Service for ZMK workspace setup operations."""

    def __init__(
        self,
        logger: logging.Logger,
        copy_service: FileCopyService,
        file_adapter: FileAdapterProtocol,
        session_metrics: MetricsProtocol | None = None,
    ) -> None:
        """Initialize workspace setup service."""
        self.logger = logger
        self.copy_service = copy_service
        self.file_adapter = file_adapter
        self.session_metrics = session_metrics

    def get_or_create_workspace(
        self,
        keymap_file: Path,
        config_file: Path,
        config: ZmkCompilationConfig,
        get_cached_workspace_func: Callable[
            [ZmkCompilationConfig], tuple[Path | None, bool, str | None]
        ],
        progress_callback: CompilationProgressCallback | None = None,
        progress_coordinator: "ProgressCoordinatorProtocol | None" = None,
    ) -> tuple[Path | None, bool, str | None]:
        """Get cached workspace or create new one.

        Returns:
            Tuple of (workspace_path, cache_was_used, cache_type) or (None, False, None) if failed
        """
        # Use SessionMetrics if available
        if self.session_metrics:
            workspace_operations = self.session_metrics.Counter(
                "workspace_operations_total",
                "Total workspace operations",
                ["repository", "branch", "operation"],
            )
            workspace_duration = self.session_metrics.Histogram(
                "workspace_operation_duration_seconds", "Workspace operation duration"
            )

            workspace_operations.labels(
                config.repository, config.branch, "get_or_create_workspace"
            ).inc()

            with workspace_duration.time():
                return self._get_or_create_workspace_internal(
                    keymap_file,
                    config_file,
                    config,
                    get_cached_workspace_func,
                    progress_callback,
                    progress_coordinator,
                )
        else:
            return self._get_or_create_workspace_internal(
                keymap_file,
                config_file,
                config,
                get_cached_workspace_func,
                progress_callback,
                progress_coordinator,
            )

    def _get_or_create_workspace_internal(
        self,
        keymap_file: Path,
        config_file: Path,
        config: ZmkCompilationConfig,
        get_cached_workspace_func: Callable[
            [ZmkCompilationConfig], tuple[Path | None, bool, str | None]
        ],
        progress_callback: CompilationProgressCallback | None = None,
        progress_coordinator: Any = None,
    ) -> tuple[Path | None, bool, str | None]:
        """Internal method for workspace creation."""
        # Track cache operations with SessionMetrics
        cache_operations = None
        cache_duration = None
        if self.session_metrics:
            cache_operations = self.session_metrics.Counter(
                "workspace_cache_operations_total",
                "Total workspace cache operations",
                ["operation", "result"],
            )
            cache_duration = self.session_metrics.Histogram(
                "workspace_cache_operation_duration_seconds",
                "Workspace cache operation duration",
            )

        # Try to use cached workspace
        if cache_duration:
            with cache_duration.time():
                cached_workspace, cache_used, cache_type = get_cached_workspace_func(
                    config
                )
        else:
            cached_workspace, cache_used, cache_type = get_cached_workspace_func(config)

        workspace_path = Path(tempfile.mkdtemp(prefix="zmk_"))

        if cached_workspace:
            # Create temporary workspace and copy from cache
            try:
                self.logger.info("Copying cached workspace from: %s", cached_workspace)

                if self.session_metrics:
                    workspace_restoration_duration = self.session_metrics.Histogram(
                        "workspace_restoration_duration_seconds",
                        "Workspace restoration duration",
                    )
                    with workspace_restoration_duration.time():
                        self._restore_cached_workspace(
                            cached_workspace,
                            workspace_path,
                            progress_callback,
                            progress_coordinator,
                        )
                        self.setup_workspace(
                            keymap_file, config_file, config, workspace_path
                        )
                    if cache_operations:
                        cache_operations.labels("restoration", "success").inc()
                else:
                    self._restore_cached_workspace(
                        cached_workspace,
                        workspace_path,
                        progress_callback,
                        progress_coordinator,
                    )
                    self.setup_workspace(
                        keymap_file, config_file, config, workspace_path
                    )

                self.logger.info("Successfully restored workspace from cache")

                # Mark cache restoration as successful in progress coordinator
                if progress_coordinator and hasattr(
                    progress_coordinator, "update_cache_progress"
                ):
                    progress_coordinator.update_cache_progress(
                        "completed", 100, 100, "Cache restoration completed", "success"
                    )

                return workspace_path, True, cache_type
            except Exception as e:
                exc_info = self.logger.isEnabledFor(logging.DEBUG)
                self.logger.error(
                    "Failed to use cached workspace: %s", e, exc_info=exc_info
                )

                # Mark cache restoration as failed in progress coordinator
                if progress_coordinator and hasattr(
                    progress_coordinator, "update_cache_progress"
                ):
                    progress_coordinator.update_cache_progress(
                        "failed",
                        0,
                        100,
                        f"Cache restoration failed: {str(e)[:50]}",
                        "failed",
                    )

                shutil.rmtree(workspace_path, ignore_errors=True)
                if cache_operations:
                    cache_operations.labels("restoration", "failed").inc()

        # Create fresh workspace
        if self.session_metrics:
            fresh_workspace_duration = self.session_metrics.Histogram(
                "fresh_workspace_setup_duration_seconds",
                "Fresh workspace setup duration",
            )
            with fresh_workspace_duration.time():
                self.setup_workspace(keymap_file, config_file, config, workspace_path)
        else:
            self.setup_workspace(keymap_file, config_file, config, workspace_path)

        return workspace_path, False, None

    def _restore_cached_workspace(
        self,
        cached_workspace: Path,
        workspace_path: Path,
        progress_callback: CompilationProgressCallback | None = None,
        progress_coordinator: Any = None,
    ) -> None:
        """Restore workspace from cached directory with enhanced progress tracking."""
        import time

        # Phase 1: Analyze cached workspace structure
        if progress_coordinator and hasattr(
            progress_coordinator, "set_enhanced_task_status"
        ):
            progress_coordinator.set_enhanced_task_status(
                "cache_analysis", "active", "Analyzing cached workspace"
            )

        if progress_coordinator and hasattr(
            progress_coordinator, "update_folder_scan_progress"
        ):
            progress_coordinator.update_folder_scan_progress(
                operation="cache analysis",
                directories_scanned=0,
                total_directories=4,  # Expected: zmk, zephyr, modules, .west
                files_found=0,
                current_directory=str(cached_workspace),
            )

        # Detect workspace components and calculate sizes
        expected_components = ["zmk", "zephyr", "modules", ".west"]
        detected_components = []
        total_files_to_copy = 0
        total_bytes_to_copy = 0

        for idx, component in enumerate(expected_components):
            component_path = cached_workspace / component
            if progress_coordinator and hasattr(
                progress_coordinator, "update_folder_scan_progress"
            ):
                progress_coordinator.update_folder_scan_progress(
                    operation="cache analysis",
                    directories_scanned=idx + 1,
                    total_directories=len(expected_components),
                    files_found=total_files_to_copy,
                    current_directory=str(component_path),
                )

            if component_path.exists():
                detected_components.append(component)
                # Calculate component size for accurate progress
                try:
                    component_files = sum(
                        1 for _ in component_path.rglob("*") if _.is_file()
                    )
                    component_bytes = sum(
                        f.stat().st_size
                        for f in component_path.rglob("*")
                        if f.is_file()
                    )
                    total_files_to_copy += component_files
                    total_bytes_to_copy += component_bytes
                except (PermissionError, OSError):
                    # Fallback estimates
                    total_files_to_copy += 200  # Rough estimate per component
                    total_bytes_to_copy += 50 * 1024 * 1024  # 50MB estimate

        # Mark cache analysis as completed
        if progress_coordinator and hasattr(
            progress_coordinator, "set_enhanced_task_status"
        ):
            progress_coordinator.set_enhanced_task_status("cache_analysis", "completed")

        # Phase 2: Enhanced cache restoration with component-level progress
        files_copied = 0
        bytes_copied = 0
        start_time = time.time()
        current_component = ""

        def enhanced_copy_progress_wrapper(copy_progress: CopyProgress) -> None:
            nonlocal files_copied, bytes_copied, current_component

            if not hasattr(copy_progress, "current_file"):
                return

            # Update running totals
            files_copied = copy_progress.files_processed or 0
            bytes_copied = copy_progress.bytes_copied or 0

            # Detect current component from file path
            current_file = copy_progress.current_file or ""
            for component in detected_components:
                if f"/{component}/" in current_file or current_file.startswith(
                    component
                ):
                    current_component = component
                    break

            # Calculate restoration speed and ETA
            elapsed_time = time.time() - start_time
            transfer_speed_mb_s = 0.0
            eta_seconds = 0.0

            if elapsed_time > 0 and bytes_copied > 0:
                transfer_speed_mb_s = (bytes_copied / (1024 * 1024)) / elapsed_time

                if transfer_speed_mb_s > 0:
                    remaining_bytes = total_bytes_to_copy - bytes_copied
                    eta_seconds = remaining_bytes / (transfer_speed_mb_s * 1024 * 1024)

            # Use enhanced cache restoration progress if available
            if progress_coordinator and hasattr(
                progress_coordinator, "update_cache_restoration_progress"
            ):
                progress_coordinator.update_cache_restoration_progress(
                    operation="restoring",
                    component=current_component,
                    files_copied=files_copied,
                    total_files=total_files_to_copy,
                    bytes_copied=bytes_copied,
                    total_bytes=total_bytes_to_copy,
                    current_file=current_file,
                    transfer_speed_mb_s=transfer_speed_mb_s,
                    eta_seconds=eta_seconds,
                )
            elif progress_coordinator and hasattr(
                progress_coordinator, "update_cache_progress"
            ):
                # Fallback to basic cache progress
                progress_coordinator.update_cache_progress(
                    operation="restoring",
                    current=bytes_copied,
                    total=total_bytes_to_copy,
                    description=f"{current_component}: {current_file}"
                    if current_component
                    else current_file,
                    status="in_progress",
                )

            # Also call original callback if provided - but need to handle type properly
            if progress_callback:
                # Convert copy_progress to compilation progress for callback compatibility
                compilation_progress = CompilationProgress(
                    repositories_downloaded=files_copied,
                    total_repositories=total_files_to_copy,
                    current_repository=current_file,
                    compilation_phase="cache_restoration",
                    bytes_downloaded=bytes_copied,
                    total_bytes=total_bytes_to_copy,
                )
                progress_callback(compilation_progress)

        self.logger.info("Restoring workspace from cache: %s", cached_workspace)
        self.logger.info(
            "Detected components: %s (%d files, %.1f MB)",
            detected_components,
            total_files_to_copy,
            total_bytes_to_copy / (1024 * 1024),
        )

        result = self.copy_service.copy_directory(
            src=cached_workspace,
            dst=workspace_path,
            exclude_git=False,
            use_pipeline=True,
            progress_callback=enhanced_copy_progress_wrapper
            if progress_coordinator
            else None,
        )
        if not result.success:
            raise RuntimeError(f"Copy operation failed: {result.error}")

        # Phase 3: Workspace validation
        if progress_coordinator and hasattr(
            progress_coordinator, "update_cache_restoration_progress"
        ):
            progress_coordinator.update_cache_restoration_progress(
                operation="validating",
                component="",
                files_copied=total_files_to_copy,
                total_files=total_files_to_copy,
                bytes_copied=total_bytes_to_copy,
                total_bytes=total_bytes_to_copy,
                current_file="workspace structure",
                transfer_speed_mb_s=0.0,
                eta_seconds=0.0,
            )

        self.logger.info(
            "Cache restoration completed using strategy '%s': %.1f MB in %.2f seconds (%.1f MB/s)",
            result.strategy_used,
            result.bytes_copied / (1024 * 1024),
            result.elapsed_time,
            result.speed_mbps,
        )

    def setup_workspace(
        self,
        keymap_file: Path,
        config_file: Path,
        config: ZmkCompilationConfig,
        workspace_path: Path,
    ) -> None:
        """Setup temporary workspace."""
        try:
            config_dir = workspace_path / "config"
            self.setup_config_dir(config_dir, keymap_file, config_file, config)

            config.build_matrix.to_yaml(workspace_path / "build.yaml")

        except Exception as e:
            raise CompilationError(f"Workspace setup failed: {e}") from e

    def setup_config_dir(
        self,
        config_dir: Path,
        keymap_file: Path,
        config_file: Path,
        config: ZmkCompilationConfig,
    ) -> None:
        """Setup config directory with files."""
        config_dir.mkdir(exist_ok=True)

        # Copy files
        shutil.copy2(keymap_file, config_dir / keymap_file.name)
        shutil.copy2(config_file, config_dir / config_file.name)

        # Create west.yml using proper west config models
        manifest = WestManifestConfig(
            manifest=WestManifest.from_repository_config(
                repository=config.repository,
                branch=config.branch,
                config_path="config",
                import_file="app/west.yml",
            )
        )
        self.file_adapter.write_text(config_dir / "west.yml", manifest.to_yaml())


def create_workspace_setup_service(
    file_adapter: FileAdapterProtocol,
    session_metrics: MetricsProtocol | None = None,
    copy_service: FileCopyService | None = None,
) -> WorkspaceSetupService:
    """Create workspace setup service with dependencies.

    Args:
        file_adapter: File adapter for file operations
        session_metrics: Optional session metrics for tracking operations
        copy_service: Optional copy service (creates default if not provided)

    Returns:
        Configured WorkspaceSetupService instance
    """
    logger = logging.getLogger(__name__)
    copy_service = copy_service or create_copy_service(use_pipeline=True, max_workers=3)

    return WorkspaceSetupService(
        logger=logger,
        copy_service=copy_service,
        file_adapter=file_adapter,
        session_metrics=session_metrics,
    )
