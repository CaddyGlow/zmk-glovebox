"""Cache models for compilation domain with rich metadata support."""

import hashlib
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field

from glovebox.config.models.cache import CacheLevel
from glovebox.models.base import GloveboxBaseModel


class ArchiveFormat(str, Enum):
    """Supported archive formats for workspace export."""

    ZIP = "zip"
    TAR = "tar"
    TAR_GZ = "tar.gz"
    TAR_BZ2 = "tar.bz2"
    TAR_XZ = "tar.xz"

    @property
    def file_extension(self) -> str:
        """Get the file extension for this archive format."""
        return f".{self.value}"

    @property
    def uses_compression(self) -> bool:
        """Check if this format uses compression."""
        return self in {self.ZIP, self.TAR_GZ, self.TAR_BZ2, self.TAR_XZ}

    @property
    def default_compression_level(self) -> int:
        """Get the default compression level for this format."""
        if self == self.ZIP:
            return 6  # zipfile default
        return 6  # reasonable default for tar formats

    @property
    def max_compression_level(self) -> int:
        """Get the maximum compression level for this format."""
        if self == self.ZIP:
            return 9
        if self == self.TAR_BZ2:
            return 9
        if self == self.TAR_XZ:
            return 9
        return 9  # general max


class WorkspaceCacheResult(GloveboxBaseModel):
    """Result of workspace cache operations."""

    success: bool
    workspace_path: Path | None = None
    metadata: "WorkspaceCacheMetadata | None" = None
    error_message: str | None = None
    created_new: bool = False


class WorkspaceExportResult(GloveboxBaseModel):
    """Result of workspace export operations."""

    success: bool
    export_path: Annotated[
        Path | None,
        Field(default=None, description="Path to the exported archive file"),
    ]
    metadata: Annotated[
        "WorkspaceCacheMetadata | None",
        Field(default=None, description="Metadata of the exported workspace"),
    ]
    archive_format: Annotated[
        ArchiveFormat | None,
        Field(default=None, description="Format of the created archive"),
    ]
    archive_size_bytes: Annotated[
        int | None,
        Field(default=None, description="Size of the created archive in bytes"),
    ]
    original_size_bytes: Annotated[
        int | None, Field(default=None, description="Original workspace size in bytes")
    ]
    compression_ratio: Annotated[
        float | None,
        Field(
            default=None,
            description="Compression ratio (compressed_size / original_size)",
        ),
    ]
    export_duration_seconds: Annotated[
        float | None,
        Field(
            default=None, description="Time taken to export the workspace in seconds"
        ),
    ]
    files_count: Annotated[
        int | None,
        Field(default=None, description="Number of files included in the export"),
    ]
    error_message: Annotated[
        str | None, Field(default=None, description="Error message if export failed")
    ]

    @property
    def compression_percentage(self) -> float | None:
        """Get compression percentage (0-100)."""
        if self.compression_ratio is None:
            return None
        return (1 - self.compression_ratio) * 100

    @property
    def export_speed_mb_s(self) -> float | None:
        """Get export speed in MB/s."""
        if (
            self.original_size_bytes is None
            or self.export_duration_seconds is None
            or self.export_duration_seconds <= 0
        ):
            return None
        return (self.original_size_bytes / (1024 * 1024)) / self.export_duration_seconds


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
        str | None,
        Field(
            default=None,
            description="Git branch name for the cached workspace (None for repo-only cache)",
        ),
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

    # Enhanced workspace creation metadata
    creation_method: Annotated[
        str,
        Field(
            default="compilation",
            description="How workspace was created: 'direct', 'compilation', 'import', etc.",
        ),
    ]

    docker_image: Annotated[
        str | None,
        Field(
            default=None,
            description="Docker image used for workspace creation (e.g., 'zmkfirmware/zmk-dev-arm:stable')",
        ),
    ]

    west_manifest_path: Annotated[
        str | None,
        Field(
            default=None,
            description="Path to west manifest file relative to workspace root",
        ),
    ]

    dependencies_updated: Annotated[
        datetime | None,
        Field(
            default=None,
            description="Timestamp when dependencies were last updated (west update)",
        ),
    ]

    creation_profile: Annotated[
        str | None,
        Field(
            default=None,
            description="Keyboard/firmware profile used during workspace creation",
        ),
    ]

    git_remotes: Annotated[
        dict[str, str],
        Field(
            default_factory=dict,
            description="Git remote URLs for tracked repositories (name -> URL mapping)",
        ),
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
        components = {
            "repository": self.repository,
            "cache_level": cache_level_value,
        }
        if self.branch is not None:
            components["branch"] = self.branch
        return components

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

    def update_dependencies_timestamp(self) -> None:
        """Update the dependencies updated timestamp to current time."""
        self.dependencies_updated = datetime.now()

    def add_git_remote(self, name: str, url: str) -> None:
        """Add or update a git remote.

        Args:
            name: Remote name (e.g., 'origin', 'upstream')
            url: Remote URL
        """
        self.git_remotes[name] = url

    def get_git_remote(self, name: str) -> str | None:
        """Get a git remote URL by name.

        Args:
            name: Remote name to lookup

        Returns:
            Remote URL if found, None otherwise
        """
        return self.git_remotes.get(name)

    def set_creation_context(
        self,
        method: str,
        docker_image: str | None = None,
        profile: str | None = None,
        west_manifest: str | None = None,
    ) -> None:
        """Set workspace creation context information.

        Args:
            method: Creation method ('direct', 'compilation', 'import', etc.)
            docker_image: Docker image used for creation
            profile: Keyboard/firmware profile used
            west_manifest: Path to west manifest file
        """
        self.creation_method = method
        if docker_image is not None:
            self.docker_image = docker_image
        if profile is not None:
            self.creation_profile = profile
        if west_manifest is not None:
            self.west_manifest_path = west_manifest

    @property
    def is_direct_creation(self) -> bool:
        """Check if workspace was created directly (not via compilation)."""
        return self.creation_method == "direct"

    @property
    def dependencies_age_hours(self) -> float | None:
        """Age of dependencies in hours since last update."""
        if self.dependencies_updated is None:
            return None
        delta = datetime.now() - self.dependencies_updated
        return delta.total_seconds() / 3600

    @property
    def are_dependencies_stale(self) -> bool:
        """Check if dependencies might be stale (older than 3 days)."""
        age = self.dependencies_age_hours
        return age is not None and age > (3 * 24)
