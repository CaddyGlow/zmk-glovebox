"""Cache configuration models for comprehensive TTL management."""

from enum import Enum
from pathlib import Path
from typing import Annotated

from pydantic import Field

from glovebox.models.base import GloveboxBaseModel


class CacheLevel(str, Enum):
    """Standardized cache levels with consistent naming across domains."""

    BASE = "base"
    BRANCH = "branch"
    FULL = "full"
    BUILD = "build"
    LAYOUT = "layout"
    FIRMWARE = "firmware"
    MOERGO = "moergo"
    CORE = "core"

    # New simplified workspace cache levels
    REPO = "repo"  # Repository-only cache (includes .git for branch fetching)
    REPO_BRANCH = "repo_branch"  # Repository + branch cache (excludes .git)


class CacheTTLConfig(GloveboxBaseModel):
    """Comprehensive TTL configuration covering all cache types across domains.

    Provides centralized control over cache expiration times for all caching
    operations in Glovebox, from workspace compilation to layout management.
    """

    # Workspace cache TTLs (compilation domain)
    workspace_base: Annotated[
        int,
        Field(
            default=30 * 24 * 3600,  # 30 days in seconds
            description="TTL for base workspace cache (repository clone)",
        ),
    ]

    workspace_branch: Annotated[
        int,
        Field(
            default=24 * 3600,  # 1 day in seconds
            description="TTL for branch-specific workspace cache",
        ),
    ]

    workspace_full: Annotated[
        int,
        Field(
            default=12 * 3600,  # 12 hours in seconds
            description="TTL for full workspace cache (with dependencies)",
        ),
    ]

    workspace_build: Annotated[
        int,
        Field(
            default=3600,  # 1 hour in seconds
            description="TTL for build-specific workspace cache",
        ),
    ]

    # Layout domain cache TTLs
    layout_processing: Annotated[
        int,
        Field(
            default=7 * 24 * 3600,  # 7 days in seconds
            description="TTL for processed layout data and validation results",
        ),
    ]

    layout_comparison: Annotated[
        int,
        Field(
            default=3 * 24 * 3600,  # 3 days in seconds
            description="TTL for layout comparison and diff results",
        ),
    ]

    layout_bookmarks: Annotated[
        int,
        Field(
            default=30 * 24 * 3600,  # 30 days in seconds
            description="TTL for layout bookmark data and metadata",
        ),
    ]

    # Firmware domain cache TTLs
    firmware_build: Annotated[
        int,
        Field(
            default=7 * 24 * 3600,  # 7 days in seconds
            description="TTL for compiled firmware binaries and build artifacts",
        ),
    ]

    firmware_metadata: Annotated[
        int,
        Field(
            default=24 * 3600,  # 1 day in seconds
            description="TTL for firmware version info and build metadata",
        ),
    ]

    # MoErgo domain cache TTLs
    moergo_auth: Annotated[
        int,
        Field(
            default=24 * 3600,  # 1 day in seconds
            description="TTL for MoErgo authentication tokens and credentials",
        ),
    ]

    moergo_layouts: Annotated[
        int,
        Field(
            default=6 * 3600,  # 6 hours in seconds
            description="TTL for MoErgo layout downloads and API responses",
        ),
    ]

    moergo_versions: Annotated[
        int,
        Field(
            default=12 * 3600,  # 12 hours in seconds
            description="TTL for MoErgo version information and updates",
        ),
    ]

    # Core infrastructure cache TTLs
    core_templates: Annotated[
        int,
        Field(
            default=7 * 24 * 3600,  # 7 days in seconds
            description="TTL for template rendering and generation results",
        ),
    ]

    core_validation: Annotated[
        int,
        Field(
            default=3 * 24 * 3600,  # 3 days in seconds
            description="TTL for validation results and schema checks",
        ),
    ]

    def get_ttl_for_level(self, cache_level: CacheLevel) -> int:
        """Get TTL value for a specific cache level.

        Args:
            cache_level: The cache level to get TTL for

        Returns:
            TTL value in seconds

        Raises:
            ValueError: If cache level is not supported
        """
        level_mapping = {
            CacheLevel.BASE: self.workspace_base,
            CacheLevel.BRANCH: self.workspace_branch,
            CacheLevel.FULL: self.workspace_full,
            CacheLevel.BUILD: self.workspace_build,
            CacheLevel.LAYOUT: self.layout_processing,
            CacheLevel.FIRMWARE: self.firmware_build,
            CacheLevel.MOERGO: self.moergo_layouts,
            CacheLevel.CORE: self.core_templates,
            # New simplified workspace cache levels
            CacheLevel.REPO: self.workspace_base,  # Map repo to base (same concept)
            CacheLevel.REPO_BRANCH: self.workspace_branch,  # Map repo_branch to branch
        }

        if cache_level not in level_mapping:
            raise ValueError(f"Unsupported cache level: {cache_level}")

        return level_mapping[cache_level]

    def get_workspace_ttls(self) -> dict[str, int]:
        """Get workspace-specific TTL values as a dictionary.

        Returns:
            Dictionary mapping workspace cache levels to TTL values
        """
        return {
            "base": self.workspace_base,
            "branch": self.workspace_branch,
            "full": self.workspace_full,
            "build": self.workspace_build,
            # New simplified workspace cache levels
            "repo": self.workspace_base,  # Map repo to base (same concept - repository clone)
            "repo_branch": self.workspace_branch,  # Map repo_branch to branch (same concept)
        }
