"""Compilation-specific cache service using generic cache system."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

from glovebox.core.cache import CacheKey, CacheManager, create_default_cache
from glovebox.core.errors import GloveboxError

logger = logging.getLogger(__name__)


class CompilationCacheError(GloveboxError):
    """Error in compilation cache operations."""


class CompilationCache:
    """Compilation-specific cache service.

    Provides high-level caching operations for compilation domain
    using the generic cache system as the underlying storage.
    """

    def __init__(self, cache_manager: CacheManager | None = None):
        """Initialize compilation cache.

        Args:
            cache_manager: Generic cache manager (uses default if None)
        """
        self.cache = cache_manager or create_default_cache()
        logger.debug("Initialized compilation cache with %s", type(self.cache).__name__)

    def get_zmk_dependencies(self, repository: str, branch: str) -> Any:
        """Get cached ZMK dependencies for repository and branch.

        Args:
            repository: ZMK repository URL
            branch: Git branch or revision

        Returns:
            Cached ZMK dependencies or None if not cached
        """
        key = CacheKey.from_parts("zmk_deps", repository, branch)
        return self.cache.get(key)

    def cache_zmk_dependencies(
        self, repository: str, branch: str, dependencies: dict[str, Any], ttl_hours: int = 24
    ) -> None:
        """Cache ZMK dependencies for repository and branch.

        Args:
            repository: ZMK repository URL
            branch: Git branch or revision
            dependencies: ZMK dependencies data to cache
            ttl_hours: Time-to-live in hours
        """
        key = CacheKey.from_parts("zmk_deps", repository, branch)
        self.cache.set(key, dependencies, ttl=ttl_hours * 3600)
        logger.debug("Cached ZMK dependencies for %s:%s", repository, branch)

    def get_keyboard_config(
        self, keyboard_profile: "KeyboardProfile"
    ) -> Any:
        """Get cached keyboard configuration.

        Args:
            keyboard_profile: Keyboard profile to get config for

        Returns:
            Cached keyboard configuration or None if not cached
        """
        # Create cache key from keyboard profile components
        key_parts = [
            "keyboard_config",
            keyboard_profile.keyboard_name,
        ]
        
        if keyboard_profile.firmware_version:
            key_parts.append(keyboard_profile.firmware_version)
            
        # Include configuration hash for cache invalidation
        if hasattr(keyboard_profile, "keyboard_config"):
            config_data = keyboard_profile.keyboard_config.dict() if hasattr(keyboard_profile.keyboard_config, "dict") else str(keyboard_profile.keyboard_config)
            config_key = CacheKey.from_dict({"config": config_data})
            key_parts.append(config_key)

        key = CacheKey.from_parts(*key_parts)
        return self.cache.get(key)

    def cache_keyboard_config(
        self, 
        keyboard_profile: "KeyboardProfile", 
        config_data: dict[str, Any], 
        ttl_hours: int = 6
    ) -> None:
        """Cache keyboard configuration.

        Args:
            keyboard_profile: Keyboard profile to cache config for
            config_data: Configuration data to cache
            ttl_hours: Time-to-live in hours
        """
        # Create same cache key as get_keyboard_config
        key_parts = [
            "keyboard_config",
            keyboard_profile.keyboard_name,
        ]
        
        if keyboard_profile.firmware_version:
            key_parts.append(keyboard_profile.firmware_version)
            
        if hasattr(keyboard_profile, "keyboard_config"):
            config_data_for_key = keyboard_profile.keyboard_config.dict() if hasattr(keyboard_profile.keyboard_config, "dict") else str(keyboard_profile.keyboard_config)
            config_key = CacheKey.from_dict({"config": config_data_for_key})
            key_parts.append(config_key)

        key = CacheKey.from_parts(*key_parts)
        self.cache.set(key, config_data, ttl=ttl_hours * 3600)
        logger.debug("Cached keyboard config for %s", keyboard_profile.keyboard_name)

    def get_workspace_cache(self, workspace_path: Path) -> Any:
        """Get cached workspace data.

        Args:
            workspace_path: Path to workspace directory

        Returns:
            Cached workspace data or None if not cached
        """
        key = CacheKey.from_path(workspace_path)
        return self.cache.get(f"workspace:{key}")

    def cache_workspace(
        self, workspace_path: Path, workspace_data: dict[str, Any], ttl_hours: int = 12
    ) -> None:
        """Cache workspace data.

        Args:
            workspace_path: Path to workspace directory
            workspace_data: Workspace data to cache
            ttl_hours: Time-to-live in hours
        """
        key = CacheKey.from_path(workspace_path)
        self.cache.set(f"workspace:{key}", workspace_data, ttl=ttl_hours * 3600)
        logger.debug("Cached workspace data for %s", workspace_path)

    def get_build_matrix(self, config_hash: str) -> Any:
        """Get cached build matrix.

        Args:
            config_hash: Hash of build configuration

        Returns:
            Cached build matrix or None if not cached
        """
        key = CacheKey.from_parts("build_matrix", config_hash)
        return self.cache.get(key)

    def cache_build_matrix(
        self, config_hash: str, build_matrix: dict[str, Any], ttl_hours: int = 6
    ) -> None:
        """Cache build matrix.

        Args:
            config_hash: Hash of build configuration
            build_matrix: Build matrix data to cache
            ttl_hours: Time-to-live in hours
        """
        key = CacheKey.from_parts("build_matrix", config_hash)
        self.cache.set(key, build_matrix, ttl=ttl_hours * 3600)
        logger.debug("Cached build matrix for config %s", config_hash)

    def get_compilation_result(
        self, keymap_path: Path, config_path: Path
    ) -> Any:
        """Get cached compilation result.

        Args:
            keymap_path: Path to keymap file
            config_path: Path to config file

        Returns:
            Cached compilation result or None if not cached
        """
        # Use file paths and modification times for cache key
        keymap_key = CacheKey.from_path(keymap_path)
        config_key = CacheKey.from_path(config_path)
        key = CacheKey.from_parts("compilation", keymap_key, config_key)
        return self.cache.get(key)

    def cache_compilation_result(
        self,
        keymap_path: Path,
        config_path: Path,
        result_data: dict[str, Any],
        ttl_hours: int = 1,
    ) -> None:
        """Cache compilation result.

        Args:
            keymap_path: Path to keymap file
            config_path: Path to config file
            result_data: Compilation result data to cache
            ttl_hours: Time-to-live in hours
        """
        keymap_key = CacheKey.from_path(keymap_path)
        config_key = CacheKey.from_path(config_path)
        key = CacheKey.from_parts("compilation", keymap_key, config_key)
        self.cache.set(key, result_data, ttl=ttl_hours * 3600)
        logger.debug("Cached compilation result for %s + %s", keymap_path.name, config_path.name)

    def clear_compilation_cache(self) -> None:
        """Clear all compilation-related cache entries."""
        # Note: This is a simplified implementation
        # A more sophisticated version would only clear compilation-specific entries
        self.cache.clear()
        logger.info("Cleared compilation cache")

    def get_cache_stats(self) -> dict[str, Any]:
        """Get compilation cache statistics.

        Returns:
            Dictionary with cache performance metrics
        """
        stats = self.cache.get_stats()
        return {
            "total_entries": stats.total_entries,
            "total_size_bytes": stats.total_size_bytes,
            "hit_count": stats.hit_count,
            "miss_count": stats.miss_count,
            "hit_rate_percent": round(stats.hit_rate, 2),
            "eviction_count": stats.eviction_count,
            "error_count": stats.error_count,
        }

    def cleanup_cache(self) -> int:
        """Run cache cleanup and return number of entries removed.

        Returns:
            Number of cache entries removed
        """
        removed = self.cache.cleanup()
        logger.debug("Compilation cache cleanup removed %d entries", removed)
        return removed


def create_compilation_cache(cache_manager: CacheManager | None = None) -> CompilationCache:
    """Create a compilation cache instance.

    Args:
        cache_manager: Generic cache manager (uses default if None)

    Returns:
        Configured compilation cache
    """
    return CompilationCache(cache_manager)