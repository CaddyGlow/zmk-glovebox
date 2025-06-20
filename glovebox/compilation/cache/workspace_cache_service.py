"""ZMK Workspace Cache Service with comprehensive cache management and auto-detection."""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from glovebox.config.models.cache import CacheLevel
from glovebox.config.user_config import UserConfig
from glovebox.core.cache_v2.cache_manager import CacheManager
from glovebox.core.workspace_cache_utils import (
    detect_git_info,
    generate_workspace_cache_key,
)
from glovebox.models.base import GloveboxBaseModel

from .models import WorkspaceCacheMetadata


class WorkspaceCacheResult(GloveboxBaseModel):
    """Result of workspace cache operations."""

    success: bool
    workspace_path: Path | None = None
    metadata: WorkspaceCacheMetadata | None = None
    error_message: str | None = None
    created_new: bool = False


class WorkspaceAutoDetectionResult(GloveboxBaseModel):
    """Result of workspace auto-detection operations."""

    success: bool
    repository: str | None = None
    branch: str | None = None
    commit_hash: str | None = None
    detected_components: list[str] = []
    workspace_path: Path | None = None
    error_message: str | None = None


class ZmkWorkspaceCacheService:
    """Centralized service for ZMK workspace cache operations with auto-detection.

    Provides comprehensive workspace cache management including:
    - Rich metadata storage with git information
    - Auto-detection of repository and branch information
    - Tiered cache level support (base, branch, full, build)
    - Integration with UserConfig for TTL management
    - Cache cleanup and maintenance operations
    """

    def __init__(self, user_config: UserConfig, cache_manager: CacheManager):
        """Initialize the workspace cache service.

        Args:
            user_config: User configuration containing cache settings
            cache_manager: Cache manager instance for data operations
        """
        self.user_config = user_config
        self.cache_manager = cache_manager
        self.logger = logging.getLogger(__name__)

    def get_cache_directory(self) -> Path:
        """Get the workspace cache directory from user config.

        Returns:
            Path to the workspace cache directory
        """
        return self.user_config._config.cache_path / "workspace"

    def get_ttls_for_cache_levels(self) -> dict[str, int]:
        """Get TTL values for all workspace cache levels.

        Returns:
            Dictionary mapping cache levels to TTL values in seconds
        """
        cache_ttls = self.user_config._config.cache_ttls
        return cache_ttls.get_workspace_ttls()

    def auto_detect_workspace_info(
        self, workspace_path: Path
    ) -> WorkspaceAutoDetectionResult:
        """Auto-detect git repository and branch information from workspace.

        Args:
            workspace_path: Path to the workspace directory to analyze

        Returns:
            WorkspaceAutoDetectionResult with detected information
        """
        try:
            workspace_path = workspace_path.resolve()

            if not workspace_path.exists() or not workspace_path.is_dir():
                return WorkspaceAutoDetectionResult(
                    success=False,
                    error_message=f"Workspace path does not exist or is not a directory: {workspace_path}",
                )

            # Use existing git detection logic
            git_info = detect_git_info(workspace_path)

            # Detect ZMK workspace components
            required_components = ["zmk", "zephyr", "modules"]
            detected_components = []

            for component in required_components:
                component_path = workspace_path / component
                if component_path.exists() and component_path.is_dir():
                    detected_components.append(component)

            if not detected_components:
                return WorkspaceAutoDetectionResult(
                    success=False,
                    error_message=f"No ZMK workspace components found in {workspace_path}. Expected: {required_components}",
                )

            return WorkspaceAutoDetectionResult(
                success=True,
                repository=git_info.get("repository"),
                branch=git_info.get("branch"),
                commit_hash=git_info.get("commit_hash"),
                detected_components=detected_components,
                workspace_path=workspace_path,
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to auto-detect workspace info: %s", e, exc_info=exc_info
            )
            return WorkspaceAutoDetectionResult(
                success=False, error_message=f"Auto-detection failed: {e}"
            )

    def get_cached_workspace(
        self, repository: str, branch: str, cache_level: str
    ) -> WorkspaceCacheResult:
        """Retrieve cached workspace metadata and path.

        Args:
            repository: Git repository name (e.g., 'zmkfirmware/zmk')
            branch: Git branch name
            cache_level: Cache level to retrieve ('base', 'branch', 'full', 'build')

        Returns:
            WorkspaceCacheResult with cached workspace information
        """
        try:
            cache_key = generate_workspace_cache_key(repository, branch, cache_level)
            cached_data = self.cache_manager.get(cache_key)

            if cached_data is None:
                return WorkspaceCacheResult(
                    success=False,
                    error_message=f"No cached workspace found for {repository}@{branch} (level: {cache_level})",
                )

            # Handle legacy cache entries (simple path strings)
            if isinstance(cached_data, str):
                workspace_path = Path(cached_data)
                if not workspace_path.exists():
                    # Remove stale cache entry
                    self.cache_manager.delete(cache_key)
                    return WorkspaceCacheResult(
                        success=False,
                        error_message=f"Cached workspace path no longer exists: {workspace_path}",
                    )

                # Create metadata for legacy entry
                metadata = WorkspaceCacheMetadata(  # type: ignore[call-arg]
                    workspace_path=workspace_path,
                    repository=repository,
                    branch=branch,
                    cache_level=CacheLevel(cache_level),
                    notes="Migrated from legacy cache entry",
                )

                return WorkspaceCacheResult(
                    success=True, workspace_path=workspace_path, metadata=metadata
                )

            # Handle rich metadata entries
            elif isinstance(cached_data, dict):
                metadata = WorkspaceCacheMetadata.from_cache_value(cached_data)

                # Verify workspace still exists
                if not metadata.workspace_path.exists():
                    # Remove stale cache entry
                    self.cache_manager.delete(cache_key)
                    return WorkspaceCacheResult(
                        success=False,
                        error_message=f"Cached workspace path no longer exists: {metadata.workspace_path}",
                    )

                # Update access time
                metadata.update_access_time()

                # Update cache with new access time
                ttls = self.get_ttls_for_cache_levels()
                ttl = ttls.get(cache_level, 3600)  # Default 1 hour
                self.cache_manager.set(cache_key, metadata.to_cache_value(), ttl=ttl)

                return WorkspaceCacheResult(
                    success=True,
                    workspace_path=metadata.workspace_path,
                    metadata=metadata,
                )

            else:
                self.logger.warning(
                    "Unknown cache data format for key %s: %s",
                    cache_key,
                    type(cached_data),
                )
                return WorkspaceCacheResult(
                    success=False,
                    error_message=f"Unknown cache data format for {repository}@{branch}",
                )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to get cached workspace: %s", e, exc_info=exc_info
            )
            return WorkspaceCacheResult(
                success=False, error_message=f"Failed to retrieve cached workspace: {e}"
            )

    def cache_workspace(
        self,
        workspace_path: Path,
        repository: str,
        branch: str,
        cache_levels: list[str],
        auto_detected: bool = False,
        auto_detected_source: str | None = None,
        build_profile: str | None = None,
        keymap_path: Path | None = None,
        config_path: Path | None = None,
    ) -> WorkspaceCacheResult:
        """Cache workspace with rich metadata across multiple cache levels.

        Copies workspace data to {cache_path}/workspace/{key} directories and stores metadata.

        Args:
            workspace_path: Path to the workspace to cache
            repository: Git repository name
            branch: Git branch name
            cache_levels: List of cache levels to store ('base', 'branch', 'full', 'build')
            auto_detected: Whether workspace was auto-detected
            auto_detected_source: Source path if auto-detected
            build_profile: Optional build profile used
            keymap_path: Optional keymap file for hash calculation
            config_path: Optional config file for hash calculation

        Returns:
            WorkspaceCacheResult with operation results
        """
        try:
            workspace_path = workspace_path.resolve()

            if not workspace_path.exists():
                return WorkspaceCacheResult(
                    success=False,
                    error_message=f"Workspace path does not exist: {workspace_path}",
                )

            # Detect workspace components
            detected_components = []
            for component in ["zmk", "zephyr", "modules"]:
                component_path = workspace_path / component
                if component_path.exists() and component_path.is_dir():
                    detected_components.append(component)

            # Calculate workspace size
            workspace_size = self._calculate_directory_size(workspace_path)

            # Get TTL values
            ttls = self.get_ttls_for_cache_levels()

            # Store cache entries for each requested level
            stored_levels = []
            cached_workspace_path = None

            for cache_level in cache_levels:
                try:
                    # Generate cache key for this level
                    cache_key = generate_workspace_cache_key(
                        repository, branch, cache_level
                    )

                    # Create cache directory path: {cache_path}/workspace/{cache_key}
                    cache_base_dir = self.get_cache_directory()
                    level_cache_dir = cache_base_dir / cache_key

                    # Only copy data for the first level to avoid duplication
                    if cached_workspace_path is None:
                        # Copy workspace data to cache directory
                        level_cache_dir.mkdir(parents=True, exist_ok=True)

                        # Copy each component directory
                        for component in detected_components:
                            src_component = workspace_path / component
                            dest_component = level_cache_dir / component

                            # Remove existing if it exists
                            if dest_component.exists():
                                shutil.rmtree(dest_component)

                            # Copy component directory
                            shutil.copytree(src_component, dest_component)
                            self.logger.debug(
                                "Copied component %s to %s", component, dest_component
                            )

                        cached_workspace_path = level_cache_dir
                        self.logger.info(
                            "Copied workspace data to cache directory: %s",
                            cached_workspace_path,
                        )
                    else:
                        # For subsequent levels, create symlink to avoid duplication
                        if level_cache_dir.exists():
                            shutil.rmtree(level_cache_dir)
                        level_cache_dir.symlink_to(
                            cached_workspace_path, target_is_directory=True
                        )
                        self.logger.debug(
                            "Created symlink from %s to %s",
                            level_cache_dir,
                            cached_workspace_path,
                        )

                    # Create metadata for this cache level pointing to the cached data
                    metadata = WorkspaceCacheMetadata(  # type: ignore[call-arg]
                        workspace_path=cached_workspace_path,
                        repository=repository,
                        branch=branch,
                        cache_level=CacheLevel(cache_level),
                        auto_detected=auto_detected,
                        auto_detected_source=auto_detected_source,
                        build_profile=build_profile,
                        cached_components=detected_components.copy(),
                        size_bytes=workspace_size,
                    )

                    # Update file hashes if provided
                    if keymap_path or config_path:
                        metadata.update_file_hashes(keymap_path, config_path)

                    # Store metadata in cache manager
                    ttl = ttls.get(cache_level, 3600)  # Default 1 hour
                    self.cache_manager.set(
                        cache_key, metadata.to_cache_value(), ttl=ttl
                    )
                    stored_levels.append(cache_level)

                    self.logger.debug(
                        "Cached workspace %s@%s (level: %s) with TTL %d seconds, data at %s",
                        repository,
                        branch,
                        cache_level,
                        ttl,
                        cached_workspace_path,
                    )

                except Exception as e:
                    self.logger.warning(
                        "Failed to cache workspace at level %s: %s", cache_level, e
                    )

            if not stored_levels:
                return WorkspaceCacheResult(
                    success=False,
                    error_message="Failed to cache workspace at any requested level",
                )

            # Return metadata for the first successfully stored level
            cache_key = generate_workspace_cache_key(
                repository, branch, stored_levels[0]
            )
            cached_data = self.cache_manager.get(cache_key)
            metadata = WorkspaceCacheMetadata.from_cache_value(cached_data)

            return WorkspaceCacheResult(
                success=True,
                workspace_path=cached_workspace_path,
                metadata=metadata,
                created_new=True,
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Failed to cache workspace: %s", e, exc_info=exc_info)
            return WorkspaceCacheResult(
                success=False, error_message=f"Failed to cache workspace: {e}"
            )

    def add_external_workspace(
        self, source_path: Path, repository: str | None = None, force: bool = False
    ) -> WorkspaceCacheResult:
        """Add an external workspace to cache with auto-detection support.

        Args:
            source_path: Path to existing workspace directory
            repository: Optional repository name (auto-detected if not provided)
            force: Whether to overwrite existing cache entries

        Returns:
            WorkspaceCacheResult with operation results
        """
        try:
            # Auto-detect workspace information
            detection_result = self.auto_detect_workspace_info(source_path)

            if not detection_result.success:
                return WorkspaceCacheResult(
                    success=False, error_message=detection_result.error_message
                )

            # Use provided repository or auto-detected
            final_repository = repository or detection_result.repository
            final_branch = detection_result.branch or "main"

            if not final_repository:
                return WorkspaceCacheResult(
                    success=False,
                    error_message="Could not determine repository name (provide manually or ensure git remote is configured)",
                )

            # Check if already cached
            if not force:
                base_cache = self.get_cached_workspace(
                    final_repository, final_branch, "base"
                )
                if base_cache.success:
                    return WorkspaceCacheResult(
                        success=False,
                        error_message=f"Workspace already cached for {final_repository}@{final_branch} (use --force to overwrite)",
                    )

            # Cache the workspace directly from source - cache_workspace will handle copying
            cache_result = self.cache_workspace(
                workspace_path=source_path,
                repository=final_repository,
                branch=final_branch,
                cache_levels=["base", "branch", "full"],
                auto_detected=True,
                auto_detected_source=str(source_path),
            )

            if cache_result.success:
                self.logger.info(
                    "Successfully added external workspace %s@%s from %s",
                    final_repository,
                    final_branch,
                    source_path,
                )

            return cache_result

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to add external workspace: %s", e, exc_info=exc_info
            )
            return WorkspaceCacheResult(
                success=False, error_message=f"Failed to add external workspace: {e}"
            )

    def list_cached_workspaces(self) -> list[WorkspaceCacheMetadata]:
        """List all cached workspaces with their metadata.

        Scans both cache metadata and filesystem to discover all cached workspaces.

        Returns:
            List of WorkspaceCacheMetadata for all cached workspaces
        """
        workspaces: list[WorkspaceCacheMetadata] = []
        seen_workspaces = set()  # Track (repository, branch) to avoid duplicates
        seen_cache_keys = set()  # Track cache keys to avoid duplicates

        try:
            # Method 1: Get workspaces from cache metadata
            cache_dir = self.get_cache_directory()
            if cache_dir.exists():
                # Scan cache directory for both workspace subdirectories and symlinks
                for cache_item in cache_dir.iterdir():
                    # Skip files (like cache.db)
                    if cache_item.is_file():
                        continue

                    # Handle both directories and symlinks
                    cache_key = cache_item.name

                    # Skip if we've already processed this cache key
                    if cache_key in seen_cache_keys:
                        continue

                    # Try to get metadata from cache manager
                    cached_data = self.cache_manager.get(cache_key)
                    if cached_data:
                        try:
                            if isinstance(cached_data, dict):
                                metadata = WorkspaceCacheMetadata.from_cache_value(
                                    cached_data
                                )
                                workspace_key = (metadata.repository, metadata.branch)

                                # For symlinks, resolve to actual workspace path
                                actual_workspace_path = metadata.workspace_path
                                if cache_item.is_symlink():
                                    try:
                                        actual_workspace_path = cache_item.resolve()
                                    except (OSError, RuntimeError):
                                        # Broken symlink, skip this entry
                                        self.logger.debug(
                                            "Skipping broken symlink: %s", cache_item
                                        )
                                        continue

                                # Verify workspace directory still exists
                                if actual_workspace_path.exists():
                                    # Update metadata to point to actual path if needed
                                    if actual_workspace_path != metadata.workspace_path:
                                        metadata.workspace_path = actual_workspace_path

                                    # Only add if we haven't seen this workspace yet
                                    if workspace_key not in seen_workspaces:
                                        workspaces.append(metadata)
                                        seen_workspaces.add(workspace_key)

                                    seen_cache_keys.add(cache_key)
                                else:
                                    # Clean up stale cache entry
                                    self.cache_manager.delete(cache_key)
                                    self.logger.debug(
                                        "Cleaned up stale cache entry: %s",
                                        cache_key,
                                    )
                        except Exception as e:
                            self.logger.warning(
                                "Failed to parse cached metadata for %s: %s",
                                cache_key,
                                e,
                            )

            # Method 2: Scan filesystem for orphaned workspace directories
            # This catches workspaces that exist on disk but have no cache metadata
            if cache_dir.exists():
                for workspace_item in cache_dir.iterdir():
                    # Skip files and items we've already processed
                    if (
                        workspace_item.is_file()
                        or workspace_item.name in seen_cache_keys
                    ):
                        continue

                    # Resolve actual workspace directory (handle symlinks)
                    actual_workspace_dir = workspace_item
                    if workspace_item.is_symlink():
                        try:
                            actual_workspace_dir = workspace_item.resolve()
                        except (OSError, RuntimeError):
                            # Broken symlink, skip
                            continue

                    # Must be a directory to be a valid workspace
                    if not actual_workspace_dir.is_dir():
                        continue

                    # Try to detect git info for directories not found in cache metadata
                    git_info = detect_git_info(actual_workspace_dir)
                    repository = git_info.get("repository")
                    branch = git_info.get("branch", "main")

                    if repository:
                        workspace_key = (repository, branch)
                        if workspace_key not in seen_workspaces:
                            # Create metadata for orphaned workspace
                            metadata = WorkspaceCacheMetadata(  # type: ignore[call-arg]
                                workspace_path=actual_workspace_dir,
                                repository=repository,
                                branch=branch,
                                cache_level=CacheLevel.BASE,
                                notes="Orphaned workspace directory (metadata missing)",
                            )
                            workspaces.append(metadata)
                            seen_workspaces.add(workspace_key)
                            self.logger.debug(
                                "Found orphaned workspace: %s@%s at %s",
                                repository,
                                branch,
                                actual_workspace_dir,
                            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to list cached workspaces: %s", e, exc_info=exc_info
            )

        return workspaces

    def delete_cached_workspace(
        self, repository: str, branch: str | None = None
    ) -> bool:
        """Delete cached workspace for a repository and optional branch.

        Deletes both cache metadata and workspace data directories.

        Args:
            repository: Repository name to delete
            branch: Optional specific branch (deletes all branches if None)

        Returns:
            True if workspace was deleted successfully
        """
        try:
            deleted_any = False
            cache_dir = self.get_cache_directory()

            # Special handling for orphaned workspaces (unknown repositories)
            if repository == "unknown":
                # For orphaned workspaces, scan cache directory and delete directories
                # that don't have corresponding cache metadata
                for cache_subdir in cache_dir.iterdir():
                    if not cache_subdir.is_dir() or cache_subdir.is_symlink():
                        continue

                    cache_key = cache_subdir.name

                    # Check if this directory has corresponding metadata
                    cached_data = self.cache_manager.get(cache_key)
                    if not cached_data:
                        # This is an orphaned directory - delete it
                        try:
                            shutil.rmtree(cache_subdir)
                            deleted_any = True
                            self.logger.debug(
                                "Deleted orphaned workspace directory: %s", cache_subdir
                            )
                        except Exception as e:
                            self.logger.warning(
                                "Failed to delete orphaned directory %s: %s",
                                cache_subdir,
                                e,
                            )

                return deleted_any

            # Normal deletion for known repositories
            levels = ["base", "branch", "full", "build"]
            branches_to_delete = (
                [branch] if branch else ["main", "master", "develop", "dev"]
            )
            workspace_dirs_to_remove = set()

            # Delete cache entries and collect workspace paths
            for branch_name in branches_to_delete:
                for level in levels:
                    cache_key = generate_workspace_cache_key(
                        repository, branch_name, level
                    )

                    # Get workspace path before deleting metadata
                    cached_data = self.cache_manager.get(cache_key)
                    if cached_data:
                        try:
                            if isinstance(cached_data, dict):
                                metadata = WorkspaceCacheMetadata.from_cache_value(
                                    cached_data
                                )
                                workspace_dirs_to_remove.add(metadata.workspace_path)
                            elif isinstance(cached_data, str):
                                # Legacy cache entry
                                workspace_dirs_to_remove.add(Path(cached_data))
                        except Exception as e:
                            self.logger.warning(
                                "Failed to parse cached metadata: %s", e
                            )

                    # Delete cache entry
                    if self.cache_manager.exists(cache_key):
                        self.cache_manager.delete(cache_key)
                        deleted_any = True
                        self.logger.debug("Deleted cache entry: %s", cache_key)

                        # Also add the expected cache directory path
                        expected_cache_dir = cache_dir / cache_key
                        workspace_dirs_to_remove.add(expected_cache_dir)

            # Delete workspace directories
            for workspace_dir in workspace_dirs_to_remove:
                if workspace_dir.exists():
                    try:
                        # Handle symlinks and regular directories
                        if workspace_dir.is_symlink():
                            workspace_dir.unlink()
                            self.logger.debug("Removed symlink: %s", workspace_dir)
                        else:
                            shutil.rmtree(workspace_dir)
                            self.logger.debug(
                                "Deleted workspace directory: %s", workspace_dir
                            )
                        deleted_any = True
                    except Exception as e:
                        self.logger.warning(
                            "Failed to delete directory %s: %s", workspace_dir, e
                        )

            return deleted_any

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to delete cached workspace: %s", e, exc_info=exc_info
            )
            return False

    def cleanup_stale_entries(self, max_age_hours: float = 24 * 7) -> int:
        """Clean up stale cache entries older than specified age.

        Args:
            max_age_hours: Maximum age in hours before entry is considered stale

        Returns:
            Number of entries cleaned up
        """
        try:
            cleaned_count = 0
            current_time = datetime.now()

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

            return cleaned_count

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to cleanup stale entries: %s", e, exc_info=exc_info
            )
            return 0

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


def create_zmk_workspace_cache_service(
    user_config: UserConfig, cache_manager: CacheManager
) -> ZmkWorkspaceCacheService:
    """Factory function to create ZmkWorkspaceCacheService instance.

    Args:
        user_config: User configuration instance
        cache_manager: Cache manager instance

    Returns:
        Configured ZmkWorkspaceCacheService
    """
    return ZmkWorkspaceCacheService(user_config, cache_manager)
