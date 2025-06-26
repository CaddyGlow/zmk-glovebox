# User Configuration

This guide covers how to configure Glovebox for your specific needs, including profiles, paths, caching, and personal preferences.

## Configuration Overview

Glovebox uses a hierarchical configuration system with multiple sources:

1. **Command line arguments** (highest priority)
2. **Environment variables**
3. **User configuration file** (`~/.glovebox/config.yml`)
4. **Default values** (lowest priority)

## Configuration File

### Default Location

```bash
~/.glovebox/config.yml
```

### Custom Location

```bash
# Set custom config file location
export GLOVEBOX_CONFIG_FILE=~/my-custom-glovebox.yml

# Or use command line option
glovebox --config-file ~/my-custom-glovebox.yml [command]
```

## Core Configuration Options

### Basic Settings

```yaml
# ~/.glovebox/config.yml

# Default profile for operations
default_profile: "glove80/v25.05"

# Default JSON layout file
default_json_file: "~/layouts/main-layout.json"

# Enable emoji output in CLI
emoji_mode: true

# Cache strategy
cache_strategy: "shared"  # shared, isolated, disabled

# Maximum cache size in GB
max_cache_size_gb: 2

# Debug logging level
log_level: "INFO"  # DEBUG, INFO, WARNING, ERROR
```

### Path Configuration

```yaml
# Additional keyboard configuration paths
keyboard_paths:
  - "~/custom-keyboards"
  - "/usr/local/share/glovebox/keyboards"

# Layout file search paths
layout_paths:
  - "~/layouts"
  - "~/Documents/keyboard-layouts"

# Build output directory
build_output_dir: "~/glovebox-builds"

# Cache directory (optional - uses system default if not set)
cache_dir: "~/.cache/glovebox"
```

### Docker Configuration

```yaml
# Docker settings for compilation
docker:
  # Docker image for ZMK compilation
  zmk_image: "zmkfirmware/zmk-build-arm:stable"
  
  # Custom Docker registry
  registry: "docker.io"
  
  # Docker build timeout in seconds
  build_timeout: 1800
  
  # Enable Docker BuildKit
  buildkit: true
  
  # Volume mount strategy
  volume_strategy: "bind"  # bind, tmpfs, volume
```

### Compilation Settings

```yaml
# Compilation preferences
compilation:
  # Default compilation strategy
  strategy: "zmk_west"  # zmk_west, moergo_nix
  
  # Parallel build jobs
  parallel_jobs: 4
  
  # Keep intermediate files
  keep_intermediate: false
  
  # West workspace settings
  west:
    # Default ZMK repository
    repository: "https://github.com/zmkfirmware/zmk.git"
    branch: "main"
    
  # MoErgo Nix settings
  moergo:
    repository: "https://github.com/moergo-sc/zmk.git"
    branch: "v25.05"
```

### Firmware Flashing

```yaml
# Firmware flashing settings
flashing:
  # Default wait timeout for device detection (seconds)
  device_timeout: 30
  
  # Auto-confirm flashing operations
  auto_confirm: false
  
  # Preferred device detection method
  detection_method: "auto"  # auto, udev, polling
  
  # Custom device patterns (regex)
  device_patterns:
    - "/dev/disk/by-label/GLOVE80.*"
    - "/dev/disk/by-label/NICENANO.*"
```

## Configuration Management

### View Current Configuration

```bash
# Show current configuration
glovebox config list

# Include default values
glovebox config list --defaults

# Show configuration sources and descriptions
glovebox config list --defaults --descriptions --sources

# JSON output for scripting
glovebox config list --format json
```

### Edit Configuration

```bash
# Get specific values
glovebox config edit --get default_profile --get cache_strategy

# Set values
glovebox config edit --set default_profile=glove80/v25.05 --set emoji_mode=true

# Add to list values
glovebox config edit --add keyboard_paths=~/my-keyboards

# Remove from list values
glovebox config edit --remove keyboard_paths=~/old-keyboards

# Multiple operations in one command
glovebox config edit \
  --get cache_strategy \
  --set emoji_mode=true \
  --add keyboard_paths=/new/path \
  --remove keyboard_paths=/old/path
```

### Export and Import

```bash
# Export current configuration
glovebox config export config-backup.yml --format yaml --include-defaults

# Export to JSON
glovebox config export config.json --format json

# Import configuration
glovebox config import config.yml --dry-run  # Preview first
glovebox config import config.yml --merge    # Merge with existing

# Force import (replace existing)
glovebox config import config.yml --force
```

## Environment Variables

### Core Variables

```bash
# Default profile
export GLOVEBOX_PROFILE=glove80/v25.05

# Default JSON file
export GLOVEBOX_JSON_FILE=~/layouts/main.json

# Custom config file
export GLOVEBOX_CONFIG_FILE=~/.my-glovebox.yml

# Cache directory
export GLOVEBOX_CACHE_DIR=~/.cache/glovebox

# Enable debug mode
export GLOVEBOX_DEBUG=1

# Log level
export GLOVEBOX_LOG_LEVEL=DEBUG
```

### Docker Variables

```bash
# Docker configuration
export DOCKER_HOST=unix:///var/run/docker.sock
export DOCKER_BUILDKIT=1

# Custom ZMK image
export GLOVEBOX_ZMK_IMAGE=custom/zmk-build:latest
```

### Path Variables

```bash
# Additional keyboard paths (colon-separated)
export GLOVEBOX_KEYBOARD_PATHS=~/keyboards:/usr/local/keyboards

# Layout search paths
export GLOVEBOX_LAYOUT_PATHS=~/layouts:~/Documents/keyboards
```

## Profile Configuration

### Understanding Profiles

Profiles combine keyboard hardware definitions with firmware configurations:

```bash
# Full profile: keyboard + firmware version
glove80/v25.05

# Keyboard-only profile: just hardware (for flashing)
glove80
```

### Setting Default Profile

```yaml
# In config file
default_profile: "glove80/v25.05"
```

```bash
# Via environment
export GLOVEBOX_PROFILE=glove80/v25.05

# Via command
glovebox config edit --set default_profile=glove80/v25.05
```

### Profile Auto-Detection

Glovebox can auto-detect profiles from layout JSON files:

```yaml
# Disable auto-detection
auto_detect_profile: false

# Profile detection precedence:
# 1. CLI --profile flag
# 2. Auto-detection from JSON (if enabled)
# 3. GLOVEBOX_PROFILE environment variable
# 4. default_profile in config file
# 5. Hardcoded fallback
```

## Advanced Configuration

### Cache Configuration

```yaml
cache:
  # Cache strategy
  strategy: "shared"  # shared, isolated, disabled
  
  # Maximum cache size in GB
  max_size_gb: 2
  
  # Cache timeout in seconds
  timeout: 30
  
  # Auto-cleanup old cache entries
  auto_cleanup: true
  
  # Cleanup threshold (% of max size)
  cleanup_threshold: 80
  
  # Tag-specific settings
  tags:
    compilation:
      max_size_gb: 1.5
      ttl: 86400  # 24 hours
    
    cli_completion:
      max_size_gb: 0.1
      ttl: 300    # 5 minutes
```

### Logging Configuration

```yaml
logging:
  # Log level
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  
  # Log format
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  
  # Log file (optional)
  file: "~/.glovebox/glovebox.log"
  
  # Rotate log files
  rotate: true
  max_size: "10MB"
  backup_count: 5
  
  # Debug-specific settings
  debug:
    # Show stack traces for errors
    show_traceback: true
    
    # Include debug info in exception logs
    exception_debug_info: true
```

### Display Configuration

```yaml
display:
  # Enable emoji in output
  emoji_mode: true
  
  # Color output
  use_colors: true
  
  # Rich formatting
  rich_formatting: true
  
  # Default output format
  default_format: "text"  # text, json, yaml, table, rich-table
  
  # Table formatting
  table:
    max_width: 120
    show_lines: true
    
  # Progress bars
  progress_bars: true
```

## Example Configurations

### Minimal Configuration

```yaml
# ~/.glovebox/config.yml
default_profile: "glove80/v25.05"
emoji_mode: true
cache_strategy: "shared"
```

### Developer Configuration

```yaml
# ~/.glovebox/config.yml
default_profile: "glove80/v25.05"
default_json_file: "~/dev/keyboard-layouts/main.json"

# Development settings
emoji_mode: true
cache_strategy: "shared"
max_cache_size_gb: 5
log_level: "DEBUG"

# Custom paths
keyboard_paths:
  - "~/dev/custom-keyboards"
  - "~/dev/zmk-keyboards"
layout_paths:
  - "~/dev/keyboard-layouts"
  - "~/dev/test-layouts"

# Build settings
build_output_dir: "~/dev/builds"
compilation:
  parallel_jobs: 8
  keep_intermediate: true
  
# Docker settings for development
docker:
  build_timeout: 3600  # 1 hour for complex builds
  buildkit: true

# Flashing settings
flashing:
  device_timeout: 60
  auto_confirm: false  # Always confirm in development
```

### Multi-Keyboard Configuration

```yaml
# ~/.glovebox/config.yml
default_profile: "glove80/v25.05"

# Support multiple keyboards
keyboard_paths:
  - "~/keyboards/glove80"
  - "~/keyboards/corne"
  - "~/keyboards/lily58"

# Organized layout paths
layout_paths:
  - "~/layouts/glove80"
  - "~/layouts/corne"
  - "~/layouts/shared"

# Efficient caching for multiple builds
cache_strategy: "shared"
max_cache_size_gb: 5

# Custom device patterns for different keyboards
flashing:
  device_patterns:
    - "/dev/disk/by-label/GLOVE80.*"
    - "/dev/disk/by-label/CORNE.*"
    - "/dev/disk/by-label/LILY58.*"
    - "/dev/disk/by-label/NICENANO.*"
```

### CI/CD Configuration

```yaml
# ~/.glovebox/config.yml
# Optimized for automated builds

# Disable interactive features
emoji_mode: false
use_colors: false
rich_formatting: false

# Efficient caching
cache_strategy: "shared"
max_cache_size_gb: 10

# Logging for CI
log_level: "INFO"
logging:
  format: "%(levelname)s: %(message)s"
  
# Fast builds
compilation:
  parallel_jobs: 16
  keep_intermediate: false

# Docker optimizations
docker:
  build_timeout: 1800
  buildkit: true
  volume_strategy: "tmpfs"  # Faster in CI

# Auto-confirm for CI
flashing:
  auto_confirm: true
```

## Configuration Validation

### Validate Current Configuration

```bash
# Check configuration validity
glovebox config validate

# Detailed validation with suggestions
glovebox config validate --verbose

# JSON output for automated checks
glovebox config validate --format json
```

### Common Configuration Issues

**Invalid profile:**
```bash
# Check available profiles
glovebox keyboard list
glovebox keyboard firmwares glove80

# Fix profile in config
glovebox config edit --set default_profile=glove80/v25.05
```

**Path issues:**
```bash
# Check if paths exist
glovebox status --verbose

# Fix paths
glovebox config edit --set keyboard_paths=~/existing/path
```

**Docker issues:**
```bash
# Test Docker connectivity
docker version

# Check Docker image
docker pull zmkfirmware/zmk-build-arm:stable
```

## Migration and Upgrades

### Upgrading Configuration

When upgrading Glovebox, your configuration may need updates:

```bash
# Backup current configuration
glovebox config export config-backup-$(date +%Y%m%d).yml

# Check for configuration updates after upgrade
glovebox status --verbose

# Update configuration if needed
glovebox config edit --set new_option=value
```

### Configuration Schema Changes

Glovebox handles configuration migrations automatically, but you can:

```bash
# Check for deprecated options
glovebox config validate --check-deprecated

# Update to new format
glovebox config migrate --dry-run  # Preview changes
glovebox config migrate            # Apply changes
```

This user configuration guide provides complete control over your Glovebox installation, allowing you to customize behavior for your specific workflow and hardware setup.