# Configuration Guide

This guide covers how to configure Glovebox for your setup, including user settings, profiles, and advanced options.

## Configuration Overview

Glovebox uses a hierarchical configuration system:

1. **Environment variables** (highest priority)
2. **User configuration file** 
3. **Profile configurations**
4. **Default values** (lowest priority)

## Configuration File Location

Your configuration is stored at:
- **Linux/macOS**: `~/.config/glovebox/config.yaml`
- **Windows**: `%APPDATA%\glovebox\config.yaml`

## Viewing Configuration

### Show Current Configuration
```bash
# Show all configuration values
glovebox config show

# Show with defaults and descriptions
glovebox config show --defaults --descriptions

# Show configuration sources
glovebox config show --sources

# Show everything
glovebox config show --defaults --descriptions --sources
```

### Show Specific Values
```bash
# Get single value
glovebox config edit --get profile

# Get multiple values
glovebox config edit --get profile,cache_strategy,icon_mode
```

## Editing Configuration

### Interactive Editing
```bash
# Open configuration in your default editor
glovebox config edit

# Use specific editor
EDITOR=vim glovebox config edit

# Interactive configuration wizard
glovebox config edit --interactive
```

### Command-Line Editing
```bash
# Set single value
glovebox config edit --set profile=glove80/v25.05

# Set multiple values
glovebox config edit \
  --set profile=glove80/v25.05 \
  --set cache_strategy=shared \
  --set icon_mode=text

# Add to list values
glovebox config edit --add profiles_paths=/path/to/custom/profiles

# Remove from list values
glovebox config edit --remove profiles_paths=/old/path
```

## Core Configuration Options

### Default Profile
Set your default keyboard and firmware combination:

```bash
# Full profile (keyboard/firmware)
glovebox config edit --set profile=glove80/v25.05

# Keyboard-only profile (uses default firmware)
glovebox config edit --set profile=glove80
```

### Cache Settings
Configure build caching for faster compilation:

```bash
# Cache strategy (shared or disabled)
glovebox config edit --set cache_strategy=shared

# Cache location
glovebox config edit --set cache_path=~/glovebox-cache

# Cache TTL settings (advanced)
glovebox config edit --set cache_ttls.compilation=3600
```

### UI and Display
Customize the interface appearance:

```bash
# Icon mode (emoji, nerdfont, text)
glovebox config edit --set icon_mode=text

# Default editor for interactive editing
glovebox config edit --set editor=vim
```

### Logging
Configure logging verbosity and format:

```bash
# Global log level
glovebox config edit --set log_level=INFO

# Disable version checks
glovebox config edit --set disable_version_checks=true
```

## Advanced Configuration

### Custom Profile Paths
Add custom keyboard and firmware profiles:

```bash
# Add custom profile directory
glovebox config edit --add profiles_paths=/path/to/custom/keyboards

# Add multiple paths
glovebox config edit \
  --add profiles_paths=/path/to/keyboards \
  --add profiles_paths=/path/to/firmwares
```

### Library Configuration
Configure layout library settings:

```bash
# Library storage path
glovebox config edit --set library_path=~/keyboard-layouts

# MoErgo service settings (for library integration)
glovebox config edit --set moergo.enabled=true
```

### Firmware Settings
Configure firmware building options:

```bash
# Docker settings for firmware building
glovebox config edit --set firmware.use_docker=true
glovebox config edit --set firmware.docker_timeout=300
```

### Filename Templates
Customize output file naming:

```bash
# Edit filename templates
glovebox config edit --set filename_templates.keymap_template="{name}_{keyboard}.keymap"
glovebox config edit --set filename_templates.config_template="{name}_{keyboard}.conf"
```

## Environment Variables

All configuration options can be set via environment variables using the `GLOVEBOX_` prefix:

```bash
# Profile setting
export GLOVEBOX_PROFILE=glove80/v25.05

# Cache settings
export GLOVEBOX_CACHE_STRATEGY=shared
export GLOVEBOX_CACHE_PATH=/tmp/glovebox-cache

# UI settings
export GLOVEBOX_ICON_MODE=text
export GLOVEBOX_LOG_LEVEL=DEBUG

# Complex settings with double underscore
export GLOVEBOX_FIRMWARE__USE_DOCKER=true
export GLOVEBOX_CACHE_TTLS__COMPILATION=7200
```

## Profile-Specific Configuration

### Viewing Profile Configuration
```bash
# List all profiles
glovebox profile list

# Show profile details
glovebox profile show glove80/v25.05

# Show keyboard-only profile
glovebox profile show glove80

# Show firmware options for keyboard
glovebox profile firmwares glove80
```

### Profile Configuration Files
Profiles are stored in:
- **Built-in profiles**: `glovebox/config/keyboards/`
- **Custom profiles**: Paths from `profiles_paths` setting

## Cache Configuration

### Cache Strategies
```bash
# Shared cache (recommended)
glovebox config edit --set cache_strategy=shared

# Disable caching
glovebox config edit --set cache_strategy=disabled
```

### Cache TTL Configuration
Fine-tune cache expiration times:

```bash
# Compilation cache (seconds)
glovebox config edit --set cache_ttls.compilation=3600

# Metrics cache
glovebox config edit --set cache_ttls.metrics=1800

# Profile cache
glovebox config edit --set cache_ttls.profiles=7200

# Library cache
glovebox config edit --set cache_ttls.library=86400
```

### Cache Management
```bash
# Show cache status
glovebox cache show

# Clear all caches
glovebox cache clear

# Clear specific cache
glovebox cache clear --tag compilation

# Show cache size
glovebox cache show --verbose
```

## Configuration Examples

### Minimal Configuration
```yaml
# ~/.config/glovebox/config.yaml
profile: "glove80/v25.05"
icon_mode: "text"
cache_strategy: "shared"
```

### Advanced Configuration
```yaml
# ~/.config/glovebox/config.yaml
profile: "glove80/v25.05"
profiles_paths:
  - "/home/user/custom-keyboards"
  - "/opt/keyboard-profiles"

cache_strategy: "shared"
cache_path: "/home/user/.cache/glovebox"
cache_ttls:
  compilation: 7200
  metrics: 3600
  profiles: 14400

icon_mode: "text"
log_level: "INFO"
editor: "vim"

firmware:
  use_docker: true
  docker_timeout: 600

library_path: "/home/user/keyboard-layouts"

filename_templates:
  keymap_template: "{title}_{keyboard}_{version}.keymap"
  config_template: "{title}_{keyboard}_{version}.conf"
  firmware_template: "{keyboard}_{side}_{version}.uf2"

moergo:
  enabled: true
  cache_layouts: true
```

### Development Configuration
```yaml
# Development setup
profile: "glove80/main"
log_level: "DEBUG"
cache_strategy: "disabled"  # For testing
disable_version_checks: true

firmware:
  use_docker: true
  docker_timeout: 900
  
logging:
  handlers:
    console:
      level: "DEBUG"
      format: "detailed"
```

## Configuration Validation

### Check Configuration
```bash
# Validate current configuration
glovebox config show --validate

# Check specific profile
glovebox profile show glove80/v25.05 --validate

# System diagnostics
glovebox status --verbose
```

### Fix Common Issues
```bash
# Reset to defaults
glovebox config edit --reset

# Fix cache issues
glovebox cache clear
glovebox config edit --set cache_strategy=shared

# Update profile paths
glovebox config edit --set profiles_paths=/correct/path
```

## Configuration Backup and Restore

### Backup Configuration
```bash
# Export current configuration
glovebox config show --format yaml > glovebox-config-backup.yaml

# Or copy file directly
cp ~/.config/glovebox/config.yaml glovebox-config-backup.yaml
```

### Restore Configuration
```bash
# Restore from backup
cp glovebox-config-backup.yaml ~/.config/glovebox/config.yaml

# Verify restoration
glovebox config show
```

## Per-Project Configuration

### Project-Local Settings
Create a `.glovebox.yaml` file in your project directory:

```yaml
# .glovebox.yaml (project-local)
profile: "corne/main"
cache_strategy: "shared"
```

### Environment-Specific Settings
```bash
# Development environment
export GLOVEBOX_PROFILE=glove80/main
export GLOVEBOX_LOG_LEVEL=DEBUG

# Production environment  
export GLOVEBOX_PROFILE=glove80/v25.05
export GLOVEBOX_LOG_LEVEL=INFO
```

## Troubleshooting Configuration

### Common Issues

#### Invalid Profile
```bash
# Check available profiles
glovebox profile list

# Set valid profile
glovebox config edit --set profile=glove80/v25.05
```

#### Cache Issues
```bash
# Clear and reset cache
glovebox cache clear
glovebox config edit --set cache_strategy=shared
```

#### Permission Issues
```bash
# Check config file permissions
ls -la ~/.config/glovebox/config.yaml

# Fix permissions if needed
chmod 644 ~/.config/glovebox/config.yaml
```

#### Path Issues
```bash
# Check path expansion
glovebox config show | grep path

# Use absolute paths
glovebox config edit --set cache_path=/full/path/to/cache
```

### Reset Configuration
```bash
# Reset to defaults (CAUTION: removes all custom settings)
rm ~/.config/glovebox/config.yaml
glovebox config show  # Recreates with defaults
```

## Next Steps

After configuring Glovebox:

1. **[Keyboard Profiles](profiles.md)** - Set up keyboard-specific profiles
2. **[Layout Commands](layout-commands.md)** - Start working with layouts
3. **[Cache Management](cache-management.md)** - Optimize build performance
4. **[Workflows](workflows.md)** - Learn common usage patterns

---

*Your Glovebox configuration controls how the tool behaves. Take time to set it up for your specific workflow and preferences.*