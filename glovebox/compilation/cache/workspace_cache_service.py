"""Simplified ZMK workspace cache service with repo and repo+branch caching."""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from glovebox.core.file_operations.models import CompilationProgress
    from glovebox.protocols.progress_context_protocol import ProgressContextProtocol
    from glovebox.protocols.progress_coordinator_protocol import (
        ProgressCoordinatorProtocol,
    )

from glovebox.cli.components.noop_progress_context import get_noop_progress_context
from glovebox.compilation.cache.models import (
    ArchiveFormat,
    WorkspaceCacheMetadata,
    WorkspaceCacheResult,
    WorkspaceExportResult,
)
from glovebox.config.models.cache import CacheLevel
from glovebox.config.user_config import UserConfig
from glovebox.core.cache.cache_manager import CacheManager
from glovebox.core.cache.models import CacheKey
from glovebox.core.file_operations import (
    CopyProgress,
    CopyProgressCallback,
    create_copy_service,
)
from glovebox.protocols.metrics_protocol import MetricsProtocol


class ZmkWorkspaceCacheService:
    """Simplified ZMK workspace cache service with two cache levels.

    Provides two cache levels:
    1. Repo-only: Includes .git folders for branch fetching (longer TTL)
    2. Repo+branch: Excludes .git folders for static branch state (shorter TTL)
    """

    def __init__(
        self,
        user_config: UserConfig,
        cache_manager: CacheManager,
        session_metrics: MetricsProtocol,
    ) -> None:
        """Initialize the workspace cache service.

        Args:
            user_config: User configuration containing cache settings
            cache_manager: Cache manager instance for data operations
        """
        self.user_config = user_config
        self.cache_manager = cache_manager
        self.logger = logging.getLogger(__name__)
        self.copy_service = create_copy_service(use_pipeline=True, max_workers=3)
        self.metrics = session_metrics

    def get_cache_directory(self) -> Path:
        """Get the workspace cache directory.

        Returns:
            Path to the workspace cache directory
        """
        return self.user_config._config.cache_path / "workspace"

    def get_ttls_for_cache_levels(self) -> dict[str, int]:
        """Get TTL values for workspace cache levels.

        Returns:
            Dictionary mapping cache levels to TTL values in seconds
        """
        cache_ttls = self.user_config._config.cache_ttls
        return cache_ttls.get_workspace_ttls()

    def _generate_cache_key(self, repository: str, branch: str | None) -> str:
        """Generate cache key for workspace.

        Args:
            repository: Git repository name (e.g., 'zmkfirmware/zmk')
            branch: Git branch name (None for repo-only caching)

        Returns:
            Generated cache key string
        """
        repo_part = repository.replace("/", "_")

        if branch is None:
            # Repo-only cache key
            parts_hash = CacheKey.from_parts(repo_part)
            return f"workspace_repo_{parts_hash}"
        else:
            # Repo+branch cache key
            parts_hash = CacheKey.from_parts(repo_part, branch)
            return f"workspace_repo_branch_{parts_hash}"

    def cache_workspace_repo_only(
        self,
        workspace_path: Path,
        repository: str,
        progress_callback: CopyProgressCallback | None = None,
        progress_coordinator: "ProgressCoordinatorProtocol | None" = None,
        progress_context: "ProgressContextProtocol | None" = None,
    ) -> WorkspaceCacheResult:
        """Cache workspace for repository-only (includes .git folders).

        Args:
            workspace_path: Path to the workspace to cache
            repository: Git repository name

        Returns:
            WorkspaceCacheResult with operation results
        """
        # Import metrics here to avoid circular dependencies

        self.metrics.set_context(
            repository=repository,
            branch=None,
            cache_level="repo",
            operation="cache_workspace_repo_only",
        )

        with self.metrics.time_operation("workspace_caching"):
            return self._cache_workspace_internal(
                workspace_path=workspace_path,
                repository=repository,
                branch=None,
                cache_level=CacheLevel.REPO,
                include_git=True,
                progress_callback=progress_callback,
                progress_coordinator=progress_coordinator,
                progress_context=progress_context,
            )

    def cache_workspace_repo_branch(
        self,
        workspace_path: Path,
        repository: str,
        branch: str,
        progress_callback: CopyProgressCallback | None = None,
        progress_coordinator: "ProgressCoordinatorProtocol | None" = None,
        progress_context: "ProgressContextProtocol | None" = None,
    ) -> WorkspaceCacheResult:
        """Cache workspace for repository+branch (excludes .git folders).

        Args:
            workspace_path: Path to the workspace to cache
            repository: Git repository name
            branch: Git branch name

        Returns:
            WorkspaceCacheResult with operation results
        """
        # Import metrics here to avoid circular dependencies
        self.metrics.set_context(
            repository=repository,
            branch=branch,
            cache_level="repo_branch",
            operation="cache_workspace_repo_branch",
        )

        with self.metrics.time_operation("workspace_caching"):
            return self._cache_workspace_internal(
                workspace_path=workspace_path,
                repository=repository,
                branch=branch,
                cache_level=CacheLevel.REPO_BRANCH,
                include_git=True,
                progress_callback=progress_callback,
                progress_coordinator=progress_coordinator,
                progress_context=progress_context,
            )

    def get_cached_workspace(
        self, repository: str, branch: str | None = None
    ) -> WorkspaceCacheResult:
        """Get cached workspace if available.

        Args:
            repository: Git repository name
            branch: Git branch name (None for repo-only lookup)

        Returns:
            WorkspaceCacheResult with cached workspace information
        """
        # Import metrics here to avoid circular dependencies

        self.metrics.set_context(
            repository=repository,
            branch=branch,
            cache_level="repo_branch" if branch else "repo",
            operation="get_cached_workspace",
        )

        return self._get_cached_workspace_internal(repository, branch, self.metrics)

    def _get_cached_workspace_internal(
        self, repository: str, branch: str | None = None, metrics: Any = None
    ) -> WorkspaceCacheResult:
        """Internal method to get cached workspace with optional metrics."""
        try:
            cache_key = self._generate_cache_key(repository, branch)

            if metrics:
                with metrics.time_operation("cache_lookup"):
                    cached_data = self.cache_manager.get(cache_key)
            else:
                cached_data = self.cache_manager.get(cache_key)

            if cached_data is None:
                cache_type = "repo+branch" if branch else "repo-only"
                if metrics:
                    metrics.record_cache_event("workspace", cache_hit=False)
                return WorkspaceCacheResult(
                    success=False,
                    error_message=f"No cached workspace found for {repository} ({cache_type})",
                )

            # Parse metadata
            metadata = WorkspaceCacheMetadata.from_cache_value(cached_data)

            # Verify workspace still exists
            if not metadata.workspace_path.exists():
                self.logger.info(
                    "Cached workspace path no longer exists: %s (treating as cache miss)",
                    metadata.workspace_path,
                )
                self.cache_manager.delete(cache_key)
                if metrics:
                    metrics.record_cache_event("workspace", cache_hit=False)
                return WorkspaceCacheResult(
                    success=False,
                    error_message=f"Cached workspace path no longer exists: {metadata.workspace_path}",
                )

            # Update access time
            metadata.update_access_time()

            # Update cache with new access time
            ttls = self.get_ttls_for_cache_levels()
            cache_level_str = (
                metadata.cache_level.value
                if hasattr(metadata.cache_level, "value")
                else str(metadata.cache_level)
            )
            ttl = ttls.get(cache_level_str, 24 * 3600)  # Default 1 day

            if metrics:
                with metrics.time_operation("cache_update"):
                    self.cache_manager.set(
                        cache_key, metadata.to_cache_value(), ttl=ttl
                    )
                    metrics.record_cache_event("workspace", cache_hit=True)
                    workspace_size_mb = (
                        metadata.size_bytes / (1024 * 1024)
                        if metadata.size_bytes
                        else 0.0
                    )
                    metrics.set_context(workspace_size_mb=workspace_size_mb)
            else:
                self.cache_manager.set(cache_key, metadata.to_cache_value(), ttl=ttl)

            return WorkspaceCacheResult(
                success=True,
                workspace_path=metadata.workspace_path,
                metadata=metadata,
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to get cached workspace: %s", e, exc_info=exc_info
            )
            return WorkspaceCacheResult(
                success=False, error_message=f"Failed to retrieve cached workspace: {e}"
            )

    def cache_workspace_from_archive(
        self,
        archive_path: Path,
        repository: str,
        branch: str | None = None,
        progress_context: "ProgressContextProtocol | None" = None,
    ) -> WorkspaceCacheResult:
        """Cache workspace by extracting archive directly to cache folder.

        This method eliminates the need for temporary directories by extracting
        archives directly into the cache location, supporting multiple formats.

        Args:
            archive_path: Path to archive file (.zip, .tar.gz, .tar.bz2, .tar.xz)
            repository: Git repository name
            branch: Git branch name (None for repo-only caching)
            progress_context: Optional progress context (defaults to NoOp if None)

        Returns:
            WorkspaceCacheResult with operation results
        """
        # Convert None to NoOp context once at the beginning
        if progress_context is None:
            progress_context = get_noop_progress_context()

        try:
            archive_path = archive_path.resolve()

            # Start validation checkpoint
            progress_context.start_checkpoint("Validating Source")
            progress_context.log(f"Validating archive: {archive_path.name}", "info")

            if not archive_path.exists() or not archive_path.is_file():
                progress_context.fail_checkpoint("Validating Source")
                return WorkspaceCacheResult(
                    success=False,
                    error_message=f"Archive path does not exist or is not a file: {archive_path}",
                )

            # Detect archive format
            archive_format = self._detect_archive_format(archive_path)
            if not archive_format:
                progress_context.fail_checkpoint("Validating Source")
                return WorkspaceCacheResult(
                    success=False,
                    error_message=f"Unsupported archive format: {archive_path.suffix}",
                )

            progress_context.complete_checkpoint("Validating Source")
            progress_context.log(f"Detected {archive_format} archive format", "info")

            # Determine cache level and git inclusion
            if branch is None:
                cache_level = CacheLevel.REPO
                include_git = True
            else:
                cache_level = CacheLevel.REPO_BRANCH
                include_git = False

            # Generate cache key and directory
            cache_key = self._generate_cache_key(repository, branch)
            cache_base_dir = self.get_cache_directory()
            cached_workspace_dir = cache_base_dir / cache_key
            cached_workspace_dir.mkdir(parents=True, exist_ok=True)

            # Extract archive directly to cache directory
            return self._extract_archive_to_cache(
                archive_path=archive_path,
                archive_format=archive_format,
                cache_dir=cached_workspace_dir,
                repository=repository,
                branch=branch,
                cache_level=cache_level,
                include_git=include_git,
                progress_context=progress_context,
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to cache workspace from archive: %s", e, exc_info=exc_info
            )
            progress_context.fail_checkpoint("Validating Source")
            return WorkspaceCacheResult(
                success=False,
                error_message=f"Failed to cache workspace from archive: {e}",
            )

    def inject_existing_workspace(
        self,
        workspace_path: Path,
        repository: str,
        branch: str | None = None,
        progress_callback: CopyProgressCallback | None = None,
        progress_coordinator: "ProgressCoordinatorProtocol | None" = None,
        progress_context: "ProgressContextProtocol | None" = None,
    ) -> WorkspaceCacheResult:
        """Inject an existing workspace into cache.

        Args:
            workspace_path: Path to existing workspace directory
            repository: Git repository name
            branch: Git branch name (None for repo-only injection)
            progress_callback: Optional legacy progress callback
            progress_coordinator: Optional legacy progress coordinator
            progress_context: Optional progress context (defaults to NoOp if None)

        Returns:
            WorkspaceCacheResult with operation results
        """
        # Convert None to NoOp context once at the beginning
        if progress_context is None:
            progress_context = get_noop_progress_context()

        try:
            workspace_path = workspace_path.resolve()

            # Start validation checkpoint
            progress_context.start_checkpoint("Validating Source")
            self.logger.info("Injecting workspace from %s", workspace_path)

            if not workspace_path.exists() or not workspace_path.is_dir():
                progress_context.fail_checkpoint("Validating Source")
                return WorkspaceCacheResult(
                    success=False,
                    error_message=f"Workspace path does not exist or is not a directory: {workspace_path}",
                )

            # Validate workspace structure
            required_components = ["zmk", "zephyr", "modules", ".west"]
            found_components = []
            for component in required_components:
                if (workspace_path / component).exists():
                    found_components.append(component)

            if not found_components:
                progress_context.fail_checkpoint("Validating Source")
                return WorkspaceCacheResult(
                    success=False,
                    error_message="Invalid workspace: no ZMK components found",
                )

            progress_context.complete_checkpoint("Validating Source")
            progress_context.log(
                f"Found {len(found_components)} workspace components", "info"
            )

            # Determine cache level and git inclusion
            if branch is None:
                cache_level = CacheLevel.REPO
                include_git = True
            else:
                cache_level = CacheLevel.REPO_BRANCH
                include_git = False

            # Cache the workspace by copying it
            return self._cache_workspace_internal(
                workspace_path=workspace_path,
                repository=repository,
                branch=branch,
                cache_level=cache_level,
                include_git=include_git,
                progress_callback=progress_callback,
                progress_coordinator=progress_coordinator,
                progress_context=progress_context,
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to inject existing workspace: %s", e, exc_info=exc_info
            )
            progress_context.fail_checkpoint("Validating Source")
            return WorkspaceCacheResult(
                success=False, error_message=f"Failed to inject existing workspace: {e}"
            )

    def delete_cached_workspace(
        self, repository: str, branch: str | None = None
    ) -> bool:
        """Delete cached workspace.

        Args:
            repository: Git repository name
            branch: Git branch name (None for repo-only deletion)

        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            cache_key = self._generate_cache_key(repository, branch)

            # Get workspace path before deleting metadata
            cached_data = self.cache_manager.get(cache_key)
            if cached_data:
                metadata = WorkspaceCacheMetadata.from_cache_value(cached_data)
                if metadata.workspace_path.exists():
                    shutil.rmtree(metadata.workspace_path)
                    self.logger.debug(
                        "Deleted workspace directory: %s", metadata.workspace_path
                    )

            # Delete cache entry
            result = self.cache_manager.delete(cache_key)
            if result:
                cache_type = "repo+branch" if branch else "repo-only"
                self.logger.info(
                    "Successfully deleted cached workspace: %s (%s)",
                    repository,
                    cache_type,
                )

            return result

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to delete cached workspace: %s", e, exc_info=exc_info
            )
            return False

    def list_cached_workspaces(self) -> list[WorkspaceCacheMetadata]:
        """List all cached workspaces.

        Returns:
            List of WorkspaceCacheMetadata for all cached workspaces
        """
        try:
            all_keys = self.cache_manager.keys()
            workspace_keys = [
                key
                for key in all_keys
                if key.startswith("workspace_repo_")
                or key.startswith("workspace_repo_branch_")
            ]

            workspaces = []
            for key in workspace_keys:
                try:
                    cached_data = self.cache_manager.get(key)
                    if cached_data:
                        metadata = WorkspaceCacheMetadata.from_cache_value(cached_data)
                        # Verify workspace still exists
                        if metadata.workspace_path.exists():
                            workspaces.append(metadata)
                        else:
                            # Clean up stale entry
                            self.cache_manager.delete(key)
                            self.logger.debug("Cleaned up stale cache entry: %s", key)
                except Exception as e:
                    self.logger.warning(
                        "Failed to parse cached metadata for %s: %s", key, e
                    )

            return workspaces

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to list cached workspaces: %s", e, exc_info=exc_info
            )
            return []

    def cleanup_stale_entries(self, max_age_hours: float = 24 * 7) -> int:
        """Clean up stale cache entries older than specified age.

        Args:
            max_age_hours: Maximum age in hours before entry is considered stale

        Returns:
            Number of entries cleaned up
        """
        try:
            cleaned_count = 0
            workspaces = self.list_cached_workspaces()

            for metadata in workspaces:
                if metadata.age_hours > max_age_hours and self.delete_cached_workspace(
                    metadata.repository, metadata.branch
                ):
                    cleaned_count += 1
                    self.logger.debug(
                        "Cleaned up stale workspace cache: %s@%s (age: %.1f hours)",
                        metadata.repository,
                        metadata.branch,
                        metadata.age_hours,
                    )

            if cleaned_count > 0:
                self.logger.info(
                    "Cleaned up %d stale workspace cache entries", cleaned_count
                )

            return cleaned_count

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to cleanup stale entries: %s", e, exc_info=exc_info
            )
            return 0

    def export_cached_workspace(
        self,
        repository: str,
        branch: str | None = None,
        output_path: Path | None = None,
        archive_format: ArchiveFormat = ArchiveFormat.ZIP,
        compression_level: int | None = None,
        include_git: bool = False,
        progress_callback: CopyProgressCallback | None = None,
        progress_coordinator: "ProgressCoordinatorProtocol | None" = None,
    ) -> WorkspaceExportResult:
        """Export cached workspace to an archive file.

        Args:
            repository: Git repository name
            branch: Git branch name (None for repo-only lookup)
            output_path: Output archive path (auto-generated if None)
            archive_format: Archive format to create
            compression_level: Compression level (None for default)
            include_git: Whether to include .git folders (if available)
            progress_callback: Optional progress callback for tracking
            progress_coordinator: Optional progress coordinator for enhanced tracking

        Returns:
            WorkspaceExportResult with export operation results
        """
        import time

        # Set metrics context
        self.metrics.set_context(
            repository=repository,
            branch=branch,
            archive_format=str(archive_format),
            operation="export_cached_workspace",
        )

        start_time = time.time()

        with self.metrics.time_operation("workspace_export"):
            try:
                # Get cached workspace
                cache_result = self._get_cached_workspace_internal(
                    repository, branch, self.metrics
                )
                if not cache_result.success or not cache_result.metadata:
                    return WorkspaceExportResult(
                        success=False,
                        error_message=cache_result.error_message
                        or "Failed to get cached workspace",
                        export_path=None,
                        metadata=None,
                        archive_format=None,
                        archive_size_bytes=None,
                        original_size_bytes=None,
                        compression_ratio=None,
                        export_duration_seconds=None,
                        files_count=None,
                    )

                metadata = cache_result.metadata
                workspace_path = metadata.workspace_path

                # Generate output path if not provided
                if output_path is None:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    repo_name = repository.replace("/", "_")
                    branch_part = f"_{branch}" if branch else ""
                    filename = f"{repo_name}{branch_part}_workspace_{timestamp}{archive_format.file_extension}"
                    output_path = Path.cwd() / filename

                # Ensure output directory exists
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # Set compression level
                if compression_level is None:
                    compression_level = archive_format.default_compression_level

                # Set export task as active if coordinator available
                # TODO: Enable after refactoring
                # if progress_coordinator and hasattr(
                #     progress_coordinator, "set_enhanced_task_status"
                # ):
                #     progress_coordinator.set_enhanced_task_status(
                #         "workspace_export",
                #         "active",
                #         f"Exporting to {archive_format.value}",
                #     )

                # Calculate workspace size for progress tracking
                original_size = self._calculate_directory_size(workspace_path)
                files_count = sum(1 for _ in workspace_path.rglob("*") if _.is_file())

                # Create the archive
                from glovebox.cli.commands.cache.workspace_processing import (
                    create_tar_archive,
                    create_zip_archive,
                )

                if archive_format == ArchiveFormat.ZIP:
                    create_zip_archive(
                        workspace_path,
                        output_path,
                        compression_level,
                        include_git,
                        metadata,
                        progress_callback,
                        progress_coordinator,
                    )
                else:
                    create_tar_archive(
                        workspace_path,
                        output_path,
                        archive_format,
                        compression_level,
                        include_git,
                        metadata,
                        progress_callback,
                        progress_coordinator,
                    )

                # Calculate final statistics
                export_duration = time.time() - start_time
                archive_size = output_path.stat().st_size if output_path.exists() else 0
                compression_ratio = (
                    archive_size / original_size if original_size > 0 else 0.0
                )

                # Mark export as completed
                # TODO: Enable after refactoring
                # if progress_coordinator and hasattr(
                #     progress_coordinator, "set_enhanced_task_status"
                # ):
                #     progress_coordinator.set_enhanced_task_status(
                #         "workspace_export", "completed"
                #     )

                # Update metrics
                self.metrics.set_context(
                    export_duration_seconds=export_duration,
                    archive_size_mb=archive_size / (1024 * 1024),
                    compression_ratio=compression_ratio,
                )

                self.logger.info(
                    "Successfully exported workspace %s (%s) to %s (%.1f MB -> %.1f MB, %.1f%% compression)",
                    repository,
                    "repo+branch" if branch else "repo-only",
                    output_path,
                    original_size / (1024 * 1024),
                    archive_size / (1024 * 1024),
                    (1 - compression_ratio) * 100,
                )

                return WorkspaceExportResult(
                    success=True,
                    export_path=output_path,
                    metadata=metadata,
                    archive_format=archive_format,
                    archive_size_bytes=archive_size,
                    original_size_bytes=original_size,
                    compression_ratio=compression_ratio,
                    export_duration_seconds=export_duration,
                    files_count=files_count,
                    error_message=None,
                )

            except Exception as e:
                # Mark export as failed
                # TODO: Enable after refactoring
                # if progress_coordinator and hasattr(
                #     progress_coordinator, "set_enhanced_task_status"
                # ):
                #     progress_coordinator.set_enhanced_task_status(
                #         "workspace_export", "failed"
                #     )

                exc_info = self.logger.isEnabledFor(logging.DEBUG)
                self.logger.error(
                    "Failed to export cached workspace: %s", e, exc_info=exc_info
                )
                return WorkspaceExportResult(
                    success=False,
                    error_message=f"Failed to export cached workspace: {e}",
                    export_path=None,
                    metadata=None,
                    archive_format=None,
                    archive_size_bytes=None,
                    original_size_bytes=None,
                    compression_ratio=None,
                    export_duration_seconds=None,
                    files_count=None,
                )

    def _cache_workspace_internal(
        self,
        workspace_path: Path,
        repository: str,
        branch: str | None,
        cache_level: CacheLevel,
        include_git: bool,
        progress_callback: CopyProgressCallback | None = None,
        progress_coordinator: "ProgressCoordinatorProtocol | None" = None,
        progress_context: "ProgressContextProtocol | None" = None,
    ) -> WorkspaceCacheResult:
        """Internal method to cache workspace with specified options.

        Args:
            workspace_path: Path to the workspace to cache
            repository: Git repository name
            branch: Git branch name (can be None)
            cache_level: Cache level enum value
            include_git: Whether to include .git folders
            progress_callback: Optional legacy progress callback
            progress_coordinator: Optional legacy progress coordinator
            progress_context: Optional progress context

        Returns:
            WorkspaceCacheResult with operation results
        """
        # Convert None to NoOp context once at the beginning
        if progress_context is None:
            progress_context = get_noop_progress_context()

        try:
            workspace_path = workspace_path.resolve()

            if not workspace_path.exists() or not workspace_path.is_dir():
                return WorkspaceCacheResult(
                    success=False,
                    error_message=f"Workspace path does not exist or is not a directory: {workspace_path}",
                )

            # Generate cache key and directory
            cache_key = self._generate_cache_key(repository, branch)
            self.logger.debug("Generating %s", cache_key)
            cache_base_dir = self.get_cache_directory()
            cached_workspace_dir = cache_base_dir / cache_key
            cached_workspace_dir.mkdir(parents=True, exist_ok=True)

            # Detect workspace components
            detected_components = []
            for component in ["zmk", "zephyr", "modules", ".west"]:
                component_path = workspace_path / component
                if component_path.exists() and component_path.is_dir():
                    detected_components.append(component)

            # Start copying checkpoint
            progress_context.start_checkpoint("Copying to Cache")
            progress_context.log(
                f"Copying {len(detected_components)} components to cache", "info"
            )

            # Copy workspace components with progress tracking
            total_components = len(detected_components)
            total_files_copied = 0
            total_bytes_copied = 0

            # Calculate total files and bytes for accurate progress
            component_stats = {}
            for component in detected_components:
                src_component = workspace_path / component
                try:
                    files_count = sum(
                        1 for _ in src_component.rglob("*") if _.is_file()
                    )
                    bytes_count = sum(
                        f.stat().st_size
                        for f in src_component.rglob("*")
                        if f.is_file()
                    )
                    component_stats[component] = {
                        "files": files_count,
                        "bytes": bytes_count,
                    }
                except (PermissionError, OSError):
                    component_stats[component] = {
                        "files": 100,
                        "bytes": 10 * 1024 * 1024,
                    }  # 10MB estimate

            total_estimated_files = sum(
                stats["files"] for stats in component_stats.values()
            )
            total_estimated_bytes = sum(
                stats["bytes"] for stats in component_stats.values()
            )

            for component_idx, component in enumerate(detected_components):
                src_component = workspace_path / component
                dest_component = cached_workspace_dir / component

                # Remove existing if it exists
                if dest_component.exists():
                    shutil.rmtree(dest_component)

                # Create enhanced progress callback that updates all progress systems
                component_progress_callback = None
                if progress_callback or progress_coordinator or progress_context:

                    def make_enhanced_callback(
                        comp_name: str,
                        comp_idx: int,
                        files_offset: int,
                        bytes_offset: int,
                    ) -> CopyProgressCallback:
                        def enhanced_callback(progress: CopyProgress) -> None:
                            # Update running totals
                            current_files = progress.files_processed or 0
                            current_bytes = progress.bytes_copied or 0

                            # Calculate overall progress across all components
                            overall_files = files_offset + current_files
                            overall_bytes = bytes_offset + current_bytes

                            # Update progress context
                            progress_context.update_progress(
                                overall_files,
                                total_estimated_files,
                                f"Copying {comp_name}: {progress.current_file or ''}",
                            )

                            # Update status info
                            if progress.current_file:
                                progress_context.set_status_info(
                                    {
                                        "current_file": progress.current_file,
                                        "component": f"{comp_name} ({comp_idx + 1}/{total_components})",
                                        "files_remaining": total_estimated_files
                                        - overall_files,
                                        "bytes_copied": overall_bytes,
                                        "total_bytes": total_estimated_bytes,
                                    }
                                )

                            # Update progress coordinator if available
                            # TODO: Enable after refactoring
                            # if progress_coordinator and hasattr(
                            #     progress_coordinator, "update_workspace_progress"
                            # ):
                            #     progress_coordinator.update_workspace_progress(
                            #         files_copied=overall_files,
                            #         total_files=total_estimated_files,
                            #         bytes_copied=overall_bytes,
                            #         total_bytes=total_estimated_bytes,
                            #         current_file=progress.current_file or "",
                            #         component=f"{comp_name} ({comp_idx + 1}/{total_components})",
                            #         transfer_speed_mb_s=0.0,  # Will be calculated by progress coordinator
                            #         eta_seconds=0.0,
                            #     )

                            # Also call original callback if provided
                            if progress_callback:
                                overall_progress = CopyProgress(
                                    files_processed=overall_files,
                                    total_files=total_estimated_files,
                                    bytes_copied=overall_bytes,
                                    total_bytes=total_estimated_bytes,
                                    current_file=progress.current_file,
                                    component_name=f"{comp_name} ({comp_idx + 1}/{total_components})",
                                )
                                progress_callback(overall_progress)

                        return enhanced_callback

                    component_progress_callback = make_enhanced_callback(
                        component, component_idx, total_files_copied, total_bytes_copied
                    )

                # Copy component directory
                self._copy_directory(
                    src_component,
                    dest_component,
                    include_git,
                    component_progress_callback,
                )

                # Update totals after component completion
                if component in component_stats:
                    total_files_copied += component_stats[component]["files"]
                    total_bytes_copied += component_stats[component]["bytes"]
                self.logger.debug(
                    "Copied component %s to %s (include_git=%s)",
                    component,
                    dest_component,
                    include_git,
                )

            # Calculate workspace size
            workspace_size = self._calculate_directory_size(cached_workspace_dir)

            # Create metadata
            metadata = WorkspaceCacheMetadata(
                workspace_path=cached_workspace_dir,
                repository=repository,
                branch=branch,
                cache_level=cache_level,
                cached_components=detected_components.copy(),
                size_bytes=workspace_size,
                notes=f"Cached with include_git={include_git}",
                # Explicitly provide optional fields to satisfy mypy
                commit_hash=None,
                keymap_hash=None,
                config_hash=None,
                auto_detected=False,
                auto_detected_source=None,
                build_id=None,
                build_profile=None,
                # Explicitly set datetime fields to satisfy mypy
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                # Add required fields
                creation_method="compilation",
                docker_image=None,
                west_manifest_path=None,
                dependencies_updated=None,
                creation_profile=None,
                git_remotes={},
            )

            # Complete copying checkpoint
            progress_context.complete_checkpoint("Copying to Cache")
            progress_context.start_checkpoint("Updating Metadata")

            # Store metadata in cache manager
            ttls = self.get_ttls_for_cache_levels()
            cache_level_str = (
                cache_level.value if hasattr(cache_level, "value") else str(cache_level)
            )
            ttl = ttls.get(cache_level_str, 24 * 3600)  # Default 1 day

            self.cache_manager.set(cache_key, metadata.to_cache_value(), ttl=ttl)

            cache_type = "repo+branch" if branch else "repo-only"
            self.logger.info(
                "Successfully cached workspace %s (%s) with TTL %d seconds, data at %s",
                repository,
                cache_type,
                ttl,
                cached_workspace_dir,
            )

            # Complete metadata checkpoint
            progress_context.complete_checkpoint("Updating Metadata")
            progress_context.log(
                f"Workspace cached successfully at {cached_workspace_dir}", "info"
            )

            # Start and complete finalizing checkpoint
            progress_context.start_checkpoint("Finalizing")
            progress_context.log("Completing workspace cache operation", "info")
            progress_context.complete_checkpoint("Finalizing")

            return WorkspaceCacheResult(
                success=True,
                workspace_path=cached_workspace_dir,
                metadata=metadata,
                created_new=True,
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Failed to cache workspace: %s", e, exc_info=exc_info)

            # Fail the current checkpoint
            progress_context.fail_checkpoint("Copying to Cache")
            progress_context.log(f"Failed to cache workspace: {e}", "error")

            return WorkspaceCacheResult(
                success=False, error_message=f"Failed to cache workspace: {e}"
            )

    def _copy_directory(
        self,
        src: Path,
        dest: Path,
        include_git: bool,
        progress_callback: CopyProgressCallback | None = None,
    ) -> None:
        """Copy directory with optional .git exclusion using optimized copy service.

        Args:
            src: Source directory
            dest: Destination directory
            include_git: Whether to include .git folders
            progress_callback: Optional progress callback for tracking copy progress
        """
        # Use the copy service with git exclusion and progress tracking
        result = self.copy_service.copy_directory(
            src=src,
            dst=dest,
            exclude_git=(not include_git),
            use_pipeline=True,
            progress_callback=progress_callback,
        )

        if not result.success:
            raise RuntimeError(f"Copy operation failed: {result.error}")

        self.logger.debug(
            "Directory copy completed using strategy '%s': %.1f MB in %.2f seconds (%.1f MB/s)",
            result.strategy_used,
            result.bytes_copied / (1024 * 1024),
            result.elapsed_time,
            result.speed_mbps,
        )

    def create_workspace_from_spec(
        self,
        repo_spec: str,
        keyboard_profile: Any | None = None,
        docker_image: str | None = None,
        force_recreate: bool = False,
        progress_callback: CopyProgressCallback | None = None,
        progress_coordinator: "ProgressCoordinatorProtocol | None" = None,
    ) -> WorkspaceCacheResult:
        """Create workspace from repository specification using direct creation.

        Args:
            repo_spec: Repository specification in format 'org/repo@branch'
            keyboard_profile: Optional keyboard profile for configuration
            docker_image: Optional Docker image override
            force_recreate: Whether to recreate workspace if it exists
            progress_callback: Optional progress callback
            progress_coordinator: Optional progress coordinator for enhanced tracking

        Returns:
            WorkspaceCacheResult with creation details
        """
        from glovebox.adapters import create_docker_adapter, create_file_adapter
        from glovebox.compilation.services.workspace_creation_service import (
            create_workspace_creation_service,
        )

        try:
            self.logger.info("Creating workspace from specification: %s", repo_spec)

            # Set metrics context
            self.metrics.set_context(
                operation="create_workspace_from_spec",
                repo_spec=repo_spec,
            )

            with self.metrics.time_operation("workspace_creation_from_spec"):
                # Parse repository specification to check if workspace already exists
                from glovebox.compilation.parsers.repository_spec_parser import (
                    create_repository_spec_parser,
                )

                parser = create_repository_spec_parser()
                repository_spec = parser.parse(repo_spec)

                # Check if workspace already exists
                if not force_recreate:
                    existing_result = self.get_cached_workspace(
                        repository_spec.repository, repository_spec.branch
                    )
                    if existing_result.success:
                        self.logger.info(
                            "Workspace for %s already exists at %s",
                            repo_spec,
                            existing_result.workspace_path,
                        )
                        return existing_result

                # Create workspace creation service
                docker_adapter = create_docker_adapter()
                file_adapter = create_file_adapter()

                creation_service = create_workspace_creation_service(
                    docker_adapter=docker_adapter,
                    file_adapter=file_adapter,
                    user_config=self.user_config,
                    session_metrics=self.metrics,
                    copy_service=self.copy_service,
                )

                # Create the workspace - convert CopyProgressCallback to CompilationProgressCallback
                compilation_progress_callback = None
                if progress_callback:
                    # Convert CopyProgress callback to CompilationProgress callback
                    def convert_callback(cp: "CompilationProgress") -> None:
                        # Convert CompilationProgress to CopyProgress for compatibility
                        copy_progress = CopyProgress(
                            files_processed=cp.repositories_downloaded,
                            total_files=cp.total_repositories,
                            bytes_copied=cp.bytes_downloaded,
                            total_bytes=cp.total_bytes,
                            current_file=cp.current_repository,
                            component_name=cp.compilation_phase,
                        )
                        progress_callback(copy_progress)

                    compilation_progress_callback = convert_callback

                creation_result = creation_service.create_workspace(
                    repo_spec=repo_spec,
                    keyboard_profile=keyboard_profile,
                    docker_image=docker_image,
                    force_recreate=force_recreate,
                    progress_callback=compilation_progress_callback,
                    progress_coordinator=progress_coordinator,
                )

                if not creation_result.success:
                    return WorkspaceCacheResult(
                        success=False,
                        error_message=creation_result.error_message,
                    )

                # Cache the created workspace
                if creation_result.workspace_path and creation_result.metadata:
                    cache_result = self.cache_workspace_repo_branch(
                        workspace_path=creation_result.workspace_path,
                        repository=repository_spec.repository,
                        branch=repository_spec.branch,
                        progress_callback=progress_callback,
                        progress_coordinator=progress_coordinator,
                    )

                    if cache_result.success:
                        self.logger.info(
                            "Successfully created and cached workspace for %s",
                            repo_spec,
                        )
                        return cache_result
                    else:
                        self.logger.warning(
                            "Workspace created but caching failed: %s",
                            cache_result.error_message,
                        )
                        return WorkspaceCacheResult(
                            success=True,
                            workspace_path=creation_result.workspace_path,
                            metadata=creation_result.metadata,
                            created_new=True,
                        )

                return WorkspaceCacheResult(
                    success=False,
                    error_message="Workspace creation succeeded but no workspace path returned",
                )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to create workspace from spec '%s': %s",
                repo_spec,
                e,
                exc_info=exc_info,
            )
            return WorkspaceCacheResult(
                success=False,
                error_message=f"Failed to create workspace from spec: {e}",
            )

    def update_workspace_dependencies(
        self,
        repository: str,
        branch: str | None = None,
        progress_callback: CopyProgressCallback | None = None,
        progress_coordinator: "ProgressCoordinatorProtocol | None" = None,
    ) -> WorkspaceCacheResult:
        """Update dependencies for an existing cached workspace.

        Args:
            repository: Git repository name
            branch: Git branch name (None for repo-only)
            progress_callback: Optional progress callback
            progress_coordinator: Optional progress coordinator for enhanced tracking

        Returns:
            WorkspaceCacheResult with update details
        """
        try:
            self.logger.info(
                "Updating dependencies for workspace %s@%s", repository, branch
            )

            # Set metrics context
            self.metrics.set_context(
                repository=repository,
                branch=branch,
                operation="update_workspace_dependencies",
            )

            with self.metrics.time_operation("workspace_dependencies_update"):
                # Get existing workspace
                cache_result = self.get_cached_workspace(repository, branch)
                if not cache_result.success or not cache_result.workspace_path:
                    return WorkspaceCacheResult(
                        success=False,
                        error_message=f"No cached workspace found for {repository}@{branch}",
                    )

                workspace_path = cache_result.workspace_path
                metadata = cache_result.metadata

                if not metadata:
                    return WorkspaceCacheResult(
                        success=False,
                        error_message="Workspace metadata not available",
                    )

                # Update dependencies using Docker
                from glovebox.adapters import create_docker_adapter
                from glovebox.models.docker import DockerUserContext
                from glovebox.utils.stream_process import DefaultOutputMiddleware

                docker_adapter = create_docker_adapter()
                docker_image = metadata.docker_image or "zmkfirmware/zmk-dev-arm:stable"

                # Update progress coordinator
                # TODO: Enable after refactoring
                # if progress_coordinator:
                #     progress_coordinator.transition_to_phase(
                #         "dependencies_update", f"Updating dependencies for {repository}"
                #     )

                # Run west update in Docker
                commands = [
                    "cd /workspace",
                    "west update",
                    "west zephyr-export",
                    "west status",
                ]

                user_context = DockerUserContext.detect_current_user()
                middleware = DefaultOutputMiddleware()

                result = docker_adapter.run_container(
                    image=docker_image,
                    command=["sh", "-c", "set -xeu; " + " && ".join(commands)],
                    volumes=[(str(workspace_path), "/workspace")],
                    environment={},
                    user_context=user_context,
                    middleware=middleware,
                )

                return_code, stdout, stderr = result

                if return_code != 0:
                    self.logger.error(
                        "Dependencies update failed with exit code %d", return_code
                    )
                    return WorkspaceCacheResult(
                        success=False,
                        error_message=f"Dependencies update failed (exit code {return_code})",
                    )

                # Update metadata
                metadata.update_dependencies_timestamp()

                # Re-cache the updated workspace
                cache_key = self._generate_cache_key(repository, branch)
                ttls = self.get_ttls_for_cache_levels()
                cache_level_str = (
                    metadata.cache_level.value
                    if hasattr(metadata.cache_level, "value")
                    else str(metadata.cache_level)
                )
                ttl = ttls.get(cache_level_str, 24 * 3600)

                self.cache_manager.set(cache_key, metadata.to_cache_value(), ttl=ttl)

                self.logger.info(
                    "Successfully updated dependencies for workspace %s@%s",
                    repository,
                    branch,
                )

                return WorkspaceCacheResult(
                    success=True,
                    workspace_path=workspace_path,
                    metadata=metadata,
                )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to update workspace dependencies: %s", e, exc_info=exc_info
            )
            return WorkspaceCacheResult(
                success=False,
                error_message=f"Failed to update workspace dependencies: {e}",
            )

    def update_workspace_branch(
        self,
        repository: str,
        old_branch: str,
        new_branch: str,
        progress_callback: CopyProgressCallback | None = None,
        progress_coordinator: "ProgressCoordinatorProtocol | None" = None,
    ) -> WorkspaceCacheResult:
        """Update workspace to use a different branch.

        Args:
            repository: Git repository name
            old_branch: Current branch name
            new_branch: New branch to switch to
            progress_callback: Optional progress callback
            progress_coordinator: Optional progress coordinator for enhanced tracking

        Returns:
            WorkspaceCacheResult with update details
        """
        try:
            self.logger.info(
                "Updating workspace %s from branch %s to %s",
                repository,
                old_branch,
                new_branch,
            )

            # Set metrics context
            self.metrics.set_context(
                repository=repository,
                old_branch=old_branch,
                new_branch=new_branch,
                operation="update_workspace_branch",
            )

            with self.metrics.time_operation("workspace_branch_update"):
                # Get existing workspace
                cache_result = self.get_cached_workspace(repository, old_branch)
                if not cache_result.success or not cache_result.workspace_path:
                    return WorkspaceCacheResult(
                        success=False,
                        error_message=f"No cached workspace found for {repository}@{old_branch}",
                    )

                workspace_path = cache_result.workspace_path
                metadata = cache_result.metadata

                if not metadata:
                    return WorkspaceCacheResult(
                        success=False,
                        error_message="Workspace metadata not available",
                    )

                # Update branch using Docker
                from glovebox.adapters import create_docker_adapter
                from glovebox.models.docker import DockerUserContext
                from glovebox.utils.stream_process import DefaultOutputMiddleware

                docker_adapter = create_docker_adapter()
                docker_image = metadata.docker_image or "zmkfirmware/zmk-dev-arm:stable"

                # Update progress coordinator
                # TODO: Enable after refactoring
                # if progress_coordinator:
                #     progress_coordinator.transition_to_phase(
                #         "branch_update",
                #         f"Switching {repository} from {old_branch} to {new_branch}",
                #     )

                # Run git operations in Docker
                commands = [
                    "cd /workspace/zmk",
                    "git fetch origin",
                    f"git checkout {new_branch}",
                    "git pull origin " + new_branch,
                    "cd /workspace",
                    "west update",
                    "west status",
                ]

                user_context = DockerUserContext.detect_current_user()
                middleware = DefaultOutputMiddleware()

                result = docker_adapter.run_container(
                    image=docker_image,
                    command=["sh", "-c", "set -xeu; " + " && ".join(commands)],
                    volumes=[(str(workspace_path), "/workspace")],
                    environment={},
                    user_context=user_context,
                    middleware=middleware,
                )

                return_code, stdout, stderr = result

                if return_code != 0:
                    self.logger.error(
                        "Branch update failed with exit code %d", return_code
                    )
                    return WorkspaceCacheResult(
                        success=False,
                        error_message=f"Branch update failed (exit code {return_code})",
                    )

                # Update metadata with new branch
                metadata.branch = new_branch
                metadata.update_dependencies_timestamp()

                # Remove old cache entry
                self.delete_cached_workspace(repository, old_branch)

                # Cache workspace with new branch
                cache_result = self.cache_workspace_repo_branch(
                    workspace_path=workspace_path,
                    repository=repository,
                    branch=new_branch,
                    progress_callback=progress_callback,
                    progress_coordinator=progress_coordinator,
                )

                if cache_result.success:
                    self.logger.info(
                        "Successfully updated workspace %s from branch %s to %s",
                        repository,
                        old_branch,
                        new_branch,
                    )
                    return cache_result
                else:
                    return WorkspaceCacheResult(
                        success=False,
                        error_message=f"Branch update succeeded but re-caching failed: {cache_result.error_message}",
                    )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to update workspace branch: %s", e, exc_info=exc_info
            )
            return WorkspaceCacheResult(
                success=False,
                error_message=f"Failed to update workspace branch: {e}",
            )

    def _detect_archive_format(self, archive_path: Path) -> str | None:
        """Detect archive format from file extension.

        Args:
            archive_path: Path to archive file

        Returns:
            Archive format string or None if unsupported
        """
        suffix = archive_path.suffix.lower()
        name = archive_path.name.lower()

        if suffix == ".zip":
            return "zip"
        elif suffix == ".gz" and name.endswith(".tar.gz"):
            return "tar.gz"
        elif suffix == ".bz2" and name.endswith(".tar.bz2"):
            return "tar.bz2"
        elif suffix == ".xz" and name.endswith(".tar.xz"):
            return "tar.xz"
        elif suffix in [".tar"]:
            return "tar"

        return None

    def _extract_archive_to_cache(
        self,
        archive_path: Path,
        archive_format: str,
        cache_dir: Path,
        repository: str,
        branch: str | None,
        cache_level: CacheLevel,
        include_git: bool,
        progress_context: "ProgressContextProtocol | None" = None,
    ) -> WorkspaceCacheResult:
        """Extract archive directly to cache directory.

        Args:
            archive_path: Path to archive file
            archive_format: Detected archive format
            cache_dir: Target cache directory
            repository: Git repository name
            branch: Git branch name
            cache_level: Cache level enum
            include_git: Whether to include .git folders
            progress_context: Progress context for tracking

        Returns:
            WorkspaceCacheResult with operation results
        """
        from datetime import datetime

        if progress_context is None:
            progress_context = get_noop_progress_context()

        # Track cache directory for cleanup on error/interruption
        cache_created = False

        try:
            # Ensure cache directory exists and is empty
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_created = True

            # Start extraction checkpoint
            progress_context.start_checkpoint("Extracting Files")
            progress_context.log(
                f"Extracting {archive_format} archive directly to cache", "info"
            )

            extracted_bytes = 0
            total_bytes = 0
            extracted_files = 0

            if archive_format == "zip":
                extracted_bytes, total_bytes, extracted_files = (
                    self._extract_zip_to_cache(
                        archive_path, cache_dir, include_git, progress_context
                    )
                )
            elif archive_format.startswith("tar"):
                extracted_bytes, total_bytes, extracted_files = (
                    self._extract_tar_to_cache(
                        archive_path,
                        archive_format,
                        cache_dir,
                        include_git,
                        progress_context,
                    )
                )
            else:
                progress_context.fail_checkpoint("Extracting Files")
                return WorkspaceCacheResult(
                    success=False,
                    error_message=f"Unsupported archive format: {archive_format}",
                )

            progress_context.complete_checkpoint("Extracting Files")
            progress_context.log(
                f"Extracted {extracted_files} files ({extracted_bytes / (1024 * 1024):.1f} MB)",
                "info",
            )

            # Validate and reorganize extracted workspace
            progress_context.start_checkpoint("Copying to Cache")
            workspace_structure = self._analyze_workspace_structure(cache_dir)

            if not workspace_structure["is_valid"]:
                progress_context.fail_checkpoint("Copying to Cache")
                return WorkspaceCacheResult(
                    success=False,
                    error_message=f"No valid ZMK workspace found in extracted archive. Found: {workspace_structure['found_components']}",
                )

            # Reorganize workspace if needed
            if workspace_structure["needs_reorganization"]:
                progress_context.log(
                    f"Reorganizing workspace from {workspace_structure['workspace_subdir']}",
                    "info",
                )
                self._reorganize_workspace_to_cache_root(
                    workspace_structure["workspace_path"], cache_dir, progress_context
                )

            progress_context.complete_checkpoint("Copying to Cache")

            # Calculate final workspace size
            workspace_size = self._calculate_directory_size(cache_dir)

            # Create metadata
            metadata = WorkspaceCacheMetadata(
                workspace_path=cache_dir,
                repository=repository,
                branch=branch,
                cache_level=cache_level,
                cached_components=self._detect_workspace_components(cache_dir),
                size_bytes=workspace_size,
                notes=f"Extracted from {archive_format} archive, include_git={include_git}",
                # Explicitly provide optional fields to satisfy mypy
                commit_hash=None,
                keymap_hash=None,
                config_hash=None,
                auto_detected=False,
                auto_detected_source=None,
                build_id=None,
                build_profile=None,
                # Explicitly set datetime fields to satisfy mypy
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                # Add required fields
                creation_method="archive_extraction",
                docker_image=None,
                west_manifest_path=None,
                dependencies_updated=None,
            )

            # Store in cache
            progress_context.start_checkpoint("Updating Metadata")
            cache_key = self._generate_cache_key(repository, branch)
            ttls = self.get_ttls_for_cache_levels()
            cache_level_str = (
                cache_level.value if hasattr(cache_level, "value") else str(cache_level)
            )
            ttl = ttls.get(cache_level_str, 24 * 3600)  # Default 1 day

            self.cache_manager.set(cache_key, metadata.to_cache_value(), ttl=ttl)

            cache_type = "repo+branch" if branch else "repo-only"
            self.logger.info(
                "Successfully cached workspace from %s: %s (%s), TTL: %ds at %s",
                archive_format,
                repository,
                cache_type,
                ttl,
                cache_dir,
            )

            progress_context.complete_checkpoint("Updating Metadata")
            progress_context.log(
                f"Workspace cached successfully at {cache_dir}", "info"
            )

            # Start and complete finalizing checkpoint
            progress_context.start_checkpoint("Finalizing")
            progress_context.log("Completing workspace cache operation", "info")
            progress_context.complete_checkpoint("Finalizing")

            return WorkspaceCacheResult(
                success=True,
                workspace_path=cache_dir,
                metadata=metadata,
                created_new=True,
            )

        except (KeyboardInterrupt, SystemExit):
            # Handle user interruption (Ctrl+C) - clean up and re-raise
            self.logger.info("Archive extraction interrupted by user")
            if cache_created and cache_dir.exists():
                progress_context.log("Cleaning up interrupted extraction...", "info")
                shutil.rmtree(cache_dir, ignore_errors=True)
            raise

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to extract archive to cache: %s", e, exc_info=exc_info
            )

            # Cleanup cache directory on any error
            if cache_created and cache_dir.exists():
                progress_context.log("Cleaning up failed extraction...", "info")
                shutil.rmtree(cache_dir, ignore_errors=True)

            # Fail the current checkpoint
            progress_context.fail_checkpoint("Extracting Files")
            progress_context.log(f"Failed to extract archive: {e}", "error")

            return WorkspaceCacheResult(
                success=False, error_message=f"Failed to extract archive to cache: {e}"
            )

    def _extract_zip_to_cache(
        self,
        archive_path: Path,
        cache_dir: Path,
        include_git: bool,
        progress_context: "ProgressContextProtocol | None" = None,
    ) -> tuple[int, int, int]:
        """Extract ZIP archive directly to cache directory.

        Returns:
            Tuple of (extracted_bytes, total_bytes, extracted_files)
        """
        import time
        import zipfile

        with zipfile.ZipFile(archive_path, "r") as zip_ref:
            file_list = zip_ref.infolist()
            total_uncompressed_size = sum(info.file_size for info in file_list)

            extracted_bytes = 0
            extracted_files = 0
            start_time = time.time()

            for i, file_info in enumerate(file_list):
                # Skip .git files if not including git
                if not include_git and "/.git/" in file_info.filename:
                    continue

                # Extract file
                zip_ref.extract(file_info, cache_dir)
                extracted_bytes += file_info.file_size
                extracted_files += 1

                # Update progress every 50 files or for last file
                if progress_context and (
                    (i + 1) % 50 == 0 or (i + 1) == len(file_list)
                ):
                    elapsed_time = time.time() - start_time
                    speed_mb_s = 0.0
                    eta_seconds = 0.0

                    if elapsed_time > 0 and extracted_bytes > 0:
                        speed_mb_s = (extracted_bytes / (1024 * 1024)) / elapsed_time
                        if speed_mb_s > 0:
                            remaining_bytes = total_uncompressed_size - extracted_bytes
                            eta_seconds = remaining_bytes / (speed_mb_s * 1024 * 1024)

                    progress_context.update_progress(
                        current=extracted_bytes,
                        total=total_uncompressed_size,
                        status=f"Extracting to cache: {file_info.filename}",
                    )

                    progress_context.set_status_info(
                        {
                            "current_file": file_info.filename,
                            "files_remaining": len(file_list) - (i + 1),
                            "bytes_copied": extracted_bytes,
                            "total_bytes": total_uncompressed_size,
                            "transfer_speed": speed_mb_s,
                            "eta_seconds": eta_seconds,
                        }
                    )

            return extracted_bytes, total_uncompressed_size, extracted_files

    def _extract_tar_to_cache(
        self,
        archive_path: Path,
        archive_format: str,
        cache_dir: Path,
        include_git: bool,
        progress_context: "ProgressContextProtocol | None" = None,
    ) -> tuple[int, int, int]:
        """Extract TAR archive directly to cache directory.

        Returns:
            Tuple of (extracted_bytes, total_bytes, extracted_files)
        """
        import tarfile
        import time

        # Determine compression mode
        if archive_format == "tar.gz":
            mode = "r:gz"
        elif archive_format == "tar.bz2":
            mode = "r:bz2"
        elif archive_format == "tar.xz":
            mode = "r:xz"
        else:
            mode = "r"

        with tarfile.open(archive_path, mode) as tar_ref:
            members = tar_ref.getmembers()
            total_uncompressed_size = sum(
                member.size for member in members if member.isfile()
            )

            extracted_bytes = 0
            extracted_files = 0
            start_time = time.time()

            for i, member in enumerate(members):
                # Skip .git files if not including git
                if not include_git and "/.git/" in member.name:
                    continue

                # Extract member
                tar_ref.extract(member, cache_dir)
                if member.isfile():
                    extracted_bytes += member.size
                    extracted_files += 1

                # Update progress every 50 files or for last file
                if progress_context and ((i + 1) % 50 == 0 or (i + 1) == len(members)):
                    elapsed_time = time.time() - start_time
                    speed_mb_s = 0.0
                    eta_seconds = 0.0

                    if elapsed_time > 0 and extracted_bytes > 0:
                        speed_mb_s = (extracted_bytes / (1024 * 1024)) / elapsed_time
                        if speed_mb_s > 0:
                            remaining_bytes = total_uncompressed_size - extracted_bytes
                            eta_seconds = remaining_bytes / (speed_mb_s * 1024 * 1024)

                    progress_context.update_progress(
                        current=extracted_bytes,
                        total=total_uncompressed_size,
                        status=f"Extracting to cache: {member.name}",
                    )

                    progress_context.set_status_info(
                        {
                            "current_file": member.name,
                            "files_remaining": len(members) - (i + 1),
                            "bytes_copied": extracted_bytes,
                            "total_bytes": total_uncompressed_size,
                            "transfer_speed": speed_mb_s,
                            "eta_seconds": eta_seconds,
                        }
                    )

            return extracted_bytes, total_uncompressed_size, extracted_files

    def _analyze_workspace_structure(self, cache_dir: Path) -> dict[str, any]:
        """Analyze workspace structure in extracted cache content.

        Args:
            cache_dir: Cache directory to analyze

        Returns:
            Dictionary with analysis results
        """

        def get_workspace_components(path: Path) -> list[str]:
            """Get ZMK workspace components found in path."""
            required_components = ["zmk", "zephyr", "modules", ".west"]
            found_components = [
                component
                for component in required_components
                if (path / component).exists()
            ]
            return found_components

        def is_valid_workspace(components: list[str]) -> bool:
            """Check if components constitute a valid workspace."""
            return len(components) >= 2  # Need at least 2 components

        # Check cache root directory
        root_components = get_workspace_components(cache_dir)
        if is_valid_workspace(root_components):
            return {
                "is_valid": True,
                "needs_reorganization": False,
                "workspace_path": cache_dir,
                "workspace_subdir": None,
                "found_components": root_components,
            }

        # Search subdirectories for workspace
        best_match = None
        best_score = 0

        for subdir in cache_dir.iterdir():
            if subdir.is_dir():
                components = get_workspace_components(subdir)
                score = len(components)

                if score > best_score and is_valid_workspace(components):
                    best_score = score
                    best_match = {
                        "is_valid": True,
                        "needs_reorganization": True,
                        "workspace_path": subdir,
                        "workspace_subdir": subdir.name,
                        "found_components": components,
                    }

        if best_match:
            return best_match

        # No valid workspace found anywhere
        all_found = root_components.copy()
        for subdir in cache_dir.iterdir():
            if subdir.is_dir():
                all_found.extend(get_workspace_components(subdir))

        return {
            "is_valid": False,
            "needs_reorganization": False,
            "workspace_path": None,
            "workspace_subdir": None,
            "found_components": list(set(all_found)),  # Remove duplicates
        }

    def _reorganize_workspace_to_cache_root(
        self,
        workspace_path: Path,
        cache_dir: Path,
        progress_context: "ProgressContextProtocol | None" = None,
    ) -> None:
        """Reorganize workspace from subdirectory to cache root.

        Args:
            workspace_path: Current workspace directory
            cache_dir: Target cache root directory
            progress_context: Progress context for logging
        """
        if progress_context is None:
            progress_context = get_noop_progress_context()

        temp_dir = cache_dir.parent / f"{cache_dir.name}_reorganize_temp"

        try:
            progress_context.log(
                f"Moving workspace contents from {workspace_path.name}/", "info"
            )

            # Create temporary directory for reorganization
            temp_dir.mkdir(exist_ok=True)

            # Move workspace contents to temp location
            items_moved = 0
            for item in workspace_path.iterdir():
                shutil.move(str(item), str(temp_dir / item.name))
                items_moved += 1

            progress_context.log(
                f"Moved {items_moved} workspace items to temporary location", "info"
            )

            # Clear cache directory
            shutil.rmtree(cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)

            # Move workspace contents to cache root
            items_restored = 0
            for item in temp_dir.iterdir():
                shutil.move(str(item), str(cache_dir / item.name))
                items_restored += 1

            progress_context.log(
                f"Reorganized {items_restored} items to cache root", "info"
            )

        except Exception as e:
            progress_context.log(f"Error during workspace reorganization: {e}", "error")
            raise
        finally:
            # Cleanup temp directory
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _detect_workspace_components(self, workspace_path: Path) -> list[str]:
        """Detect workspace components in the given path.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            List of detected component names
        """
        detected_components = []
        for component in ["zmk", "zephyr", "modules", ".west"]:
            if (workspace_path / component).exists():
                detected_components.append(component)
        return detected_components

    def _calculate_directory_size(self, directory: Path) -> int:
        """Calculate total size of directory in bytes.

        Args:
            directory: Directory to calculate size for

        Returns:
            Total size in bytes
        """
        total = 0
        try:
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    total += file_path.stat().st_size
        except (OSError, PermissionError):
            pass
        return total


__all__ = [
    "ZmkWorkspaceCacheService",
    "WorkspaceCacheMetadata",
    "WorkspaceCacheResult",
    "WorkspaceExportResult",
]
