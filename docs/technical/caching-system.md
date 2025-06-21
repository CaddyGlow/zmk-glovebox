# Glovebox Caching System

Glovebox includes a **shared cache coordination system** that provides efficient, domain-isolated caching across all application components while maintaining proper test isolation.

## Architecture Overview

The caching system has been refactored to eliminate multiple independent cache instances by:
- **Coordinating cache instances** across domains using a central registry
- **Domain isolation** through cache tags (compilation, metrics, layout, etc.)
- **CLAUDE.md compliance** using factory functions (no singletons)
- **Thread/process safety** with DiskCache SQLite backend
- **Test safety** with automatic cache reset between tests

```
Shared Cache Coordination System
├── Cache Coordinator (glovebox/core/cache_v2/cache_coordinator.py)
│   ├── get_shared_cache_instance() - Central coordination function
│   ├── reset_shared_cache_instances() - Test isolation utility
│   └── Instance registry with cache key coordination
├── Domain-Specific Factories
│   ├── create_compilation_cache_service() - Compilation domain
│   ├── create_default_cache(tag="metrics") - Metrics domain
│   └── create_default_cache(tag="layout") - Layout domain
└── Updated Factory Functions
    ├── create_default_cache() - Uses shared coordination
    └── create_cache_from_user_config() - Uses shared coordination
```

## Core Components

### 1. Cache Coordinator

Central coordination function that manages shared cache instances:

```python
def get_shared_cache_instance(
    cache_root: Path,
    tag: str | None = None,
    enabled: bool = True,
    max_size_gb: int = 2,
    timeout: int = 30,
) -> CacheManager:
    """Get shared cache instance, creating if needed."""
```

**Key Features:**
- **Instance Registry**: Maps cache keys to active cache instances
- **Tag-Based Isolation**: Different tags create separate cache instances
- **Resource Efficiency**: Same tag returns same instance across the application
- **Graceful Degradation**: Returns DisabledCache when caching is disabled

### 2. Domain-Specific Cache Factories

Each domain has dedicated factory functions for cache coordination:

```python
# Compilation Domain
from glovebox.compilation.cache import create_compilation_cache_service

def create_compilation_cache_service(
    user_config: UserConfig,
) -> tuple[CacheManager, ZmkWorkspaceCacheService]:
    """Factory function for compilation cache service with shared coordination."""
    cache_manager = create_cache_from_user_config(
        user_config._config, tag="compilation"
    )
    workspace_service = create_zmk_workspace_cache_service(user_config, cache_manager)
    return cache_manager, workspace_service
```

### 3. Updated Factory Functions

Core cache factory functions now use shared coordination:

```python
# Core cache factories (glovebox/core/cache_v2/)
def create_default_cache(tag: str | None = None) -> CacheManager:
    """Create default cache with shared coordination."""
    return get_shared_cache_instance(
        cache_root=Path.home() / ".cache" / "glovebox",
        tag=tag,
        enabled=True
    )

def create_cache_from_user_config(
    user_config: Any, tag: str | None = None
) -> CacheManager:
    """Create cache from user configuration with shared coordination."""
    return get_shared_cache_instance(
        cache_root=getattr(user_config, "cache_path", Path.home() / ".cache" / "glovebox"),
        tag=tag,
        enabled=getattr(user_config, "cache_strategy", "enabled") != "disabled"
    )
```

## Cache Coordination Benefits

### 1. Single Cache Instances

Same tag → same cache instance across all domains:

```python
# These return the same cache instance
compilation_cache = create_default_cache(tag="compilation")
compilation_cache2 = create_default_cache(tag="compilation")
assert compilation_cache is compilation_cache2  # True
```

### 2. Domain Isolation

Different tags → separate cache instances with isolated namespaces:

```python
# These return different cache instances
compilation_cache = create_default_cache(tag="compilation")
metrics_cache = create_default_cache(tag="metrics")
layout_cache = create_default_cache(tag="layout")

assert compilation_cache is not metrics_cache  # True
assert compilation_cache is not layout_cache   # True
```

### 3. Memory Efficiency

- **Eliminates duplicate cache managers** across domains
- **Reduces memory usage** by sharing instances
- **Optimizes resource utilization** in multi-domain operations

### 4. Thread/Process Safety

- **DiskCache with SQLite backend** supports concurrent access
- **Atomic operations** prevent cache corruption
- **Process isolation** allows safe multi-process usage

## Implementation Patterns

### 1. Service Integration

Services use domain-specific cache factories:

```python
# ZMK West Service uses compilation cache coordination
def create_zmk_west_service() -> CompilationServiceProtocol:
    docker_adapter = create_docker_adapter()
    user_config = create_user_config()
    
    # Use shared cache coordination via domain-specific factory
    cache, workspace_service = create_compilation_cache_service(user_config)
    
    return create_zmk_west_service(
        docker_adapter, user_config, cache, workspace_service
    )
```

### 2. Tag-Based Isolation

Each domain gets its own isolated cache namespace:

```python
# Domain-specific cache creation
compilation_cache = create_default_cache(tag="compilation")  # For ZMK builds
metrics_cache = create_default_cache(tag="metrics")          # For usage tracking  
layout_cache = create_default_cache(tag="layout")            # For layout processing
moergo_cache = create_default_cache(tag="moergo")            # For MoErgo API
```

### 3. Configuration-Based Cache Management

Cache behavior respects user configuration:

```python
# Cache disabled globally
os.environ["GLOVEBOX_CACHE_GLOBAL"] = "disabled"
cache = create_default_cache()  # Returns DisabledCache

# Cache disabled for specific domain
os.environ["GLOVEBOX_CACHE_COMPILATION"] = "disabled"
cache = create_default_cache(tag="compilation")  # Returns DisabledCache

# User config cache strategy
user_config.cache_strategy = "disabled"
cache = create_cache_from_user_config(user_config)  # Returns DisabledCache
```

## Test Isolation

### Automatic Cache Reset

Complete test isolation through automatic cache reset:

```python
# tests/conftest.py
@pytest.fixture(autouse=True)
def reset_shared_cache() -> Generator[None, None, None]:
    """Reset shared cache instances before each test for isolation."""
    reset_shared_cache_instances()  # Before test
    yield
    reset_shared_cache_instances()  # After test
```

### Test Safety Features

- **Automatic cleanup** of all shared cache instances between tests
- **Workspace cache cleanup** for filesystem-based caches
- **No test pollution** - each test starts with clean cache state
- **Debug utilities** for cache instance monitoring

```python
# Debug cache state in tests
def test_cache_coordination(shared_cache_stats):
    cache1 = create_default_cache(tag="test")
    cache2 = create_default_cache(tag="test")
    
    stats = shared_cache_stats()
    assert stats["instance_count"] == 1
    assert cache1 is cache2
```

## Cache Operations

### Basic Operations

All cache operations use the standard CacheManager interface:

```python
# Get cache instance for domain
cache = create_default_cache(tag="compilation")

# Standard cache operations
cache.set("build_key", build_data, ttl=3600)
cached_data = cache.get("build_key", default=None)
exists = cache.exists("build_key")
cache.delete("build_key")
cache.clear()  # Clear all entries

# Metadata and statistics
metadata = cache.get_metadata("build_key")
stats = cache.get_stats()
cleaned_count = cache.cleanup()  # Remove expired entries
```

### Cache Configuration

Cache behavior can be configured through environment variables:

```bash
# Global cache control
export GLOVEBOX_CACHE_GLOBAL=disabled      # Disable all caching
export GLOVEBOX_CACHE_GLOBAL=enabled       # Enable all caching (default)

# Domain-specific cache control
export GLOVEBOX_CACHE_COMPILATION=disabled # Disable compilation caching
export GLOVEBOX_CACHE_METRICS=disabled     # Disable metrics caching
export GLOVEBOX_CACHE_LAYOUT=disabled      # Disable layout caching

# Cache directory customization
export XDG_CACHE_HOME=/custom/cache        # Custom cache root
```

## Performance Benefits

### ZMK Compilation Caching

The compilation domain uses workspace caching for ZMK builds:

```python
# Compilation service with workspace caching
cache_manager, workspace_service = create_compilation_cache_service(user_config)

# Workspace cache operations
cached_workspace = workspace_service.get_cached_workspace(config)
workspace_service.cache_workspace(workspace_path, config)
```

**Performance Improvements:**
- **First Build**: Downloads and caches ZMK dependencies (~5-10 minutes)
- **Subsequent Builds**: Reuses cached workspace (~30 seconds - 2 minutes)
- **Cross-Build Reuse**: Same ZMK repository shared across builds
- **Version Isolation**: Different ZMK versions maintain separate workspaces

### Cache Locations

```bash
# Default cache locations (XDG compliant)
~/.cache/glovebox/
├── default/                    # Default cache namespace
├── compilation/               # Compilation domain cache
│   ├── cache.db              # DiskCache SQLite database
│   └── workspace/            # ZMK workspace cache
├── metrics/                  # Metrics domain cache
├── layout/                   # Layout domain cache
└── moergo/                   # MoErgo domain cache
```

## Troubleshooting

### Cache Debugging

Enable debug logging to see cache coordination activity:

```bash
# Enable debug logging
glovebox --debug layout compile input.json output/

# Look for cache coordination messages:
# DEBUG - Creating new shared cache instance: /home/user/.cache/glovebox:compilation
# DEBUG - Reusing existing shared cache instance: /home/user/.cache/glovebox:compilation
```

### Cache Instance Monitoring

Monitor cache instances during development:

```python
from glovebox.core.cache_v2 import (
    get_cache_instance_count,
    get_cache_instance_keys,
    cleanup_shared_cache_instances
)

# Check active cache instances
print(f"Active instances: {get_cache_instance_count()}")
print(f"Instance keys: {get_cache_instance_keys()}")

# Cleanup expired entries across all instances
cleanup_results = cleanup_shared_cache_instances()
print(f"Cleanup results: {cleanup_results}")
```

### Common Issues

**Cache not being shared:**
- Check that the same tag is used across cache creation calls
- Verify cache coordination is enabled (not globally disabled)

**Memory usage concerns:**
- Each domain uses separate cache instances (by design)
- Use `reset_shared_cache_instances()` to clear all instances
- Monitor instance count with `get_cache_instance_count()`

**Test isolation problems:**
- Ensure tests use `isolated_config` fixture
- Verify `reset_shared_cache` fixture is working (`autouse=True`)
- Check for proper cleanup in test fixtures

## Migration from Previous System

The shared cache coordination system replaces the previous independent cache approach:

**Before (Multiple Independent Caches):**
```python
# Each domain created its own cache instances
compilation_cache = create_diskcache_manager(cache_root / "compilation")
metrics_cache = create_diskcache_manager(cache_root / "metrics")
# No coordination, potential resource duplication
```

**After (Shared Coordination):**
```python
# Coordinated cache instances with proper isolation
compilation_cache = create_default_cache(tag="compilation")
metrics_cache = create_default_cache(tag="metrics")
# Same tag = same instance, different tags = different instances
```

All existing cache operations continue to work unchanged - only the underlying coordination mechanism has been enhanced for better resource utilization and test safety.