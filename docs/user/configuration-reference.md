# Configuration Reference

This reference covers all Glovebox configuration options, their formats, and usage examples.

## Configuration File Format

Glovebox uses YAML configuration files with the following structure:

```yaml
# ~/.config/glovebox/config.yaml
profile: "glove80/v25.05"
cache_strategy: "shared"
icon_mode: "text"
log_level: "INFO"

# Additional settings...
```

## Core Configuration Options

### Default Profile

Sets the default keyboard and firmware combination.

**Field**: `profile`  
**Type**: `string`  
**Default**: `"glove80/v25.05"`  
**Format**: `"keyboard[/firmware]"`

```yaml
# Full profile (keyboard/firmware)
profile: "glove80/v25.05"

# Keyboard-only profile (uses default firmware)
profile: "glove80"

# Other examples
profile: "corne/main"
profile: "lily58/stable"
```

**CLI Configuration**:
```bash
# Set full profile
glovebox config edit --set profile=glove80/v25.05

# Set keyboard-only
glovebox config edit --set profile=glove80

# Get current profile
glovebox config edit --get profile
```

**Environment Variable**: `GLOVEBOX_PROFILE`

### Custom Profile Paths

Additional directories to search for keyboard and firmware profiles.

**Field**: `profiles_paths`  
**Type**: `list[string]`  
**Default**: `[]`

```yaml
profiles_paths:
  - "/home/user/custom-keyboards"
  - "/opt/keyboard-profiles"
  - "~/my-keyboards"
```

**CLI Configuration**:
```bash
# Add custom path
glovebox config edit --add profiles_paths=/path/to/custom/profiles

# Remove path
glovebox config edit --remove profiles_paths=/old/path

# List current paths
glovebox config edit --get profiles_paths
```

**Environment Variable**: `GLOVEBOX_PROFILES_PATHS` (comma-separated)

## Logging Configuration

### Log Level

Global logging verbosity level.

**Field**: `log_level`  
**Type**: `string`  
**Default**: `"INFO"`  
**Valid Values**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

```yaml
log_level: "INFO"      # Normal operation
log_level: "DEBUG"     # Detailed debugging
log_level: "WARNING"   # Only warnings and errors
```

**CLI Configuration**:
```bash
glovebox config edit --set log_level=DEBUG
```

**Environment Variable**: `GLOVEBOX_LOG_LEVEL`

### Advanced Logging Configuration

**Field**: `logging_config`  
**Type**: `object`  
**Default**: Default logging configuration

```yaml
logging_config:
  handlers:
    console:
      level: "INFO"
      format: "simple"
      enabled: true
    file:
      level: "DEBUG"
      format: "detailed"
      enabled: false
      filename: "glovebox.log"
      max_bytes: 10485760  # 10MB
      backup_count: 5
  loggers:
    glovebox:
      level: "INFO"
    urllib3:
      level: "WARNING"
```

**Console Handler Options**:
- `level`: Log level for console output
- `format`: `"simple"`, `"detailed"`, `"minimal"`
- `enabled`: Enable/disable console logging

**File Handler Options**:
- `level`: Log level for file output
- `format`: Log format style
- `enabled`: Enable/disable file logging
- `filename`: Log file name (relative to config directory)
- `max_bytes`: Maximum log file size before rotation
- `backup_count`: Number of backup files to keep

## Cache Configuration

### Cache Strategy

Controls how build caching operates.

**Field**: `cache_strategy`  
**Type**: `string`  
**Default**: `"shared"`  
**Valid Values**: `"shared"`, `"disabled"`

```yaml
cache_strategy: "shared"     # Enable shared caching (recommended)
cache_strategy: "disabled"   # Disable all caching
```

**CLI Configuration**:
```bash
glovebox config edit --set cache_strategy=shared
```

**Environment Variable**: `GLOVEBOX_CACHE_STRATEGY`

### Cache Directory

Location for storing cache data.

**Field**: `cache_path`  
**Type**: `string`  
**Default**: `"$XDG_CACHE_HOME/glovebox"` or `"~/.cache/glovebox"`

```yaml
cache_path: "~/.cache/glovebox"
cache_path: "/tmp/glovebox-cache"
cache_path: "$HOME/glovebox-cache"
```

**CLI Configuration**:
```bash
glovebox config edit --set cache_path=~/my-glovebox-cache
```

**Environment Variable**: `GLOVEBOX_CACHE_PATH`

### Cache TTL Configuration

Time-to-live settings for different cache types.

**Field**: `cache_ttls`  
**Type**: `object`  
**Default**: See below

```yaml
cache_ttls:
  compilation: 3600      # 1 hour
  metrics: 1800          # 30 minutes  
  profiles: 7200         # 2 hours
  library: 86400         # 1 day
  workspaces: 604800     # 1 week
  docker_images: 259200  # 3 days
```

**CLI Configuration**:
```bash
# Set specific TTL (in seconds)
glovebox config edit --set cache_ttls.compilation=7200

# Get current TTLs
glovebox config edit --get cache_ttls
```

**Environment Variables**:
- `GLOVEBOX_CACHE_TTLS__COMPILATION`
- `GLOVEBOX_CACHE_TTLS__METRICS`
- `GLOVEBOX_CACHE_TTLS__PROFILES`
- etc.

## User Interface Configuration

### Icon Mode

Controls icon display style in CLI output.

**Field**: `icon_mode`  
**Type**: `string`  
**Default**: `"emoji"`  
**Valid Values**: `"emoji"`, `"nerdfont"`, `"text"`

```yaml
icon_mode: "emoji"      # 🔧 (colorful emojis)
icon_mode: "nerdfont"   # \uf2db (nerd font icons)
icon_mode: "text"       # ✓ (ASCII/Unicode text)
```

**CLI Configuration**:
```bash
glovebox config edit --set icon_mode=text
```

**Environment Variable**: `GLOVEBOX_ICON_MODE`

### Editor

Default text editor for interactive configuration editing.

**Field**: `editor`  
**Type**: `string`  
**Default**: `$EDITOR` environment variable or `"nano"`

```yaml
editor: "vim"
editor: "code"
editor: "nano"
editor: "emacs"
```

**CLI Configuration**:
```bash
glovebox config edit --set editor=vim
```

**Environment Variable**: `GLOVEBOX_EDITOR`

## Version and Update Configuration

### Disable Version Checks

Controls automatic version checking for updates.

**Field**: `disable_version_checks`  
**Type**: `boolean`  
**Default**: `false`

```yaml
disable_version_checks: false   # Enable version checks
disable_version_checks: true    # Disable version checks
```

**CLI Configuration**:
```bash
glovebox config edit --set disable_version_checks=true
```

**Environment Variable**: `GLOVEBOX_DISABLE_VERSION_CHECKS`

## Firmware Configuration

### Firmware Settings

**Field**: `firmware`  
**Type**: `object`  
**Default**: See below

```yaml
firmware:
  use_docker: true
  docker_timeout: 300
  default_strategy: "auto"
  parallel_builds: true
  max_build_jobs: 4
```

**Options**:
- `use_docker`: Enable Docker-based builds
- `docker_timeout`: Build timeout in seconds
- `default_strategy`: `"auto"`, `"zmk_west"`, `"moergo_nix"`
- `parallel_builds`: Enable parallel compilation
- `max_build_jobs`: Maximum parallel jobs

**CLI Configuration**:
```bash
glovebox config edit --set firmware.use_docker=true
glovebox config edit --set firmware.docker_timeout=600
```

**Environment Variables**:
- `GLOVEBOX_FIRMWARE__USE_DOCKER`
- `GLOVEBOX_FIRMWARE__DOCKER_TIMEOUT`

## Library Configuration

### Library Path

Directory for storing downloaded layout libraries.

**Field**: `library_path`  
**Type**: `string`  
**Default**: `"$XDG_DATA_HOME/glovebox/library"` or `"~/.local/share/glovebox/library"`

```yaml
library_path: "~/.local/share/glovebox/library"
library_path: "~/keyboard-layouts"
library_path: "/opt/glovebox/library"
```

**CLI Configuration**:
```bash
glovebox config edit --set library_path=~/keyboard-layouts
```

**Environment Variable**: `GLOVEBOX_LIBRARY_PATH`

## MoErgo Service Configuration

### MoErgo Integration

**Field**: `moergo`  
**Type**: `object`  
**Default**: See below

```yaml
moergo:
  enabled: true
  cache_layouts: true
  api_timeout: 30
  max_retries: 3
  credential_storage: "keyring"
```

**Options**:
- `enabled`: Enable MoErgo service integration
- `cache_layouts`: Cache downloaded layouts
- `api_timeout`: API request timeout in seconds
- `max_retries`: Maximum retry attempts for failed requests
- `credential_storage`: Credential storage method

**CLI Configuration**:
```bash
glovebox config edit --set moergo.enabled=true
glovebox config edit --set moergo.cache_layouts=false
```

## Filename Template Configuration

### Template Settings

**Field**: `filename_templates`  
**Type**: `object`  
**Default**: See below

```yaml
filename_templates:
  keymap_template: "{name}.keymap"
  config_template: "{name}.conf"
  firmware_template: "{keyboard}_{side}.uf2"
  layout_backup_template: "{name}_{timestamp}.json"
```

**Template Variables**:
- `{name}`: Layout name
- `{keyboard}`: Keyboard name
- `{firmware}`: Firmware version
- `{side}`: Side (for split keyboards): `lh`, `rh`
- `{timestamp}`: Current timestamp
- `{version}`: Layout version
- `{title}`: Layout title

**CLI Configuration**:
```bash
glovebox config edit --set filename_templates.keymap_template="{title}_{keyboard}.keymap"
```

## Environment Variable Reference

All configuration options can be set via environment variables using the `GLOVEBOX_` prefix:

### Basic Variables
```bash
export GLOVEBOX_PROFILE="glove80/v25.05"
export GLOVEBOX_CACHE_STRATEGY="shared"
export GLOVEBOX_ICON_MODE="text"
export GLOVEBOX_LOG_LEVEL="DEBUG"
export GLOVEBOX_EDITOR="vim"
```

### Path Variables
```bash
export GLOVEBOX_CACHE_PATH="/tmp/glovebox-cache"
export GLOVEBOX_LIBRARY_PATH="~/keyboard-layouts"
export GLOVEBOX_PROFILES_PATHS="/path1,/path2,/path3"
```

### Complex Variables (using double underscore)
```bash
export GLOVEBOX_CACHE_TTLS__COMPILATION="7200"
export GLOVEBOX_FIRMWARE__USE_DOCKER="true"
export GLOVEBOX_FIRMWARE__DOCKER_TIMEOUT="600"
export GLOVEBOX_MOERGO__ENABLED="true"
```

## Configuration Validation

### Validation Commands
```bash
# Validate current configuration
glovebox config show --validate

# Check specific settings
glovebox config edit --get profile
glovebox config edit --get cache_strategy

# Show configuration with sources
glovebox config show --sources
```

### Common Validation Errors

#### Invalid Profile Format
```yaml
# ❌ Invalid
profile: "glove80-v25.05"    # Wrong separator
profile: "/v25.05"           # Missing keyboard
profile: "glove80/"          # Missing firmware

# ✅ Valid
profile: "glove80/v25.05"    # Full profile
profile: "glove80"           # Keyboard-only
```

#### Invalid Log Level
```yaml
# ❌ Invalid
log_level: "VERBOSE"         # Not a valid level
log_level: "info"            # Must be uppercase

# ✅ Valid
log_level: "INFO"            # Correct format
log_level: "DEBUG"           # Valid level
```

#### Invalid Cache Strategy
```yaml
# ❌ Invalid
cache_strategy: "enabled"    # Not a valid strategy
cache_strategy: "memory"     # Not supported

# ✅ Valid
cache_strategy: "shared"     # Recommended
cache_strategy: "disabled"   # Valid option
```

## Configuration Examples

### Minimal Configuration
```yaml
# Minimal setup for basic usage
profile: "glove80/v25.05"
cache_strategy: "shared"
icon_mode: "text"
```

### Development Configuration
```yaml
# Development setup with debug logging
profile: "glove80/main"
log_level: "DEBUG"
cache_strategy: "disabled"
disable_version_checks: true

firmware:
  docker_timeout: 900
  
logging_config:
  handlers:
    console:
      level: "DEBUG"
      format: "detailed"
    file:
      level: "DEBUG"
      enabled: true
```

### Production Configuration
```yaml
# Production setup with caching and optimizations
profile: "glove80/v25.05"
cache_strategy: "shared"
icon_mode: "text"
log_level: "WARNING"

cache_ttls:
  compilation: 7200
  workspaces: 604800

firmware:
  use_docker: true
  docker_timeout: 300
  parallel_builds: true

moergo:
  enabled: true
  cache_layouts: true
```

### Multi-User Configuration
```yaml
# Configuration for shared systems
profiles_paths:
  - "/opt/glovebox/profiles"
  - "/usr/local/share/glovebox/profiles"

cache_path: "/var/cache/glovebox"
library_path: "/opt/glovebox/library"

cache_strategy: "shared"
cache_ttls:
  compilation: 14400  # 4 hours for shared cache
```

## Troubleshooting Configuration

### Reset Configuration
```bash
# Backup current configuration
cp ~/.config/glovebox/config.yaml ~/.config/glovebox/config.yaml.bak

# Reset to defaults
rm ~/.config/glovebox/config.yaml
glovebox config show  # Recreates with defaults
```

### Debug Configuration Loading
```bash
# Show configuration with sources
glovebox config show --sources

# Show environment variables
env | grep GLOVEBOX_

# Test specific settings
glovebox config edit --get profile --verbose
```

### Fix Common Issues
```bash
# Fix permission issues
chmod 644 ~/.config/glovebox/config.yaml
chmod 755 ~/.config/glovebox/

# Fix YAML syntax
python -c "import yaml; yaml.safe_load(open('~/.config/glovebox/config.yaml'))"

# Validate configuration
glovebox config show --validate
```

---

*This reference covers all available configuration options. Use `glovebox config show` to see your current configuration and `glovebox config edit --help` for editing commands.*