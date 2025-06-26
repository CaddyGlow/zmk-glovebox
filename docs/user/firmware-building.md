# Firmware Building

This guide covers building ZMK firmware from layouts and keymap files using Glovebox.

## Overview

Glovebox provides two main paths for firmware building:

1. **Layout to Firmware**: Compile JSON layout files directly to firmware
2. **Keymap to Firmware**: Compile ZMK keymap and config files to firmware

Both paths use the same underlying ZMK compilation system with Docker containers for consistent, reproducible builds.

## Quick Start

### From Layout File

```bash
# One-step: layout JSON to firmware
glovebox layout compile layout.json --output build/firmware --profile glove80/v25.05

# This creates:
# build/firmware.keymap  - ZMK keymap file
# build/firmware.conf    - ZMK config file
# build/firmware.uf2     - Compiled firmware (if Docker available)
```

### From Keymap Files

```bash
# Two-step: keymap files to firmware
glovebox firmware compile layout.keymap config.conf --profile glove80/v25.05
```

## Layout to Firmware Workflow

### Complete Workflow

```bash
# 1. Start with a layout JSON file
glovebox layout validate my-layout.json --profile glove80/v25.05

# 2. Compile layout to ZMK files and firmware
glovebox layout compile my-layout.json \
  --output build/my-layout \
  --profile glove80/v25.05

# 3. Flash firmware to keyboard
glovebox firmware flash build/my-layout.uf2 --profile glove80
```

### Environment Setup

```bash
# Set defaults for convenience
export GLOVEBOX_JSON_FILE=~/layouts/main-layout.json
export GLOVEBOX_PROFILE=glove80/v25.05

# Now commands can omit file and profile
glovebox layout validate
glovebox layout compile --output build/current
glovebox firmware flash build/current.uf2 --profile glove80
```

### Compilation Options

```bash
# Basic compilation
glovebox layout compile layout.json --output build/firmware --profile glove80/v25.05

# Force overwrite existing files
glovebox layout compile layout.json --output build/firmware --profile glove80/v25.05 --force

# Disable auto-profile detection
glovebox layout compile layout.json --output build/firmware --no-auto --profile glove80/v25.05

# JSON output for automation
glovebox layout compile layout.json --output build/firmware --profile glove80/v25.05 --output-format json
```

## Keymap to Firmware Workflow

### Direct Compilation

```bash
# Compile existing keymap and config files
glovebox firmware compile my-layout.keymap my-config.conf --profile glove80/v25.05

# Specify output directory
glovebox firmware compile layout.keymap config.conf \
  --output build/custom-firmware \
  --profile glove80/v25.05

# Force overwrite
glovebox firmware compile layout.keymap config.conf \
  --profile glove80/v25.05 \
  --force
```

### Working with Custom Keymaps

```bash
# If you have manually created or modified keymap files
glovebox firmware compile custom.keymap custom.conf --profile glove80/v25.05

# Validate keymap syntax first (if validation tools available)
# Then compile
glovebox firmware compile validated.keymap config.conf --profile glove80/v25.05
```

## Compilation Profiles

### Profile Selection

Different keyboards and firmware versions require specific compilation profiles:

```bash
# Glove80 with MoErgo firmware
glovebox layout compile layout.json --profile glove80/v25.05

# Glove80 with upstream ZMK
glovebox layout compile layout.json --profile glove80/main

# Corne with standard ZMK
glovebox layout compile corne-layout.json --profile corne/main

# Check available profiles
glovebox keyboard list
glovebox keyboard firmwares glove80
```

### Profile Auto-Detection

```json
{
  "keyboard": "glove80",
  "title": "My Layout",
  "layers": [...]
}
```

```bash
# Auto-detects glove80 profile from JSON
glovebox layout compile layout.json --output build/auto

# Disable auto-detection
glovebox layout compile layout.json --no-auto --profile glove80/v25.05
```

## Build Configuration

### Compilation Strategies

Glovebox supports multiple compilation strategies:

```bash
# ZMK West workspace (default)
glovebox config edit --set compilation.strategy=zmk_west

# MoErgo Nix-based compilation
glovebox config edit --set compilation.strategy=moergo_nix

# Check current strategy
glovebox config list | grep strategy
```

### Build Performance

```yaml
# ~/.glovebox/config.yml
compilation:
  # Use multiple CPU cores
  parallel_jobs: 8
  
  # Keep intermediate files for debugging
  keep_intermediate: false

# Docker settings
docker:
  # Build timeout (30 minutes)
  build_timeout: 1800
  
  # Enable BuildKit for faster builds
  buildkit: true
```

### Caching

```bash
# Enable shared caching for faster rebuilds
glovebox config edit --set cache_strategy=shared

# Check cache status
glovebox cache stats

# Clear compilation cache if needed
glovebox cache clear --tag compilation
```

## Docker Configuration

### Docker Requirements

Firmware compilation requires Docker for ZMK builds:

```bash
# Check Docker status
docker version
docker info

# Test Docker access
docker run hello-world

# Pull ZMK build image
docker pull zmkfirmware/zmk-build-arm:stable
```

### Docker Settings

```yaml
# ~/.glovebox/config.yml
docker:
  # ZMK build image
  zmk_image: "zmkfirmware/zmk-build-arm:stable"
  
  # Custom registry if needed
  registry: "docker.io"
  
  # Build timeout (30 minutes)
  build_timeout: 1800
  
  # Enable BuildKit
  buildkit: true
  
  # Volume strategy
  volume_strategy: "bind"  # bind, tmpfs, volume
```

### Docker Troubleshooting

```bash
# Check Docker connectivity
glovebox status --verbose

# Manual image pull
docker pull zmkfirmware/zmk-build-arm:stable

# Check available space
docker system df

# Clean up if needed
docker system prune
```

## Output Files

### Generated Files

When compiling layouts, Glovebox generates:

```
build/
├── layout.keymap    # ZMK Device Tree keymap
├── layout.conf      # ZMK Kconfig configuration
└── layout.uf2       # Compiled firmware binary (if Docker available)
```

### File Descriptions

**`.keymap` file:**
- ZMK Device Tree Source (DTS) format
- Contains key bindings, behaviors, and layout structure
- Human-readable but follows strict syntax rules

**`.conf` file:**
- ZMK Kconfig options
- Enables/disables firmware features
- Simple KEY=value format

**`.uf2` file:**
- Compiled firmware binary
- Ready to flash to keyboard
- Generated only if Docker compilation succeeds

### Custom Output Naming

```bash
# Default naming (uses input filename)
glovebox layout compile my-layout.json --output build/

# Creates: build/my-layout.keymap, build/my-layout.conf, build/my-layout.uf2

# Custom prefix
glovebox layout compile layout.json --output build/gaming-layout

# Creates: build/gaming-layout.keymap, build/gaming-layout.conf, build/gaming-layout.uf2

# Directory structure
glovebox layout compile layout.json --output keyboards/glove80/v2/main

# Creates: keyboards/glove80/v2/main.keymap, etc.
```

## Advanced Features

### Custom Behaviors

Layout JSON files can include custom ZMK behaviors:

```json
{
  "keyboard": "glove80",
  "title": "Custom Layout",
  
  "custom_defined_behaviors": "#define CUSTOM_BEHAVIOR ...",
  "custom_devicetree": "/ { behaviors { ... }; };",
  
  "layers": [...]
}
```

These are automatically included in the generated keymap file.

### Build Matrix Configuration

For advanced users, custom build matrices can be specified:

```yaml
# Profile configuration
firmwares:
  custom:
    type: "zmk_config"
    repository: "https://github.com/zmkfirmware/zmk.git"
    branch: "main"
    
    build_matrix:
      board: ["nice_nano_v2"]
      shield: ["glove80_lh", "glove80_rh"]
      
    kconfig:
      - "CONFIG_ZMK_SLEEP=y"
      - "CONFIG_ZMK_IDLE_TIMEOUT=300000"
```

### Development Builds

```bash
# Enable development features
glovebox config edit --set compilation.keep_intermediate=true

# Use development branch
glovebox layout compile layout.json --profile glove80/main

# Debug build output
glovebox --debug layout compile layout.json --profile glove80/v25.05
```

## Batch Processing

### Multiple Layouts

```bash
# Process multiple layouts
for layout in layouts/*.json; do
  echo "Building $layout"
  glovebox layout compile "$layout" --output "build/$(basename $layout .json)" --profile glove80/v25.05
done
```

### Automated Builds

```bash
#!/bin/bash
# build-all.sh

set -e

PROFILE="glove80/v25.05"
BUILD_DIR="builds/$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BUILD_DIR"

for layout in layouts/*.json; do
  name=$(basename "$layout" .json)
  echo "Building $name..."
  
  if glovebox layout validate "$layout" --profile "$PROFILE"; then
    glovebox layout compile "$layout" --output "$BUILD_DIR/$name" --profile "$PROFILE"
    echo "✓ Built $name"
  else
    echo "✗ Validation failed for $name"
  fi
done

echo "Builds completed in $BUILD_DIR"
```

### CI/CD Integration

```yaml
# .github/workflows/build-firmware.yml
name: Build Firmware

on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install Glovebox
      run: pip install glovebox
    
    - name: Validate layouts
      run: |
        for layout in layouts/*.json; do
          glovebox layout validate "$layout" --profile glove80/v25.05
        done
    
    - name: Build firmware
      run: |
        for layout in layouts/*.json; do
          name=$(basename "$layout" .json)
          glovebox layout compile "$layout" --output "builds/$name" --profile glove80/v25.05
        done
    
    - name: Upload firmware
      uses: actions/upload-artifact@v3
      with:
        name: firmware-builds
        path: builds/
```

## Error Handling

### Common Build Errors

**Docker not available:**
```bash
# Check Docker status
docker version

# Install Docker if missing
# Linux: sudo apt install docker.io
# macOS: brew install docker
# Windows: Install Docker Desktop
```

**Profile not found:**
```bash
# Check available profiles
glovebox keyboard list
glovebox keyboard firmwares glove80

# Use correct profile format
glovebox layout compile layout.json --profile glove80/v25.05
```

**Invalid keymap syntax:**
```bash
# Validate layout first
glovebox layout validate layout.json --profile glove80/v25.05

# Check for common issues:
# - Invalid behavior names
# - Incorrect parameter counts
# - Syntax errors in custom behaviors
```

### Debug Mode

```bash
# Enable debug output
glovebox --debug layout compile layout.json --profile glove80/v25.05

# Check Docker build logs
docker logs [container-id]

# Verbose compilation
glovebox layout compile layout.json --profile glove80/v25.05 --verbose
```

## Best Practices

### Development Workflow

1. **Validate first**: Always validate layouts before compilation
2. **Use version control**: Track layout files and generated keymaps
3. **Test incrementally**: Start with basic layouts, add complexity gradually
4. **Backup working firmware**: Keep copies of known-good firmware files

### Performance Optimization

1. **Enable caching**: Use shared cache for faster rebuilds
2. **Parallel builds**: Configure appropriate parallel job count
3. **Docker optimization**: Enable BuildKit and use SSD for Docker storage
4. **Clean builds**: Periodically clear cache and rebuild from scratch

### Security Considerations

1. **Verify sources**: Only use trusted ZMK repositories and branches
2. **Review custom code**: Carefully review custom behaviors and device tree code
3. **Backup firmware**: Keep backup of factory firmware before flashing custom builds
4. **Test safely**: Test new firmware on non-critical keyboards first

This guide provides comprehensive coverage of firmware building with Glovebox. The combination of Docker-based compilation and smart caching ensures reliable, reproducible firmware builds for your custom keyboard layouts.