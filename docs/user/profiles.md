# Keyboard Profiles Guide

This guide covers how to work with keyboard profiles in Glovebox, which define keyboard hardware specifications and firmware combinations.

## Understanding Profiles

### What Are Profiles?

Profiles combine keyboard hardware specifications with firmware versions to provide complete build configurations. They contain:

- **Keyboard specifications**: Hardware layout, pin mappings, features
- **Firmware configurations**: ZMK versions, build settings, compilation methods
- **Build options**: Docker images, compilation strategies, default settings

### Profile Format

Profiles follow these formats:

```bash
# Full profile: keyboard/firmware
glove80/v25.05    # Glove80 with v25.05 firmware
corne/main        # Corne with main branch firmware

# Keyboard-only: keyboard
glove80           # Glove80 with default firmware
corne             # Corne with default firmware
```

## Viewing Profiles

### List All Profiles

```bash
# List all available profiles
glovebox profile list

# Show only keyboard names
glovebox profile list --keyboards-only

# Verbose profile information
glovebox profile list --verbose

# JSON output for scripting
glovebox profile list --format json
```

### Show Profile Details

```bash
# Show specific profile
glovebox profile show glove80/v25.05

# Show keyboard-only profile
glovebox profile show glove80

# Verbose profile details
glovebox profile show glove80/v25.05 --verbose

# JSON output
glovebox profile show glove80/v25.05 --format json
```

### Firmware Versions

```bash
# List firmware versions for a keyboard
glovebox profile firmwares glove80

# Show specific firmware details
glovebox profile firmware glove80 v25.05

# JSON output
glovebox profile firmwares glove80 --format json
```

## Built-in Profiles

### Glove80 Profiles

MoErgo Glove80 split ergonomic keyboard:

```bash
# Available Glove80 profiles
glove80/v25.05    # Stable release v25.05
glove80/v25.04    # Previous stable release
glove80/main      # Latest main branch
glove80           # Default (currently v25.05)

# Show Glove80 details
glovebox profile show glove80/v25.05
```

**Glove80 Features:**
- 80-key split ergonomic layout
- RGB underglow support
- OLED display support (optional)
- USB-C connectivity
- Nice!Nano v2 controller

### Corne (CRKBD) Profiles

Popular 42-key split keyboard:

```bash
# Available Corne profiles
corne/main        # Latest ZMK main branch
corne/stable      # Stable ZMK release
corne             # Default (main)

# Show Corne details
glovebox profile show corne/main
```

**Corne Features:**
- 42-key split layout
- OLED display support
- RGB underglow support
- Pro Micro/Elite-C compatible

### Lily58 Profiles

58-key split keyboard with number row:

```bash
# Available Lily58 profiles
lily58/main       # Latest ZMK main branch
lily58/stable     # Stable ZMK release
lily58            # Default (main)

# Show Lily58 details
glovebox profile show lily58/main
```

**Lily58 Features:**
- 58-key split layout with number row
- OLED display support
- Rotary encoder support
- Pro Micro compatible

### Planck Profiles

Compact 40% ortholinear keyboard:

```bash
# Available Planck profiles
planck/main       # Latest ZMK main branch
planck/stable     # Stable ZMK release
planck            # Default (main)

# Show Planck details
glovebox profile show planck/main
```

**Planck Features:**
- 47-key ortholinear layout
- Compact 40% form factor
- Multiple controller options

## Setting Default Profile

### Configuration

Set your default profile to avoid specifying it every time:

```bash
# Set default profile
glovebox config edit --set profile=glove80/v25.05

# Set keyboard-only default
glovebox config edit --set profile=glove80

# View current default
glovebox config edit --get profile
```

### Override for Single Commands

```bash
# Use default profile
glovebox layout compile layout.json output/

# Override with specific profile
glovebox layout compile layout.json output/ --profile corne/main

# Override with keyboard-only
glovebox firmware flash firmware.uf2 --profile glove80
```

## Profile Configuration

### View Configuration

```bash
# Show profile configuration
glovebox profile show glove80/v25.05 --verbose

# Show keyboard configuration
glovebox profile show glove80

# Show firmware-specific settings
glovebox profile firmware glove80 v25.05
```

### Edit Profile Settings

```bash
# Edit profile configuration
glovebox profile edit glove80/v25.05 --interactive

# Get specific setting
glovebox profile edit glove80/v25.05 --get build_timeout

# Set specific setting
glovebox profile edit glove80/v25.05 --set build_timeout=600
```

## Custom Profiles

### Creating Custom Profiles

Add custom keyboard or firmware profiles:

```bash
# Add custom profile directory
glovebox config edit --add profiles_paths=/path/to/custom/profiles

# Show profile search paths
glovebox config show | grep profiles_paths
```

### Custom Profile Structure

Create custom profiles with YAML files:

```yaml
# keyboards/my_keyboard.yaml
keyboard: "my_keyboard"
description: "My Custom Keyboard"
layout: "split"
controller: "nice_nano_v2"

# Hardware configuration
hardware:
  rows: 4
  cols: 6
  split: true
  underglow_leds: 12
  
# Build configuration
build:
  strategy: "zmk_west"
  timeout: 300
  docker_image: "zmkfirmware/zmk-build-arm:3.5"

# Available firmware versions
firmwares:
  main:
    version: "main"
    description: "Latest main branch"
    repository: "https://github.com/zmkfirmware/zmk"
    branch: "main"
    
  stable:
    version: "stable"
    description: "Stable release"
    repository: "https://github.com/zmkfirmware/zmk" 
    branch: "v3.5.0"
```

### Using Custom Profiles

```bash
# List custom profiles
glovebox profile list | grep my_keyboard

# Use custom profile
glovebox layout compile layout.json output/ --profile my_keyboard/main

# Show custom profile details
glovebox profile show my_keyboard/main --verbose
```

## Profile Compatibility

### Layout Compatibility

Ensure layouts work with your target profile:

```bash
# Validate layout for profile
glovebox layout validate layout.json --profile glove80/v25.05

# Test layout with multiple profiles
glovebox layout validate layout.json --profile glove80/v25.05
glovebox layout validate layout.json --profile corne/main

# Show profile-specific features
glovebox profile show glove80/v25.05 --features
```

### Feature Support

Different profiles support different features:

```bash
# Glove80 features
glovebox profile show glove80/v25.05 --features
# - RGB underglow
# - OLED display
# - Split layout
# - 80 keys

# Corne features  
glovebox profile show corne/main --features
# - RGB underglow
# - OLED display
# - Split layout
# - 42 keys

# Check feature compatibility
glovebox layout validate layout.json \
  --profile glove80/v25.05 \
  --check-features
```

## Profile-Specific Operations

### Glove80-Specific Operations

```bash
# Compile for Glove80
glovebox layout compile layout.json output/ --profile glove80/v25.05

# Build firmware with RGB support
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --define CONFIG_ZMK_RGB_UNDERGLOW=y

# Flash Glove80 firmware
glovebox firmware flash firmware/glove80_lh.uf2 --profile glove80
glovebox firmware flash firmware/glove80_rh.uf2 --profile glove80
```

### Corne-Specific Operations

```bash
# Compile for Corne
glovebox layout compile layout.json output/ --profile corne/main

# Build with OLED support
glovebox firmware compile layout.json firmware/ \
  --profile corne/main \
  --define CONFIG_ZMK_DISPLAY=y

# Flash Corne firmware
glovebox firmware flash firmware/corne.uf2 --profile corne
```

### Generic ZMK Operations

```bash
# Use generic profiles for unsupported keyboards
glovebox layout compile layout.json output/ \
  --profile generic/main \
  --config my_keyboard.conf
```

## Advanced Profile Features

### Build Strategies

Profiles define different build strategies:

```bash
# ZMK West strategy (default)
glovebox firmware compile layout.json firmware/ \
  --profile corne/main \
  --strategy zmk_west

# MoErgo Nix strategy (Glove80)
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --strategy moergo_nix

# Let profile choose strategy
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05
```

### Docker Configuration

Profiles specify Docker images and settings:

```bash
# Show Docker configuration
glovebox profile show glove80/v25.05 --docker

# Override Docker image
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --docker-image custom/zmk-build:latest
```

### Build Options

Profiles include optimized build settings:

```bash
# Show build options
glovebox profile show glove80/v25.05 --build-options

# Override build timeout
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --timeout 900

# Override parallel jobs
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --jobs 2
```

## Profile Management

### Profile Cache

Profiles are cached for performance:

```bash
# Show profile cache
glovebox cache show --tag profiles

# Clear profile cache
glovebox cache clear --tag profiles

# Refresh profile data
glovebox profile list --refresh
```

### Profile Updates

Keep profiles up to date:

```bash
# Update profile definitions
glovebox profile update

# Check for profile updates
glovebox profile check-updates

# Update specific profile
glovebox profile update glove80
```

### Profile Validation

Ensure profiles are correctly configured:

```bash
# Validate profile
glovebox profile show glove80/v25.05 --validate

# Check profile dependencies
glovebox profile show glove80/v25.05 --check-deps

# Test profile functionality
glovebox profile test glove80/v25.05
```

## Troubleshooting Profiles

### Profile Not Found

```bash
# List available profiles
glovebox profile list

# Check profile name spelling
glovebox profile show glove80/v25.05  # Correct
glovebox profile show glove80/v2505   # Incorrect

# Check custom profile paths
glovebox config show | grep profiles_paths
```

### Profile Loading Issues

```bash
# Verbose profile loading
glovebox profile show glove80/v25.05 --verbose

# Check profile file syntax
glovebox profile validate glove80/v25.05

# Reset profile cache
glovebox cache clear --tag profiles
```

### Build Issues with Profiles

```bash
# Check profile build configuration
glovebox profile show glove80/v25.05 --build

# Test profile with simple layout
glovebox layout compile simple_layout.json output/ \
  --profile glove80/v25.05

# Use verbose build output
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --verbose
```

## Best Practices

### 1. Set Appropriate Defaults

```bash
# Set profile for your main keyboard
glovebox config edit --set profile=glove80/v25.05

# Use keyboard-only for device operations
glovebox firmware devices --profile glove80
```

### 2. Validate Compatibility

```bash
# Always test layouts with target profile
glovebox layout validate layout.json --profile glove80/v25.05

# Check feature compatibility
glovebox profile show glove80/v25.05 --features
```

### 3. Use Specific Firmware Versions

```bash
# Use specific firmware for reproducible builds
glovebox firmware compile layout.json firmware/ --profile glove80/v25.05

# Avoid "latest" for production use
glovebox firmware compile layout.json firmware/ --profile glove80/main  # For testing only
```

### 4. Document Profile Requirements

```bash
# Document layout requirements
echo "# Requires: glove80/v25.05 or later" >> layout.json

# Test with multiple profiles
glovebox layout validate layout.json --profile glove80/v25.05
glovebox layout validate layout.json --profile glove80/v25.04
```

### 5. Keep Profiles Updated

```bash
# Regular profile updates
glovebox profile update

# Check for firmware updates
glovebox config check-updates

# Test new firmware versions
glovebox firmware compile test_layout.json test_firmware/ \
  --profile glove80/main
```

---

*Profiles are central to Glovebox operations. Understanding how to choose, configure, and use profiles will ensure successful builds for your specific keyboard hardware.*