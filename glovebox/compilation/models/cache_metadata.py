"""Cache metadata models for workspace and build caching."""

import time
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class CacheMetadata(BaseModel):
    """Metadata for workspace and build caches.

    Tracks cache validity, version information, and invalidation triggers
    for intelligent cache management.
    """

    workspace_path: str
    cached_at: str = Field(default_factory=lambda: str(int(time.time())))
    cache_version: str = "1.0"
    west_modules: list[str] = Field(default_factory=list)
    manifest_hash: str = "unknown"
    config_hash: str = "unknown"
    west_version: str = "unknown"


class WorkspaceCacheEntry(BaseModel):
    """Individual workspace cache entry.

    Represents a cached workspace with its metadata and validation status.
    """

    workspace_name: str
    workspace_path: Path
    metadata: CacheMetadata
    size_bytes: int = 0
    last_used: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class CacheValidationResult(BaseModel):
    """Result of cache validation check.

    Contains validation status and reasons for cache invalidation.
    """

    is_valid: bool
    reasons: list[str] = Field(default_factory=list)
    cache_age_hours: float = 0.0
    needs_refresh: bool = False


class CacheConfig(BaseModel):
    """Configuration for cache management.

    Controls cache behavior, retention policies, and cleanup strategies.
    """

    max_age_hours: float = 24.0
    max_cache_size_gb: float = 5.0
    cleanup_interval_hours: float = 6.0
    enable_compression: bool = True
    enable_smart_invalidation: bool = True
