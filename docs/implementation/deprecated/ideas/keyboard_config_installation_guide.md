# Keyboard Configuration Installation Guide

## Quick Start

Glovebox makes it easy to install and manage keyboard configurations from various sources. Whether you're installing a community keyboard configuration or managing your own custom configs, this guide will get you started.

### Prerequisites

- Glovebox installed and configured
- Basic familiarity with the `glovebox config` commands

### Basic Installation

```bash
# Install from a local file
glovebox config install ./my_keyboard.yaml

# Install from a URL
glovebox config install https://raw.githubusercontent.com/user/repo/corne-v3.yaml

# List all available keyboards (including installed)
glovebox config list --all

# Use installed keyboard in a profile
glovebox layout compile input.json output/ --profile corne-v3/stable
```

## Installation Sources

Glovebox supports installing keyboard configurations from multiple sources:

### 1. Local Files

Install configuration files from your local filesystem:

```bash
# Install with automatic name detection
glovebox config install ./keyboards/corne-v3.yaml

# Install with custom name
glovebox config install ./my_board.yaml --name experimental_corne

# Install and validate before installation
glovebox config install ./keyboard.yaml --validate
```

**Use cases:**
- Installing configurations you've developed locally
- Installing configurations downloaded manually
- Testing configurations before sharing

### 2. URLs (Direct Download)

Install configurations directly from web URLs:

```bash
# Install from GitHub raw URL
glovebox config install https://raw.githubusercontent.com/splitkb/keyboards/main/corne.yaml

# Install from any HTTPS URL
glovebox config install https://example.com/keyboards/lily58.yaml

# Install with custom name
glovebox config install https://example.com/config.yaml --name my_lily58
```

**Supported URL types:**
- GitHub raw URLs (`raw.githubusercontent.com`)
- GitLab raw URLs
- Any HTTPS URL serving YAML content
- Direct download links from keyboard vendors

### 3. Git Repositories (Future)

Install configurations from Git repositories:

```bash
# Install from Git repository
glovebox config install --repo https://github.com/user/keyboards --keyboard corne-v3

# Install specific version/tag
glovebox config install --repo https://github.com/user/keyboards --keyboard corne-v3 --tag v1.2.0

# Install from specific branch
glovebox config install --repo https://github.com/user/keyboards --keyboard corne-v3 --branch experimental
```

### 4. Registry (Future)

Install from the community registry:

```bash
# Install latest version from registry
glovebox config install --registry corne-v3

# Install specific version
glovebox config install --registry corne-v3@1.2.0

# Search and install
glovebox config search "split keyboard"
glovebox config install --registry splitkb/corne-v3
```

## Installation Options

### Basic Options

```bash
# Install with custom name
glovebox config install source.yaml --name my_custom_name

# Force overwrite existing configuration
glovebox config install source.yaml --name existing_board --force

# Validate configuration before installing
glovebox config install source.yaml --validate

# Install to specific location (future)
glovebox config install source.yaml --location user|project|system
```

### Validation Options

```bash
# Validate without installing
glovebox config validate ./keyboard.yaml

# Strict validation (require all optional fields)
glovebox config validate ./keyboard.yaml --strict

# Validate and show detailed report
glovebox config validate ./keyboard.yaml --verbose
```

## Managing Installed Configurations

### Listing Configurations

```bash
# List all keyboards (built-in and installed)
glovebox config list --all

# List only installed keyboards
glovebox config list --installed

# List only built-in keyboards
glovebox config list --available

# JSON output for scripting
glovebox config list --all --format json
```

### Viewing Configuration Details

```bash
# Show keyboard details
glovebox config show-keyboard corne-v3

# Show firmware options
glovebox config firmwares corne-v3

# Show specific firmware details
glovebox config firmware corne-v3 stable

# JSON output
glovebox config show-keyboard corne-v3 --format json
```

### Removing Configurations

```bash
# Remove installed configuration
glovebox config remove corne-v3

# Force removal (skip confirmation)
glovebox config remove corne-v3 --force

# Remove multiple configurations
glovebox config remove corne-v3 lily58 planck
```

**Note:** Only user-installed configurations can be removed. Built-in configurations are protected.

## Validation and Safety

### Configuration Validation

Glovebox automatically validates all configurations during installation:

**Required sections:**
- `keyboard` - Keyboard identifier
- `description` - Human-readable description
- `vendor` - Manufacturer or creator
- `key_count` - Number of keys
- `flash` - Flash configuration
- `build` - Build configuration

**Optional sections:**
- `firmwares` - Firmware configurations
- `keymap` - Keymap settings and behaviors
- `version` - Configuration version
- `homepage` - Documentation URL
- `repository` - Source repository

### Validation Examples

```bash
# Basic validation
glovebox config validate ./my_keyboard.yaml
✓ Configuration is valid
✓ All required sections present
✓ Flash configuration valid
✓ Build configuration valid
⚠ No firmware configurations defined (keyboard-only mode)

# Strict validation
glovebox config validate ./my_keyboard.yaml --strict
✗ Missing optional field: version
✗ Missing optional field: homepage
✗ No firmware configurations defined

# Detailed validation report
glovebox config validate ./my_keyboard.yaml --verbose
Configuration: my_keyboard.yaml
├── ✓ keyboard: "my_custom_board"
├── ✓ description: "Custom split keyboard"
├── ✓ vendor: "Community"
├── ✓ key_count: 52
├── ✓ flash: mass_storage (valid)
├── ✓ build: docker (valid)
├── ⚠ firmwares: none (keyboard-only mode)
└── ✓ keymap: valid
```

### Safety Features

**Backup Protection:**
- Configurations are backed up before overwriting
- Built-in configurations cannot be modified
- Installation metadata tracks all changes

**Source Verification:**
- URLs are validated before download
- File integrity checks (when available)
- User confirmation for external sources

**Isolation:**
- Installed configurations stored in user directories only
- No system-wide modifications
- No root privileges required

## Working with Profiles

Once installed, keyboard configurations work seamlessly with Glovebox profiles:

### Creating Profiles

```bash
# Use installed keyboard with firmware
glovebox layout compile input.json output/ --profile corne-v3/stable

# Keyboard-only profile (no firmware specified)
glovebox status --profile corne-v3

# Flash firmware with installed keyboard profile
glovebox firmware flash firmware.uf2 --profile corne-v3/stable
```

### Profile Discovery

```bash
# List available profiles (includes installed keyboards)
glovebox config list --all

# Show profile details
glovebox config show-keyboard corne-v3

# List firmware options for installed keyboard
glovebox config firmwares corne-v3
```

## Common Use Cases

### 1. Installing Community Keyboards

Install popular community keyboard configurations:

```bash
# Corne keyboard from splitkb
glovebox config install https://raw.githubusercontent.com/splitkb/keyboards/main/corne.yaml

# Lily58 from community repo
glovebox config install https://raw.githubusercontent.com/kata0510/lily58/main/glovebox.yaml

# Planck from QMK community
glovebox config install https://example.com/keyboards/planck.yaml --name planck-community
```

### 2. Managing Development Configurations

Work with configurations during development:

```bash
# Install development version
glovebox config install ./dev/my_keyboard.yaml --name my_keyboard_dev

# Validate before committing
glovebox config validate ./keyboards/production.yaml --strict

# Update development configuration
glovebox config remove my_keyboard_dev
glovebox config install ./dev/my_keyboard.yaml --name my_keyboard_dev

# Use in development workflow
glovebox layout compile test_layout.json output/ --profile my_keyboard_dev/experimental
```

### 3. Sharing Configurations

Share your keyboard configurations with others:

```bash
# Validate before sharing
glovebox config validate ./my_custom_keyboard.yaml --strict

# Test installation process
glovebox config install ./my_custom_keyboard.yaml --name test_install

# Share via URL (after uploading to GitHub/GitLab)
# Users can install with:
# glovebox config install https://raw.githubusercontent.com/yourname/keyboards/main/your_keyboard.yaml
```

### 4. Managing Multiple Keyboard Variants

Handle different versions of the same keyboard:

```bash
# Install different variants
glovebox config install ./corne_basic.yaml --name corne_basic
glovebox config install ./corne_rgb.yaml --name corne_rgb
glovebox config install ./corne_oled.yaml --name corne_oled

# List all variants
glovebox config list --installed

# Use specific variant
glovebox layout compile layout.json output/ --profile corne_rgb/stable
```

## Troubleshooting

### Common Installation Issues

#### Configuration Not Found After Installation

```bash
# Check installation status
glovebox config list --installed

# Verify configuration file exists
ls ~/.config/glovebox/keyboards/

# Check installation metadata
cat ~/.config/glovebox/installed.json
```

#### Validation Errors

```bash
# Common validation error: Missing required fields
✗ Missing required field: flash.method

# Solution: Ensure all required sections are present
flash:
  method: "mass_storage"
  query: "vendor=Example"
  usb_vid: "0x1234"
  usb_pid: "0x5678"
```

```bash
# Common validation error: Invalid YAML syntax
✗ YAML parsing error: mapping values are not allowed here

# Solution: Check YAML formatting with proper indentation
```

#### Download Issues

```bash
# Network connectivity issues
✗ Failed to download: Connection timeout

# Solution: Check internet connection and URL accessibility
curl -I https://raw.githubusercontent.com/user/repo/keyboard.yaml
```

```bash
# Invalid URL or 404 errors
✗ Failed to download: HTTP 404 Not Found

# Solution: Verify URL is correct and file exists
```

#### Name Conflicts

```bash
# Configuration already exists
✗ Configuration 'corne-v3' already exists

# Solutions:
# 1. Use different name
glovebox config install source.yaml --name corne-v3-custom

# 2. Force overwrite
glovebox config install source.yaml --name corne-v3 --force

# 3. Remove existing first
glovebox config remove corne-v3
glovebox config install source.yaml --name corne-v3
```

### Debug Information

Enable debug output for troubleshooting:

```bash
# Enable debug logging
glovebox --debug config install ./keyboard.yaml

# Check configuration search paths
glovebox --debug config list

# Validate with detailed output
glovebox config validate ./keyboard.yaml --verbose
```

### Getting Help

```bash
# Get help for config commands
glovebox config --help

# Get help for specific command
glovebox config install --help
glovebox config validate --help

# Check system status
glovebox status
```

## File Locations

Understanding where configurations are stored:

### Installation Directories

```bash
# User-installed configurations
~/.config/glovebox/keyboards/
├── corne-v3.yaml
├── lily58.yaml
└── custom_board.yaml

# Installation metadata
~/.config/glovebox/installed.json

# User configuration
~/.config/glovebox/config.yaml

# Built-in configurations (read-only)
<glovebox-package>/keyboards/
├── glove80.yaml
└── kingston_test.yaml
```

### Search Order

Glovebox searches for configurations in this order:

1. **Built-in configurations** - Package `keyboards/` directory
2. **User-installed configurations** - `~/.config/glovebox/keyboards/`
3. **Environment paths** - `GLOVEBOX_KEYBOARD_PATH` variable
4. **User-defined paths** - From configuration files

### Environment Variables

```bash
# Additional keyboard search paths
export GLOVEBOX_KEYBOARD_PATH="/project/keyboards:/shared/keyboards"

# XDG config directory override
export XDG_CONFIG_HOME="/custom/config"
# Results in: /custom/config/glovebox/keyboards/
```

## Best Practices

### Configuration Management

1. **Validate before installing**
   ```bash
   glovebox config validate ./keyboard.yaml
   glovebox config install ./keyboard.yaml
   ```

2. **Use descriptive names**
   ```bash
   # Good
   glovebox config install source.yaml --name corne-v3-rgb-rotary

   # Avoid
   glovebox config install source.yaml --name kb1
   ```

3. **Back up important configurations**
   ```bash
   # Copy configurations before major changes
   cp ~/.config/glovebox/keyboards/my_custom.yaml ./backup/
   ```

### Development Workflow

1. **Use development naming**
   ```bash
   glovebox config install ./dev.yaml --name my_keyboard_dev
   # Work with development version
   glovebox config remove my_keyboard_dev
   glovebox config install ./dev.yaml --name my_keyboard_dev
   ```

2. **Validate frequently**
   ```bash
   # Include validation in your development script
   #!/bin/bash
   glovebox config validate ./my_keyboard.yaml --strict
   if [ $? -eq 0 ]; then
       glovebox config install ./my_keyboard.yaml --name my_keyboard_dev --force
   fi
   ```

3. **Test with real layouts**
   ```bash
   # Test configuration with actual layout compilation
   glovebox layout compile test_layout.json output/ --profile my_keyboard_dev/stable
   ```

### Sharing and Distribution

1. **Include complete metadata**
   ```yaml
   keyboard: "my_awesome_keyboard"
   description: "Custom 40% split ortholinear keyboard"
   vendor: "Your Name"
   version: "1.0.0"
   homepage: "https://github.com/yourname/keyboard-configs"
   repository: "https://github.com/yourname/keyboard-configs"
   license: "MIT"
   ```

2. **Provide installation instructions**
   ```markdown
   ## Installation
   
   Install this keyboard configuration with:
   
   ```bash
   glovebox config install https://raw.githubusercontent.com/yourname/keyboards/main/my_keyboard.yaml
   ```

3. **Version your configurations**
   - Use semantic versioning in the `version` field
   - Tag releases in your Git repository
   - Document changes between versions

This installation guide provides comprehensive coverage of keyboard configuration management in Glovebox, from basic installation to advanced troubleshooting and best practices.