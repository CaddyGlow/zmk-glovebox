"""Shared utilities for workspace cache management.

This module provides common functions for workspace cache key generation
and git information detection that are used by both the CLI commands
and the ZmkWestService compilation service.
"""

import logging
from pathlib import Path
from typing import Any

from glovebox.core.cache_v2.models import CacheKey


logger = logging.getLogger(__name__)


def detect_git_info(workspace_path: Path) -> dict[str, str]:
    """Auto-detect git repository information from workspace.

    Args:
        workspace_path: Path to workspace directory containing .git

    Returns:
        Dictionary with 'repository' and 'branch' keys
    """
    git_dir = workspace_path / ".git"
    result = {"repository": "unknown", "branch": "main"}

    try:
        if git_dir.exists():
            # Try to read git config for any remote
            config_file = git_dir / "zmk"
            if config_file.exists():
                config_content = config_file.read_text()
                lines = config_content.split("\n")
                for _i, line in enumerate(lines):
                    if "url =" in line:
                        url = line.split("url =")[-1].strip()
                        # Extract repo name from URL (github.com/user/repo.git -> user/repo)
                        if "github.com" in url or "gitlab.com" in url:
                            repo_part = url.split("/")[-2:]
                            if len(repo_part) == 2:
                                result["repository"] = (
                                    f"{repo_part[0]}/{repo_part[1].replace('.git', '')}"
                                )
                            break

            # Try to read current branch
            head_file = git_dir / "HEAD"
            if head_file.exists():
                head_content = head_file.read_text().strip()
                if head_content.startswith("ref: refs/heads/"):
                    result["branch"] = head_content.replace("ref: refs/heads/", "")
    except Exception:
        pass  # Use defaults if git detection fails

    return result


def generate_workspace_cache_key(
    repository: str,
    branch: str = "main",
    level: str = "base",
    image: str = "zmkfirmware/zmk-build-arm:stable",
    build_matrix_data: dict[str, Any] | None = None,
    additional_parts: list[str] | None = None,
) -> str:
    """Generate cache key for workspace following ZmkWestService pattern.

    Args:
        repository: Repository URL (e.g., 'zmkfirmware/zmk')
        branch: Git branch name
        level: Cache level - 'base', 'branch', 'full', or 'build'
        image: Docker image for compilation (used in branch/full/build levels)
        build_matrix_data: Build matrix data for full/build levels
        additional_parts: Additional key parts for build level (file hashes)

    Returns:
        Generated cache key string
    """
    if level == "base":
        # Base repository cache - longest TTL (30 days)
        key_parts = ["zmk_workspace_base", repository]
    elif level == "branch":
        # Repository + branch cache - medium TTL (1 day)
        key_parts = ["zmk_workspace_branch", repository, branch, image]
    elif level == "full":
        # Full configuration cache - shorter TTL (12 hours)
        key_parts = ["zmk_workspace_full", repository, branch, image]
        if build_matrix_data:
            build_matrix_hash = str(hash(str(build_matrix_data)))
            key_parts.append(build_matrix_hash)
    else:  # level == "build"
        # Build result cache - shortest TTL (1 hour), includes input file hashes
        key_parts = ["zmk_build_result", repository, branch, image]
        if build_matrix_data:
            build_matrix_hash = str(hash(str(build_matrix_data)))
            key_parts.append(build_matrix_hash)

        # Add additional parts for build-specific caching (file hashes)
        if additional_parts:
            key_parts.extend(additional_parts)

    return CacheKey.from_parts(*key_parts)


def get_workspace_cache_dir(user_config: Any = None) -> Path:
    """Get workspace cache directory from user config or default location.

    Args:
        user_config: Optional UserConfig instance to get cache path from

    Returns:
        Path to workspace cache directory
    """
    if (
        user_config
        and hasattr(user_config, "_config")
        and hasattr(user_config._config, "cache_path")
    ):
        # Use user-configured cache path
        return user_config._config.cache_path / "workspaces"  # type: ignore[no-any-return]

    # Fall back to default location for backward compatibility
    return Path.home() / ".cache" / "glovebox" / "workspaces"


def get_workspace_cache_ttls(user_config: Any = None) -> dict[str, int]:
    """Get workspace cache TTL values from user config or defaults.

    Args:
        user_config: Optional UserConfig instance to get TTL values from

    Returns:
        Dictionary mapping cache levels to TTL in seconds
    """
    if (
        user_config
        and hasattr(user_config, "_config")
        and hasattr(user_config._config, "cache_ttls")
    ):
        # Use user-configured TTL values
        return user_config._config.cache_ttls.get_workspace_ttls()  # type: ignore[no-any-return]

    # Fall back to default values for backward compatibility
    return {
        "base": 30 * 24 * 3600,  # 30 days
        "branch": 24 * 3600,  # 1 day
        "full": 12 * 3600,  # 12 hours
        "build": 3600,  # 1 hour
    }
