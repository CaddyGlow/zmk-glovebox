"""Cache data models and types."""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CacheMetadata:
    """Metadata for cached entries."""

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


@dataclass
class CacheEntry:
    """Complete cache entry with data and metadata."""

    data: Any
    metadata: CacheMetadata

    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return self.metadata.is_expired

    def touch(self) -> None:
        """Update access metadata."""
        self.metadata.touch()


@dataclass
class CacheStats:
    """In memory cache performance statistics."""

    total_entries: int
    total_size_bytes: int
    hit_count: int
    miss_count: int
    eviction_count: int
    error_count: int

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


@dataclass
class CacheConfig:
    """Configuration for cache instances."""

    max_size_bytes: int | None = None
    max_entries: int | None = None
    default_ttl_seconds: int | None = None
    eviction_policy: str = "lru"  # "lru", "lfu", "fifo", "ttl"
    cleanup_interval_seconds: int = 300  # 5 minutes
    enable_statistics: bool = True
    cache_root: Path | None = None
    use_file_locking: bool = True
    cache_strategy: str = "disabled"


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
        """Generate cache key from file path and modification time."""
        try:
            stat = path.stat()
            return CacheKey.from_parts(str(path), str(stat.st_mtime), str(stat.st_size))
        except OSError:
            # File doesn't exist or can't be accessed
            return CacheKey.from_parts(str(path))
