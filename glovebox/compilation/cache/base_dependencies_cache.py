"""Base ZMK dependencies cache implementation.

Manages caching of shared ZMK dependencies including:
- Zephyr RTOS
- ZMK modules and dependencies
- ZMK firmware repository

This forms the foundation layer that all compilations can reuse.
"""

import hashlib
import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.adapters import FileAdapter
from glovebox.core.errors import GloveboxError


if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class BaseDependenciesCacheError(GloveboxError):
    """Error in base dependencies cache operations."""


class BaseDependenciesCache:
    """Cache for base ZMK dependencies shared across all compilations.

    This cache stores the fundamental dependencies that all ZMK builds require:
    - Zephyr RTOS repository and modules
    - ZMK firmware repository
    - Shared build tools and dependencies

    The cache key is based on the ZMK repository URL and branch/revision,
    ensuring different ZMK versions have separate cache entries.
    """

    def __init__(
        self,
        cache_root: Path | None = None,
        file_adapter: FileAdapter | None = None,
    ) -> None:
        """Initialize base dependencies cache.

        Args:
            cache_root: Root directory for cache storage
            file_adapter: File operations adapter
        """
        self.cache_root = cache_root or (
            Path.home() / ".glovebox" / "cache" / "base_deps"
        )
        self.file_adapter = file_adapter
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def get_cache_key(
        self,
        zmk_repo_url: str,
        zmk_revision: str = "main",
        additional_context: dict[str, Any] | None = None,
    ) -> str:
        """Generate cache key for base dependencies.

        Args:
            zmk_repo_url: ZMK repository URL
            zmk_revision: ZMK branch/revision
            additional_context: Additional context for cache key generation

        Returns:
            str: Cache key for the dependencies
        """
        # Normalize repository URL for consistent caching
        normalized_url = self._normalize_repo_url(zmk_repo_url)

        # Create base cache key components
        key_components = [
            f"zmk_repo={normalized_url}",
            f"revision={zmk_revision}",
        ]

        # Add additional context if provided
        if additional_context:
            for key, value in sorted(additional_context.items()):
                key_components.append(f"{key}={value}")

        # Generate hash from components for consistent key length
        key_string = "|".join(key_components)
        cache_key = hashlib.sha256(key_string.encode()).hexdigest()[:16]

        self.logger.debug(
            "Generated cache key %s for %s@%s", cache_key, normalized_url, zmk_revision
        )
        return cache_key

    def get_cached_workspace(self, cache_key: str) -> Path | None:
        """Get cached workspace path if it exists and is valid.

        Args:
            cache_key: Cache key for the dependencies

        Returns:
            Path | None: Path to cached workspace, or None if not available
        """
        cache_path = self.cache_root / cache_key

        if not self._is_cache_valid(cache_path):
            return None

        self.logger.info("Found valid base dependencies cache: %s", cache_path)
        return cache_path

    def create_cached_workspace(
        self,
        cache_key: str,
        zmk_repo_url: str,
        zmk_revision: str = "main",
    ) -> Path:
        """Create and populate cached workspace with base dependencies.

        Args:
            cache_key: Cache key for the dependencies
            zmk_repo_url: ZMK repository URL
            zmk_revision: ZMK branch/revision

        Returns:
            Path: Path to created cached workspace

        Raises:
            BaseDependenciesCacheError: If cache creation fails
        """
        cache_path = self.cache_root / cache_key

        try:
            self.logger.info("Creating base dependencies cache: %s", cache_path)

            # Ensure cache directory exists
            self._ensure_cache_directory(cache_path)

            # Initialize west workspace with ZMK dependencies
            if not self._initialize_base_workspace(
                cache_path, zmk_repo_url, zmk_revision
            ):
                raise BaseDependenciesCacheError(
                    f"Failed to initialize base workspace at {cache_path}"
                )

            # Create cache metadata
            self._create_cache_metadata(cache_path, zmk_repo_url, zmk_revision)

            self.logger.info(
                "Base dependencies cache created successfully: %s", cache_path
            )
            return cache_path

        except Exception as e:
            msg = f"Failed to create base dependencies cache: {e}"
            self.logger.error(msg)
            raise BaseDependenciesCacheError(msg) from e

    def clone_cached_workspace(
        self, source_cache_path: Path, target_path: Path
    ) -> bool:
        """Clone cached workspace to target location for compilation.

        Args:
            source_cache_path: Source cached workspace path
            target_path: Target workspace path for compilation

        Returns:
            bool: True if cloning succeeded

        Raises:
            BaseDependenciesCacheError: If cloning fails
        """
        try:
            self.logger.info(
                "Cloning cached workspace: %s -> %s", source_cache_path, target_path
            )

            # Ensure target directory exists
            if self.file_adapter:
                self.file_adapter.create_directory(target_path.parent)
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)

            # Use cp -r or similar to efficiently copy the workspace
            result = subprocess.run(
                ["cp", "-r", str(source_cache_path), str(target_path)],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout for large workspaces
            )

            if result.returncode != 0:
                raise BaseDependenciesCacheError(
                    f"Failed to clone workspace: {result.stderr}"
                )

            self.logger.info("Workspace cloned successfully")
            return True

        except subprocess.TimeoutExpired as e:
            msg = f"Workspace cloning timed out: {e}"
            self.logger.error(msg)
            raise BaseDependenciesCacheError(msg) from e
        except Exception as e:
            msg = f"Failed to clone cached workspace: {e}"
            self.logger.error(msg)
            raise BaseDependenciesCacheError(msg) from e

    def cleanup_cache(self, max_age_days: int = 30) -> None:
        """Clean up old cache entries.

        Args:
            max_age_days: Maximum age in days for cache entries
        """
        try:
            if not self.cache_root.exists():
                return

            import time

            current_time = time.time()
            cutoff_time = current_time - (max_age_days * 24 * 3600)

            for cache_dir in self.cache_root.iterdir():
                if not cache_dir.is_dir():
                    continue

                # Check cache age using metadata or directory modification time
                cache_time = cache_dir.stat().st_mtime
                if cache_time < cutoff_time:
                    self.logger.info("Removing old cache entry: %s", cache_dir)
                    if self.file_adapter:
                        self.file_adapter.remove_dir(cache_dir)
                    else:
                        import shutil

                        shutil.rmtree(cache_dir)

        except Exception as e:
            self.logger.warning("Cache cleanup failed: %s", e)

    def _normalize_repo_url(self, repo_url: str) -> str:
        """Normalize repository URL for consistent caching.

        Args:
            repo_url: Repository URL to normalize

        Returns:
            str: Normalized repository URL
        """
        # Handle different URL formats consistently
        if repo_url.startswith("https://github.com/"):
            # Extract org/repo from full URL
            return repo_url.replace("https://github.com/", "").rstrip("/")
        elif "/" in repo_url and not repo_url.startswith("http"):
            # Handle org/repo format
            return repo_url.rstrip("/")
        else:
            # Return as-is for other formats
            return repo_url

    def _is_cache_valid(self, cache_path: Path) -> bool:
        """Check if cached workspace is valid and complete.

        Args:
            cache_path: Path to cached workspace

        Returns:
            bool: True if cache is valid
        """
        if not cache_path.exists() or not cache_path.is_dir():
            return False

        # Check for essential directories/files (excluding .west)
        required_paths = [
            cache_path / "zephyr",
            cache_path / "zmk",
            cache_path / "modules",
            cache_path / ".glovebox_cache_metadata.json",
        ]

        for required_path in required_paths:
            if not required_path.exists():
                self.logger.debug("Cache invalid - missing: %s", required_path)
                return False

        self.logger.debug("Cache validation passed: %s", cache_path)
        return True

    def _ensure_cache_directory(self, cache_path: Path) -> None:
        """Ensure cache directory exists and is ready.

        Args:
            cache_path: Path to cache directory
        """
        if self.file_adapter:
            self.file_adapter.create_directory(cache_path)
        else:
            cache_path.mkdir(parents=True, exist_ok=True)

    def _initialize_base_workspace(
        self, cache_path: Path, zmk_repo_url: str, zmk_revision: str
    ) -> bool:
        """Initialize base west workspace with ZMK dependencies.

        Args:
            cache_path: Path to cache directory
            zmk_repo_url: ZMK repository URL
            zmk_revision: ZMK branch/revision

        Returns:
            bool: True if initialization succeeded
        """
        try:
            # Create minimal west.yml for the workspace
            west_yml_content = self._create_base_west_yml(zmk_repo_url, zmk_revision)
            west_yml_path = cache_path / "west.yml"

            if self.file_adapter:
                self.file_adapter.write_text(west_yml_path, west_yml_content)
            else:
                west_yml_path.write_text(west_yml_content)

            # Initialize west workspace
            result = subprocess.run(
                ["west", "init", "-l", str(cache_path)],
                capture_output=True,
                text=True,
                cwd=cache_path.parent,
                timeout=120,
            )

            if result.returncode != 0:
                self.logger.error("West init failed: %s", result.stderr)
                return False

            # Update dependencies
            result = subprocess.run(
                ["west", "update"],
                capture_output=True,
                text=True,
                cwd=cache_path,
                timeout=600,  # 10 minute timeout for dependency updates
            )

            if result.returncode != 0:
                self.logger.error("West update failed: %s", result.stderr)
                return False

            self.logger.info("Base workspace initialized successfully")
            return True

        except subprocess.TimeoutExpired as e:
            self.logger.error("West command timed out: %s", e)
            return False
        except Exception as e:
            self.logger.error("Failed to initialize base workspace: %s", e)
            return False

    def _create_base_west_yml(self, zmk_repo_url: str, zmk_revision: str) -> str:
        """Create base west.yml for ZMK dependencies.

        Args:
            zmk_repo_url: ZMK repository URL
            zmk_revision: ZMK branch/revision

        Returns:
            str: west.yml content
        """
        # Handle different repository URL formats
        if zmk_repo_url.startswith("https://github.com/"):
            repo_path = zmk_repo_url.replace("https://github.com/", "")
            org_name, repo_name = repo_path.split("/")
        elif "/" in zmk_repo_url:
            org_name, repo_name = zmk_repo_url.split("/")
        else:
            # Fallback
            org_name = "zmkfirmware"
            repo_name = "zmk"

        return f"""# Base ZMK Dependencies - Generated by Glovebox Cache
manifest:
  defaults:
    remote: {org_name}
  remotes:
    - name: {org_name}
      url-base: https://github.com/{org_name}
  projects:
    - name: {repo_name}
      remote: {org_name}
      revision: {zmk_revision}
      import: app/west.yml
  self:
    path: cache-workspace
"""

    def _create_cache_metadata(
        self, cache_path: Path, zmk_repo_url: str, zmk_revision: str
    ) -> None:
        """Create cache metadata for tracking and validation.

        Args:
            cache_path: Path to cache directory
            zmk_repo_url: ZMK repository URL
            zmk_revision: ZMK branch/revision
        """
        import json
        from datetime import datetime

        metadata = {
            "created_at": datetime.now().isoformat(),
            "zmk_repo_url": zmk_repo_url,
            "zmk_revision": zmk_revision,
            "cache_version": "1.0",
            "glovebox_version": "1.0.0",  # Could be retrieved from package
        }

        metadata_path = cache_path / ".glovebox_cache_metadata.json"
        metadata_content = json.dumps(metadata, indent=2)

        if self.file_adapter:
            self.file_adapter.write_text(metadata_path, metadata_content)
        else:
            metadata_path.write_text(metadata_content)


def create_base_dependencies_cache(
    cache_root: Path | None = None,
    file_adapter: FileAdapter | None = None,
) -> BaseDependenciesCache:
    """Create base dependencies cache instance.

    Args:
        cache_root: Root directory for cache storage
        file_adapter: File operations adapter

    Returns:
        BaseDependenciesCache: New cache instance
    """
    return BaseDependenciesCache(cache_root=cache_root, file_adapter=file_adapter)
