"""ZMK compilation caching system.

This module implements a tiered caching strategy for ZMK firmware compilation:

1. Base ZMK Dependencies Cache - Caches Zephyr, modules, and ZMK repositories
2. Keyboard Configuration Cache - Caches keyboard-specific workspace configurations

The caching system reduces compilation time by reusing shared dependencies
and previously compiled components across multiple builds.
"""
