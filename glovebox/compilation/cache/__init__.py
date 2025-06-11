"""ZMK compilation caching system.

This module implements a modern caching strategy for ZMK firmware compilation
using the generic cache system:

1. Generic Cache System - Domain-agnostic caching infrastructure
2. Compilation Cache - High-level compilation-specific caching operations
3. Legacy Cache Migration - Backward compatibility for existing cache implementations

The caching system reduces compilation time by reusing shared dependencies
and previously compiled components across multiple builds.
"""

# Legacy cache imports for backward compatibility during migration
from glovebox.compilation.cache.base_dependencies_cache import (
    BaseDependenciesCache,
    BaseDependenciesCacheError,
)
from glovebox.compilation.cache.compilation_cache import (
    CompilationCache,
    CompilationCacheError,
    create_compilation_cache,
)
from glovebox.compilation.cache.keyboard_config_cache import (
    KeyboardConfigCache,
    KeyboardConfigCacheError,
)


__all__ = [
    "CompilationCache",
    "CompilationCacheError",
    "create_compilation_cache",
    # Legacy exports
    "BaseDependenciesCache",
    "BaseDependenciesCacheError",
    "KeyboardConfigCache",
    "KeyboardConfigCacheError",
]
