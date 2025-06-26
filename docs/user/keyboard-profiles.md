# Keyboard Profiles

This guide explains how Glovebox uses keyboard profiles to manage different keyboards and firmware configurations.

## What are Profiles?

Profiles in Glovebox define the combination of keyboard hardware and firmware configuration needed for compilation and flashing operations.

### Profile Format

```bash
# Full profile: keyboard + firmware version
{keyboard}/{firmware_version}

# Examples:
glove80/v25.05
corne/main
lily58/bluetooth

# Keyboard-only profile: just hardware definition
{keyboard}

# Examples:
glove80
corne
lily58
```

## Profile Types

### Full Profiles (Keyboard + Firmware)

Used for compilation operations that need both hardware and firmware information:

```bash
# Compile with full profile
glovebox layout compile layout.json --profile glove80/v25.05

# Validate with firmware context
glovebox layout validate layout.json --profile glove80/v25.05
```

### Keyboard-Only Profiles

Used for operations that only need hardware information:

```bash
# Flash firmware (only needs device detection info)
glovebox firmware flash firmware.uf2 --profile glove80

# Show keyboard details
glovebox keyboard show glove80
```

## Available Keyboards

### List All Keyboards

```bash
# Basic list
glovebox keyboard list

# Detailed information
glovebox keyboard list --verbose

# JSON format
glovebox keyboard list --format json
```

### Keyboard Details

```bash
# Show keyboard specifications
glovebox keyboard show glove80

# Complete configuration details
glovebox keyboard show glove80 --verbose --format yaml
```

## Available Firmware Versions

### List Firmware Versions

```bash
# Show available firmware versions for a keyboard
glovebox keyboard firmwares glove80

# JSON output
glovebox keyboard firmwares glove80 --format json
```

### Firmware Information

Each firmware version includes:
- **Repository**: Source code repository
- **Branch/Tag**: Specific version or branch
- **Build Configuration**: Compilation settings
- **Supported Features**: Available ZMK features

## Profile Resolution

Glovebox resolves profiles using this precedence order:

1. **CLI `--profile` flag** (highest priority)
2. **Auto-detection from JSON keyboard field** (unless `--no-auto`)
3. **`GLOVEBOX_PROFILE` environment variable**
4. **`default_profile` in user configuration**
5. **Hardcoded fallback profile** (lowest priority)

### Auto-Detection

Glovebox can automatically detect the appropriate profile from your layout JSON file:

```json
{
  "keyboard": "glove80",
  "title": "My Layout",
  "layers": [...]
}
```

```bash
# Auto-detects glove80 profile from JSON
glovebox layout compile layout.json --output build/

# Disable auto-detection
glovebox layout compile layout.json --no-auto --profile glove80/v25.05
```

### Setting Defaults

```bash
# Set default profile in configuration
glovebox config edit --set default_profile=glove80/v25.05

# Use environment variable
export GLOVEBOX_PROFILE=glove80/v25.05
```

## Supported Keyboards

### Glove80

**Hardware:**
- Split ergonomic keyboard
- 80 keys total (40 per half)
- Hot-swappable switches
- RGB underglow
- OLED displays

**Profiles:**
```bash
# Available firmware versions
glovebox keyboard firmwares glove80

# Common profiles
glove80/v25.05    # Latest stable
glove80/main      # Development branch
glove80/v24.12    # Previous stable
```

**Example Usage:**
```bash
# Compile for Glove80
glovebox layout compile my-glove80.json --profile glove80/v25.05

# Flash to Glove80
glovebox firmware flash glove80.uf2 --profile glove80
```

### Corne (CRKBD)

**Hardware:**
- Split keyboard
- 42 keys total (21 per half)
- Compact columnar layout
- Optional OLED and RGB

**Profiles:**
```bash
# Available firmware versions
glovebox keyboard firmwares corne

# Common profiles
corne/main        # Standard ZMK
corne/bluetooth   # Bluetooth optimized
corne/nice_nano   # Nice!Nano controller
```

**Example Usage:**
```bash
# Compile for Corne
glovebox layout compile corne-layout.json --profile corne/main

# Flash to Corne
glovebox firmware flash corne.uf2 --profile corne
```

### Adding Custom Keyboards

See [Custom Keyboards Guide](custom-keyboards.md) for detailed instructions on adding new keyboard support.

## Profile Configuration

### Keyboard Configuration Structure

Each keyboard profile is defined by configuration files:

```yaml
# keyboards/glove80/main.yaml
keyboard: "glove80"
description: "MoErgo Glove80 split ergonomic keyboard"

# Hardware specifications
hardware:
  layout: "split_80"
  key_count: 80
  matrix: "10x8"
  controller: "nice_nano_v2"

# Device detection
usb:
  vendor_id: "0x1d50"
  product_id: "0x615e"
  manufacturer: "MoErgo"
  product: "Glove80"

# Flash detection patterns
flash_patterns:
  - "/dev/disk/by-label/GLOVE80*"
  - "/Volumes/GLOVE80*"
  - "D:\\GLOVE80*"

# Include firmware configurations
includes:
  - "firmwares.yaml"
  - "behaviors.yaml"
  - "kconfig.yaml"
```

### Firmware Configuration

```yaml
# keyboards/glove80/firmwares.yaml
firmwares:
  v25.05:
    type: "moergo"
    repository: "https://github.com/moergo-sc/zmk.git"
    branch: "v25.05"
    
    build_matrix:
      board: ["glove80_lh", "glove80_rh"]
      shield: []
    
    features:
      - "bluetooth"
      - "usb"
      - "split"
      - "oled"
      - "rgb_underglow"
  
  main:
    type: "zmk_config"
    repository: "https://github.com/zmkfirmware/zmk.git"
    branch: "main"
    
    build_matrix:
      board: ["nice_nano_v2"]
      shield: ["glove80_lh", "glove80_rh"]
```

## Working with Profiles

### Profile Testing

```bash
# Test profile compilation
glovebox layout compile test-layout.json --profile glove80/v25.05 --dry-run

# Validate profile configuration
glovebox status --profile glove80/v25.05

# Check profile compatibility
glovebox keyboard show glove80 --verbose
```

### Profile Debugging

```bash
# Debug profile resolution
glovebox --debug layout compile layout.json --profile glove80/v25.05

# Check auto-detection
glovebox layout compile layout.json --verbose

# Verify firmware availability
glovebox keyboard firmwares glove80
```

## Profile Best Practices

### Development Workflow

```bash
# Set up development environment
export GLOVEBOX_PROFILE=glove80/v25.05
export GLOVEBOX_JSON_FILE=~/layouts/development.json

# Now commands use defaults
glovebox layout validate
glovebox layout compile --output build/dev/
```

### Multiple Keyboards

```bash
# Organize by keyboard type
~/layouts/
├── glove80/
│   ├── gaming.json
│   ├── coding.json
│   └── default.json
├── corne/
│   ├── minimal.json
│   └── full.json
└── shared/
    └── common-macros.json

# Use appropriate profiles
glovebox layout compile layouts/glove80/gaming.json --profile glove80/v25.05
glovebox layout compile layouts/corne/minimal.json --profile corne/main
```

### Configuration Management

```yaml
# ~/.glovebox/config.yml

# Default profile for most work
default_profile: "glove80/v25.05"

# Keyboard-specific settings
keyboards:
  glove80:
    default_firmware: "v25.05"
    layout_path: "~/layouts/glove80"
    
  corne:
    default_firmware: "main"
    layout_path: "~/layouts/corne"
```

## Profile Troubleshooting

### Common Issues

**Profile not found:**
```bash
# Check available keyboards
glovebox keyboard list

# Check available firmware versions
glovebox keyboard firmwares glove80

# Use correct profile format
glovebox layout compile layout.json --profile glove80/v25.05
```

**Auto-detection failure:**
```bash
# Check JSON keyboard field
jq '.keyboard' layout.json

# Disable auto-detection and specify manually
glovebox layout compile layout.json --no-auto --profile glove80/v25.05
```

**Compilation issues:**
```bash
# Verify profile configuration
glovebox status --profile glove80/v25.05 --verbose

# Check firmware repository access
glovebox keyboard show glove80 --verbose

# Try different firmware version
glovebox layout compile layout.json --profile glove80/main
```

**Device detection problems:**
```bash
# Check device patterns
glovebox keyboard show glove80

# Verify device is connected
glovebox firmware flash firmware.uf2 --profile glove80 --verbose

# Manual device specification
glovebox firmware flash firmware.uf2 --device /dev/sdb
```

### Diagnostic Commands

```bash
# Complete system check
glovebox status --verbose

# Profile-specific diagnostics
glovebox status --profile glove80/v25.05 --verbose

# Keyboard configuration details
glovebox keyboard show glove80 --verbose --format json

# Test profile compilation
glovebox layout validate test.json --profile glove80/v25.05
```

## Advanced Profile Features

### Custom Build Matrices

Some profiles support custom build matrices for specialized builds:

```yaml
# Custom build configuration
firmwares:
  custom:
    type: "zmk_config"
    repository: "https://github.com/myuser/custom-zmk.git"
    branch: "custom-features"
    
    build_matrix:
      board: ["nice_nano_v2"]
      shield: ["custom_keyboard_left", "custom_keyboard_right"]
      
    kconfig:
      - "CONFIG_ZMK_SLEEP=y"
      - "CONFIG_ZMK_IDLE_TIMEOUT=300000"
```

### Profile Inheritance

Profiles can inherit from base configurations:

```yaml
# Base configuration
base_profile: &base
  type: "zmk_config"
  repository: "https://github.com/zmkfirmware/zmk.git"
  
# Specific versions inherit base settings
firmwares:
  stable:
    <<: *base
    branch: "main"
    
  beta:
    <<: *base
    branch: "beta"
```

### Environment-Specific Profiles

```bash
# Development profile with debugging
export GLOVEBOX_PROFILE=glove80/dev

# Production profile with optimizations
export GLOVEBOX_PROFILE=glove80/v25.05

# Testing profile with experimental features
export GLOVEBOX_PROFILE=glove80/experimental
```

Understanding and properly configuring keyboard profiles is essential for getting the most out of Glovebox. Profiles ensure that your keyboard layouts are compiled with the correct hardware definitions and firmware features for your specific setup.