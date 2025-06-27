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
    CompilationProgressCallback,
    FileCopyService,
    create_copy_service,
)
from glovebox.protocols import FileAdapterProtocol, MetricsProtocol


if TYPE_CHECKING:
    from glovebox.cli.components.unified_progress_coordinator import (
        UnifiedCompilationProgressCoordinator,
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
        progress_coordinator: "UnifiedCompilationProgressCoordinator | None" = None,
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
                return workspace_path, True, cache_type
            except Exception as e:
                exc_info = self.logger.isEnabledFor(logging.DEBUG)
                self.logger.error(
                    "Failed to use cached workspace: %s", e, exc_info=exc_info
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
        """Restore workspace from cached directory with progress tracking."""

        # Create a wrapper to use unified coordinator for progress tracking
        def copy_progress_wrapper(copy_progress: Any) -> None:
            if progress_coordinator and hasattr(copy_progress, "current_file"):
                # Use coordinator to update cache restoration progress
                progress_coordinator.update_cache_progress(
                    operation="restoring",
                    current=copy_progress.bytes_copied or 0,
                    total=copy_progress.total_bytes or 100,
                    description=copy_progress.current_file,
                )

        self.logger.info("Restoring workspace from cache: %s", cached_workspace)
        result = self.copy_service.copy_directory(
            src=cached_workspace,
            dst=workspace_path,
            exclude_git=False,
            use_pipeline=True,
            progress_callback=copy_progress_wrapper if progress_coordinator else None,
        )
        if not result.success:
            raise RuntimeError(f"Copy operation failed: {result.error}")

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
