"""Simplified ZMK workspace cache service with repo and repo+branch caching."""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from glovebox.protocols.progress_coordinator_protocol import (
        ProgressCoordinatorProtocol,
    )

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
            )

    def cache_workspace_repo_branch(
        self,
        workspace_path: Path,
        repository: str,
        branch: str,
        progress_callback: CopyProgressCallback | None = None,
        progress_coordinator: "ProgressCoordinatorProtocol | None" = None,
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
                include_git=False,
                progress_callback=progress_callback,
                progress_coordinator=progress_coordinator,
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

    def inject_existing_workspace(
        self,
        workspace_path: Path,
        repository: str,
        branch: str | None = None,
        progress_callback: CopyProgressCallback | None = None,
        progress_coordinator: "ProgressCoordinatorProtocol | None" = None,
    ) -> WorkspaceCacheResult:
        """Inject an existing workspace into cache.

        Args:
            workspace_path: Path to existing workspace directory
            repository: Git repository name
            branch: Git branch name (None for repo-only injection)

        Returns:
            WorkspaceCacheResult with operation results
        """
        try:
            workspace_path = workspace_path.resolve()

            if not workspace_path.exists() or not workspace_path.is_dir():
                return WorkspaceCacheResult(
                    success=False,
                    error_message=f"Workspace path does not exist or is not a directory: {workspace_path}",
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
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to inject existing workspace: %s", e, exc_info=exc_info
            )
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
        import json
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
                cache_result = self._get_cached_workspace_internal(repository, branch, self.metrics)
                if not cache_result.success or not cache_result.metadata:
                    return WorkspaceExportResult(
                        success=False,
                        error_message=cache_result.error_message or "Failed to get cached workspace",
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
                if progress_coordinator and hasattr(progress_coordinator, "set_enhanced_task_status"):
                    progress_coordinator.set_enhanced_task_status(
                        "workspace_export", "active", f"Exporting to {archive_format.value}"
                    )

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
                compression_ratio = archive_size / original_size if original_size > 0 else 0.0

                # Mark export as completed
                if progress_coordinator and hasattr(progress_coordinator, "set_enhanced_task_status"):
                    progress_coordinator.set_enhanced_task_status("workspace_export", "completed")

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
                )

            except Exception as e:
                # Mark export as failed
                if progress_coordinator and hasattr(progress_coordinator, "set_enhanced_task_status"):
                    progress_coordinator.set_enhanced_task_status("workspace_export", "failed")

                exc_info = self.logger.isEnabledFor(logging.DEBUG)
                self.logger.error("Failed to export cached workspace: %s", e, exc_info=exc_info)
                return WorkspaceExportResult(
                    success=False,
                    error_message=f"Failed to export cached workspace: {e}",
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
    ) -> WorkspaceCacheResult:
        """Internal method to cache workspace with specified options.

        Args:
            workspace_path: Path to the workspace to cache
            repository: Git repository name
            branch: Git branch name (can be None)
            cache_level: Cache level enum value
            include_git: Whether to include .git folders

        Returns:
            WorkspaceCacheResult with operation results
        """
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

            # Set workspace injection task as active if coordinator available
            if progress_coordinator and hasattr(progress_coordinator, "set_enhanced_task_status"):
                progress_coordinator.set_enhanced_task_status("workspace_injection", "active", "Copying workspace components")

            # Copy workspace components with progress tracking
            total_components = len(detected_components)
            total_files_copied = 0
            total_bytes_copied = 0

            # Calculate total files and bytes for accurate progress
            component_stats = {}
            for component in detected_components:
                src_component = workspace_path / component
                try:
                    files_count = sum(1 for _ in src_component.rglob("*") if _.is_file())
                    bytes_count = sum(f.stat().st_size for f in src_component.rglob("*") if f.is_file())
                    component_stats[component] = {"files": files_count, "bytes": bytes_count}
                except (PermissionError, OSError):
                    component_stats[component] = {"files": 100, "bytes": 10 * 1024 * 1024}  # 10MB estimate

            total_estimated_files = sum(stats["files"] for stats in component_stats.values())
            total_estimated_bytes = sum(stats["bytes"] for stats in component_stats.values())

            for component_idx, component in enumerate(detected_components):
                src_component = workspace_path / component
                dest_component = cached_workspace_dir / component

                # Remove existing if it exists
                if dest_component.exists():
                    shutil.rmtree(dest_component)

                # Create enhanced progress callback that updates both old and new progress systems
                component_progress_callback = None
                if progress_callback or progress_coordinator:

                    def make_enhanced_callback(
                        comp_name: str, comp_idx: int, files_offset: int, bytes_offset: int
                    ) -> CopyProgressCallback:
                        def enhanced_callback(progress: CopyProgress) -> None:
                            # Update running totals
                            current_files = progress.files_processed or 0
                            current_bytes = progress.bytes_copied or 0

                            # Calculate overall progress across all components
                            overall_files = files_offset + current_files
                            overall_bytes = bytes_offset + current_bytes

                            # Update progress coordinator if available
                            if progress_coordinator and hasattr(progress_coordinator, "update_workspace_progress"):
                                progress_coordinator.update_workspace_progress(
                                    files_copied=overall_files,
                                    total_files=total_estimated_files,
                                    bytes_copied=overall_bytes,
                                    total_bytes=total_estimated_bytes,
                                    current_file=progress.current_file or "",
                                    component=f"{comp_name} ({comp_idx + 1}/{total_components})",
                                    transfer_speed_mb_s=0.0,  # Will be calculated by progress coordinator
                                    eta_seconds=0.0,
                                )

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
            )

            # Mark workspace injection as completed
            if progress_coordinator and hasattr(progress_coordinator, "set_enhanced_task_status"):
                progress_coordinator.set_enhanced_task_status("workspace_injection", "completed")

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

            return WorkspaceCacheResult(
                success=True,
                workspace_path=cached_workspace_dir,
                metadata=metadata,
                created_new=True,
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Failed to cache workspace: %s", e, exc_info=exc_info)
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


__all__ = ["ZmkWorkspaceCacheService", "WorkspaceCacheMetadata", "WorkspaceCacheResult", "WorkspaceExportResult"]
