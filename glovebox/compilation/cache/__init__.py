"""ZMK compilation caching system.

This module implements a modern caching strategy for ZMK firmware compilation
using base dependencies caching for shared components.

The caching system reduces compilation time by reusing shared dependencies
across multiple builds.
"""

from glovebox.compilation.cache.cache_injector import (
    CacheInjectorError,
    inject_base_dependencies_cache_from_workspace,
)


__all__ = [
    "inject_base_dependencies_cache_from_workspace",
    "CacheInjectorError",
]
