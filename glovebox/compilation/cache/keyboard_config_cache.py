"""Keyboard configuration cache implementation.

Manages caching of keyboard-specific workspace configurations built on top
of the base ZMK dependencies cache. This includes:
- Keyboard-specific build.yaml configurations
- Shield and board combinations
- Custom keyboard modifications and overlays

This forms the second tier of the caching system.
"""

import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.adapters import FileAdapter
from glovebox.compilation.cache.base_dependencies_cache import (
    BaseDependenciesCache,
    BaseDependenciesCacheError,
)
from glovebox.core.errors import GloveboxError


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile

logger = logging.getLogger(__name__)


class KeyboardConfigCacheError(GloveboxError):
    """Error in keyboard configuration cache operations."""


class KeyboardConfigCache:
    """Cache for keyboard-specific workspace configurations.

    This cache builds on top of the base dependencies cache and stores
    keyboard-specific configurations including:
    - Build matrix configurations (build.yaml)
    - Shield and board combinations
    - Keyboard-specific overlays and modifications

    The cache key is based on keyboard profile and configuration parameters,
    ensuring different keyboard configurations have separate cache entries.
    """

    def __init__(
        self,
        base_cache: BaseDependenciesCache,
        cache_root: Path | None = None,
        file_adapter: FileAdapter | None = None,
    ) -> None:
        """Initialize keyboard configuration cache.

        Args:
            base_cache: Base dependencies cache instance
            cache_root: Root directory for cache storage
            file_adapter: File operations adapter
        """
        self.base_cache = base_cache
        self.cache_root = cache_root or (
            Path.home() / ".glovebox" / "cache" / "keyboard_config"
        )
        self.file_adapter = file_adapter
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def get_cache_key(
        self,
        keyboard_profile: "KeyboardProfile",
        shield_name: str | None = None,
        board_name: str = "nice_nano_v2",
        additional_context: dict[str, Any] | None = None,
    ) -> str:
        """Generate cache key for keyboard configuration.

        Args:
            keyboard_profile: Keyboard profile configuration
            shield_name: Shield name for the keyboard
            board_name: Board name for builds
            additional_context: Additional context for cache key generation

        Returns:
            str: Cache key for the keyboard configuration
        """
        # Extract relevant configuration parameters
        keyboard_name = keyboard_profile.keyboard_name

        # Include firmware configuration if available
        firmware_context = {}
        if keyboard_profile.firmware_config:
            build_options = keyboard_profile.firmware_config.build_options
            firmware_context.update(
                {
                    "zmk_repo": build_options.repository,
                    "zmk_branch": build_options.branch,
                }
            )

        # Create keyboard-specific cache key components
        key_components = [
            f"keyboard={keyboard_name}",
            f"shield={shield_name or keyboard_name}",
            f"board={board_name}",
        ]

        # Add firmware context
        for key, value in sorted(firmware_context.items()):
            key_components.append(f"{key}={value}")

        # Add additional context if provided
        if additional_context:
            for key, value in sorted(additional_context.items()):
                key_components.append(f"{key}={value}")

        # Generate hash from components for consistent key length
        key_string = "|".join(key_components)
        cache_key = hashlib.sha256(key_string.encode()).hexdigest()[:16]

        self.logger.debug(
            "Generated keyboard cache key %s for %s/%s@%s",
            cache_key,
            keyboard_name,
            shield_name,
            board_name,
        )
        return cache_key

    def get_cached_workspace(
        self,
        cache_key: str,
        base_cache_key: str,
    ) -> Path | None:
        """Get cached keyboard workspace if it exists and is valid.

        Args:
            cache_key: Cache key for the keyboard configuration
            base_cache_key: Base dependencies cache key

        Returns:
            Path | None: Path to cached workspace, or None if not available
        """
        cache_path = self.cache_root / f"{base_cache_key}_{cache_key}"

        if not self._is_cache_valid(cache_path, base_cache_key):
            return None

        self.logger.info("Found valid keyboard config cache: %s", cache_path)
        return cache_path

    def create_cached_workspace(
        self,
        cache_key: str,
        base_cache_key: str,
        base_workspace_path: Path,
        keyboard_profile: "KeyboardProfile",
        shield_name: str | None = None,
        board_name: str = "nice_nano_v2",
    ) -> Path:
        """Create keyboard-specific cached workspace from base dependencies.

        Args:
            cache_key: Cache key for the keyboard configuration
            base_cache_key: Base dependencies cache key
            base_workspace_path: Path to base dependencies workspace
            keyboard_profile: Keyboard profile configuration
            shield_name: Shield name for the keyboard
            board_name: Board name for builds

        Returns:
            Path: Path to created cached workspace

        Raises:
            KeyboardConfigCacheError: If cache creation fails
        """
        cache_path = self.cache_root / f"{base_cache_key}_{cache_key}"

        try:
            self.logger.info("Creating keyboard config cache: %s", cache_path)

            # Clone base workspace to keyboard-specific cache
            if not self.base_cache.clone_cached_workspace(
                base_workspace_path, cache_path
            ):
                raise KeyboardConfigCacheError(
                    f"Failed to clone base workspace to {cache_path}"
                )

            # Add keyboard-specific configuration
            if not self._configure_keyboard_workspace(
                cache_path, keyboard_profile, shield_name, board_name
            ):
                raise KeyboardConfigCacheError(
                    f"Failed to configure keyboard workspace at {cache_path}"
                )

            # Create keyboard cache metadata
            self._create_keyboard_cache_metadata(
                cache_path, base_cache_key, keyboard_profile, shield_name, board_name
            )

            self.logger.info(
                "Keyboard config cache created successfully: %s", cache_path
            )
            return cache_path

        except Exception as e:
            msg = f"Failed to create keyboard config cache: {e}"
            self.logger.error(msg)
            raise KeyboardConfigCacheError(msg) from e

    def clone_cached_workspace(
        self, source_cache_path: Path, target_path: Path
    ) -> bool:
        """Clone cached keyboard workspace to target location for compilation.

        Args:
            source_cache_path: Source cached workspace path
            target_path: Target workspace path for compilation

        Returns:
            bool: True if cloning succeeded
        """
        try:
            # Use base cache cloning functionality
            return self.base_cache.clone_cached_workspace(
                source_cache_path, target_path
            )
        except BaseDependenciesCacheError as e:
            msg = f"Failed to clone keyboard cached workspace: {e}"
            self.logger.error(msg)
            raise KeyboardConfigCacheError(msg) from e

    def cleanup_cache(self, max_age_days: int = 30) -> None:
        """Clean up old keyboard cache entries.

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

                # Check cache age
                cache_time = cache_dir.stat().st_mtime
                if cache_time < cutoff_time:
                    self.logger.info("Removing old keyboard cache entry: %s", cache_dir)
                    if self.file_adapter:
                        self.file_adapter.remove_dir(cache_dir)
                    else:
                        import shutil

                        shutil.rmtree(cache_dir)

        except Exception as e:
            self.logger.warning("Keyboard cache cleanup failed: %s", e)

    def _is_cache_valid(self, cache_path: Path, base_cache_key: str) -> bool:
        """Check if cached keyboard workspace is valid and complete.

        Args:
            cache_path: Path to cached workspace
            base_cache_key: Base dependencies cache key for validation

        Returns:
            bool: True if cache is valid
        """
        if not cache_path.exists() or not cache_path.is_dir():
            return False

        # Check for essential directories/files (inherits from base cache)
        required_paths = [
            cache_path / ".west",
            cache_path / "zephyr",
            cache_path / "zmk",
            cache_path / ".glovebox_cache_metadata.json",
            cache_path / ".glovebox_keyboard_cache_metadata.json",
            cache_path / "config",
            cache_path / "build.yaml",
        ]

        for required_path in required_paths:
            if not required_path.exists():
                self.logger.debug("Keyboard cache invalid - missing: %s", required_path)
                return False

        # Validate base cache key consistency
        try:
            import json

            metadata_path = cache_path / ".glovebox_keyboard_cache_metadata.json"
            if self.file_adapter:
                metadata_content = self.file_adapter.read_text(metadata_path)
            else:
                metadata_content = metadata_path.read_text()

            metadata = json.loads(metadata_content)
            if metadata.get("base_cache_key") != base_cache_key:
                self.logger.debug("Keyboard cache invalid - base cache key mismatch")
                return False

        except Exception as e:
            self.logger.debug("Keyboard cache invalid - metadata error: %s", e)
            return False

        self.logger.debug("Keyboard cache validation passed: %s", cache_path)
        return True

    def _configure_keyboard_workspace(
        self,
        workspace_path: Path,
        keyboard_profile: "KeyboardProfile",
        shield_name: str | None = None,
        board_name: str = "nice_nano_v2",
    ) -> bool:
        """Configure workspace with keyboard-specific settings.

        Args:
            workspace_path: Path to workspace directory
            keyboard_profile: Keyboard profile configuration
            shield_name: Shield name for the keyboard
            board_name: Board name for builds

        Returns:
            bool: True if configuration succeeded
        """
        try:
            # Create config directory
            config_dir = workspace_path / "config"
            if self.file_adapter:
                self.file_adapter.create_directory(config_dir)
            else:
                config_dir.mkdir(exist_ok=True)

            # Generate build.yaml for this keyboard configuration
            effective_shield = shield_name or keyboard_profile.keyboard_name
            build_yaml_content = self._create_keyboard_build_yaml(
                effective_shield, board_name
            )
            build_yaml_path = workspace_path / "build.yaml"

            if self.file_adapter:
                self.file_adapter.write_text(build_yaml_path, build_yaml_content)
            else:
                build_yaml_path.write_text(build_yaml_content)

            # Create keyboard-specific west.yml in config directory
            west_yml_content = self._create_keyboard_west_yml(keyboard_profile)
            west_yml_path = config_dir / "west.yml"

            if self.file_adapter:
                self.file_adapter.write_text(west_yml_path, west_yml_content)
            else:
                west_yml_path.write_text(west_yml_content)

            self.logger.debug("Keyboard workspace configured successfully")
            return True

        except Exception as e:
            self.logger.error("Failed to configure keyboard workspace: %s", e)
            return False

    def _create_keyboard_build_yaml(self, shield_name: str, board_name: str) -> str:
        """Create build.yaml content for keyboard configuration.

        Args:
            shield_name: Shield name for builds
            board_name: Board name for builds

        Returns:
            str: build.yaml content
        """
        # Detect if this is a split keyboard by shield name patterns
        is_split = any(
            indicator in shield_name.lower()
            for indicator in ["corne", "crkbd", "lily58", "sofle", "kyria", "glove80"]
        )

        if is_split:
            if "glove80" in shield_name.lower():
                # Glove80 uses board array format
                return f"""# ZMK Build Configuration - Generated by Glovebox Cache
board: [ "{shield_name}_lh", "{shield_name}_rh" ]
"""
            else:
                # Standard split keyboards use include format with shields
                return f"""# ZMK Build Configuration - Generated by Glovebox Cache
include:
  - board: {board_name}
    shield: {shield_name}_left
  - board: {board_name}
    shield: {shield_name}_right
"""
        else:
            # Single keyboard build target
            return f"""# ZMK Build Configuration - Generated by Glovebox Cache
include:
  - board: {board_name}
    shield: {shield_name}
"""

    def _create_keyboard_west_yml(self, keyboard_profile: "KeyboardProfile") -> str:
        """Create west.yml for keyboard-specific configuration.

        Args:
            keyboard_profile: Keyboard profile to determine ZMK repository

        Returns:
            str: west.yml content
        """
        # Use the same logic as the content generator
        if keyboard_profile.firmware_config is not None:
            build_options = keyboard_profile.firmware_config.build_options
            repository_url = build_options.repository
            branch = build_options.branch

            if repository_url.startswith("https://github.com/"):
                repo_path = repository_url.replace("https://github.com/", "")
                org_name, repo_name = repo_path.split("/")
            elif "/" in repository_url:
                org_name, repo_name = repository_url.split("/")
            else:
                org_name = "zmkfirmware"
                repo_name = "zmk"

            return f"""# West configuration for ZMK - Generated by Glovebox Cache
manifest:
  defaults:
    remote: {org_name}
  remotes:
    - name: {org_name}
      url-base: https://github.com/{org_name}
  projects:
    - name: {repo_name}
      remote: {org_name}
      revision: {branch}
      import: app/west.yml
  self:
    path: config
"""
        elif "glove80" in keyboard_profile.keyboard_name.lower():
            return """# West configuration for ZMK - Generated by Glovebox Cache
manifest:
  remotes:
    - name: moergo-sc
      url-base: https://github.com/moergo-sc
  projects:
    - name: zmk
      remote: moergo-sc
      revision: main
      import: app/west.yml
  self:
    path: config
"""
        else:
            return """# West configuration for ZMK - Generated by Glovebox Cache
manifest:
  defaults:
    remote: zmkfirmware
  remotes:
    - name: zmkfirmware
      url-base: https://github.com/zmkfirmware
  projects:
    - name: zmk
      remote: zmkfirmware
      revision: main
      import: app/west.yml
  self:
    path: config
"""

    def _create_keyboard_cache_metadata(
        self,
        cache_path: Path,
        base_cache_key: str,
        keyboard_profile: "KeyboardProfile",
        shield_name: str | None = None,
        board_name: str = "nice_nano_v2",
    ) -> None:
        """Create keyboard cache metadata for tracking and validation.

        Args:
            cache_path: Path to cache directory
            base_cache_key: Base dependencies cache key
            keyboard_profile: Keyboard profile configuration
            shield_name: Shield name for the keyboard
            board_name: Board name for builds
        """
        import json
        from datetime import datetime

        metadata = {
            "created_at": datetime.now().isoformat(),
            "base_cache_key": base_cache_key,
            "keyboard_name": keyboard_profile.keyboard_name,
            "shield_name": shield_name,
            "board_name": board_name,
            "cache_version": "1.0",
            "glovebox_version": "1.0.0",
        }

        # Add firmware configuration if available
        if keyboard_profile.firmware_config:
            build_options = keyboard_profile.firmware_config.build_options
            metadata.update(
                {
                    "zmk_repo": build_options.repository,
                    "zmk_branch": build_options.branch,
                }
            )

        metadata_path = cache_path / ".glovebox_keyboard_cache_metadata.json"
        metadata_content = json.dumps(metadata, indent=2)

        if self.file_adapter:
            self.file_adapter.write_text(metadata_path, metadata_content)
        else:
            metadata_path.write_text(metadata_content)


def create_keyboard_config_cache(
    base_cache: BaseDependenciesCache,
    cache_root: Path | None = None,
    file_adapter: FileAdapter | None = None,
) -> KeyboardConfigCache:
    """Create keyboard configuration cache instance.

    Args:
        base_cache: Base dependencies cache instance
        cache_root: Root directory for cache storage
        file_adapter: File operations adapter

    Returns:
        KeyboardConfigCache: New cache instance
    """
    return KeyboardConfigCache(
        base_cache=base_cache,
        cache_root=cache_root,
        file_adapter=file_adapter,
    )
