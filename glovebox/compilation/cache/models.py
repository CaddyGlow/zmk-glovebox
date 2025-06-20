"""Cache models for compilation domain with rich metadata support."""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field

from glovebox.config.models.cache import CacheLevel
from glovebox.models.base import GloveboxBaseModel


class WorkspaceCacheMetadata(GloveboxBaseModel):
    """Rich metadata for workspace cache entries replacing simple path strings.

    Provides comprehensive information about cached workspaces including
    git repository details, file hashes, creation timestamps, and cache levels.
    """

    # Core workspace information
    workspace_path: Annotated[
        Path, Field(description="Absolute path to the cached workspace directory")
    ]

    # Git repository information
    repository: Annotated[
        str, Field(description="Git repository name (e.g., 'zmkfirmware/zmk')")
    ]

    branch: Annotated[
        str, Field(description="Git branch name for the cached workspace")
    ]

    commit_hash: Annotated[
        str | None,
        Field(default=None, description="Git commit hash if available during caching"),
    ]

    # Cache metadata
    cache_level: Annotated[
        CacheLevel,
        Field(description="Cache level indicating the completeness of cached data"),
    ]

    created_at: Annotated[
        datetime,
        Field(
            default_factory=datetime.now,
            description="Timestamp when the cache entry was created",
        ),
    ]

    last_accessed: Annotated[
        datetime,
        Field(
            default_factory=datetime.now,
            description="Timestamp when the cache entry was last accessed",
        ),
    ]

    # File integrity information
    keymap_hash: Annotated[
        str | None,
        Field(
            default=None,
            description="SHA256 hash of the keymap file used for this cache",
        ),
    ]

    config_hash: Annotated[
        str | None,
        Field(
            default=None,
            description="SHA256 hash of the config file used for this cache",
        ),
    ]

    # Auto-detection flags
    auto_detected: Annotated[
        bool,
        Field(
            default=False,
            description="Whether this workspace was auto-detected from existing directory",
        ),
    ]

    auto_detected_source: Annotated[
        str | None,
        Field(
            default=None,
            description="Source path if workspace was auto-detected (e.g., CLI add command)",
        ),
    ]

    # Build information
    build_id: Annotated[
        str | None,
        Field(
            default=None,
            description="Unique build identifier if this cache is associated with a build",
        ),
    ]

    build_profile: Annotated[
        str | None,
        Field(
            default=None, description="Keyboard/firmware profile used for this cache"
        ),
    ]

    # Workspace components
    cached_components: Annotated[
        list[str],
        Field(
            default_factory=list,
            description="List of workspace components that are cached (zmk, zephyr, modules)",
        ),
    ]

    # Additional metadata
    size_bytes: Annotated[
        int | None,
        Field(default=None, description="Total size of cached workspace in bytes"),
    ]

    notes: Annotated[
        str | None,
        Field(default=None, description="Optional notes about this cache entry"),
    ]

    @property
    def cache_key_components(self) -> dict[str, str]:
        """Components used to generate the cache key for this metadata."""
        # Handle both enum and string cache levels for backward compatibility
        cache_level_value = (
            self.cache_level.value
            if hasattr(self.cache_level, "value")
            else str(self.cache_level)
        )
        return {
            "repository": self.repository,
            "branch": self.branch,
            "cache_level": cache_level_value,
        }

    @property
    def age_hours(self) -> float:
        """Age of the cache entry in hours."""
        delta = datetime.now() - self.created_at
        return delta.total_seconds() / 3600

    @property
    def is_stale(self) -> bool:
        """Whether the cache entry might be considered stale (older than 7 days)."""
        return self.age_hours > (7 * 24)

    def update_access_time(self) -> None:
        """Update the last accessed timestamp to current time."""
        self.last_accessed = datetime.now()

    def calculate_file_hash(self, file_path: Path) -> str | None:
        """Calculate SHA256 hash of a file.

        Args:
            file_path: Path to the file to hash

        Returns:
            SHA256 hash string, or None if file doesn't exist or can't be read
        """
        try:
            if not file_path.exists() or not file_path.is_file():
                return None

            sha256_hash = hashlib.sha256()
            with file_path.open("rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception:
            return None

    def update_file_hashes(
        self, keymap_path: Path | None = None, config_path: Path | None = None
    ) -> None:
        """Update file hashes for keymap and config files.

        Args:
            keymap_path: Path to keymap file to hash
            config_path: Path to config file to hash
        """
        if keymap_path:
            self.keymap_hash = self.calculate_file_hash(keymap_path)
        if config_path:
            self.config_hash = self.calculate_file_hash(config_path)

    def add_cached_component(self, component: str) -> None:
        """Add a component to the list of cached components.

        Args:
            component: Name of the component (e.g., 'zmk', 'zephyr', 'modules')
        """
        if component not in self.cached_components:
            self.cached_components.append(component)

    def has_component(self, component: str) -> bool:
        """Check if a specific component is cached.

        Args:
            component: Name of the component to check

        Returns:
            True if the component is cached
        """
        return component in self.cached_components

    def to_cache_value(self) -> dict[str, Any]:
        """Convert metadata to a dictionary suitable for cache storage.

        Returns:
            Dictionary representation using model_dump with proper serialization
        """
        return self.model_dump(mode="json", by_alias=True, exclude_unset=True)

    @classmethod
    def from_cache_value(cls, data: dict[str, Any]) -> "WorkspaceCacheMetadata":
        """Create metadata instance from cached dictionary data.

        Args:
            data: Dictionary data from cache

        Returns:
            WorkspaceCacheMetadata instance
        """
        return cls.model_validate(data)

    def create_auto_detection_info(
        self, source_path: Path, detected_repo: str, detected_branch: str
    ) -> None:
        """Mark this metadata as auto-detected and store detection info.

        Args:
            source_path: Original path where workspace was detected
            detected_repo: Auto-detected repository name
            detected_branch: Auto-detected branch name
        """
        self.auto_detected = True
        self.auto_detected_source = str(source_path)
        self.repository = detected_repo
        self.branch = detected_branch
        self.notes = f"Auto-detected from {source_path}"
