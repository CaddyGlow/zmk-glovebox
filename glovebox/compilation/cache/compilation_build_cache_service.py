"""Compilation build cache service for ZMK build artifacts."""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from glovebox.config.user_config import UserConfig
from glovebox.core.cache_v2.cache_manager import CacheManager
from glovebox.core.cache_v2.models import CacheKey


class CompilationBuildCacheService:
    """Service for caching ZMK compilation build results.

    Provides short-term caching (3600s TTL) of successful compilation build directories
    based on repository, branch, config file hash, and keymap file hash.
    """

    def __init__(self, user_config: UserConfig, cache_manager: CacheManager) -> None:
        """Initialize the compilation build cache service.

        Args:
            user_config: User configuration containing cache settings
            cache_manager: Cache manager instance for data operations
        """
        self.user_config = user_config
        self.cache_manager = cache_manager
        self.logger = logging.getLogger(__name__)

        # Build cache TTL (1 hour as specified)
        self.BUILD_CACHE_TTL = 3600

    def get_cache_directory(self) -> Path:
        """Get the compilation build cache directory.

        Returns:
            Path to the compilation build cache directory
        """
        return self.user_config._config.cache_path / "compilation" / "builds"

    def generate_cache_key(
        self,
        repository: str,
        branch: str,
        config_hash: str,
        keymap_hash: str,
    ) -> str:
        """Generate cache key for build result.

        Args:
            repository: Git repository name (e.g., 'zmkfirmware/zmk')
            branch: Git branch name
            config_hash: Hash of the config file
            keymap_hash: Hash of the keymap file

        Returns:
            Generated cache key string
        """
        # Create a human-readable cache key with hash for uniqueness
        repo_part = repository.replace("/", "_")
        parts_hash = CacheKey.from_parts(repo_part, branch, config_hash, keymap_hash)
        return f"compilation_build_{parts_hash}"

    def generate_cache_key_from_files(
        self,
        repository: str,
        branch: str,
        config_file: Path,
        keymap_file: Path,
    ) -> str:
        """Generate cache key from actual file paths.

        Args:
            repository: Git repository name
            branch: Git branch name
            config_file: Path to config file
            keymap_file: Path to keymap file

        Returns:
            Generated cache key string
        """
        config_hash = CacheKey.from_path(config_file)
        keymap_hash = CacheKey.from_path(keymap_file)

        cache_key = self.generate_cache_key(
            repository, branch, config_hash, keymap_hash
        )

        # Debug logging to track cache key generation
        self.logger.debug(
            "Generated build cache key: %s (repo=%s, branch=%s, config_hash=%s, keymap_hash=%s)",
            cache_key,
            repository,
            branch,
            config_hash,
            keymap_hash,
        )

        return cache_key

    def cache_build_result(self, build_dir: Path, cache_key: str) -> bool:
        """Cache a successful build result.

        Args:
            build_dir: Path to the build directory to cache
            cache_key: Cache key for this build

        Returns:
            True if caching was successful, False otherwise
        """
        try:
            self.logger.debug(
                "Caching build result with key: %s from dir: %s", cache_key, build_dir
            )

            if not build_dir.exists() or not build_dir.is_dir():
                self.logger.warning("Build directory does not exist: %s", build_dir)
                return False

            # Create cache directory structure
            cache_base_dir = self.get_cache_directory()
            cached_build_dir = cache_base_dir / cache_key
            cached_build_dir.mkdir(parents=True, exist_ok=True)

            self.logger.debug("Created cache directory: %s", cached_build_dir)

            # Copy build artifacts to cache
            self._copy_build_artifacts(build_dir, cached_build_dir)

            # Create cache metadata
            cache_data = {
                "cached_path": str(cached_build_dir),
                "build_artifacts": list(self._get_build_artifacts(cached_build_dir)),
                "created_at": datetime.now().isoformat(),
                "source_build_dir": str(build_dir),
            }

            # Store in cache with TTL
            self.cache_manager.set(cache_key, cache_data, ttl=self.BUILD_CACHE_TTL)

            self.logger.info(
                "Successfully cached build result: %s -> %s (key: %s)",
                build_dir,
                cached_build_dir,
                cache_key,
            )
            return True

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Failed to cache build result: %s", e, exc_info=exc_info)
            return False

    def get_cached_build(self, cache_key: str) -> Path | None:
        """Get cached build directory if available.

        Args:
            cache_key: Cache key to look up

        Returns:
            Path to cached build directory, or None if not found
        """
        try:
            self.logger.debug("Looking up build cache with key: %s", cache_key)

            cached_data = self.cache_manager.get(cache_key)
            if not cached_data:
                self.logger.debug("No cached data found for key: %s", cache_key)
                return None

            cached_path = Path(cached_data["cached_path"])
            self.logger.debug("Found cached data, path: %s", cached_path)

            # Verify cached build still exists
            if not cached_path.exists():
                self.logger.info(
                    "Cached build path no longer exists: %s (treating as cache miss)",
                    cached_path,
                )
                self.cache_manager.delete(cache_key)
                return None

            self.logger.info("Cache hit for build: %s -> %s", cache_key, cached_path)
            return cached_path

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Failed to get cached build: %s", e, exc_info=exc_info)
            return None

    def delete_cached_build(self, cache_key: str) -> bool:
        """Delete a cached build.

        Args:
            cache_key: Cache key to delete

        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            # Get cached data to find directory path
            cached_data = self.cache_manager.get(cache_key)
            if cached_data:
                cached_path = Path(cached_data["cached_path"])
                if cached_path.exists():
                    shutil.rmtree(cached_path)
                    self.logger.debug("Deleted cached build directory: %s", cached_path)

            # Delete cache entry
            result = self.cache_manager.delete(cache_key)
            if result:
                self.logger.info("Successfully deleted cached build: %s", cache_key)

            return result

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Failed to delete cached build: %s", e, exc_info=exc_info)
            return False

    def list_cached_builds(self) -> list[tuple[str, dict[str, Any]]]:
        """List all cached builds.

        Returns:
            List of tuples containing (cache_key, cache_data)
        """
        try:
            all_keys = self.cache_manager.keys()
            build_keys = [
                key for key in all_keys if key.startswith("compilation_build_")
            ]

            cached_builds = []
            for key in build_keys:
                cached_data = self.cache_manager.get(key)
                if cached_data:
                    cached_builds.append((key, cached_data))

            return cached_builds

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error("Failed to list cached builds: %s", e, exc_info=exc_info)
            return []

    def cleanup_stale_entries(self) -> int:
        """Clean up stale cache entries where build directories no longer exist.

        Returns:
            Number of entries cleaned up
        """
        try:
            cleaned_count = 0
            cached_builds = self.list_cached_builds()

            for cache_key, cache_data in cached_builds:
                cached_path = Path(cache_data["cached_path"])
                if not cached_path.exists() and self.delete_cached_build(cache_key):
                    cleaned_count += 1
                    self.logger.debug(
                        "Cleaned up stale build cache entry: %s", cache_key
                    )

            if cleaned_count > 0:
                self.logger.info(
                    "Cleaned up %d stale build cache entries", cleaned_count
                )

            return cleaned_count

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to cleanup stale entries: %s", e, exc_info=exc_info
            )
            return 0

    def _copy_directory(self, source_dir: Path, target_dir: Path) -> None:
        pass

    def _copy_build_artifacts(self, source_dir: Path, target_dir: Path) -> None:
        """Copy build artifacts from source to target directory.

        Args:
            source_dir: Source build directory
            target_dir: Target cache directory
        """
        # Define build artifacts to copy
        artifact_patterns = [
            "*.uf2",
            "*.hex",
            "*.bin",
            "*.elf",
            "*.kconfig",
            "*.dts",
            "*.dts.pre",
            "devicetree_generated.h",
        ]

        for pattern in artifact_patterns:
            for artifact_file in source_dir.rglob(pattern):
                # Maintain relative structure within the target directory
                relative_path = artifact_file.relative_to(source_dir)
                target_file = target_dir / relative_path
                target_file.parent.mkdir(parents=True, exist_ok=True)

                shutil.copy2(artifact_file, target_file)
                # self.logger.debug(
                #     "Copied artifact: %s -> %s", artifact_file, target_file
                # )

    def _get_build_artifacts(self, build_dir: Path) -> list[str]:
        """Get list of build artifacts in a directory.

        Args:
            build_dir: Build directory to scan

        Returns:
            List of artifact file names
        """
        artifacts = []
        artifact_patterns = [
            "*.uf2",
            "*.hex",
            "*.bin",
            "*.elf",
            "*.kconfig",
            "*.dts",
            "*.dts.pre",
            "devicetree_generated.h",
        ]

        for pattern in artifact_patterns:
            for artifact_file in build_dir.rglob(pattern):
                relative_path = artifact_file.relative_to(build_dir)
                artifacts.append(str(relative_path))

        return artifacts
