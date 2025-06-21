# Shared Cache Coordination Architecture

This document describes the shared cache coordination system implemented to eliminate multiple independent cache instances across Glovebox domains while maintaining proper isolation.

## Background

### Problem Statement

Previously, each domain created independent cache instances:
- Compilation domain: Created its own cache for ZMK workspace management
- Metrics domain: Created its own cache for usage tracking
- Layout domain: Created its own cache for layout processing
- MoErgo domain: Created its own cache for API responses

This resulted in:
- **Resource duplication**: Multiple cache managers for similar operations
- **Memory inefficiency**: Separate cache instances even for identical configurations
- **Test pollution**: No centralized cache cleanup mechanism
- **Inconsistent behavior**: Different cache lifetimes and configurations

### Solution Requirements

The solution needed to:
1. **Eliminate duplicate cache instances** while maintaining domain isolation
2. **Follow CLAUDE.md conventions** (factory functions, no singletons)
3. **Ensure test safety** with proper isolation between tests
4. **Maintain backward compatibility** with existing cache operations
5. **Support domain-specific configuration** and cache strategies

## Architecture Overview

### Core Design Principles

1. **Shared Coordination**: Single cache instances shared across domains when appropriate
2. **Tag-Based Isolation**: Different domains use different cache namespaces
3. **Factory Function Pattern**: No singletons, consistent with CLAUDE.md requirements
4. **Test Safety**: Automatic cache reset between tests
5. **Graceful Degradation**: Falls back to disabled cache when needed

### System Components

```
glovebox/core/cache_v2/
├── cache_coordinator.py       # Central coordination logic
├── cache_manager.py          # CacheManager protocol/interface
├── diskcache_manager.py      # DiskCache implementation
├── disabled_cache.py         # No-op cache implementation
├── models.py                 # Cache configuration models
└── __init__.py              # Public API with shared coordination
```

## Implementation Details

### 1. Cache Coordinator (`cache_coordinator.py`)

Central module that manages shared cache instances:

```python
# Global registry for shared cache instances
_shared_cache_instances: dict[str, CacheManager] = {}

def get_shared_cache_instance(
    cache_root: Path,
    tag: str | None = None,
    enabled: bool = True,
    max_size_gb: int = 2,
    timeout: int = 30,
) -> CacheManager:
    """Get shared cache instance, creating if needed."""
    
    if not enabled:
        return DisabledCache()
    
    # Create cache key for instance coordination
    cache_key = f"{cache_root.resolve()}:{tag or 'default'}"
    
    if cache_key not in _shared_cache_instances:
        # Create new cache instance
        cache_dir = cache_root / (tag or "default")
        config = DiskCacheConfig(
            cache_path=cache_dir,
            max_size_bytes=max_size_gb * 1024 * 1024 * 1024,
            timeout=timeout,
        )
        _shared_cache_instances[cache_key] = DiskCacheManager(config)
    
    return _shared_cache_instances[cache_key]
```

**Key Features:**
- **Instance Registry**: Maps cache keys to active instances
- **Cache Key Generation**: Combines cache root path and tag for uniqueness
- **Lazy Creation**: Creates instances only when needed
- **Resource Management**: Reuses existing instances when possible

### 2. Updated Factory Functions

Core factory functions updated to use shared coordination:

```python
def create_default_cache(tag: str | None = None) -> CacheManager:
    """Create default cache with shared coordination."""
    if _is_cache_globally_disabled():
        return _create_disabled_cache()
    
    if tag and _is_module_cache_disabled(tag):
        return _create_disabled_cache()
    
    cache_root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "glovebox"
    
    return get_shared_cache_instance(
        cache_root=cache_root,
        tag=tag,
        enabled=True,
        max_size_gb=2,
        timeout=30,
    )

def create_cache_from_user_config(
    user_config: Any, tag: str | None = None
) -> CacheManager:
    """Create cache from user configuration with shared coordination."""
    # Check various disable conditions
    if _is_cache_globally_disabled():
        return _create_disabled_cache()
    
    if hasattr(user_config, "cache_strategy") and user_config.cache_strategy == "disabled":
        return _create_disabled_cache()
    
    if tag and _is_module_cache_disabled(tag):
        return _create_disabled_cache()
    
    # Use shared coordination
    cache_root = getattr(user_config, "cache_path", Path.home() / ".cache" / "glovebox")
    return get_shared_cache_instance(
        cache_root=cache_root,
        tag=tag,
        enabled=True,
    )
```

### 3. Domain-Specific Factories

Each domain provides specialized factory functions:

```python
# glovebox/compilation/cache/__init__.py
def create_compilation_cache_service(
    user_config: UserConfig,
) -> tuple[CacheManager, ZmkWorkspaceCacheService]:
    """Factory function for compilation cache service with shared coordination."""
    
    # Use shared cache coordination for compilation domain
    cache_manager = create_cache_from_user_config(
        user_config._config, tag="compilation"
    )
    
    # Create workspace cache service with shared cache
    workspace_service = create_zmk_workspace_cache_service(user_config, cache_manager)
    
    return cache_manager, workspace_service
```

### 4. Test Isolation System

Complete test isolation through automatic cache reset:

```python
# tests/conftest.py
@pytest.fixture(autouse=True)
def reset_shared_cache() -> Generator[None, None, None]:
    """Reset shared cache instances before each test for isolation."""
    from glovebox.core.cache_v2 import reset_shared_cache_instances
    
    # Reset cache before test
    reset_shared_cache_instances()
    
    yield
    
    # Reset cache after test for extra safety
    reset_shared_cache_instances()

def reset_shared_cache_instances() -> None:
    """Reset all shared cache instances."""
    global _shared_cache_instances
    
    # Close all existing cache instances
    for cache_key, cache_instance in _shared_cache_instances.items():
        try:
            if hasattr(cache_instance, "close"):
                cache_instance.close()
        except Exception as e:
            logger.warning("Error closing cache instance %s: %s", cache_key, e)
    
    # Clear the registry
    _shared_cache_instances.clear()
    
    # Clean up workspace cache directories for test isolation
    try:
        workspace_cache_dir = Path.home() / ".cache" / "glovebox" / "workspace"
        if workspace_cache_dir.exists():
            shutil.rmtree(workspace_cache_dir, ignore_errors=True)
    except Exception as e:
        logger.warning("Error cleaning workspace cache directory: %s", e)
```

## Cache Coordination Behavior

### Same Tag = Same Instance

When multiple calls use the same tag, they get the same cache instance:

```python
# These return the same instance
cache1 = create_default_cache(tag="compilation")
cache2 = create_default_cache(tag="compilation")
assert cache1 is cache2  # True

# Instance count remains 1
assert get_cache_instance_count() == 1
```

### Different Tags = Different Instances

When calls use different tags, they get separate cache instances:

```python
# These return different instances
compilation_cache = create_default_cache(tag="compilation")
metrics_cache = create_default_cache(tag="metrics")
layout_cache = create_default_cache(tag="layout")

assert compilation_cache is not metrics_cache  # True
assert compilation_cache is not layout_cache   # True
assert metrics_cache is not layout_cache       # True

# Instance count is 3
assert get_cache_instance_count() == 3
```

### Cache Key Generation

Cache keys are generated from cache root path and tag:

```python
# Examples of cache key generation:
# Path: /home/user/.cache/glovebox, Tag: compilation
# Key: "/home/user/.cache/glovebox:compilation"

# Path: /home/user/.cache/glovebox, Tag: metrics  
# Key: "/home/user/.cache/glovebox:metrics"

# Path: /home/user/.cache/glovebox, Tag: None
# Key: "/home/user/.cache/glovebox:default"
```

## Service Integration Patterns

### Compilation Domain Integration

```python
# glovebox/compilation/__init__.py
def create_zmk_west_service() -> CompilationServiceProtocol:
    """Create ZMK with West compilation service using shared cache coordination."""
    from glovebox.adapters import create_docker_adapter
    from glovebox.config.user_config import create_user_config
    from glovebox.compilation.cache import create_compilation_cache_service
    
    docker_adapter = create_docker_adapter()
    user_config = create_user_config()
    
    # Use shared cache coordination via domain-specific factory
    cache, workspace_service = create_compilation_cache_service(user_config)
    
    return create_zmk_west_service(
        docker_adapter, user_config, cache, workspace_service
    )
```

### CLI Command Integration

```python
# glovebox/cli/commands/cache.py
def _get_cache_manager_and_service(user_config: UserConfig) -> tuple[CacheManager, ZmkWorkspaceCacheService]:
    """Get cache manager and workspace service for cache commands."""
    # Use shared cache coordination through domain-specific factory
    return create_compilation_cache_service(user_config)
```

## Configuration and Environment Variables

### Global Cache Control

```bash
# Disable all caching globally
export GLOVEBOX_CACHE_GLOBAL=disabled
export GLOVEBOX_CACHE_GLOBAL=false
export GLOVEBOX_CACHE_GLOBAL=0

# Enable all caching (default)
export GLOVEBOX_CACHE_GLOBAL=enabled
export GLOVEBOX_CACHE_GLOBAL=true
export GLOVEBOX_CACHE_GLOBAL=1
```

### Domain-Specific Cache Control

```bash
# Disable caching for specific domains
export GLOVEBOX_CACHE_COMPILATION=disabled
export GLOVEBOX_CACHE_METRICS=disabled
export GLOVEBOX_CACHE_LAYOUT=disabled
export GLOVEBOX_CACHE_MOERGO=disabled
```

### Cache Directory Customization

```bash
# Custom cache root directory
export XDG_CACHE_HOME=/custom/cache
# Results in cache at: /custom/cache/glovebox/

# User config can also specify cache path
user_config.cache_path = Path("/project/cache")
# Results in cache at: /project/cache/
```

## Monitoring and Debugging

### Cache Instance Monitoring

```python
from glovebox.core.cache_v2 import (
    get_cache_instance_count,
    get_cache_instance_keys,
    cleanup_shared_cache_instances
)

# Monitor active cache instances
print(f"Active instances: {get_cache_instance_count()}")
print(f"Instance keys: {get_cache_instance_keys()}")

# Example output:
# Active instances: 2
# Instance keys: ['/home/user/.cache/glovebox:compilation', '/home/user/.cache/glovebox:metrics']
```

### Debug Logging

```python
# Enable debug logging to see cache coordination activity
import logging
logging.getLogger("glovebox.core.cache_v2.cache_coordinator").setLevel(logging.DEBUG)

# Cache operations will log:
# DEBUG - Creating new shared cache instance: /home/user/.cache/glovebox:compilation
# DEBUG - Reusing existing shared cache instance: /home/user/.cache/glovebox:compilation
```

### Test Debugging

```python
# Use shared_cache_stats fixture in tests
def test_cache_coordination(shared_cache_stats):
    cache1 = create_default_cache(tag="test")
    cache2 = create_default_cache(tag="test")
    
    stats = shared_cache_stats()
    assert stats["instance_count"] == 1
    assert stats["instance_keys"] == ["/home/user/.cache/glovebox:test"]
    assert cache1 is cache2
```

## Error Handling and Resilience

### Cache Creation Failures

```python
def get_shared_cache_instance(...) -> CacheManager:
    try:
        # Attempt to create cache instance
        config = DiskCacheConfig(...)
        _shared_cache_instances[cache_key] = DiskCacheManager(config)
    except Exception as e:
        logger.warning("Failed to create cache instance %s: %s", cache_key, e)
        # Return disabled cache as fallback
        return DisabledCache()
```

### Cache Operation Failures

```python
# All cache operations include error handling
def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
    try:
        self._cache.set(key, value, expire=ttl)
        return True
    except Exception as e:
        logger.warning("Cache set failed for key %s: %s", key, e)
        return False
```

### Test Isolation Failures

```python
def reset_shared_cache_instances() -> None:
    try:
        # Attempt to close cache instances gracefully
        for cache_key, cache_instance in _shared_cache_instances.items():
            if hasattr(cache_instance, "close"):
                cache_instance.close()
    except Exception as e:
        # Log warning but continue with registry cleanup
        logger.warning("Error closing cache instance: %s", e)
    finally:
        # Always clear the registry
        _shared_cache_instances.clear()
```

## Performance Characteristics

### Memory Usage

- **Before**: N domains × M cache instances = N×M cache managers in memory
- **After**: N domains with unique tags = N cache managers in memory
- **Improvement**: Eliminates duplicate cache managers for same tag usage

### Cache Hit Rates

- **Improved**: Shared instances increase cache hit rates across domain boundaries
- **Domain Isolation**: Different tags maintain separate hit rate statistics
- **Workspace Caching**: ZMK workspace reuse provides significant performance gains

### Startup Performance

- **Lazy Creation**: Cache instances created only when first accessed
- **Instance Reuse**: Subsequent domain initialization is faster
- **Configuration Respect**: Disabled caches avoid unnecessary initialization

## Future Enhancements

### Potential Improvements

1. **Cache Statistics Aggregation**: Combine statistics across all shared instances
2. **Memory Pressure Management**: Automatic cache eviction under memory pressure
3. **Distributed Caching**: Share cache instances across development teams
4. **Smart Cache Warming**: Pre-populate frequently used cache entries
5. **Cache Analytics**: Detailed metrics on usage patterns and effectiveness

### Backward Compatibility

The shared cache coordination system maintains full backward compatibility:
- All existing cache operations continue to work unchanged
- Cache manager interfaces remain identical
- Service creation patterns are preserved
- Only the underlying coordination mechanism has been enhanced

This ensures existing code continues to function while benefiting from improved resource utilization and test safety.