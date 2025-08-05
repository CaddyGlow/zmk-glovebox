"""CLI workspace display utilities for consistent formatting and filtering."""

import logging
from pathlib import Path
from typing import Any

from glovebox.compilation.cache.workspace_cache_service import (
    WorkspaceCacheMetadata,
    ZmkWorkspaceCacheService,
)
from glovebox.core.cache.models import CacheKey
from glovebox.core.structlog_logger import get_struct_logger


logger = get_struct_logger(__name__)


def format_size(size_bytes: float) -> str:
    """Format size in human readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def get_directory_size(path: Path) -> int:
    """Get total size of directory in bytes."""
    total = 0
    try:
        for file_path in path.rglob("*"):
            if file_path.is_file():
                total += file_path.stat().st_size
    except (OSError, PermissionError):
        pass
    return total


def format_workspace_entry(
    workspace_metadata: WorkspaceCacheMetadata,
    ttl_config: dict[str, int],
) -> dict[str, Any]:
    """Format workspace metadata into a standardized display entry.

    Args:
        workspace_metadata: Workspace metadata from cache service
        ttl_config: TTL configuration mapping cache levels to seconds

    Returns:
        Dictionary with formatted display fields
    """
    # Extract cache level
    cache_level_value = (
        workspace_metadata.cache_level.value
        if hasattr(workspace_metadata.cache_level, "value")
        else str(workspace_metadata.cache_level)
    )

    # Format age and TTL
    age_hours = workspace_metadata.age_hours
    if age_hours >= 24:  # >= 1 day
        age_str = f"{age_hours / 24:.1f}d"
    elif age_hours >= 1:  # >= 1 hour
        age_str = f"{age_hours:.1f}h"
    else:  # < 1 hour
        age_str = f"{age_hours * 60:.1f}m"

    # Calculate TTL remaining
    ttl_seconds = ttl_config.get(cache_level_value, 3600)
    age_seconds = age_hours * 3600
    ttl_remaining_seconds = max(0, ttl_seconds - age_seconds)

    # Format remaining TTL
    if ttl_remaining_seconds > 0:
        if ttl_remaining_seconds >= 86400:  # >= 1 day
            ttl_str = f"{ttl_remaining_seconds / 86400:.1f}d"
        elif ttl_remaining_seconds >= 3600:  # >= 1 hour
            ttl_str = f"{ttl_remaining_seconds / 3600:.1f}h"
        elif ttl_remaining_seconds >= 60:  # >= 1 minute
            ttl_str = f"{ttl_remaining_seconds / 60:.1f}m"
        else:
            ttl_str = f"{ttl_remaining_seconds:.0f}s"
    else:
        ttl_str = "EXPIRED"

    # Generate cache key for display (matches the directory name)
    cache_key = generate_workspace_cache_key(
        workspace_metadata.repository,
        workspace_metadata.branch or "main",
        cache_level_value,
    )

    # Calculate size
    try:
        if workspace_metadata.workspace_path.exists():
            size_bytes = get_directory_size(workspace_metadata.workspace_path)
            size_display = format_size(size_bytes)
        else:
            size_display = "N/A"
    except Exception:
        size_display = "N/A"

    # Check for symlinks
    path_display = str(workspace_metadata.workspace_path)
    if workspace_metadata.workspace_path.is_symlink():
        try:
            actual_path = workspace_metadata.workspace_path.resolve()
            path_display = f"{workspace_metadata.workspace_path} → {actual_path}"
        except (OSError, RuntimeError):
            path_display = f"{workspace_metadata.workspace_path} → [BROKEN]"

    return {
        "cache_key": cache_key,
        "repository": workspace_metadata.repository,
        "branch": workspace_metadata.branch,
        "cache_level": cache_level_value,
        "age": age_str,
        "ttl_remaining": ttl_str,
        "size": size_display,
        "workspace_path": path_display,
        "notes": workspace_metadata.notes or "",
    }


def filter_workspaces(
    entries: list[dict[str, Any]],
    filter_repository: str | None = None,
    filter_branch: str | None = None,
    filter_level: str | None = None,
) -> list[dict[str, Any]]:
    """Apply filters to workspace entries.

    Args:
        entries: List of workspace entries to filter
        filter_repository: Filter by repository name (partial match)
        filter_branch: Filter by branch name (partial match)
        filter_level: Filter by cache level (exact match)

    Returns:
        Filtered list of workspace entries
    """
    filtered_entries = entries

    if filter_repository:
        filtered_entries = [
            entry
            for entry in filtered_entries
            if filter_repository.lower() in entry["repository"].lower()
        ]

    if filter_branch:
        filtered_entries = [
            entry
            for entry in filtered_entries
            if filter_branch.lower() in entry["branch"].lower()
        ]

    if filter_level:
        filtered_entries = [
            entry
            for entry in filtered_entries
            if entry["cache_level"].lower() == filter_level.lower()
        ]

    return filtered_entries


def generate_workspace_cache_key(
    repository: str,
    branch: str = "main",
    level: str = "repo_branch",
) -> str:
    """Generate cache key for workspace following ZmkWorkspaceCacheService pattern.

    Args:
        repository: Repository name (e.g., 'zmkfirmware/zmk')
        branch: Git branch name
        level: Cache level - 'repo' or 'repo_branch'

    Returns:
        Generated cache key string
    """
    repo_part = repository.replace("/", "_")

    if level == "repo":
        # Repo-only cache key
        parts_hash = CacheKey.from_parts(repo_part)
        return f"workspace_repo_{parts_hash}"
    else:
        # Repo+branch cache key
        parts_hash = CacheKey.from_parts(repo_part, branch)
        return f"workspace_repo_branch_{parts_hash}"


def get_workspace_summary(
    workspace_cache_service: ZmkWorkspaceCacheService,
) -> dict[str, Any]:
    """Get summary information about cached workspaces.

    Args:
        workspace_cache_service: Service to query workspace cache

    Returns:
        Dictionary with summary information
    """
    try:
        cached_workspaces = workspace_cache_service.list_cached_workspaces()

        # Filter out build-level caches as they represent compiled artifacts, not workspaces
        workspace_entries = []
        for workspace_metadata in cached_workspaces:
            cache_level_value = (
                workspace_metadata.cache_level.value
                if hasattr(workspace_metadata.cache_level, "value")
                else str(workspace_metadata.cache_level)
            )
            if cache_level_value != "build":
                workspace_entries.append(workspace_metadata)

        total_size = sum(
            workspace.size_bytes or get_directory_size(workspace.workspace_path)
            for workspace in workspace_entries
        )

        return {
            "total_entries": len(workspace_entries),
            "total_size_bytes": total_size,
            "total_size_formatted": format_size(total_size),
            "cache_levels_present": list(
                {
                    workspace.cache_level.value
                    if hasattr(workspace.cache_level, "value")
                    else str(workspace.cache_level)
                    for workspace in workspace_entries
                }
            ),
            "repositories_present": list(
                {workspace.repository for workspace in workspace_entries}
            ),
        }
    except Exception as e:
        logger.warning("Failed to get workspace summary: %s", e)
        return {
            "total_entries": 0,
            "total_size_bytes": 0,
            "total_size_formatted": "0 B",
            "cache_levels_present": [],
            "repositories_present": [],
        }
