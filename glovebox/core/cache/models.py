"""Data models for DiskCache-based cache system."""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class DiskCacheConfig:
    """Configuration for DiskCache manager.

    Args:
        cache_path: Directory for cache storage
        max_size_bytes: Maximum cache size in bytes (default: 2GB)
        timeout: Operation timeout in seconds (default: 30)
        eviction_policy: Eviction policy, always 'least-recently-stored' for DiskCache
    """

    cache_path: Path | str
    max_size_bytes: int = 2 * 1024 * 1024 * 1024  # 2GB default
    timeout: int = 30
    eviction_policy: str = "least-recently-stored"  # DiskCache default

    def __post_init__(self) -> None:
        """Ensure cache_path is a Path object."""
        if isinstance(self.cache_path, str):
            object.__setattr__(self, "cache_path", Path(self.cache_path))


@dataclass
class CacheStats:
    """Cache performance statistics compatible with old cache interface."""

    total_entries: int
    total_size_bytes: int
    hit_count: int
    miss_count: int
    eviction_count: int
    error_count: int = 0
    # Metrics-specific fields
    operation_count: int = 0
    total_operation_time: float = 0.0
    tag: str | None = None

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate as percentage."""
        total_requests = self.hit_count + self.miss_count
        if total_requests == 0:
            return 0.0
        return (self.hit_count / total_requests) * 100.0

    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate as percentage."""
        return 100.0 - self.hit_rate

    @property
    def avg_operation_time(self) -> float:
        """Calculate average operation time in seconds."""
        if self.operation_count == 0:
            return 0.0
        return self.total_operation_time / self.operation_count

    def to_metrics_dict(self) -> dict[str, Any]:
        """Convert stats to metrics dictionary for SessionMetrics."""
        return {
            "total_entries": self.total_entries,
            "total_size_bytes": self.total_size_bytes,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "eviction_count": self.eviction_count,
            "error_count": self.error_count,
            "operation_count": self.operation_count,
            "total_operation_time": self.total_operation_time,
            "hit_rate": self.hit_rate,
            "miss_rate": self.miss_rate,
            "avg_operation_time": self.avg_operation_time,
            "tag": self.tag,
        }


@dataclass
class CacheMetadata:
    """Cache entry metadata compatible with old cache interface."""

    key: str
    size_bytes: int
    created_at: float
    last_accessed: float
    access_count: int
    ttl_seconds: int | None = None
    tags: list[str] | None = None

    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired based on TTL."""
        if self.ttl_seconds is None:
            return False
        return time.time() > (self.created_at + self.ttl_seconds)

    @property
    def age_seconds(self) -> float:
        """Get age of cache entry in seconds."""
        return time.time() - self.created_at

    def touch(self) -> None:
        """Update last accessed time and increment access count."""
        self.last_accessed = time.time()
        self.access_count += 1


class CacheKey:
    """Helper for generating consistent cache keys."""

    @staticmethod
    def from_parts(*parts: str) -> str:
        """Generate cache key from multiple string parts."""
        import hashlib

        # Join parts with separator and hash for consistent length
        combined = ":".join(str(part) for part in parts if part)
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    @staticmethod
    def from_dict(data: dict[str, Any]) -> str:
        """Generate cache key from dictionary data."""
        import json

        # Sort keys for consistency
        sorted_json = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return CacheKey.from_parts(sorted_json)

    @staticmethod
    def from_path(path: Path) -> str:
        """Generate cache key from file content hash.

        Args:
            path: Path to the file to hash

        Returns:
            Content-based hash of the file
        """
        import hashlib

        try:
            # Use actual file content hash for more reliable caching
            with path.open("rb") as f:
                file_hash = hashlib.sha256()
                # Read file in chunks to handle large files efficiently
                for chunk in iter(lambda: f.read(8192), b""):
                    file_hash.update(chunk)
                return file_hash.hexdigest()[:16]
        except OSError:
            # File doesn't exist or can't be accessed - use path as fallback
            return CacheKey.from_parts(str(path))
