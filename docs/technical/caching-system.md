# Glovebox Caching System

Glovebox includes a sophisticated **2-tier caching system** that dramatically reduces ZMK firmware compilation times by reusing shared dependencies across builds.

## Overview

The caching system operates on two levels:

```
Tier 1: Base ZMK Dependencies Cache
├── Zephyr RTOS repositories and modules
├── ZMK firmware repository (per branch/version)
└── Shared build tools and dependencies

Tier 2: Keyboard Configuration Cache  
├── Keyboard-specific build.yaml configurations
├── Shield and board combinations
└── ZMK workspace configurations per keyboard profile
```

## Performance Benefits

- **First Build**: Downloads and caches ZMK dependencies (~5-10 minutes)
- **Subsequent Builds**: Reuses cached dependencies (~30 seconds - 2 minutes)
- **Cross-Keyboard Reuse**: Same ZMK version shared across all keyboard configurations
- **Version Isolation**: Different ZMK versions maintain separate cache entries

## How It Works

### Automatic Operation

Caching is **enabled by default** and requires no configuration:

```bash
# First build for any keyboard using ZMK main branch
glovebox firmware compile layout.keymap config.conf --profile corne/main
# → Creates base cache for zmkfirmware/zmk@main
# → Creates keyboard cache for corne + nice_nano_v2

# Second build for different keyboard using same ZMK version  
glovebox firmware compile layout.keymap config.conf --profile glove80/v25.05
# → Reuses base cache (if same ZMK version)
# → Creates new keyboard cache for glove80 + glove80_lh/glove80_rh

# Third build for original keyboard
glovebox firmware compile updated_layout.keymap config.conf --profile corne/main
# → Reuses both base and keyboard caches
# → Only copies user files and compiles firmware
```

### Cache Key Generation

**Base Dependencies Cache Keys** based on:
- ZMK repository URL (e.g., `zmkfirmware/zmk`, `moergo-sc/zmk`)
- ZMK branch/revision (e.g., `main`, `v25.05`)

**Keyboard Configuration Cache Keys** based on:
- Keyboard profile name
- Shield name
- Board name  
- ZMK repository details

### Cache Locations

```bash
# Default cache locations
~/.glovebox/cache/base_deps/          # Base ZMK dependencies
~/.glovebox/cache/keyboard_config/    # Keyboard-specific configurations

# Cache structure example
~/.glovebox/cache/
├── base_deps/
│   ├── a1b2c3d4e5f6g7h8/            # zmkfirmware/zmk@main
│   └── f1e2d3c4b5a6g7h8/            # moergo-sc/zmk@main
└── keyboard_config/
    ├── a1b2c3d4e5f6g7h8_x1y2z3w4/  # corne + nice_nano_v2
    └── f1e2d3c4b5a6g7h8_p1q2r3s4/  # glove80 + glove80_lh/rh
```

## Cache Management

### Viewing Cache Activity

```bash
# Enable verbose output to see cache operations
glovebox -v firmware compile layout.keymap config.conf --profile corne/main

# Example output:
# INFO - Using cached approach - base: a1b2c3d4, keyboard: x1y2z3w4
# INFO - Found valid keyboard config cache: ~/.glovebox/cache/keyboard_config/a1b2c3d4_x1y2z3w4
# INFO - Using cached keyboard workspace: ~/.glovebox/cache/keyboard_config/a1b2c3d4_x1y2z3w4
# INFO - Dynamic ZMK config workspace initialized successfully using cache
```

### Pre-populating Cache

You can pre-populate the base cache from existing ZMK workspaces:

```bash
# Generate base cache from existing workspace
python scripts/generate_base_cache.py --workspace /path/to/existing/zmk-config

# Auto-detect ZMK repository info
python scripts/generate_base_cache.py --workspace /path/to/workspace --verbose

# Specify ZMK repository manually
python scripts/generate_base_cache.py --workspace /path/to/workspace \
  --zmk-repo moergo-sc/zmk --zmk-revision main

# See scripts/README.md for complete usage guide
```

### Cache Validation

The system automatically validates cache integrity:

**Base Dependencies Cache Validation:**
- Presence of `.west/`, `zephyr/`, `zmk/` directories
- Cache metadata file with repository information
- West workspace integrity

**Keyboard Configuration Cache Validation:**
- All base dependencies validation requirements
- Presence of `config/` directory and `build.yaml`
- Keyboard-specific metadata consistency
- Base cache key matching

### Cache Cleanup

```bash
# Automatic cleanup (configurable)
# - Base cache: 30 days retention by default
# - Keyboard cache: 30 days retention by default

# Manual cleanup (if needed)
rm -rf ~/.glovebox/cache/base_deps/old_cache_key
rm -rf ~/.glovebox/cache/keyboard_config/old_combined_key
```

## Architecture Details

### Workspace Manager Integration

The caching system is fully integrated with `ZmkConfigWorkspaceManager`:

```python
# Cached workspace initialization
if self.base_dependencies_cache and self.keyboard_config_cache:
    return self._initialize_dynamic_workspace_cached(...)
else:
    return self._initialize_dynamic_workspace_direct(...)  # Fallback
```

### Fallback Mechanism

If caching fails at any stage, the system gracefully falls back to direct workspace creation:

1. **Cache Miss**: Creates new cache entries
2. **Cache Corruption**: Falls back to direct creation
3. **Cache Disabled**: Uses direct creation only

### Error Handling

- **Workspace Validation Failures**: Fall back to direct creation
- **Permission Issues**: Log warnings and continue with direct method
- **Disk Space Issues**: Automatic cleanup of old cache entries

## Configuration Options

### Disabling Caching

```python
# Disable caching programmatically
workspace_manager = create_zmk_config_workspace_manager(enable_caching=False)
```

### Custom Cache Locations

```python
# Custom cache directories
base_cache = create_base_dependencies_cache(
    cache_root=Path("/custom/cache/base")
)
keyboard_cache = create_keyboard_config_cache(
    base_cache=base_cache,
    cache_root=Path("/custom/cache/keyboard")
)
```

## Troubleshooting

### Common Issues

**Cache not being used:**
```bash
# Check verbose output for cache activity
glovebox -v firmware compile layout.keymap config.conf --profile corne/main

# Look for messages like:
# "Using cached approach - base: ..., keyboard: ..."
# "Found valid keyboard config cache: ..."
```

**Cache corruption:**
```bash
# Clear specific cache entry
rm -rf ~/.glovebox/cache/base_deps/corrupted_key
rm -rf ~/.glovebox/cache/keyboard_config/corrupted_key

# Clear all cache
rm -rf ~/.glovebox/cache/
```

**Permission issues:**
```bash
# Ensure cache directories are writable
chmod -R u+w ~/.glovebox/cache/
```

### Debug Information

```bash
# Enable debug logging for cache operations
glovebox --debug firmware compile layout.keymap config.conf --profile corne/main

# Look for detailed cache validation and operation logs
```

## Performance Metrics

Typical performance improvements with caching:

| Build Type | Without Cache | With Cache | Improvement |
|------------|---------------|------------|-------------|
| First build (any keyboard) | 5-10 minutes | 5-10 minutes | Baseline |
| Same keyboard, different layout | 5-10 minutes | 30-120 seconds | **85-95% faster** |
| Different keyboard, same ZMK version | 5-10 minutes | 60-180 seconds | **70-90% faster** |
| Different keyboard, different ZMK version | 5-10 minutes | 3-7 minutes | **30-50% faster** |

## Future Enhancements

Potential future improvements to the caching system:

- **Compressed Cache Storage**: Reduce disk usage with compressed cache entries
- **Distributed Caching**: Share cache entries across development teams
- **Smart Invalidation**: Detect when ZMK dependencies have been updated
- **Cache Statistics**: Detailed metrics on cache hit rates and storage usage
- **Build Artifact Caching**: Cache compiled firmware for identical configurations