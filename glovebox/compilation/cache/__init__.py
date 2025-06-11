"""ZMK compilation caching system.

This module implements a modern caching strategy for ZMK firmware compilation
using the generic cache system:

1. Generic Cache System - Domain-agnostic caching infrastructure
2. Compilation Cache - High-level compilation-specific caching operations

The caching system reduces compilation time by reusing shared dependencies
and previously compiled components across multiple builds.
"""

from glovebox.compilation.cache.compilation_cache import (
    CompilationCache,
    CompilationCacheError,
    create_compilation_cache,
)


__all__ = [
    "CompilationCache",
    "CompilationCacheError",
    "create_compilation_cache",
]
