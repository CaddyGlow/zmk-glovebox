# Glovebox Scripts

This directory contains utility scripts for Glovebox development and operations.

## Cache Management Scripts

### Generate Base Cache from Existing Workspace

Use these scripts to create a base dependencies cache from an existing ZMK workspace. This is useful for pre-populating the cache or migrating existing workspaces to speed up future compilations.

#### Scripts

- **`generate_base_cache.py`** - Main Python script with full functionality
- **`cache-from-workspace`** - Simple bash wrapper for easier usage

#### Usage Examples

##### Basic Usage (Auto-detect ZMK info)
```bash
# Auto-detect ZMK repository and revision from workspace
python scripts/generate_base_cache.py --workspace /path/to/existing/zmk-workspace

# Or use the wrapper
./scripts/cache-from-workspace --workspace /path/to/existing/zmk-workspace
```

##### Specify ZMK Repository
```bash
# For standard ZMK
python scripts/generate_base_cache.py --workspace /path/to/workspace --zmk-repo zmkfirmware/zmk --zmk-revision main

# For Glove80 (MoErgo's fork)
python scripts/generate_base_cache.py --workspace /path/to/workspace --zmk-repo moergo-sc/zmk --zmk-revision main
```

##### Custom Cache Location
```bash
python scripts/generate_base_cache.py --workspace /path/to/workspace --cache-root ~/.glovebox/cache/custom
```

##### Dry Run (Preview)
```bash
python scripts/generate_base_cache.py --workspace /path/to/workspace --dry-run
```

##### Force Overwrite Existing Cache
```bash
python scripts/generate_base_cache.py --workspace /path/to/workspace --force
```

##### Verbose Output
```bash
python scripts/generate_base_cache.py --workspace /path/to/workspace --verbose
```

#### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--workspace` | Path to existing ZMK workspace directory | **Required** |
| `--zmk-repo` | ZMK repository URL (e.g., 'zmkfirmware/zmk') | Auto-detected |
| `--zmk-revision` | ZMK revision/branch | `main` or auto-detected |
| `--cache-root` | Custom cache root directory | `~/.glovebox/cache/base_deps` |
| `--verbose`, `-v` | Enable verbose logging | `false` |
| `--dry-run` | Show what would be done without creating cache | `false` |
| `--force` | Overwrite existing cache entry if it exists | `false` |

#### Features

##### Auto-Detection
- **ZMK Repository**: Reads `west.yml` or git remote info to detect repository
- **ZMK Revision**: Detects current branch from git or west configuration  
- **Validation**: Ensures workspace has required directories (`.west`, `zephyr`, `zmk`)

##### Smart Workspace Detection
The script looks for ZMK info in multiple places:
1. **`west.yml`** in workspace root
2. **`config/west.yml`** in workspace
3. **Git remote** in `zmk/` subdirectory

##### Safety Features
- **Validation**: Checks workspace has required ZMK dependencies
- **Dry Run**: Preview what would be done
- **Force Option**: Override existing cache entries
- **Comprehensive Logging**: Verbose mode for debugging

#### Example Output

```bash
$ python scripts/generate_base_cache.py --workspace /path/to/my-zmk-config --verbose

2025-01-11 10:30:15 - __main__ - INFO - Detected ZMK info from west.yml: moergo-sc/zmk@main
2025-01-11 10:30:15 - __main__ - INFO - Using ZMK repository: moergo-sc/zmk@main  
2025-01-11 10:30:15 - __main__ - INFO - Workspace validation passed
2025-01-11 10:30:15 - __main__ - INFO - Generated cache key: f3b2c1d4e5a6b7c8
2025-01-11 10:30:15 - __main__ - INFO - Cache path: /home/user/.glovebox/cache/base_deps/f3b2c1d4e5a6b7c8
2025-01-11 10:30:15 - __main__ - INFO - Copying workspace /path/to/my-zmk-config -> /home/user/.glovebox/cache/base_deps/f3b2c1d4e5a6b7c8
2025-01-11 10:30:45 - __main__ - INFO - Successfully copied workspace to cache
2025-01-11 10:30:45 - __main__ - INFO - ✅ Successfully created base dependencies cache!
2025-01-11 10:30:45 - __main__ - INFO - Cache key: f3b2c1d4e5a6b7c8
2025-01-11 10:30:45 - __main__ - INFO - ✅ Cache verification passed
```

#### Requirements

- Python 3.8+
- PyYAML (for parsing `west.yml` files)
- Git (for auto-detection from git repositories)

#### Common Use Cases

##### 1. Migrate Existing ZMK Config Repository
If you have an existing ZMK config repository with dependencies already downloaded:

```bash
cd /path/to/your-zmk-config
west update  # Ensure dependencies are up to date
python /path/to/glovebox/scripts/generate_base_cache.py --workspace .
```

##### 2. Pre-populate Cache for Team
Create a cache entry that can be shared across a development team:

```bash
# Create cache from a reference workspace
python scripts/generate_base_cache.py --workspace /reference/zmk-workspace --verbose

# The cache will be available for all future glovebox compilations
```

##### 3. Multiple ZMK Versions
Create separate cache entries for different ZMK versions:

```bash
# Standard ZMK main branch
python scripts/generate_base_cache.py --workspace /path/to/zmk-main --zmk-repo zmkfirmware/zmk --zmk-revision main

# MoErgo's Glove80 fork
python scripts/generate_base_cache.py --workspace /path/to/glove80-workspace --zmk-repo moergo-sc/zmk --zmk-revision main

# Specific development branch
python scripts/generate_base_cache.py --workspace /path/to/dev-workspace --zmk-repo myorg/zmk --zmk-revision feature-branch
```

##### 4. Test Cache Creation
Before committing to cache creation, preview what would happen:

```bash
python scripts/generate_base_cache.py --workspace /path/to/workspace --dry-run --verbose
```

#### Integration with Glovebox

Once you've created a base cache using this script, it will automatically be used by Glovebox's tiered caching system:

1. **Base Dependencies Cache** ← *Created by this script*
2. **Keyboard Configuration Cache** ← *Built on top of base cache*

This significantly reduces compilation time by reusing shared ZMK dependencies across all keyboard configurations.