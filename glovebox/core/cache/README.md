# Glovebox Cache System

A domain-agnostic caching infrastructure for the Glovebox project that provides persistent and in-memory caching capabilities with comprehensive configuration and monitoring.

## Architecture Overview

The cache system follows a clean, protocol-based architecture:

```
CacheManager (Protocol)
├── FilesystemCache (Persistent storage)
├── MemoryCache (In-memory storage)
└── BaseCacheManager (Common functionality)
```

### Key Components

- **CacheManager**: Protocol defining the cache interface
- **BaseCacheManager**: Abstract base class with common functionality
- **FilesystemCache**: File-based persistent cache with file locking
- **MemoryCache**: Fast in-memory cache for temporary data
- **CacheConfig**: Configuration model with validation
- **Factory Functions**: Simple creation patterns for different cache types

## Quick Start

### Basic Usage

```python
from glovebox.core.cache import create_default_cache

# Create a default filesystem cache
cache = create_default_cache()

# Store and retrieve data
cache.set("my_key", {"data": "example"}, ttl=3600)
data = cache.get("my_key")

# Check existence and metadata
if cache.exists("my_key"):
    metadata = cache.get_metadata("my_key")
    print(f"Cache entry size: {metadata.size_bytes} bytes")
```

### User Configuration Integration

```python
from glovebox.core.cache import create_cache_from_user_config
from glovebox.config.models.user import UserConfigData

# Use user configuration
config = UserConfigData(
    cache_strategy="shared",
    cache_file_locking=True
)
cache = create_cache_from_user_config(config)
```

## Cache Strategies

### Process Isolated 
- **Strategy**: `"process_isolated"`
- **Description**: Each process gets its own cache directory
- **Use Case**: Multi-process environments, development
- **Directory**: `/tmp/glovebox_cache/proc_{PID}`

### Shared Cache (Default)
- **Strategy**: `"shared"`  
- **Description**: All processes share the same cache directory
- **Use Case**: Production environments with coordination
- **Directory**: `/tmp/glovebox_cache`

### Disabled (Memory Fallback)
- **Strategy**: `"disabled"`
- **Description**: Uses in-memory cache instead of filesystem
- **Use Case**: Testing, constrained environments
- **Storage**: RAM only

## Factory Functions

### create_default_cache()

Creates a general-purpose cache with sensible defaults.

```python
def create_default_cache(
    cache_strategy: str = "process_isolated",
    cache_file_locking: bool = True,
) -> CacheManager
```

**Configuration:**
- 500MB max size
- 10,000 max entries  
- 24-hour default TTL
- LRU eviction policy

### create_filesystem_cache()

Creates a customized filesystem cache.

```python
def create_filesystem_cache(
    cache_root: Path | None = None,
    max_size_mb: int | None = None,
    max_entries: int | None = None,
    default_ttl_hours: int | None = None,
    use_file_locking: bool = True,
    cache_strategy: str = "process_isolated",
) -> CacheManager
```

### create_memory_cache()

Creates an in-memory cache for temporary storage.

```python
def create_memory_cache(
    max_size_mb: int | None = None,
    max_entries: int | None = None,
    default_ttl_hours: int | None = None,
) -> CacheManager
```

### create_cache_from_user_config()

Creates a cache using user configuration settings.

```python
def create_cache_from_user_config(user_config: Any) -> CacheManager
```

## Configuration Models

### CacheConfig

Core configuration for cache instances:

```python
@dataclass
class CacheConfig:
    max_size_bytes: int | None = None
    max_entries: int | None = None
    default_ttl_seconds: int | None = None
    eviction_policy: str = "lru"  # "lru", "lfu", "fifo", "ttl"
    cleanup_interval_seconds: int = 300  # 5 minutes
    enable_statistics: bool = True
    cache_root: Path | None = None
    use_file_locking: bool = True
    cache_strategy: str = "process_isolated"
```

### User Configuration Integration

Cache settings integrate with the user configuration system:

```python
class UserConfigData(BaseSettings):
    cache_strategy: str = Field(
        default="process_isolated",
        description="Cache strategy: 'process_isolated', 'shared', or 'disabled'",
    )
    cache_file_locking: bool = Field(
        default=True,
        description="Enable file locking for cache operations",
    )
```

## File Locking and Concurrency

The filesystem cache implements comprehensive file locking to prevent race conditions:

### Lock Types
- **Shared locks (LOCK_SH)**: For read operations
- **Exclusive locks (LOCK_EX)**: For write/delete operations
- **Non-blocking**: Uses LOCK_NB with timeout handling

### Locking Strategy
```python
with self._file_lock(key, "read"):    # Shared lock
    data = self._load_data(key)

with self._file_lock(key, "write"):   # Exclusive lock  
    self._save_data(key, value)

with self._file_lock(key, "delete"):  # Exclusive lock
    self._delete_data(key)
```

### Timeout Handling
- Default timeout: 5 seconds
- Graceful degradation on timeout
- Automatic lock cleanup on completion

## Persistent Statistics

The filesystem cache automatically persists statistics across application restarts and cache instances.

### How It Works

- **Automatic Loading**: Statistics are loaded from disk when a cache instance is created
- **Periodic Saving**: Stats are saved every 100 cache operations (gets/sets)
- **Cleanup Saving**: Stats are saved after each cleanup operation
- **Graceful Shutdown**: Stats are saved when the cache object is destroyed
- **Atomic Writes**: Stats file is written atomically to prevent corruption

### Stats File Location

Statistics are stored in a hidden file within the cache directory:
```
{cache_root}/.cache_stats.json
```

### What's Persisted

- **Hit Count**: Total number of cache hits across all sessions
- **Miss Count**: Total number of cache misses across all sessions  
- **Eviction Count**: Total number of entries evicted due to limits
- **Error Count**: Total number of cache operation errors
- **Last Updated**: Timestamp of when stats were last saved
- **Current Size**: Current total size and entry count (recalculated on load)

### Configuration

```python
# Enable/disable statistics persistence
config = CacheConfig(
    enable_statistics=True,  # Default: True
    cache_root=Path("/path/to/cache")
)
cache = FilesystemCache(config)

# Stats are automatically loaded and saved
stats = cache.get_stats()
print(f"Total hits across all sessions: {stats.hit_count}")
```

### Cross-Process Sharing

When using shared cache strategy, statistics are shared across processes:

```python
# Process 1
cache1 = create_default_cache(cache_strategy="shared")
cache1.set("key", "value")
cache1.get("key")  # Hit count: 1

# Process 2 (later)
cache2 = create_default_cache(cache_strategy="shared")
cache2.get("key")  # Hit count: 2 (accumulated)
```

### Error Handling

- **Corrupted Stats**: If the stats file is corrupted, the cache starts with fresh statistics
- **Missing File**: New cache instances start with zero stats if no file exists
- **Write Failures**: Warnings are logged but don't affect cache operation
- **Race Conditions**: Atomic writes prevent corruption during concurrent access

## Cache Operations

### Core Operations

```python
# Store data with optional TTL
cache.set("user:123", user_data, ttl=3600)

# Retrieve data with default fallback
user_data = cache.get("user:123", default={})

# Check existence (respects TTL)
if cache.exists("user:123"):
    print("User data is cached")

# Remove specific entry
was_deleted = cache.delete("user:123")

# Clear all entries
cache.clear()
```

### Metadata and Statistics

```python
# Get entry metadata
metadata = cache.get_metadata("user:123")
if metadata:
    print(f"Size: {metadata.size_bytes} bytes")
    print(f"Age: {metadata.age_seconds} seconds")
    print(f"Access count: {metadata.access_count}")

# Get cache statistics
stats = cache.get_stats()
print(f"Hit rate: {stats.hit_rate:.1f}%")
print(f"Total entries: {stats.total_entries}")
print(f"Total size: {stats.total_size_bytes} bytes")
```

### Cache Cleanup

```python
# Manual cleanup (removes expired entries)
removed_count = cache.cleanup()
print(f"Removed {removed_count} expired entries")

# Automatic cleanup runs every 5 minutes by default
# Configurable via cleanup_interval_seconds
```

## Key Generation

Use `CacheKey` helpers for consistent key generation:

```python
from glovebox.core.cache.models import CacheKey

# From multiple parts
key = CacheKey.from_parts("user", "profile", "123")

# From dictionary data
key = CacheKey.from_dict({"user_id": 123, "type": "profile"})

# From file path (includes modification time)
key = CacheKey.from_path(Path("/path/to/file.json"))
```

## Error Handling

The cache system is designed to be resilient:

```python
# Cache operations never raise exceptions for retrieval
data = cache.get("nonexistent")  # Returns None, never raises

# Corrupt cache entries are automatically cleaned up
# Network/disk errors are logged but don't crash the application

# Statistics track error counts
stats = cache.get_stats()
if stats.error_count > 0:
    print(f"Cache errors encountered: {stats.error_count}")
```

## Eviction Policies

Configure how the cache removes entries when limits are reached:

### LRU (Least Recently Used) - Default
Removes entries that haven't been accessed recently.

### LFU (Least Frequently Used)  
Removes entries with the lowest access count.

### FIFO (First In, First Out)
Removes the oldest entries first.

### TTL (Time To Live)
Only removes expired entries, no size-based eviction.

```python
config = CacheConfig(
    max_size_bytes=100 * 1024 * 1024,  # 100MB
    eviction_policy="lfu"
)
cache = FilesystemCache(config)
```

## Integration Examples

### Layout Service Integration

```python
from glovebox.core.cache import create_default_cache
from glovebox.layout import create_layout_service

cache = create_default_cache()
layout_service = create_layout_service(cache=cache)

# Cache layout parsing results
layout = layout_service.load_layout("my_layout.json")  # Cached automatically
```

### MoErgo Client Integration

```python
from glovebox.core.cache import create_cache_from_user_config
from glovebox.moergo.client import create_moergo_client

cache = create_cache_from_user_config(user_config)
client = create_moergo_client(user_config=user_config)

# API responses are cached automatically
firmware_list = client.list_firmware()  # Cached for performance
```

## Performance Considerations

### Filesystem Cache
- **Best for**: Persistent data, large objects, cross-process sharing
- **Storage**: Disk-based with file locking
- **Overhead**: File I/O, serialization costs
- **Concurrency**: Safe with file locking

### Memory Cache  
- **Best for**: Temporary data, small objects, single-process use
- **Storage**: RAM-based with Python objects
- **Overhead**: Minimal, no serialization
- **Concurrency**: Thread-safe with locks

### Size Guidelines
- **Default**: 500MB filesystem cache
- **Memory**: Limit to 100MB for memory cache  
- **Entries**: 10,000 max entries for good performance
- **TTL**: 24 hours default, adjust based on data freshness needs

## Monitoring and Debugging

### Enable Debug Logging

```python
import logging
logging.getLogger("glovebox.core.cache").setLevel(logging.DEBUG)
```

### Cache Statistics

```python
stats = cache.get_stats()
print(f"""Cache Performance:
- Hit Rate: {stats.hit_rate:.1f}%
- Miss Rate: {stats.miss_rate:.1f}%
- Total Entries: {stats.total_entries}
- Total Size: {stats.total_size_bytes:,} bytes
- Evictions: {stats.eviction_count}
- Errors: {stats.error_count}
""")
```

### Cache Inspection

```python
# Check specific cache directories
cache_root = Path("/tmp/glovebox_cache")
if cache_root.exists():
    data_files = list((cache_root / "data").glob("*.json"))
    meta_files = list((cache_root / "metadata").glob("*.meta.json"))
    print(f"Data files: {len(data_files)}")
    print(f"Metadata files: {len(meta_files)}")
```

## Migration Guide

### From Environment Variables

The cache system no longer supports environment variable configuration. Update your code:

**Old (Deprecated):**
```bash
export GLOVEBOX_CACHE_STRATEGY=shared
export GLOVEBOX_CACHE_FILE_LOCKING=false
```

**New (Recommended):**
```python
# Via user configuration
config = UserConfigData(
    cache_strategy="shared",
    cache_file_locking=False
)
cache = create_cache_from_user_config(config)

# Or directly
cache = create_default_cache(
    cache_strategy="shared",
    cache_file_locking=False
)
```

### From Optional Parameters

**Old (Deprecated):**
```python
cache = create_default_cache(
    cache_strategy=None,  # Would fall back to environment
    cache_file_locking=None
)
```

**New (Required):**
```python
cache = create_default_cache(
    cache_strategy="process_isolated",
    cache_file_locking=True
)
```

## Testing

The cache system includes comprehensive test coverage:

```bash
# Run cache tests
pytest tests/test_config/test_cache_integration.py -v

# Run all cache-related tests
pytest -k cache -v

# Test with different strategies
pytest tests/test_config/test_cache_integration.py::TestCacheUserConfigIntegration::test_user_config_cache_strategy_shared -v
```

## Troubleshooting

### Common Issues

**Cache Directory Permissions**
```bash
# Ensure cache directory is writable
chmod 755 /tmp/glovebox_cache
```

**File Locking Issues**
```python
# Disable file locking if needed
cache = create_default_cache(cache_file_locking=False)
```

**High Memory Usage**
```python
# Reduce cache size limits
config = CacheConfig(
    max_size_bytes=50 * 1024 * 1024,  # 50MB
    max_entries=5000
)
```

**Slow Performance**
```python
# Use memory cache for frequently accessed data
fast_cache = create_memory_cache(
    max_size_mb=50,
    default_ttl_hours=1
)
```

### Debug Cache Corruption

```python
# Force cleanup of corrupted entries
removed = cache.cleanup()
print(f"Cleaned up {removed} corrupted entries")

# Clear entire cache if needed
cache.clear()
```

## Development Guidelines

### Adding New Cache Types

1. Implement the `CacheManager` protocol
2. Extend `BaseCacheManager` for common functionality  
3. Add factory function following naming conventions
4. Include comprehensive tests
5. Update this documentation

### Testing Cache Implementations

```python
def test_cache_implementation(cache: CacheManager):
    """Standard test suite for cache implementations."""
    # Test basic operations
    cache.set("test", "value")
    assert cache.get("test") == "value"
    assert cache.exists("test")
    
    # Test TTL
    cache.set("ttl_test", "value", ttl=1)
    time.sleep(2)
    assert not cache.exists("ttl_test")
    
    # Test statistics
    stats = cache.get_stats()
    assert stats.hit_count > 0
```

### Performance Testing

```python
import time
from glovebox.core.cache import create_default_cache

def benchmark_cache():
    cache = create_default_cache()
    
    # Write performance
    start = time.time()
    for i in range(1000):
        cache.set(f"key_{i}", f"value_{i}")
    write_time = time.time() - start
    
    # Read performance  
    start = time.time()
    for i in range(1000):
        cache.get(f"key_{i}")
    read_time = time.time() - start
    
    print(f"Write: {write_time:.3f}s, Read: {read_time:.3f}s")
```

---

For more information, see the main project documentation and the test suite for comprehensive usage examples.
