# Cache Architecture

This document provides comprehensive technical reference for Glovebox's shared cache coordination system, including architecture, implementation details, performance optimization, and usage patterns.

## Overview

Glovebox implements a sophisticated caching system with shared coordination that:
- **Eliminates cache duplication** across domains through shared instances
- **Provides domain isolation** using cache tags for namespace separation  
- **Ensures thread/process safety** with DiskCache SQLite backend
- **Supports intelligent cleanup** with TTL-based expiration and size limits
- **Enables performance monitoring** with comprehensive statistics
- **Maintains test safety** with automatic reset capabilities

## Architecture Components

### Cache Coordinator

The cache coordinator manages shared cache instances across the entire application.

```python
from glovebox.core.cache.cache_coordinator import (
    get_shared_cache_instance,
    reset_shared_cache_instances,
    get_cache_instance_count
)

# Shared cache coordination
def get_shared_cache_instance(
    cache_root: Path,
    tag: str | None = None,
    enabled: bool = True,
    max_size_gb: int = 2,
    timeout: int = 30,
) -> CacheManager:
    """Get shared cache instance, creating if needed.
    
    Args:
        cache_root: Root directory for cache storage
        tag: Cache tag for domain isolation (e.g., "compilation", "metrics")
        enabled: Enable cache operations
        max_size_gb: Maximum cache size in GB
        timeout: Operation timeout in seconds
        
    Returns:
        CacheManager: Shared cache instance for the specified tag
    """
```

**Key Principles:**
- **Same tag → same instance**: Multiple calls with identical tags return the same cache instance
- **Different tags → different instances**: Each tag gets its own isolated cache namespace
- **Global registry**: Single registry maintains all active cache instances
- **Automatic cleanup**: Instances are automatically cleaned up when no longer referenced

### Cache Manager Protocol

All cache implementations follow the `CacheManager` protocol:

```python
@runtime_checkable
class CacheManager(Protocol):
    """Generic cache manager interface."""
    
    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve value from cache."""
        ...
    
    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store value in cache."""
        ...
    
    def delete(self, key: str) -> bool:
        """Remove value from cache."""
        ...
    
    def delete_many(self, keys: list[str]) -> int:
        """Remove multiple values from cache."""
        ...
    
    def clear(self) -> None:
        """Clear all entries from cache."""
        ...
    
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        ...
    
    def get_metadata(self, key: str) -> CacheMetadata | None:
        """Get metadata for cache entry."""
        ...
    
    def get_stats(self) -> CacheStats:
        """Get cache performance statistics."""
        ...
    
    def cleanup(self) -> int:
        """Remove expired entries and enforce size limits."""
        ...
    
    def keys(self) -> list[str]:
        """Get all cache keys."""
        ...
    
    def close(self) -> None:
        """Close the cache and release resources."""
        ...
```

### DiskCache Manager

The primary cache implementation using DiskCache with SQLite backend:

```python
from glovebox.core.cache.diskcache_manager import DiskCacheManager

class DiskCacheManager:
    """DiskCache-based cache manager with SQLite backend."""
    
    def __init__(
        self,
        cache_dir: Path,
        max_size_gb: int = 2,
        timeout: int = 30,
        tag: str | None = None,
    ):
        """Initialize DiskCache manager.
        
        Args:
            cache_dir: Cache directory path
            max_size_gb: Maximum cache size in GB
            timeout: Operation timeout in seconds
            tag: Cache tag for identification
        """
        self.cache_dir = cache_dir
        self.max_size_bytes = max_size_gb * 1024 * 1024 * 1024
        self.timeout = timeout
        self.tag = tag or "default"
        
        # Create DiskCache instance with SQLite backend
        self._cache = diskcache.Cache(
            directory=str(cache_dir),
            size_limit=self.max_size_bytes,
            timeout=timeout,
            statistics=True,  # Enable statistics collection
        )
```

**Features:**
- **SQLite backend** for ACID compliance and concurrent access
- **Size limits** with automatic eviction of least-recently-used entries
- **TTL support** for automatic expiration
- **Statistics collection** for performance monitoring
- **Thread safety** through SQLite's locking mechanisms
- **Process safety** for multi-process environments

### Factory Functions

Cache instances are created through factory functions following CLAUDE.md patterns:

```python
from glovebox.core.cache import (
    create_default_cache,
    create_cache_from_user_config,
    create_diskcache_manager
)

def create_default_cache(
    tag: str | None = None,
    enabled: bool = True,
    max_size_gb: int = 2,
    timeout: int = 30,
) -> CacheManager:
    """Create default cache instance with shared coordination.
    
    This function uses shared coordination to ensure the same tag
    returns the same cache instance across all domains.
    """
    user_config = create_user_config()
    cache_root = Path(user_config.cache_dir).expanduser()
    
    return get_shared_cache_instance(
        cache_root=cache_root,
        tag=tag,
        enabled=enabled,
        max_size_gb=max_size_gb,
        timeout=timeout,
    )

def create_cache_from_user_config(
    user_config: UserConfig,
    tag: str | None = None,
) -> CacheManager:
    """Create cache instance from user configuration."""
    cache_root = Path(user_config.cache_dir).expanduser()
    
    return get_shared_cache_instance(
        cache_root=cache_root,
        tag=tag,
        enabled=user_config.cache_strategy != "disabled",
        max_size_gb=2,  # Default size
        timeout=30,
    )
```

## Domain-Specific Cache Integration

### Compilation Domain

```python
from glovebox.compilation.cache import create_compilation_cache_service

def create_compilation_cache_service(
    user_config: UserConfig,
) -> tuple[CacheManager, ZmkWorkspaceCacheService]:
    """Create compilation cache service with shared coordination.
    
    Returns:
        Tuple of (cache_manager, workspace_service) both using shared cache
    """
    # Get shared cache instance for compilation domain
    cache_manager = create_cache_from_user_config(user_config, tag="compilation")
    
    # Create workspace cache service using shared cache
    workspace_service = ZmkWorkspaceCacheService(cache_manager)
    
    return cache_manager, workspace_service
```

**Usage in compilation services:**
```python
class ZmkWestService:
    def __init__(self, user_config: UserConfig):
        self.cache_manager, self.workspace_service = create_compilation_cache_service(user_config)
    
    def compile(self, keymap_file: Path, config_file: Path, ...) -> BuildResult:
        # Use cache for build artifacts
        cache_key = f"build:{keymap_hash}:{config_hash}"
        cached_result = self.cache_manager.get(cache_key)
        
        if cached_result and self._is_cache_valid(cached_result):
            return cached_result
        
        # Execute compilation
        result = self._execute_build(...)
        
        # Cache result with TTL
        self.cache_manager.set(cache_key, result, ttl=86400)  # 24 hours
        
        return result
```

### Layout Domain

```python
# Layout domain uses separate cache namespace
layout_cache = create_default_cache(tag="layout")

class LayoutService:
    def __init__(self):
        self.cache = create_default_cache(tag="layout")
    
    def compile(self, input_file: Path, ...) -> LayoutResult:
        # Cache parsed layouts
        layout_hash = self._compute_layout_hash(input_file)
        cache_key = f"parsed_layout:{layout_hash}"
        
        cached_layout = self.cache.get(cache_key)
        if cached_layout:
            return self._process_cached_layout(cached_layout)
        
        # Parse and cache layout
        layout = self._parse_layout(input_file)
        self.cache.set(cache_key, layout, ttl=3600)  # 1 hour
        
        return self._process_layout(layout)
```

### Metrics Domain

```python
# Metrics domain uses separate cache namespace
metrics_cache = create_default_cache(tag="metrics")

class SessionMetrics:
    def __init__(self):
        self.cache = create_default_cache(tag="metrics")
    
    def store_session(self, session_id: str, metrics: dict[str, Any]) -> None:
        """Store session metrics with automatic cleanup."""
        cache_key = f"session:{session_id}"
        self.cache.set(cache_key, metrics, ttl=7 * 86400)  # 7 days
    
    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve session metrics."""
        cache_key = f"session:{session_id}"
        return self.cache.get(cache_key)
```

## Cache Coordination Benefits

### Memory Efficiency

**Before (independent caches):**
```python
# Each domain creates its own cache instance
compilation_cache = create_diskcache_manager(cache_dir, tag="compilation")
layout_cache = create_diskcache_manager(cache_dir, tag="layout")  
metrics_cache = create_diskcache_manager(cache_dir, tag="metrics")

# Results in multiple DiskCache instances, separate SQLite connections
# Memory overhead: 3x cache managers + 3x SQLite connections
```

**After (shared coordination):**
```python
# Same tag returns same instance
cache1 = create_default_cache(tag="compilation")
cache2 = create_default_cache(tag="compilation")  # Same instance as cache1
cache3 = create_default_cache(tag="layout")       # Different instance

assert cache1 is cache2  # True - shared instance
assert cache1 is not cache3  # True - different namespace
```

### Domain Isolation

Each domain gets its own isolated cache namespace:

```python
# Compilation domain
compilation_cache = create_default_cache(tag="compilation")
compilation_cache.set("workspace:abc123", workspace_data)

# Layout domain  
layout_cache = create_default_cache(tag="layout")
layout_cache.set("workspace:abc123", layout_data)  # Different namespace

# No collision - each domain has isolated keys
assert compilation_cache.get("workspace:abc123") != layout_cache.get("workspace:abc123")
```

### Performance Optimization

**Cache hit rates by domain:**
```python
def get_cache_performance_report() -> dict[str, CacheStats]:
    """Get performance report for all active cache instances."""
    report = {}
    
    for tag in get_cache_instance_keys():
        cache = create_default_cache(tag=tag)
        stats = cache.get_stats()
        report[tag] = stats
    
    return report

# Example output:
{
    "compilation": CacheStats(hits=150, misses=25, hit_rate=0.857),
    "layout": CacheStats(hits=89, misses=11, hit_rate=0.890),
    "metrics": CacheStats(hits=45, misses=5, hit_rate=0.900)
}
```

## Cache Models and Statistics

### CacheStats

Performance statistics for cache operations:

```python
from glovebox.core.cache.models import CacheStats

class CacheStats(GloveboxBaseModel):
    """Cache performance statistics."""
    
    hits: int = 0
    misses: int = 0
    total_keys: int = 0
    size_bytes: int = 0
    hit_rate: float = 0.0
    
    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate."""
        total = self.hits + self.misses
        return self.misses / total if total > 0 else 0.0
    
    @property
    def size_mb(self) -> float:
        """Get cache size in megabytes."""
        return self.size_bytes / (1024 * 1024)
```

### CacheMetadata

Metadata for individual cache entries:

```python
from glovebox.core.cache.models import CacheMetadata

class CacheMetadata(GloveboxBaseModel):
    """Metadata for cache entries."""
    
    key: str
    size: int
    created: datetime
    accessed: datetime
    ttl: int | None = None
    tag: str | None = None
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        if self.ttl is None:
            return False
        return (datetime.now() - self.created).total_seconds() > self.ttl
    
    @property
    def age_seconds(self) -> float:
        """Get entry age in seconds."""
        return (datetime.now() - self.created).total_seconds()
```

### CacheKey

Structured cache key with namespace support:

```python
from glovebox.core.cache.models import CacheKey

class CacheKey(GloveboxBaseModel):
    """Structured cache key."""
    
    namespace: str
    category: str
    identifier: str
    version: str | None = None
    
    def to_string(self) -> str:
        """Convert to cache key string."""
        parts = [self.namespace, self.category, self.identifier]
        if self.version:
            parts.append(self.version)
        return ":".join(parts)
    
    @classmethod
    def from_string(cls, key: str) -> "CacheKey":
        """Parse cache key from string."""
        parts = key.split(":")
        if len(parts) < 3:
            raise ValueError(f"Invalid cache key format: {key}")
        
        return cls(
            namespace=parts[0],
            category=parts[1], 
            identifier=parts[2],
            version=parts[3] if len(parts) > 3 else None
        )

# Usage
key = CacheKey(
    namespace="compilation",
    category="workspace", 
    identifier="zmk-main-abc123",
    version="v1"
)
cache.set(key.to_string(), workspace_data)
```

## Performance Considerations

### Cache Key Design

**Effective cache key patterns:**
```python
# Good: Hierarchical with version
"compilation:workspace:zmk-main:abc123:v1"

# Good: Content-based hash
"layout:parsed:sha256:def456"

# Good: Time-based with granularity
"metrics:session:2024-01:user123"

# Bad: Too generic (high collision risk)
"data"

# Bad: Too specific (low reuse)
"compilation:workspace:zmk-main:abc123:v1:timestamp-1672531200"
```

### TTL Strategy

**TTL recommendations by content type:**
```python
# Build artifacts (expensive to regenerate)
compilation_cache.set(key, result, ttl=86400)  # 24 hours

# Parsed layouts (moderate cost)
layout_cache.set(key, layout, ttl=3600)  # 1 hour

# Temporary session data
session_cache.set(key, data, ttl=300)  # 5 minutes

# Master layouts (rarely change)
master_cache.set(key, master, ttl=7*86400)  # 7 days

# User preferences (change rarely)
config_cache.set(key, config, ttl=3600)  # 1 hour
```

### Size Management

**Automatic size management:**
```python
class DiskCacheManager:
    def _enforce_size_limits(self) -> int:
        """Enforce cache size limits with LRU eviction."""
        if self._cache.volume() > self.max_size_bytes:
            # DiskCache automatically evicts LRU entries
            return self._cache.cull()
        return 0
    
    def cleanup(self) -> int:
        """Remove expired entries and enforce size limits."""
        expired_count = 0
        
        # Remove expired entries
        for key in self.keys():
            metadata = self.get_metadata(key)
            if metadata and metadata.is_expired:
                self.delete(key)
                expired_count += 1
        
        # Enforce size limits
        evicted_count = self._enforce_size_limits()
        
        return expired_count + evicted_count
```

### Concurrent Access

**Thread-safe operations:**
```python
import threading
from concurrent.futures import ThreadPoolExecutor

def concurrent_cache_access():
    """Demonstrate thread-safe cache operations."""
    cache = create_default_cache(tag="test")
    
    def worker(worker_id: int):
        # Each thread can safely access the cache
        for i in range(100):
            key = f"worker_{worker_id}_item_{i}"
            cache.set(key, {"worker": worker_id, "item": i})
            
            # Retrieve and verify
            data = cache.get(key)
            assert data["worker"] == worker_id
    
    # Multiple threads accessing same cache instance
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(worker, i) for i in range(4)]
        for future in futures:
            future.result()
```

## Cache Warming and Preloading

### Strategic Cache Warming

```python
class CacheWarmer:
    """Strategic cache warming for common operations."""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache = cache_manager
    
    def warm_compilation_cache(self, profiles: list[KeyboardProfile]) -> None:
        """Pre-warm compilation cache with common builds."""
        for profile in profiles:
            # Pre-cache workspace setups
            workspace_key = f"workspace:{profile.keyboard_name}:{profile.firmware_version}"
            if not self.cache.exists(workspace_key):
                workspace = self._setup_workspace(profile)
                self.cache.set(workspace_key, workspace, ttl=86400)
            
            # Pre-cache common build configurations
            config_key = f"build_config:{profile.keyboard_name}:{profile.firmware_version}"
            if not self.cache.exists(config_key):
                config = self._generate_build_config(profile)
                self.cache.set(config_key, config, ttl=3600)
    
    def warm_layout_cache(self, layout_files: list[Path]) -> None:
        """Pre-warm layout cache with parsed layouts."""
        for layout_file in layout_files:
            layout_hash = self._compute_file_hash(layout_file)
            cache_key = f"parsed_layout:{layout_hash}"
            
            if not self.cache.exists(cache_key):
                layout = self._parse_layout(layout_file)
                self.cache.set(cache_key, layout, ttl=3600)
```

## Test Safety and Cleanup

### Automatic Test Isolation

```python
# Automatic cache reset fixture
@pytest.fixture(autouse=True)
def reset_shared_cache() -> Generator[None, None, None]:
    """Reset shared cache instances before and after each test."""
    reset_shared_cache_instances()  # Before test
    yield
    reset_shared_cache_instances()  # After test

def reset_shared_cache_instances() -> None:
    """Reset all shared cache instances for test isolation."""
    global _shared_cache_instances
    
    # Close all existing cache instances
    for cache_manager in _shared_cache_instances.values():
        try:
            cache_manager.close()
        except Exception:
            pass  # Ignore cleanup errors
    
    # Clear the registry
    _shared_cache_instances.clear()
```

### Cache Testing Utilities

```python
def test_cache_coordination():
    """Test cache coordination behavior."""
    # Same tag returns same instance
    cache1 = create_default_cache(tag="test")
    cache2 = create_default_cache(tag="test")
    assert cache1 is cache2
    
    # Different tag returns different instance
    cache3 = create_default_cache(tag="other")
    assert cache1 is not cache3
    
    # Test isolation
    cache1.set("key", "value1")
    cache3.set("key", "value2")
    
    assert cache1.get("key") == "value1"
    assert cache3.get("key") == "value2"

def test_cache_cleanup():
    """Test cache cleanup operations."""
    cache = create_default_cache(tag="cleanup_test")
    
    # Add entries with different TTLs
    cache.set("short", "data1", ttl=1)
    cache.set("long", "data2", ttl=3600)
    cache.set("permanent", "data3")  # No TTL
    
    # Wait for short TTL to expire
    time.sleep(2)
    
    # Cleanup should remove expired entries
    removed_count = cache.cleanup()
    assert removed_count >= 1
    
    # Verify cleanup results
    assert not cache.exists("short")
    assert cache.exists("long")
    assert cache.exists("permanent")
```

## Monitoring and Debugging

### Cache Statistics Monitoring

```python
def monitor_cache_performance() -> None:
    """Monitor cache performance across all domains."""
    stats_by_domain = {}
    
    for tag in get_cache_instance_keys():
        cache = create_default_cache(tag=tag)
        stats = cache.get_stats()
        stats_by_domain[tag] = stats
        
        # Log performance metrics
        logger.info(
            "Cache performance for %s: hit_rate=%.3f, size_mb=%.1f, total_keys=%d",
            tag, stats.hit_rate, stats.size_mb, stats.total_keys
        )
        
        # Alert on poor performance
        if stats.hit_rate < 0.5 and stats.total_keys > 10:
            logger.warning("Low cache hit rate for domain %s: %.3f", tag, stats.hit_rate)
```

### Debug Information

```python
def get_cache_debug_info() -> dict[str, Any]:
    """Get comprehensive cache debug information."""
    debug_info = {
        "instance_count": get_cache_instance_count(),
        "active_tags": get_cache_instance_keys(),
        "memory_usage": {},
        "statistics": {}
    }
    
    for tag in get_cache_instance_keys():
        cache = create_default_cache(tag=tag)
        stats = cache.get_stats()
        
        debug_info["statistics"][tag] = {
            "hits": stats.hits,
            "misses": stats.misses,
            "hit_rate": stats.hit_rate,
            "total_keys": stats.total_keys,
            "size_bytes": stats.size_bytes
        }
    
    return debug_info
```

This comprehensive cache architecture provides efficient, thread-safe caching with domain isolation while maintaining simplicity through the shared coordination pattern. The system automatically handles cleanup, provides detailed performance monitoring, and ensures test safety through automatic reset capabilities.