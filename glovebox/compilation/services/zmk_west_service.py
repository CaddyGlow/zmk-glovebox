"""ZMK config with west compilation service."""

import logging
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from glovebox.compilation.cache.compilation_build_cache_service import (
    CompilationBuildCacheService,
)
from glovebox.compilation.cache.workspace_cache_service import (
    ZmkWorkspaceCacheService,
)
from glovebox.compilation.models import (
    CompilationConfigUnion,
    ZmkCompilationConfig,
)
from glovebox.compilation.models.build_matrix import BuildMatrix
from glovebox.compilation.models.west_config import (
    WestManifest,
    WestManifestConfig,
)
from glovebox.compilation.protocols.compilation_protocols import (
    CompilationServiceProtocol,
)
from glovebox.config.user_config import UserConfig
from glovebox.core.cache.cache_manager import CacheManager
from glovebox.core.cache.models import CacheKey
from glovebox.core.errors import CompilationError
from glovebox.core.file_operations import (
    CompilationProgress,
    CompilationProgressCallback,
    FileCopyService,
    create_copy_service,
)
from glovebox.firmware.models import BuildResult, FirmwareOutputFiles
from glovebox.models.docker import DockerUserContext
from glovebox.protocols import (
    DockerAdapterProtocol,
    FileAdapterProtocol,
    MetricsProtocol,
)
from glovebox.utils.stream_process import (
    DefaultOutputMiddleware,
    OutputMiddleware,
    create_chained_middleware,
)


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile


class WorkspaceSetup:
    """Helper class for ZMK workspace setup operations."""

    def __init__(
        self,
        logger: logging.Logger,
        copy_service: FileCopyService,
        file_adapter: FileAdapterProtocol,
        session_metrics: MetricsProtocol | None = None,
    ) -> None:
        """Initialize with logger."""
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
        progress_coordinator: Any = None,
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
        # # Copy cached workspace
        # for subdir in ["modules", "zephyr", "zmk", ".west"]:
        #     src_dir = cached_workspace / subdir
        #     dst_dir = workspace_path / subdir
        #     if src_dir.exists():
        #         self.logger.debug("Copying %s to workspace", subdir)
        #         shutil.copytree(src_dir, dst_dir)
        #         # Special handling for .west directory to ensure config is preserved
        #         if subdir == ".west" and (dst_dir / "config").exists():
        #             self.logger.debug("Preserved .west/config from cached workspace")
        #     else:
        #         self.logger.debug("Subdir %s not found in cached workspace", subdir)

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


class ZmkWestService(CompilationServiceProtocol):
    """Ultra-simplified ZMK config compilation service with intelligent caching."""

    def __init__(
        self,
        docker_adapter: DockerAdapterProtocol,
        user_config: UserConfig,
        file_adapter: FileAdapterProtocol,
        cache_manager: CacheManager,
        session_metrics: MetricsProtocol,
        workspace_cache_service: ZmkWorkspaceCacheService | None = None,
        build_cache_service: CompilationBuildCacheService | None = None,
        copy_service: FileCopyService | None = None,
    ) -> None:
        """Initialize with Docker adapter, user config, file adapter, cache services, and metrics."""
        self.docker_adapter = docker_adapter
        self.user_config = user_config
        self.file_adapter = file_adapter
        self.cache_manager = cache_manager
        self.session_metrics = session_metrics
        self.logger = logging.getLogger(__name__)
        self.copy_service = copy_service or create_copy_service(
            use_pipeline=True, max_workers=3
        )

        # Initialize workspace setup helper
        self.workspace_setup = WorkspaceSetup(
            self.logger,
            copy_service=self.copy_service,
            file_adapter=file_adapter,
            session_metrics=session_metrics,
        )

        # Create cache services if not provided
        if workspace_cache_service is None:
            self.workspace_cache_service: ZmkWorkspaceCacheService | None = (
                ZmkWorkspaceCacheService(user_config, cache_manager, session_metrics)
            )
        else:
            self.workspace_cache_service = workspace_cache_service

        if build_cache_service is None:
            self.build_cache_service: CompilationBuildCacheService | None = (
                CompilationBuildCacheService(user_config, cache_manager)
            )
        else:
            self.build_cache_service = build_cache_service

    def compile(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: CompilationConfigUnion,
        keyboard_profile: "KeyboardProfile",
        progress_callback: "CompilationProgressCallback | None" = None,
    ) -> BuildResult:
        """Execute ZMK compilation."""
        self.logger.info("Starting ZMK config compilation")

        # Initialize compilation metrics if SessionMetrics available
        if self.session_metrics:
            compilation_operations = self.session_metrics.Counter(
                "compilation_operations_total",
                "Total compilation operations",
                ["keyboard_name", "firmware_version", "strategy"],
            )
            compilation_duration = self.session_metrics.Histogram(
                "compilation_duration_seconds", "Compilation operation duration"
            )

            compilation_operations.labels(
                keyboard_profile.keyboard_name,
                keyboard_profile.firmware_version or "unknown",
                "zmk_config",
            ).inc()

            with compilation_duration.time():
                return self._compile_internal(
                    keymap_file,
                    config_file,
                    output_dir,
                    config,
                    keyboard_profile,
                    progress_callback,
                )
        else:
            return self._compile_internal(
                keymap_file,
                config_file,
                output_dir,
                config,
                keyboard_profile,
                progress_callback,
            )

    def _compile_internal(
        self,
        keymap_file: Path,
        config_file: Path,
        output_dir: Path,
        config: CompilationConfigUnion,
        keyboard_profile: "KeyboardProfile",
        progress_callback: CompilationProgressCallback | None = None,
    ) -> BuildResult:
        """Execute ZMK compilation."""
        try:
            if not isinstance(config, ZmkCompilationConfig):
                return BuildResult(
                    success=False, errors=["Invalid config type for ZMK compilation"]
                )

            # Initialize cache metrics
            cache_operations = None
            cache_duration = None
            if self.session_metrics:
                cache_operations = self.session_metrics.Counter(
                    "build_cache_operations_total",
                    "Total build cache operations",
                    ["operation", "result"],
                )
                cache_duration = self.session_metrics.Histogram(
                    "build_cache_operation_duration_seconds",
                    "Build cache operation duration",
                )

            # Try to use cached build result first (most specific cache)
            if cache_duration:
                with cache_duration.time():
                    cached_build_path = self._get_cached_build_result(
                        keymap_file, config_file, config
                    )
            else:
                cached_build_path = self._get_cached_build_result(
                    keymap_file, config_file, config
                )

            if cached_build_path:
                if cache_operations:
                    cache_operations.labels("lookup", "hit").inc()

                # Create progress coordinator for cache restoration display
                progress_coordinator = None
                if progress_callback:
                    from glovebox.cli.components.unified_progress_coordinator import (
                        create_unified_progress_coordinator,
                    )

                    progress_coordinator = create_unified_progress_coordinator(
                        tui_callback=progress_callback,
                        total_boards=1,  # Not relevant for cache restoration
                        board_names=[],
                        total_repositories=1,  # Single cache operation
                    )

                    # Show cache restoration progress
                    progress_coordinator.transition_to_phase("cache_restoration", "Restoring cached build")
                    progress_coordinator.update_cache_progress("restoring", 50, 100, "Loading cached build artifacts")

                self.logger.info(
                    "Found cached build - copying artifacts and skipping compilation"
                )

                if progress_coordinator:
                    progress_coordinator.update_cache_progress("copying", 75, 100, "Copying cached artifacts")

                output_files = self._collect_files(cached_build_path, output_dir)

                if progress_coordinator:
                    progress_coordinator.update_cache_progress("completed", 100, 100, "Cache restoration completed")

                return BuildResult(
                    success=True,
                    output_files=output_files,
                    messages=["Used cached build result"],
                )

            if cache_operations:
                cache_operations.labels("lookup", "miss").inc()

            # Create unified progress coordinator early for workspace setup
            progress_coordinator = None
            if progress_callback:
                from glovebox.cli.components.unified_progress_coordinator import (
                    create_unified_progress_coordinator,
                )

                # Extract board information for progress tracking
                board_info = self._extract_board_info_from_config(config)

                progress_coordinator = create_unified_progress_coordinator(
                    tui_callback=progress_callback,
                    total_boards=board_info["total_boards"],
                    board_names=board_info["board_names"],
                    total_repositories=39,  # Default repository count
                )

            # Try to use cached workspace
            workspace_path, cache_used, cache_type = (
                self.workspace_setup.get_or_create_workspace(
                    keymap_file,
                    config_file,
                    config,
                    self._get_cached_workspace,
                    progress_callback,
                    progress_coordinator,
                )
            )
            if not workspace_path:
                self.logger.error("Workspace setup failed")
                return BuildResult(success=False, errors=["Workspace setup failed"])

            # Run compilation
            if self.session_metrics:
                docker_operations = self.session_metrics.Counter(
                    "docker_operations_total",
                    "Total Docker operations",
                    ["operation", "result"],
                )
                docker_duration = self.session_metrics.Histogram(
                    "docker_operation_duration_seconds", "Docker operation duration"
                )
                with docker_duration.time():
                    compilation_success = self._run_compilation(
                        workspace_path,
                        config,
                        cache_used,
                        cache_type,
                        progress_callback,
                        progress_coordinator,
                    )
                if compilation_success:
                    docker_operations.labels("compilation", "success").inc()
                else:
                    docker_operations.labels("compilation", "failed").inc()
            else:
                compilation_success = self._run_compilation(
                    workspace_path,
                    config,
                    cache_used,
                    cache_type,
                    progress_callback,
                    progress_coordinator,
                )

            # Cache workspace dependencies if it was created fresh (not from cache)
            # As per user request: "we never update the two cache once they are created"
            if not cache_used:
                self._cache_workspace(workspace_path, config, progress_coordinator)
            elif cache_type == "repo_only" and self.workspace_cache_service:
                # Update progress coordinator for workspace cache saving
                if progress_coordinator:
                    progress_coordinator.update_cache_saving("workspace", "Starting workspace cache save")

                cache_result = self.workspace_cache_service.cache_workspace_repo_branch(
                    workspace_path, config.repository, config.branch
                )
                if cache_result.success:
                    self.logger.info(
                        "Cached workspace (repo+branch) for %s@%s: %s",
                        config.repository,
                        config.branch,
                        cache_result.workspace_path,
                    )
                    if progress_coordinator:
                        progress_coordinator.update_cache_saving("workspace", "Workspace cache saved successfully")
                else:
                    self.logger.warning(
                        "Failed to cache workspace (repo+branch): %s",
                        cache_result.error_message,
                    )
                    if progress_coordinator:
                        progress_coordinator.update_cache_saving("workspace", f"Workspace cache failed: {cache_result.error_message}")

            # Always try to collect artifacts, even on build failure (for debugging)
            if self.session_metrics:
                artifact_duration = self.session_metrics.Histogram(
                    "artifact_collection_duration_seconds",
                    "Artifact collection duration",
                )
                with artifact_duration.time():
                    output_files = self._collect_files(workspace_path, output_dir)
            else:
                output_files = self._collect_files(workspace_path, output_dir)

            if not compilation_success:
                self.logger.error(
                    "Compilation failed, returning partial results for debugging"
                )
                return BuildResult(
                    success=False,
                    errors=["Compilation failed"],
                    output_files=output_files,  # Include partial artifacts for debugging
                )

            build_result = BuildResult(
                success=True,
                output_files=output_files,
                messages=[
                    f"Generated {'1' if output_files.main_uf2 else '0'} firmware files"
                ],
            )

            # Cache the successful build result
            self._cache_build_result(keymap_file, config_file, config, workspace_path, progress_coordinator)

            # Record final compilation metrics
            if self.session_metrics:
                artifacts_generated = self.session_metrics.Gauge(
                    "artifacts_generated", "Number of artifacts generated"
                )
                firmware_size = self.session_metrics.Gauge(
                    "firmware_size_bytes", "Firmware file size in bytes"
                )

                artifacts_generated.set(1 if output_files.main_uf2 else 0)
                if output_files.main_uf2 and output_files.main_uf2.exists():
                    firmware_size.set(output_files.main_uf2.stat().st_size)

            self.logger.info("ZMK compilation completed successfully")
            return build_result

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Compilation failed: %s", e, exc_info=exc_info)
            return BuildResult(success=False, errors=[str(e)])

    def compile_from_json(
        self,
        json_file: Path,
        output_dir: Path,
        config: CompilationConfigUnion,
        keyboard_profile: "KeyboardProfile",
        progress_callback: CompilationProgressCallback | None = None,
    ) -> BuildResult:
        """Execute compilation from JSON layout file."""
        self.logger.info("Starting JSON to firmware compilation")

        try:
            # Convert JSON to keymap/config files first
            from glovebox.adapters import create_file_adapter, create_template_adapter
            from glovebox.layout import (
                create_behavior_registry,
                create_grid_layout_formatter,
                create_layout_component_service,
                create_layout_display_service,
                create_layout_service,
            )
            from glovebox.layout.behavior.formatter import BehaviorFormatterImpl
            from glovebox.layout.zmk_generator import ZmkFileContentGenerator

            # Create all dependencies for layout service
            file_adapter = create_file_adapter()
            template_adapter = create_template_adapter()
            behavior_registry = create_behavior_registry()
            behavior_formatter = BehaviorFormatterImpl(behavior_registry)
            dtsi_generator = ZmkFileContentGenerator(behavior_formatter)
            layout_generator = create_grid_layout_formatter()
            component_service = create_layout_component_service(file_adapter)
            layout_display_service = create_layout_display_service(layout_generator)

            layout_service = create_layout_service(
                file_adapter=file_adapter,
                template_adapter=template_adapter,
                behavior_registry=behavior_registry,
                component_service=component_service,
                layout_service=layout_display_service,
                behavior_formatter=behavior_formatter,
                dtsi_generator=dtsi_generator,
            )

            # Create temporary directory for intermediate files
            with tempfile.TemporaryDirectory(prefix="json_to_keymap_") as temp_dir:
                temp_path = Path(temp_dir)
                output_prefix = temp_path / "layout"

                # Generate keymap and config files from JSON
                # Use session_metrics which is always available
                layout_session_metrics = self.session_metrics

                layout_result = layout_service.generate_from_file(
                    profile=keyboard_profile,
                    json_file_path=json_file,
                    output_file_prefix=str(output_prefix),
                    session_metrics=layout_session_metrics,
                    force=True,
                )

                if not layout_result.success:
                    return BuildResult(
                        success=False,
                        errors=[
                            f"JSON to keymap conversion failed: {', '.join(layout_result.errors)}"
                        ],
                    )

                # Get the generated files
                output_files = layout_result.get_output_files()
                keymap_file = output_files.get("keymap")
                config_file = output_files.get("conf")

                if not keymap_file or not config_file:
                    return BuildResult(
                        success=False,
                        errors=["Failed to generate keymap or config files from JSON"],
                    )

                # Now compile using the generated files
                return self.compile(
                    keymap_file=Path(keymap_file),
                    config_file=Path(config_file),
                    output_dir=output_dir,
                    config=config,
                    keyboard_profile=keyboard_profile,
                    progress_callback=progress_callback,
                )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("JSON compilation failed: %s", e, exc_info=exc_info)
            return BuildResult(success=False, errors=[str(e)])

    def validate_config(self, config: CompilationConfigUnion) -> bool:
        """Validate configuration."""
        return isinstance(config, ZmkCompilationConfig) and bool(config.image)

    def check_available(self) -> bool:
        """Check availability."""
        return self.docker_adapter is not None

    def _get_cached_workspace(
        self, config: ZmkCompilationConfig
    ) -> tuple[Path | None, bool, str | None]:
        """Get cached workspace if available using new simplified cache.

        Returns:
            Tuple of (workspace_path, cache_was_used, cache_type) or (None, False, None) if no cache found
            cache_type: 'repo_branch' or 'repo_only' to distinguish cache types
        """
        if not config.use_cache or not self.workspace_cache_service:
            return None, False, None

        # Try repo+branch lookup first (more specific) - check if it has complete dependencies
        cache_result = self.workspace_cache_service.get_cached_workspace(
            config.repository,
            config.branch,
        )

        if cache_result.success and cache_result.workspace_path:
            self.logger.debug(
                "Cache lookup (repo+branch) success: %s", cache_result.workspace_path
            )
            if cache_result.workspace_path.exists():
                self.logger.debug("Workspace path exists, checking for zmk directory")
                zmk_dir = cache_result.workspace_path / "zmk"
                if zmk_dir.exists():
                    self.logger.info(
                        "Found cached workspace (repo+branch): %s",
                        cache_result.workspace_path,
                    )
                    return cache_result.workspace_path, True, "repo_branch"
                else:
                    self.logger.warning(
                        "Cached workspace missing zmk directory: %s",
                        cache_result.workspace_path,
                    )
            else:
                self.logger.warning(
                    "Cached workspace path does not exist: %s",
                    cache_result.workspace_path,
                )
        else:
            self.logger.debug("Cache lookup (repo+branch) failed or no workspace path")

        # Try repo-only lookup (includes .git for west operations)
        cache_result = self.workspace_cache_service.get_cached_workspace(
            config.repository, None
        )

        if cache_result.success and cache_result.workspace_path:
            self.logger.debug(
                "Cache lookup (repo-only) success: %s", cache_result.workspace_path
            )
            if cache_result.workspace_path.exists():
                self.logger.debug("Workspace path exists, checking for zmk directory")
                zmk_dir = cache_result.workspace_path / "zmk"
                if zmk_dir.exists():
                    self.logger.info(
                        "Found cached workspace (repo-only): %s",
                        cache_result.workspace_path,
                    )
                    return cache_result.workspace_path, True, "repo_only"
                else:
                    self.logger.warning(
                        "Cached workspace missing zmk directory: %s",
                        cache_result.workspace_path,
                    )
            else:
                self.logger.warning(
                    "Cached workspace path does not exist: %s",
                    cache_result.workspace_path,
                )
        else:
            self.logger.debug("Cache lookup (repo-only) failed or no workspace path")

        self.logger.info("No suitable cached workspace found")
        return None, False, None

    def _cache_workspace(
        self,
        workspace_path: Path,
        config: ZmkCompilationConfig,
        progress_coordinator: Any = None,
    ) -> None:
        """Cache workspace for future use with new dual-level strategy."""
        if not config.use_cache or not self.workspace_cache_service:
            return

        if progress_coordinator:
            progress_coordinator.update_cache_saving("workspace", "Starting workspace cache")

        # Use SessionMetrics if available
        if self.session_metrics:
            cache_operations = self.session_metrics.Counter(
                "workspace_cache_storage_total",
                "Total workspace cache storage operations",
                ["repository", "branch", "operation"],
            )
            cache_operations.labels(
                config.repository, config.branch, "cache_workspace"
            ).inc()

        self._cache_workspace_internal(workspace_path, config, progress_coordinator)

    def _cache_workspace_internal(
        self,
        workspace_path: Path,
        config: ZmkCompilationConfig,
        progress_coordinator: Any = None,
    ) -> None:
        """Internal method for workspace caching."""
        if not self.workspace_cache_service:
            self.logger.warning("Workspace cache service not available")
            return

        try:
            # Cache at both levels: repo+branch (more specific, excludes .git)
            # and repo-only (less specific, includes .git for branch fetching)

            if progress_coordinator:
                progress_coordinator.update_cache_saving("workspace", "Caching repo+branch workspace")

            # Cache repo+branch level first (most commonly used)
            cache_result = self.workspace_cache_service.cache_workspace_repo_branch(
                workspace_path, config.repository, config.branch
            )

            if cache_result.success:
                self.logger.info(
                    "Cached workspace (repo+branch) for %s@%s: %s",
                    config.repository,
                    config.branch,
                    cache_result.workspace_path,
                )
                if progress_coordinator:
                    progress_coordinator.update_cache_saving("workspace", f"Repo+branch cache saved for {config.repository}@{config.branch}")
                # Track successful cache operation
                if self.session_metrics:
                    cache_success = self.session_metrics.Counter(
                        "workspace_cache_success_total",
                        "Successful workspace cache operations",
                        ["cache_type"],
                    )
                    cache_success.labels("repo_branch").inc()
            else:
                self.logger.warning(
                    "Failed to cache workspace (repo+branch): %s",
                    cache_result.error_message,
                )
                if progress_coordinator:
                    progress_coordinator.update_cache_saving("workspace", f"Repo+branch cache failed: {cache_result.error_message}")

            if progress_coordinator:
                progress_coordinator.update_cache_saving("workspace", "Caching repo-only workspace")

            # Cache repo-only level (for branch fetching scenarios)
            cache_result = self.workspace_cache_service.cache_workspace_repo_only(
                workspace_path, config.repository
            )

            if cache_result.success:
                self.logger.info(
                    "Cached workspace (repo-only) for %s: %s",
                    config.repository,
                    cache_result.workspace_path,
                )
                if progress_coordinator:
                    progress_coordinator.update_cache_saving("workspace", f"Repo-only cache saved for {config.repository}")
                # Track successful cache operation
                if self.session_metrics:
                    cache_success = self.session_metrics.Counter(
                        "workspace_cache_success_total",
                        "Successful workspace cache operations",
                        ["cache_type"],
                    )
                    cache_success.labels("repo_only").inc()
            else:
                self.logger.warning(
                    "Failed to cache workspace (repo-only): %s",
                    cache_result.error_message,
                )
                if progress_coordinator:
                    progress_coordinator.update_cache_saving("workspace", f"Repo-only cache failed: {cache_result.error_message}")

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.warning("Failed to cache workspace: %s", e, exc_info=exc_info)
            if progress_coordinator:
                progress_coordinator.update_cache_saving("workspace", f"Workspace cache error: {e}")

    def _get_cached_build_result(
        self, keymap_file: Path, config_file: Path, config: ZmkCompilationConfig
    ) -> Path | None:
        """Get cached build directory if available."""
        if not config.use_cache or not self.build_cache_service:
            return None

        # Generate cache key using the build cache service
        cache_key = self.build_cache_service.generate_cache_key_from_files(
            repository=config.repository,
            branch=config.branch,
            config_file=config_file,
            keymap_file=keymap_file,
        )

        # Get cached build directory
        cached_build_path = self.build_cache_service.get_cached_build(cache_key)

        if cached_build_path:
            self.logger.info(
                "Found cached build for %s: %s", keymap_file.name, cached_build_path
            )

        return cached_build_path

    def _cache_build_result(
        self,
        keymap_file: Path,
        config_file: Path,
        config: ZmkCompilationConfig,
        workspace_path: Path,
        progress_coordinator: Any = None,
    ) -> None:
        """Cache successful build directory for future use."""
        if not config.use_cache or not self.build_cache_service:
            return

        if progress_coordinator:
            progress_coordinator.update_cache_saving("build", "Starting build result cache")

        try:
            # Generate cache key using the build cache service
            cache_key = self.build_cache_service.generate_cache_key_from_files(
                repository=config.repository,
                branch=config.branch,
                config_file=config_file,
                keymap_file=keymap_file,
            )

            if progress_coordinator:
                progress_coordinator.update_cache_saving("build", "Caching build artifacts")

            # Cache the workspace build directory (contains all build artifacts)
            success = self.build_cache_service.cache_build_result(
                workspace_path, cache_key
            )

            if success:
                self.logger.info("Cached build result for %s", keymap_file.name)
                if progress_coordinator:
                    progress_coordinator.update_cache_saving("build", f"Build cache saved for {keymap_file.name}")
            else:
                self.logger.warning(
                    "Failed to cache build result for %s", keymap_file.name
                )
                if progress_coordinator:
                    progress_coordinator.update_cache_saving("build", f"Build cache failed for {keymap_file.name}")

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.warning(
                "Failed to cache build result: %s", e, exc_info=exc_info
            )
            if progress_coordinator:
                progress_coordinator.update_cache_saving("build", f"Build cache error: {e}")

    def _should_run_west_update(
        self,
        workspace_path: Path,
        cache_was_used: bool = False,
        cache_type: str | None = None,
    ) -> bool:
        """Determine if west update should be run based on cache usage and cache type.

        Args:
            workspace_path: Path to the workspace
            cache_was_used: Whether workspace was loaded from cache
            cache_type: Type of cache used ('repo_branch' or 'repo_only')

        Returns:
            True if west update should be run
        """
        # Always update for fresh workspaces (cache not used)
        if not cache_was_used:
            self.logger.info("Running west update for fresh workspace")
            return True

        # Skip update for all cached workspaces (dependencies should be complete)
        cache_type_desc = (
            f"for {cache_type} cache" if cache_type else "for cached workspace"
        )
        self.logger.info(
            "Skipping west update %s (dependencies should be complete)", cache_type_desc
        )
        return False

    def _run_compilation(
        self,
        workspace_path: Path,
        config: ZmkCompilationConfig,
        cache_was_used: bool = False,
        cache_type: str | None = None,
        progress_callback: CompilationProgressCallback | None = None,
        progress_coordinator: Any = None,
    ) -> bool:
        """Run Docker compilation with intelligent west update logic.

        Args:
            workspace_path: Path to the workspace
            config: ZMK compilation configuration
            cache_was_used: Whether workspace was loaded from cache
            cache_type: Type of cache used ('repo_branch' or 'repo_only')
            progress_callback: Optional callback for compilation progress updates
        """
        try:
            # Check if Docker image exists, build if not
            if not self._ensure_docker_image(config):
                self.logger.error("Failed to ensure Docker image is available")
                return False

            # Generate proper build commands using build matrix
            build_commands = self._generate_build_commands(workspace_path, config)
            if not build_commands:
                return False

            # Build base commands with conditional west initialization and update
            base_commands = ["cd /workspace"]

            # Check if workspace is already initialized (has .west/config)
            west_config_file = workspace_path / ".west" / "config"
            workspace_initialized = west_config_file.exists()

            if workspace_initialized:
                self.logger.info(
                    "Workspace already initialized (found .west/config), skipping west init"
                )
            else:
                self.logger.info("Initializing workspace with west init")
                base_commands.append("west init -l config")

            # Only run west update if needed based on cache usage and type
            if not cache_was_used:
                base_commands.append("west update")
            else:
                self.logger.info("Skipping west update for cached workspace")

            # Always run west zephyr-export to set up Zephyr environment variables
            base_commands.append("west zephyr-export")

            all_commands = base_commands + build_commands

            # Use current user context to avoid permission issues
            user_context = DockerUserContext.detect_current_user()

            self.logger.info("Running Docker compilation")

            # Create progress middleware if progress coordinator is provided
            middlewares: list[OutputMiddleware[Any]] = []
            if progress_coordinator:
                from glovebox.adapters import create_compilation_progress_middleware

                # Create middleware that delegates to existing coordinator
                middleware = create_compilation_progress_middleware(
                    progress_coordinator=progress_coordinator,
                    skip_west_update=cache_was_used,  # Skip west update if cache was used
                )

                middlewares.append(middleware)

            middlewares.append(DefaultOutputMiddleware())

            chained = create_chained_middleware(middlewares)
            result: tuple[int, list[str], list[str]] = (
                self.docker_adapter.run_container(
                    image=config.image,
                    command=["sh", "-c", "set -xeu; " + " && ".join(all_commands)],
                    volumes=[(str(workspace_path), "/workspace")],
                    environment={},  # {"JOBS": "4"},
                    user_context=user_context,
                    middleware=chained,
                )
            )
            return_code, stdout, stderr = result

            if return_code != 0:
                self.logger.error("Build failed with exit code %d", return_code)
                return False

            self.logger.info("Build completed successfully")
            return True
        except Exception as e:
            self.logger.error("Docker execution failed: %s", e)
            return False

    def _generate_build_commands(
        self, workspace_path: Path, config: ZmkCompilationConfig
    ) -> list[str]:
        """Generate west build commands from build matrix."""
        try:
            config_path = workspace_path / "config"
            app_relative_path = Path("zmk/app")

            build_yaml = workspace_path / "build.yaml"
            if not build_yaml.exists():
                self.logger.error("build.yaml not found")
                return []

            # Load and parse build matrix
            build_matrix = BuildMatrix.from_yaml(build_yaml)

            build_commands: list[str] = []

            for target in build_matrix.targets:
                build_dir = f"{target.artifact_name}"

                # Build west command
                cmd_parts = [
                    "west build",
                    f"-s {app_relative_path}",
                    f"-b {target.board}",
                    f"-d {build_dir}",
                    "--",
                ]

                # Add CMake arguments
                cmake_args = [f"-DZMK_CONFIG={config_path}"]
                if target.shield:
                    cmake_args.append(f"-DSHIELD={target.shield}")
                if target.cmake_args:
                    cmake_args.extend(target.cmake_args)
                if target.snippet:
                    cmake_args.append(f"-DZMK_EXTRA_MODULES={target.snippet}")

                cmd_parts.extend(cmake_args)
                build_commands.append(" ".join(cmd_parts))

            self.logger.info("Generated %d build commands", len(build_commands))
            return build_commands

        except Exception as e:
            self.logger.error("Failed to generate build commands: %s", e)
            return []

    def _extract_board_info(self, workspace_path: Path) -> dict[str, Any]:
        """Extract board information from build matrix for progress tracking.

        Args:
            workspace_path: Path to the workspace directory

        Returns:
            Dictionary with total_boards and board_names
        """
        try:
            build_yaml = workspace_path / "build.yaml"
            if not build_yaml.exists():
                self.logger.warning("build.yaml not found, using default single board")
                return {"total_boards": 1, "board_names": []}

            # Load build matrix to extract board information
            build_matrix = BuildMatrix.from_yaml(build_yaml)

            # Extract board names from targets
            board_names = [target.board for target in build_matrix.targets]
            total_boards = len(board_names)

            self.logger.info(
                "Detected %d boards for compilation: %s",
                total_boards,
                ", ".join(board_names),
            )

            return {
                "total_boards": total_boards,
                "board_names": board_names,
            }

        except Exception as e:
            self.logger.warning("Failed to extract board info: %s", e)
            return {"total_boards": 1, "board_names": []}

    def _extract_board_info_from_config(
        self, config: ZmkCompilationConfig
    ) -> dict[str, Any]:
        """Extract board information from ZmkCompilationConfig for early progress tracking.

        Args:
            config: ZMK compilation configuration

        Returns:
            Dictionary with total_boards and board_names
        """
        try:
            # Extract board names from build matrix in config
            if config.build_matrix and config.build_matrix.targets:
                board_names = [target.board for target in config.build_matrix.targets]
                total_boards = len(board_names)

                self.logger.info(
                    "Detected %d boards from config: %s",
                    total_boards,
                    ", ".join(board_names),
                )

                return {
                    "total_boards": total_boards,
                    "board_names": board_names,
                }
            else:
                # Fallback to default single board
                self.logger.info(
                    "No build matrix in config, using default single board"
                )
                return {"total_boards": 1, "board_names": []}

        except Exception as e:
            self.logger.error("Error extracting board info from config: %s", e)
            return {"total_boards": 1, "board_names": []}

    def _collect_files(
        self, workspace_path: Path, output_dir: Path
    ) -> FirmwareOutputFiles:
        """Collect firmware files from build directories determined by build matrix."""
        output_dir.mkdir(parents=True, exist_ok=True)
        main_uf2 = None
        artifacts_dir = None
        collected_items = []

        try:
            # Use build matrix resolver to determine expected build directories
            build_yaml = workspace_path / "build.yaml"
            if not build_yaml.exists():
                self.logger.error(
                    "build.yaml not found, cannot determine build directories"
                )
                return FirmwareOutputFiles(
                    output_dir=output_dir, main_uf2=None, artifacts_dir=None
                )

            build_matrix = BuildMatrix.from_yaml(build_yaml)

            # Look for build directories based on build matrix targets
            for target in build_matrix.targets:
                build_dir_name = target.artifact_name
                build_path = workspace_path / build_dir_name
                if not build_path.is_dir():
                    self.logger.warning(
                        "Expected build directory not found: %s", build_path
                    )
                    continue

                try:
                    cur_build_out = output_dir / build_dir_name
                    cur_build_out.mkdir(parents=True, exist_ok=True)

                    if artifacts_dir is None:
                        artifacts_dir = output_dir

                    # Copy firmware files and other artifacts
                    build_collected = self._copy_build_artifacts(
                        build_path, cur_build_out, build_dir_name
                    )
                    collected_items.extend(build_collected)

                    # Set main_uf2 to the first .uf2 file found
                    uf2_file = cur_build_out / "zmk.uf2"
                    if uf2_file.exists() and main_uf2 is None:
                        main_uf2 = uf2_file

                except Exception as e:
                    self.logger.warning(
                        "Failed to copy build directory %s: %s", build_path, e
                    )

        except Exception as e:
            self.logger.error(
                "Failed to resolve build matrix for artifact collection: %s", e
            )

        if collected_items:
            self.logger.info("Collected %d ZMK artifacts", len(collected_items))
        else:
            self.logger.warning("No build artifacts found in workspace")

        return FirmwareOutputFiles(
            output_dir=output_dir,
            main_uf2=main_uf2,
            artifacts_dir=artifacts_dir,
        )

    def _copy_build_artifacts(
        self, build_path: Path, cur_build_out: Path, build_dir_name: str
    ) -> list[str]:
        """Copy artifacts from a single build directory."""
        collected_items = []

        # Define file mappings: [source_path_from_zephyr, destination_filename]
        file_mappings = [
            # Firmware files
            ["zmk.uf2", "zmk.uf2"],
            ["zmk.hex", "zmk.hex"],
            ["zmk.bin", "zmk.bin"],
            ["zmk.elf", "zmk.elf"],
            # Configuration and debug files
            [".config", "zmk.kconfig"],
            ["zephyr.dts", "zmk.dts"],
            ["zephyr.dts.pre", "zmk.dts.pre"],
            ["include/generated/devicetree_generated.h", "devicetree_generated.h"],
        ]

        for src_path, dst_filename in file_mappings:
            src_file = build_path / "zephyr" / src_path
            dst_file = cur_build_out / dst_filename

            if src_file.exists():
                try:
                    shutil.copy2(src_file, dst_file)
                    collected_items.append(f"{build_dir_name}/{dst_filename}")
                except Exception as e:
                    self.logger.warning(
                        "Failed to copy %s to %s: %s", src_file, dst_file, e
                    )

        # Copy UF2 to base output directory with build directory name
        uf2_source = build_path / "zephyr" / "zmk.uf2"
        if uf2_source.exists():
            base_uf2 = cur_build_out.parent / f"{build_dir_name}.uf2"
            try:
                shutil.copy2(uf2_source, base_uf2)
                collected_items.append(f"{build_dir_name}.uf2")
            except Exception as e:
                self.logger.warning("Failed to copy UF2 to base: %s", e)

        return collected_items

    def _ensure_docker_image(self, config: ZmkCompilationConfig) -> bool:
        """Ensure Docker image exists, pull if not found."""
        try:
            # Parse image name and tag
            image_parts = config.image.split(":")
            image_name = image_parts[0]
            image_tag = image_parts[1] if len(image_parts) > 1 else "latest"

            # Check cache for recent image verification
            image_cache_key = CacheKey.from_parts("docker_image", image_name, image_tag)
            if self.cache_manager:
                cached_verification = self.cache_manager.get(image_cache_key)

                if cached_verification:
                    return True

            # Check if image exists
            if self.docker_adapter.image_exists(image_name, image_tag):
                # Cache verification for 1 hour to avoid repeated checks
                if self.cache_manager:
                    self.cache_manager.set(image_cache_key, True, ttl=3600)  # 1 hour
                return True

            self.logger.info("Docker image not found, pulling: %s", config.image)

            # Pull the image using the new pull_image method with middleware to show progress
            middleware = DefaultOutputMiddleware()
            result: tuple[int, list[str], list[str]] = self.docker_adapter.pull_image(
                image_name=image_name,
                image_tag=image_tag,
                middleware=middleware,
            )

            if result[0] == 0:
                self.logger.info("Successfully pulled Docker image: %s", config.image)
                # Cache successful pull for 1 hour
                if self.cache_manager:
                    self.cache_manager.set(image_cache_key, True, ttl=3600)  # 1 hour
                return True
            else:
                self.logger.error(
                    "Failed to pull Docker image: %s (exit code: %d)",
                    config.image,
                    result[0],
                )
                return False

        except Exception as e:
            self.logger.error("Error ensuring Docker image: %s", e)
            return False


def create_zmk_west_service(
    docker_adapter: DockerAdapterProtocol,
    user_config: UserConfig,
    file_adapter: FileAdapterProtocol,
    cache_manager: CacheManager,
    session_metrics: MetricsProtocol,
    workspace_cache_service: ZmkWorkspaceCacheService | None = None,
    build_cache_service: CompilationBuildCacheService | None = None,
) -> ZmkWestService:
    """Create ZMK West service with dual cache management and metrics.

    Args:
        docker_adapter: Docker adapter for container operations
        user_config: User configuration with cache settings
        file_adapter: File adapter for file operations
        cache_manager: Optional cache manager instance for both cache services
        workspace_cache_service: Optional workspace cache service
        build_cache_service: Optional build cache service
        session_metrics: Optional session metrics for tracking operations

    Returns:
        Configured ZmkWestService instance
    """
    return ZmkWestService(
        docker_adapter=docker_adapter,
        user_config=user_config,
        file_adapter=file_adapter,
        cache_manager=cache_manager,
        session_metrics=session_metrics,
        workspace_cache_service=workspace_cache_service,
        build_cache_service=build_cache_service,
    )
