# CLI Reference

Complete reference for all Glovebox CLI commands and options.

## Command Structure

```bash
glovebox [GLOBAL_OPTIONS] COMMAND [COMMAND_OPTIONS] [ARGUMENTS]
```

## Global Options

| Option | Description |
|--------|-------------|
| `--help`, `-h` | Show help message and exit |
| `--version` | Show version information |
| `--verbose`, `-v` | Enable verbose output |
| `--debug` | Enable debug output with stack traces |
| `--config-file PATH` | Use custom configuration file |
| `--profile PROFILE` | Set default profile for session |

## Commands Overview

| Command | Purpose | Key Features |
|---------|---------|--------------|
| [`layout`](#layout-commands) | Layout operations | Compile, edit, diff, patch, split, merge |
| [`firmware`](#firmware-commands) | Firmware operations | Compile, flash, manage builds |
| [`config`](#config-commands) | Configuration management | View, edit, import, export settings |
| [`keyboard`](#keyboard-commands) | Keyboard information | List keyboards, show details, firmwares |
| [`status`](#status-command) | System status | Check installation, dependencies |
| [`cache`](#cache-commands) | Cache management | Clear, stats, maintenance |

## Layout Commands

See the complete [Layout Commands Guide](layout-commands.md) for detailed documentation.

### Quick Reference

```bash
# Compile layout to ZMK files
glovebox layout compile layout.json --output build/ --profile glove80/v25.05

# Compare layouts and create patch
glovebox layout diff new.json old.json --output changes.json --detailed

# Apply patch to layout
glovebox layout patch base.json changes.json --output patched.json

# Edit layout fields
glovebox layout edit layout.json --set title="My Layout" --output modified.json

# Validate layout
glovebox layout validate layout.json --profile glove80/v25.05

# Show layout content
glovebox layout show layout.json --layer 0 --output-format rich-table

# Split layout into components
glovebox layout split layout.json ./components/

# Merge components into layout
glovebox layout merge ./components/ merged.json
```

## Firmware Commands

### compile

Compile ZMK firmware from keymap and config files.

```bash
glovebox firmware compile KEYMAP CONFIG [OPTIONS]
```

**Options:**
- `--output`, `-o PATH` - Output directory for firmware files
- `--profile PROFILE` - Keyboard profile (e.g., 'glove80/v25.05')
- `--force` - Overwrite existing files
- `--output-format FORMAT` - Output format (text|json|table)

**Examples:**
```bash
# Basic compilation
glovebox firmware compile layout.keymap config.conf --profile glove80/v25.05

# Custom output directory
glovebox firmware compile layout.keymap config.conf --output ./firmware/

# Force overwrite
glovebox firmware compile layout.keymap config.conf --force --output ./build/
```

### flash

Flash firmware to keyboard device.

```bash
glovebox firmware flash FIRMWARE [OPTIONS]
```

**Options:**
- `--profile PROFILE` - Keyboard profile for device detection
- `--device PATH` - Specific device path (overrides auto-detection)
- `--timeout SECONDS` - Wait timeout for device detection (default: 30)
- `--force` - Skip confirmations
- `--dry-run` - Show what would be flashed without doing it

**Examples:**
```bash
# Auto-detect device and flash
glovebox firmware flash firmware.uf2 --profile glove80

# Specify device manually
glovebox firmware flash firmware.uf2 --device /dev/sdb

# Wait longer for device
glovebox firmware flash firmware.uf2 --profile glove80 --timeout 60
```

## Config Commands

### list

Show current configuration with optional details.

```bash
glovebox config list [OPTIONS]
```

**Options:**
- `--defaults` - Show default values alongside current values
- `--descriptions` - Include parameter descriptions
- `--sources` - Show configuration sources
- `--format FORMAT` - Output format (text|json|yaml|table)

**Examples:**
```bash
# Basic configuration list
glovebox config list

# Complete information
glovebox config list --defaults --descriptions --sources

# JSON output
glovebox config list --format json
```

### edit

Unified configuration editing with multiple operations.

```bash
glovebox config edit [OPTIONS]
```

**Options:**
- `--get KEY [KEY...]` - Get configuration values
- `--set KEY=VALUE [KEY=VALUE...]` - Set configuration values
- `--add KEY=VALUE [KEY=VALUE...]` - Add values to list configurations
- `--remove KEY=VALUE [KEY=VALUE...]` - Remove values from list configurations
- `--save / --no-save` - Control whether changes are persisted (default: --save)

**Examples:**
```bash
# Get values
glovebox config edit --get cache_strategy --get emoji_mode

# Set values
glovebox config edit --set cache_strategy=shared --set emoji_mode=true

# Multiple operations
glovebox config edit \
  --get cache_strategy \
  --set emoji_mode=true \
  --add keyboard_paths=/new/path \
  --remove keyboard_paths=/old/path \
  --save
```

### export

Export configuration to file.

```bash
glovebox config export [FILE] [OPTIONS]
```

**Options:**
- `--format FORMAT` - Export format (json|yaml|toml)
- `--include-defaults` - Include default values in export
- `--exclude-secrets` - Exclude sensitive values

**Examples:**
```bash
# Export to YAML
glovebox config export config.yaml --format yaml

# Include defaults
glovebox config export config.json --include-defaults

# To stdout
glovebox config export --format json
```

### import

Import configuration from file.

```bash
glovebox config import FILE [OPTIONS]
```

**Options:**
- `--merge` - Merge with existing configuration (default: replace)
- `--dry-run` - Show what would be imported without applying
- `--force` - Overwrite existing values without confirmation

**Examples:**
```bash
# Import with preview
glovebox config import config.yaml --dry-run

# Merge configuration
glovebox config import config.yaml --merge

# Force import
glovebox config import config.yaml --force
```

## Keyboard Commands

### list

List available keyboards.

```bash
glovebox keyboard list [OPTIONS]
```

**Options:**
- `--verbose` - Show detailed keyboard information
- `--format FORMAT` - Output format (text|json|table)

**Examples:**
```bash
# Basic list
glovebox keyboard list

# Detailed information
glovebox keyboard list --verbose

# JSON output
glovebox keyboard list --format json
```

### show

Show detailed information about a specific keyboard.

```bash
glovebox keyboard show KEYBOARD [OPTIONS]
```

**Options:**
- `--verbose` - Include all configuration details
- `--format FORMAT` - Output format (text|json|yaml|table)

**Examples:**
```bash
# Show keyboard details
glovebox keyboard show glove80

# Complete details in JSON
glovebox keyboard show glove80 --verbose --format json
```

### firmwares

List available firmware versions for a keyboard.

```bash
glovebox keyboard firmwares KEYBOARD [OPTIONS]
```

**Options:**
- `--format FORMAT` - Output format (text|json|table)

**Examples:**
```bash
# List firmware versions
glovebox keyboard firmwares glove80

# JSON output
glovebox keyboard firmwares glove80 --format json
```

## Status Command

Show system status and health checks.

```bash
glovebox status [OPTIONS]
```

**Options:**
- `--profile PROFILE` - Check specific profile components
- `--verbose` - Include detailed diagnostic information
- `--format FORMAT` - Output format (text|json|table)

**Examples:**
```bash
# Basic status
glovebox status

# Profile-specific checks
glovebox status --profile glove80/v25.05

# Detailed diagnostics
glovebox status --verbose --format json
```

## Cache Commands

### clear

Clear cache data.

```bash
glovebox cache clear [OPTIONS]
```

**Options:**
- `--tag TAG` - Clear specific cache tag (compilation|metrics|layout|cli_completion)
- `--all` - Clear all cache data
- `--older-than DAYS` - Clear cache older than specified days

**Examples:**
```bash
# Clear all cache
glovebox cache clear --all

# Clear specific tag
glovebox cache clear --tag compilation

# Clear old cache
glovebox cache clear --older-than 7
```

### stats

Show cache statistics.

```bash
glovebox cache stats [OPTIONS]
```

**Options:**
- `--tag TAG` - Show stats for specific tag
- `--format FORMAT` - Output format (text|json|table)

**Examples:**
```bash
# Overall stats
glovebox cache stats

# Specific tag stats
glovebox cache stats --tag compilation

# JSON format
glovebox cache stats --format json
```

## Environment Variables

Glovebox respects these environment variables:

| Variable | Purpose | Example |
|----------|---------|---------|
| `GLOVEBOX_JSON_FILE` | Default layout file | `export GLOVEBOX_JSON_FILE=my-layout.json` |
| `GLOVEBOX_PROFILE` | Default profile | `export GLOVEBOX_PROFILE=glove80/v25.05` |
| `GLOVEBOX_CONFIG_FILE` | Custom config file | `export GLOVEBOX_CONFIG_FILE=~/.my-glovebox.yml` |
| `GLOVEBOX_CACHE_DIR` | Cache directory | `export GLOVEBOX_CACHE_DIR=~/.cache/glovebox` |
| `GLOVEBOX_DEBUG` | Enable debug mode | `export GLOVEBOX_DEBUG=1` |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid command line arguments |
| 3 | Configuration error |
| 4 | File not found |
| 5 | Permission denied |
| 10 | Compilation error |
| 11 | Validation error |
| 20 | Device not found |
| 21 | Flash error |

## Output Formats

All commands support consistent output formats:

### text (default)
Human-readable formatted output with colors and symbols.

### json
Structured JSON output suitable for scripting and automation.

### yaml
YAML formatted output, useful for configuration files.

### table
Simple table format without colors.

### rich-table
Rich colored table with borders and styling.

### rich-panel
Rich panel format with borders and titles.

### rich-grid
Rich grid layout for complex data.

## Common Patterns

### Environment Setup
```bash
# Set up environment for session
export GLOVEBOX_JSON_FILE=my-layout.json
export GLOVEBOX_PROFILE=glove80/v25.05

# Now commands work without specifying files
glovebox layout validate
glovebox layout compile --output build/
glovebox firmware flash build/firmware.uf2
```

### Scripting and Automation
```bash
# Use JSON output for scripting
if glovebox layout validate layout.json --format json | jq -r '.valid'; then
    glovebox layout compile layout.json --output build/
fi

# Batch operations
for layout in layouts/*.json; do
    glovebox layout validate "$layout" --format json > "${layout%.json}.validation.json"
done
```

### Development Workflow
```bash
# Complete development cycle
glovebox layout edit layout.json --set version="2.0-dev"
glovebox layout validate layout.json
glovebox layout compile layout.json --output build/dev/
glovebox firmware flash build/dev/firmware.uf2 --profile glove80
```

### Debugging
```bash
# Debug mode with stack traces
glovebox --debug layout compile layout.json --output build/

# Verbose output
glovebox --verbose firmware flash firmware.uf2 --profile glove80

# Dry run to see what would happen
glovebox firmware flash firmware.uf2 --profile glove80 --dry-run
```

## Tips and Best Practices

### Performance
- Use `--format json` for scripting to avoid formatting overhead
- Set `GLOVEBOX_CACHE_DIR` to fast storage for better performance
- Use environment variables to avoid repeating common parameters

### Error Handling
- Always check exit codes in scripts
- Use `--dry-run` to preview destructive operations
- Enable debug mode when troubleshooting: `glovebox --debug`

### Configuration Management
- Use `glovebox config export` to backup configurations
- Version control your configuration files
- Use profiles to manage different keyboards/setups

### Security
- Use `--exclude-secrets` when sharing configuration exports
- Be careful with `--force` options in scripts
- Review `--dry-run` output before actual operations

This CLI reference provides the foundation for all Glovebox operations. For detailed examples and workflows, see the specific command guides.