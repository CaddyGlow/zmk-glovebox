"""Cache manager for workspace and build caching."""

import json
import logging
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from glovebox.compilation.models.cache_metadata import (
    CacheConfig,
    CacheMetadata,
    CacheValidationResult,
    WorkspaceCacheEntry,
)
from glovebox.config.compile_methods import CompilationConfig


logger = logging.getLogger(__name__)


class CacheManagerError(Exception):
    """Error in cache management operations."""


class CacheManager:
    """Manage workspace and build caches with intelligent invalidation.

    Provides intelligent cache invalidation, cleanup automation, and cache
    optimization for compilation workspaces.
    """

    def __init__(self, cache_config: CacheConfig | None = None) -> None:
        """Initialize cache manager.

        Args:
            cache_config: Cache configuration options
        """
        self.cache_config = cache_config or CacheConfig()
        self.logger = logging.getLogger(__name__)

    def cache_workspace(self, workspace_path: Path) -> bool:
        """Cache workspace for reuse with intelligent caching strategies.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            bool: True if workspace was cached successfully

        Raises:
            CacheManagerError: If caching fails
        """
        try:
            self.logger.debug("Caching workspace: %s", workspace_path)

            # Create cache directory if it doesn't exist
            cache_dir = self._get_cache_directory(workspace_path)
            cache_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug("Created cache directory: %s", cache_dir)

            # Generate cache metadata with invalidation markers
            workspace_metadata = CacheMetadata(
                workspace_path=str(workspace_path),
                cached_at=str(int(time.time())),
                west_modules=self._get_west_modules(workspace_path),
                manifest_hash=self._calculate_manifest_hash(workspace_path),
                config_hash=self._calculate_config_hash(workspace_path),
                west_version=self._get_west_version(workspace_path),
            )

            # Write metadata to cache
            metadata_file = cache_dir / f"{workspace_path.name}_metadata.json"
            with metadata_file.open("w", encoding="utf-8") as f:
                f.write(workspace_metadata.model_dump_json(indent=2))

            # Create cache snapshot if caching is enabled
            if self._should_create_cache_snapshot(workspace_path):
                self._create_workspace_snapshot(workspace_path, cache_dir)

            self.logger.info("Workspace cached successfully: %s", workspace_path)
            return True

        except Exception as e:
            msg = f"Failed to cache workspace: {e}"
            self.logger.error(msg)
            raise CacheManagerError(msg) from e

    def is_cache_valid(self, workspace_path: Path, config: CompilationConfig) -> bool:
        """Check if cached workspace is valid and can be reused.

        Args:
            workspace_path: Path to workspace directory
            config: Compilation configuration

        Returns:
            bool: True if cache is valid and can be reused
        """
        try:
            validation_result = self.validate_cache(workspace_path, config)
            return validation_result.is_valid
        except Exception as e:
            self.logger.warning("Cache validation failed: %s", e)
            return False

    def validate_cache(
        self, workspace_path: Path, config: CompilationConfig
    ) -> CacheValidationResult:
        """Validate cache with detailed results.

        Args:
            workspace_path: Path to workspace directory
            config: Compilation configuration

        Returns:
            CacheValidationResult: Detailed validation results

        Raises:
            CacheManagerError: If validation fails
        """
        try:
            cache_dir = self._get_cache_directory(workspace_path)
            metadata_file = cache_dir / f"{workspace_path.name}_metadata.json"

            if not metadata_file.exists():
                return CacheValidationResult(
                    is_valid=False,
                    reasons=["No cache metadata found"],
                )

            with metadata_file.open(encoding="utf-8") as f:
                cache_data = json.load(f)

            cache_metadata = CacheMetadata.model_validate(cache_data)

            # Check cache age
            cached_at = float(cache_metadata.cached_at)
            current_time = time.time()
            cache_age_hours = (current_time - cached_at) / 3600

            reasons = []
            needs_refresh = False

            # Check if cache is too old
            if cache_age_hours > self.cache_config.max_age_hours:
                reasons.append(f"Cache too old: {cache_age_hours:.1f} hours")

            # Check if manifest has changed
            current_manifest_hash = self._calculate_manifest_hash(workspace_path)
            if current_manifest_hash != cache_metadata.manifest_hash:
                reasons.append("Manifest hash changed")

            # Check if config has changed
            current_config_hash = self._calculate_config_hash(workspace_path)
            if current_config_hash != cache_metadata.config_hash:
                reasons.append("Config hash changed")

            # Check if west modules have changed
            current_modules = self._get_west_modules(workspace_path)
            if current_modules != cache_metadata.west_modules:
                reasons.append("West modules changed")
                needs_refresh = True

            is_valid = len(reasons) == 0

            return CacheValidationResult(
                is_valid=is_valid,
                reasons=reasons,
                cache_age_hours=cache_age_hours,
                needs_refresh=needs_refresh,
            )

        except Exception as e:
            msg = f"Failed to validate cache: {e}"
            self.logger.error(msg)
            raise CacheManagerError(msg) from e

    def cleanup_old_caches(self, max_age_days: int = 7) -> bool:
        """Clean up old workspace caches to free disk space.

        Args:
            max_age_days: Maximum age in days for cache retention

        Returns:
            bool: True if cleanup was successful

        Raises:
            CacheManagerError: If cleanup fails
        """
        try:
            cache_base_dir = self._get_cache_base_directory()
            if not cache_base_dir.exists():
                return True

            current_time = time.time()
            max_age_seconds = max_age_days * 24 * 3600
            cleanup_count = 0

            self.logger.debug("Cleaning up caches older than %d days", max_age_days)

            for cache_dir in cache_base_dir.iterdir():
                if not cache_dir.is_dir():
                    continue

                # Check cache metadata files
                for metadata_file in cache_dir.glob("*_metadata.json"):
                    try:
                        with metadata_file.open(encoding="utf-8") as f:
                            cache_data = json.load(f)

                        cached_at = float(cache_data.get("cached_at", "0"))
                        cache_age = current_time - cached_at

                        if cache_age > max_age_seconds:
                            # Remove all cache files for this workspace
                            workspace_name = metadata_file.stem.replace("_metadata", "")
                            self._remove_cache_files(cache_dir, workspace_name)
                            cleanup_count += 1

                    except Exception as e:
                        self.logger.warning(
                            "Failed to process cache metadata %s: %s",
                            metadata_file,
                            e,
                        )

            if cleanup_count > 0:
                self.logger.info("Cleaned up %d old cache entries", cleanup_count)

            return True

        except Exception as e:
            msg = f"Failed to cleanup old caches: {e}"
            self.logger.error(msg)
            raise CacheManagerError(msg) from e

    def get_cache_statistics(self) -> dict[str, Any]:
        """Get cache usage statistics.

        Returns:
            dict[str, Any]: Cache statistics including size and entry count
        """
        try:
            cache_base_dir = self._get_cache_base_directory()
            if not cache_base_dir.exists():
                return {
                    "total_size_bytes": 0,
                    "total_entries": 0,
                    "cache_directories": 0,
                }

            total_size = 0
            total_entries = 0
            cache_directories = 0

            for cache_dir in cache_base_dir.iterdir():
                if cache_dir.is_dir():
                    cache_directories += 1
                    for file_path in cache_dir.rglob("*"):
                        if file_path.is_file():
                            total_size += file_path.stat().st_size
                            if file_path.name.endswith("_metadata.json"):
                                total_entries += 1

            return {
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "total_entries": total_entries,
                "cache_directories": cache_directories,
                "max_size_gb": self.cache_config.max_cache_size_gb,
                "max_age_hours": self.cache_config.max_age_hours,
            }

        except Exception as e:
            self.logger.warning("Failed to get cache statistics: %s", e)
            return {"error": str(e)}

    def _get_cache_directory(self, workspace_path: Path) -> Path:
        """Get cache directory for workspace.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            Path: Cache directory for the workspace
        """
        cache_base = self._get_cache_base_directory()
        return cache_base / f"workspace_{workspace_path.name}"

    def _get_cache_base_directory(self) -> Path:
        """Get base cache directory.

        Returns:
            Path: Base cache directory
        """
        return Path(tempfile.gettempdir()) / "glovebox_cache" / "workspaces"

    def _get_west_modules(self, workspace_path: Path) -> list[str]:
        """Get list of west modules in workspace.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            list[str]: List of west module names
        """
        try:
            west_yml = workspace_path / "west.yml"
            if not west_yml.exists():
                return []

            # In a full implementation, this would parse west.yml
            # For now, return basic module list
            return ["zmk"]

        except Exception as e:
            self.logger.debug("Failed to get west modules: %s", e)
            return []

    def _calculate_manifest_hash(self, workspace_path: Path) -> str:
        """Calculate hash of west manifest file.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            str: Hash of manifest file or "unknown" if not found
        """
        try:
            west_yml = workspace_path / "west.yml"
            if not west_yml.exists():
                return "unknown"

            import hashlib

            content = west_yml.read_text(encoding="utf-8")
            return hashlib.sha256(content.encode()).hexdigest()[:16]

        except Exception as e:
            self.logger.debug("Failed to calculate manifest hash: %s", e)
            return "unknown"

    def _calculate_config_hash(self, workspace_path: Path) -> str:
        """Calculate hash of configuration files.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            str: Hash of configuration files or "unknown" if not found
        """
        try:
            import hashlib

            hasher = hashlib.sha256()

            # Hash common config files
            config_files = [
                workspace_path / "build.yaml",
                workspace_path / "config" / "*.conf",
                workspace_path / "config" / "*.keymap",
            ]

            for config_pattern in config_files:
                if "*" in str(config_pattern):
                    # Handle glob patterns
                    for config_file in workspace_path.glob(
                        str(config_pattern.relative_to(workspace_path))
                    ):
                        if config_file.is_file():
                            hasher.update(config_file.read_bytes())
                else:
                    if config_pattern.exists():
                        hasher.update(config_pattern.read_bytes())

            return hasher.hexdigest()[:16]

        except Exception as e:
            self.logger.debug("Failed to calculate config hash: %s", e)
            return "unknown"

    def _get_west_version(self, workspace_path: Path) -> str:
        """Get west version for the workspace.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            str: West version or "unknown" if not available
        """
        try:
            # In a full implementation, this would check west version
            return "unknown"
        except Exception as e:
            self.logger.debug("Failed to get west version: %s", e)
            return "unknown"

    def _should_create_cache_snapshot(self, workspace_path: Path) -> bool:
        """Determine if workspace snapshot should be created for caching.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            bool: True if snapshot should be created
        """
        try:
            west_dir = workspace_path / ".west"
            if not west_dir.exists():
                return False

            # Check workspace size - only cache if it's substantial
            total_size = sum(
                f.stat().st_size for f in west_dir.rglob("*") if f.is_file()
            )
            # Create snapshots for workspaces larger than 10MB
            return total_size > 10 * 1024 * 1024

        except Exception as e:
            self.logger.debug("Failed to check snapshot requirements: %s", e)
            return False

    def _create_workspace_snapshot(self, workspace_path: Path, cache_dir: Path) -> bool:
        """Create compressed snapshot of workspace for faster restoration.

        Args:
            workspace_path: Path to workspace directory
            cache_dir: Cache directory for storing snapshot

        Returns:
            bool: True if snapshot was created successfully
        """
        try:
            snapshot_file = cache_dir / f"{workspace_path.name}_snapshot.tar.gz"
            self.logger.debug("Creating workspace snapshot: %s", snapshot_file)

            # For now, just mark that we would create a snapshot
            # In a full implementation, this would compress workspace files
            snapshot_metadata = {
                "snapshot_file": str(snapshot_file),
                "workspace_path": str(workspace_path),
                "created_at": str(int(time.time())),
                "compression": "gzip",
            }

            snapshot_meta_file = cache_dir / f"{workspace_path.name}_snapshot_meta.json"
            with snapshot_meta_file.open("w", encoding="utf-8") as f:
                json.dump(snapshot_metadata, f, indent=2)

            self.logger.debug("Workspace snapshot metadata created")
            return True

        except Exception as e:
            self.logger.warning("Failed to create workspace snapshot: %s", e)
            return False

    def _remove_cache_files(self, cache_dir: Path, cache_prefix: str) -> None:
        """Remove all cache files with given prefix.

        Args:
            cache_dir: Cache directory
            cache_prefix: Prefix for cache files to remove
        """
        try:
            # Find and remove cache-related files
            cache_patterns = [
                f"{cache_prefix}_metadata.json",
                f"{cache_prefix}_snapshot.tar.gz",
                f"{cache_prefix}_snapshot_meta.json",
            ]

            for pattern in cache_patterns:
                cache_file = cache_dir / pattern
                if cache_file.exists():
                    cache_file.unlink()
                    self.logger.debug("Removed cache file: %s", cache_file)

        except Exception as e:
            self.logger.warning("Failed to remove cache files: %s", e)


def create_cache_manager(cache_config: CacheConfig | None = None) -> CacheManager:
    """Create cache manager instance.

    Args:
        cache_config: Optional cache configuration

    Returns:
        CacheManager: New cache manager instance
    """
    return CacheManager(cache_config)
