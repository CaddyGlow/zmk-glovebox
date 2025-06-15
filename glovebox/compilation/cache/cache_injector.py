"""Cache injection tool for creating base dependencies cache from existing workspace."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from glovebox.compilation.cache.base_dependencies_cache import (
    BaseDependenciesCache,
    BaseDependenciesCacheError,
)


if TYPE_CHECKING:
    from glovebox.adapters import FileAdapter

logger = logging.getLogger(__name__)


class CacheInjectorError(BaseDependenciesCacheError):
    """Error in cache injection operations."""


def inject_base_dependencies_cache_from_workspace(
    source_workspace: Path,
    zmk_repo_url: str = "zmkfirmware/zmk",
    zmk_revision: str = "main",
    cache_root: Path | None = None,
    file_adapter: "FileAdapter | None" = None,
) -> str:
    """Inject base dependencies cache from existing workspace.

    Args:
        source_workspace: Path to existing workspace with ZMK dependencies
        zmk_repo_url: ZMK repository URL for cache key generation
        zmk_revision: ZMK revision for cache key generation
        cache_root: Root directory for cache storage
        file_adapter: File operations adapter

    Returns:
        str: Cache key for the injected cache

    Raises:
        CacheInjectorError: If cache injection fails
    """
    try:
        # Validate source workspace
        if not _validate_workspace_for_injection(source_workspace):
            raise CacheInjectorError(
                f"Source workspace is not valid for cache injection: {source_workspace}"
            )

        # Create base dependencies cache instance
        base_cache = BaseDependenciesCache(
            cache_root=cache_root, file_adapter=file_adapter
        )

        # Generate cache key
        cache_key = base_cache.get_cache_key(zmk_repo_url, zmk_revision)

        # Check if cache already exists
        existing_cache = base_cache.get_cached_workspace(cache_key)
        if existing_cache:
            logger.warning(
                "Cache with key %s already exists at %s. Skipping injection.",
                cache_key,
                existing_cache,
            )
            return cache_key

        # Get cache path
        cache_path = base_cache.cache_root / cache_key

        logger.info(
            "Injecting base dependencies cache from workspace: %s -> %s",
            source_workspace,
            cache_path,
        )

        # Ensure cache directory exists
        base_cache._ensure_cache_directory(cache_path)

        # Copy workspace contents to cache
        _copy_workspace_to_cache(source_workspace, cache_path, file_adapter)

        # Create cache metadata
        base_cache._create_cache_metadata(cache_path, zmk_repo_url, zmk_revision)

        logger.info(
            "Base dependencies cache injected successfully with key: %s", cache_key
        )
        return cache_key

    except Exception as e:
        msg = f"Failed to inject base dependencies cache: {e}"
        logger.error(msg)
        raise CacheInjectorError(msg) from e


def _validate_workspace_for_injection(workspace_path: Path) -> bool:
    """Validate workspace has required ZMK dependencies for cache injection.

    Args:
        workspace_path: Path to workspace to validate

    Returns:
        bool: True if workspace is valid for injection
    """
    if not workspace_path.exists() or not workspace_path.is_dir():
        logger.error(
            "Workspace does not exist or is not a directory: %s", workspace_path
        )
        return False

    # Check for essential ZMK dependencies
    required_paths = [
        workspace_path / "zephyr",
        workspace_path / "zmk",
        workspace_path / "modules",
    ]

    missing_paths = []
    for required_path in required_paths:
        if not required_path.exists():
            missing_paths.append(required_path)

    if missing_paths:
        logger.error(
            "Workspace missing required ZMK dependencies: %s",
            ", ".join(str(p) for p in missing_paths),
        )
        return False

    logger.debug("Workspace validation passed for cache injection: %s", workspace_path)
    return True


def _copy_workspace_to_cache(
    source_workspace: Path,
    cache_path: Path,
    file_adapter: "FileAdapter | None" = None,
) -> None:
    """Copy workspace contents to cache directory.

    Args:
        source_workspace: Source workspace path
        cache_path: Target cache path
        file_adapter: File operations adapter
    """
    import subprocess

    # Copy essential directories for base dependencies cache
    essential_dirs = ["zephyr", "zmk", "modules"]

    for dir_name in essential_dirs:
        source_dir = source_workspace / dir_name
        target_dir = cache_path / dir_name

        if source_dir.exists():
            logger.debug("Copying %s to cache", source_dir)

            # Use cp -r for efficient copying
            result = subprocess.run(
                ["cp", "-r", str(source_dir), str(target_dir)],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode != 0:
                raise CacheInjectorError(
                    f"Failed to copy {source_dir} to cache: {result.stderr}"
                )
        else:
            logger.warning("Source directory %s does not exist, skipping", source_dir)

    # Copy west.yml if it exists
    west_yml = source_workspace / "west.yml"
    if west_yml.exists():
        target_west_yml = cache_path / "west.yml"
        if file_adapter:
            file_adapter.copy_file(west_yml, target_west_yml)
        else:
            import shutil

            shutil.copy2(west_yml, target_west_yml)
        logger.debug("Copied west.yml to cache")
