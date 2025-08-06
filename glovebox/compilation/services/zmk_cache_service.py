"""ZMK cache service for workspace and build result caching."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.core.structlog_logger import get_struct_logger

from glovebox.compilation.cache.compilation_build_cache_service import (
    CompilationBuildCacheService,
)
from glovebox.compilation.cache.workspace_cache_service import (
    ZmkWorkspaceCacheService,
)
from glovebox.compilation.models import ZmkCompilationConfig
from glovebox.config.user_config import UserConfig
from glovebox.core.cache.cache_manager import CacheManager
from glovebox.protocols import MetricsProtocol


if TYPE_CHECKING:
    from glovebox.protocols.progress_coordinator_protocol import (
        ProgressCoordinatorProtocol,
    )


class ZmkCacheService:
    """Service for ZMK workspace and build caching operations."""

    def __init__(
        self,
        user_config: UserConfig,
        cache_manager: CacheManager,
        session_metrics: MetricsProtocol,
        workspace_cache_service: ZmkWorkspaceCacheService | None = None,
        build_cache_service: CompilationBuildCacheService | None = None,
    ) -> None:
        """Initialize ZMK cache service."""
        self.user_config = user_config
        self.cache_manager = cache_manager
        self.session_metrics = session_metrics
        self.logger = get_struct_logger(__name__)

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

    def get_cached_workspace(
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

    def cache_workspace(
        self,
        workspace_path: Path,
        config: ZmkCompilationConfig,
        progress_coordinator: "ProgressCoordinatorProtocol | None" = None,
    ) -> None:
        """Cache workspace for future use with new dual-level strategy."""
        if not config.use_cache or not self.workspace_cache_service:
            return

        # TODO: Enable after refactoring
        # if progress_coordinator:
        #     progress_coordinator.update_cache_saving(
        #         "workspace", "Starting workspace cache"
        #     )

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

            # TODO: Enable after refactoring
            # if progress_coordinator:
            #     progress_coordinator.update_cache_saving(
            #         "workspace", "Caching repo+branch workspace"
            #     )

            # Cache repo+branch level first (most commonly used)
            cache_result = self.workspace_cache_service.cache_workspace_repo_branch(
                workspace_path,
                config.repository,
                config.branch,
                progress_coordinator=progress_coordinator,
            )

            if cache_result.success:
                self.logger.info(
                    "Cached workspace (repo+branch) for %s@%s: %s",
                    config.repository,
                    config.branch,
                    cache_result.workspace_path,
                )
                # TODO: Enable after refactoring
                # if progress_coordinator:
                #     progress_coordinator.update_cache_saving(
                #         "workspace",
                #         f"Repo+branch cache saved for {config.repository}@{config.branch}",
                #     )
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
                # TODO: Enable after refactoring
                # if progress_coordinator:
                #     progress_coordinator.update_cache_saving(
                #         "workspace",
                #         f"Repo+branch cache failed: {cache_result.error_message}",
                #     )

            # TODO: Enable after refactoring
            # if progress_coordinator:
            #     progress_coordinator.update_cache_saving(
            #         "workspace", "Caching repo-only workspace"
            #     )

            # Cache repo-only level (for branch fetching scenarios)
            cache_result = self.workspace_cache_service.cache_workspace_repo_only(
                workspace_path,
                config.repository,
                progress_coordinator=progress_coordinator,
            )

            if cache_result.success:
                self.logger.info(
                    "Cached workspace (repo-only) for %s: %s",
                    config.repository,
                    cache_result.workspace_path,
                )
                # TODO: Enable after refactoring
                # if progress_coordinator:
                #     progress_coordinator.update_cache_saving(
                #         "workspace", f"Repo-only cache saved for {config.repository}"
                #     )
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
                # TODO: Enable after refactoring
                # if progress_coordinator:
                #     progress_coordinator.update_cache_saving(
                #         "workspace",
                #         f"Repo-only cache failed: {cache_result.error_message}",
                #     )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.warning("failed_to_cache_workspace", error=str(e), exc_info=exc_info)
            # TODO: Enable after refactoring
            # if progress_coordinator:
            #     progress_coordinator.update_cache_saving(
            #         "workspace", f"Workspace cache error: {e}"
            #     )

    def cache_workspace_repo_branch_only(
        self,
        workspace_path: Path,
        config: ZmkCompilationConfig,
        progress_coordinator: "ProgressCoordinatorProtocol | None" = None,
    ) -> None:
        """Cache workspace for repo+branch only (used when upgrading from repo-only cache)."""
        if not config.use_cache or not self.workspace_cache_service:
            return

        # Update progress coordinator for workspace cache saving
        # TODO: Enable after refactoring
        # if progress_coordinator:
        #     progress_coordinator.update_cache_saving(
        #         "workspace", "Starting workspace cache save"
        #     )

        cache_result = self.workspace_cache_service.cache_workspace_repo_branch(
            workspace_path,
            config.repository,
            config.branch,
            progress_coordinator=progress_coordinator,
        )
        if cache_result.success:
            self.logger.info(
                "Cached workspace (repo+branch) for %s@%s: %s",
                config.repository,
                config.branch,
                cache_result.workspace_path,
            )
            # TODO: Enable after refactoring
            # if progress_coordinator:
            #     progress_coordinator.update_cache_saving(
            #         "workspace", "Workspace cache saved successfully"
            #     )
        else:
            self.logger.warning(
                "Failed to cache workspace (repo+branch): %s",
                cache_result.error_message,
            )
            # TODO: Enable after refactoring
            # if progress_coordinator:
            #     progress_coordinator.update_cache_saving(
            #         "workspace",
            #         f"Workspace cache failed: {cache_result.error_message}",
            #     )

    def get_cached_build_result(
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

    def cache_build_result(
        self,
        keymap_file: Path,
        config_file: Path,
        config: ZmkCompilationConfig,
        workspace_path: Path,
        progress_coordinator: "ProgressCoordinatorProtocol | None" = None,
    ) -> None:
        """Cache successful build directory for future use."""
        if not config.use_cache or not self.build_cache_service:
            return

        # TODO: Enable after refactoring
        # if progress_coordinator:
        #     progress_coordinator.update_cache_saving(
        #         "build", "Starting build result cache"
        #     )

        try:
            # Generate cache key using the build cache service
            cache_key = self.build_cache_service.generate_cache_key_from_files(
                repository=config.repository,
                branch=config.branch,
                config_file=config_file,
                keymap_file=keymap_file,
            )

            # TODO: Enable after refactoring
            # if progress_coordinator:
            #     progress_coordinator.update_cache_saving(
            #         "build", "Caching build artifacts"
            #     )

            # Cache the workspace build directory (contains all build artifacts)
            success = self.build_cache_service.cache_build_result(
                workspace_path, cache_key
            )

            if success:
                self.logger.info("cached_build_result", keymap_file=keymap_file.name)
                # TODO: Enable after refactoring
                # if progress_coordinator:
                #     progress_coordinator.update_cache_saving(
                #         "build", f"Build cache saved for {keymap_file.name}"
                #     )
            else:
                self.logger.warning(
                    "Failed to cache build result for %s", keymap_file.name
                )
                # TODO: Enable after refactoring
                # if progress_coordinator:
                #     progress_coordinator.update_cache_saving(
                #         "build", f"Build cache failed for {keymap_file.name}"
                #     )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.warning(
                "Failed to cache build result: %s", e, exc_info=exc_info
            )
            # TODO: Enable after refactoring
            # if progress_coordinator:
            #     progress_coordinator.update_cache_saving(
            #         "build", f"Build cache error: {e}"
            #     )


def create_zmk_cache_service(
    user_config: UserConfig,
    cache_manager: CacheManager,
    session_metrics: MetricsProtocol,
    workspace_cache_service: ZmkWorkspaceCacheService | None = None,
    build_cache_service: CompilationBuildCacheService | None = None,
) -> ZmkCacheService:
    """Create ZMK cache service with dependencies.

    Args:
        user_config: User configuration with cache settings
        cache_manager: Cache manager instance for both cache services
        session_metrics: Session metrics for tracking operations
        workspace_cache_service: Optional workspace cache service
        build_cache_service: Optional build cache service

    Returns:
        Configured ZmkCacheService instance
    """
    return ZmkCacheService(
        user_config=user_config,
        cache_manager=cache_manager,
        session_metrics=session_metrics,
        workspace_cache_service=workspace_cache_service,
        build_cache_service=build_cache_service,
    )
