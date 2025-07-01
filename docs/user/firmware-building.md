# Firmware Building Guide

This guide covers how to build ZMK firmware using Glovebox, from basic compilation to advanced build configurations and troubleshooting.

## Overview

Glovebox builds firmware using Docker-based ZMK toolchains. It can compile from JSON layouts, ZMK keymap files, or existing ZMK source directories.

## Understanding Firmware Building

### Build Pipeline

The firmware building process follows this flow:

```
Input → ZMK Files → Docker Build → Firmware Binary
```

1. **Input**: JSON layout, ZMK files, or source directory
2. **ZMK Files**: Generated `.keymap` and `.conf` files
3. **Docker Build**: Compilation using ZMK toolchain in Docker
4. **Firmware**: Final `.uf2` binary files for flashing

### Build Strategies

Glovebox supports different build strategies:

- **ZMK West**: Standard ZMK builds using west workspace
- **MoErgo Nix**: MoErgo-specific builds using Nix toolchain
- **Local**: Use local ZMK installation (advanced)

## Basic Firmware Building

### From JSON Layout

The most common way to build firmware:

```bash
# Basic firmware build
glovebox firmware compile my_layout.json firmware/ --profile glove80/v25.05

# With verbose output
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --verbose

# Clean build (no cache)
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --clean
```

**Output for split keyboards (e.g., Glove80):**
- `firmware/glove80_lh.uf2` - Left hand firmware
- `firmware/glove80_rh.uf2` - Right hand firmware

**Output for single keyboards (e.g., Corne):**
- `firmware/corne.uf2` - Single firmware file

### From ZMK Files

Build from existing keymap and config files:

```bash
# Build from keymap and config
glovebox firmware compile keymap.keymap firmware/ \
  --profile glove80/v25.05 \
  --config config.conf

# Build from directory containing ZMK files
glovebox firmware compile zmk_files/ firmware/ \
  --profile glove80/v25.05
```

### Two-Step Process

Separate layout compilation and firmware building:

```bash
# Step 1: Compile layout to ZMK files
glovebox layout compile layout.json zmk_files/ --profile glove80/v25.05

# Step 2: Build firmware from ZMK files
glovebox firmware compile zmk_files/layout.keymap firmware/ \
  --profile glove80/v25.05 \
  --config zmk_files/layout.conf
```

## Advanced Build Options

### Build Timeouts

Control build duration limits:

```bash
# Extended timeout for large builds
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --timeout 600

# Quick timeout for testing
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --timeout 120
```

### Build Modes

Different build approaches:

```bash
# Development build (faster, less optimized)
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --mode development

# Release build (slower, fully optimized)
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --mode release

# Debug build (with debug symbols)
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --mode debug
```

### Custom Configuration

Add additional configuration options:

```bash
# With additional config file
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --config custom_features.conf

# With inline config options
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --define CONFIG_ZMK_RGB_UNDERGLOW=y
```

## Build Strategies

### ZMK West Strategy

Standard ZMK builds using the west workspace:

```bash
# Force ZMK west strategy
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --strategy zmk-west

# With specific ZMK branch
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --strategy zmk-west \
  --zmk-branch main
```

### MoErgo Nix Strategy

MoErgo-specific builds using Nix:

```bash
# Force MoErgo Nix strategy
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --strategy moergo-nix

# With specific firmware version
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --strategy moergo-nix \
  --firmware-version v25.05
```

### Strategy Selection

Glovebox automatically selects the best strategy based on your profile, but you can override:

```bash
# Let Glovebox choose (default)
glovebox firmware compile layout.json firmware/ --profile glove80/v25.05

# Force specific strategy
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --strategy zmk-west
```

## Docker Configuration

### Docker Settings

Configure Docker behavior for builds:

```bash
# Check Docker status
glovebox status --verbose

# Force Docker image update
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --update-docker

# Use specific Docker image
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --docker-image zmkfirmware/zmk-build-arm:3.5
```

### Docker Troubleshooting

Common Docker issues and solutions:

```bash
# Check Docker connectivity
docker run hello-world

# Update Docker images
docker pull zmkfirmware/zmk-build-arm:3.5

# Clean Docker cache
docker system prune

# Check Docker permissions (Linux)
sudo usermod -aG docker $USER
```

## Caching and Performance

### Build Caching

Glovebox caches build artifacts for faster compilation:

```bash
# Show cache status
glovebox cache show

# Build with cache (default)
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05

# Force clean build (ignore cache)
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --clean

# Cache-only build (prepare for later)
glovebox firmware compile layout.json /dev/null \
  --profile glove80/v25.05 \
  --cache-only
```

### Workspace Management

Manage build workspaces:

```bash
# Show build workspaces
glovebox cache workspace show

# Create workspace for profile
glovebox cache workspace create zmk --profile glove80/v25.05

# Clean old workspaces
glovebox cache workspace cleanup

# Export workspace
glovebox cache workspace export zmk workspace.tar.gz
```

### Pre-warming Cache

Prepare for faster builds:

```bash
# Pre-download dependencies
glovebox cache workspace create zmk --profile glove80/v25.05

# Pre-compile common components
glovebox firmware compile example_layout.json /dev/null \
  --profile glove80/v25.05 \
  --cache-only
```

## Profile-Specific Building

### Glove80 Builds

MoErgo Glove80 specific options:

```bash
# Standard Glove80 build
glovebox firmware compile layout.json firmware/ --profile glove80/v25.05

# With RGB underglow
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --define CONFIG_ZMK_RGB_UNDERGLOW=y

# With display support
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --define CONFIG_ZMK_DISPLAY=y
```

### Generic ZMK Builds

Standard ZMK keyboards:

```bash
# Corne keyboard
glovebox firmware compile layout.json firmware/ --profile corne/main

# Lily58 keyboard
glovebox firmware compile layout.json firmware/ --profile lily58/main

# Planck keyboard
glovebox firmware compile layout.json firmware/ --profile planck/main
```

### Custom Keyboard Builds

For custom or unsupported keyboards:

```bash
# Use generic profile with custom config
glovebox firmware compile layout.json firmware/ \
  --profile generic/main \
  --config my_keyboard.conf \
  --define CONFIG_ZMK_KEYBOARD_NAME="my_keyboard"
```

## Build Monitoring and Debugging

### Verbose Output

Get detailed build information:

```bash
# Verbose build output
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --verbose

# Debug-level output
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --debug

# Real-time build progress
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --verbose \
  --progress
```

### Build Logs

Access and analyze build logs:

```bash
# Save build log
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --verbose 2>&1 | tee build.log

# Build with log file
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --log-file build.log
```

### Dry Run

Preview build without executing:

```bash
# Show build plan
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --dry-run

# Validate build configuration
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --dry-run \
  --verbose
```

## Error Handling

### Common Build Errors

#### Docker Not Running
```bash
# Check Docker status
systemctl status docker  # Linux
open -a Docker           # macOS

# Start Docker
systemctl start docker   # Linux
```

#### Permission Errors
```bash
# Fix Docker permissions (Linux)
sudo usermod -aG docker $USER
# Log out and back in

# Fix file permissions
chmod 644 layout.json
chmod 755 output/
```

#### Memory Issues
```bash
# Increase Docker memory limit
# Docker Desktop: Settings → Resources → Memory

# Clean Docker to free space
docker system prune -a
```

#### Network Issues
```bash
# Test Docker connectivity
docker run hello-world

# Check proxy settings
echo $HTTP_PROXY
echo $HTTPS_PROXY

# Use alternative Docker registry
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --docker-registry alternative-registry.com
```

### Build Failures

#### ZMK Compilation Errors
```bash
# Check ZMK syntax
glovebox layout validate layout.json --profile glove80/v25.05

# Use verbose output for details
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --verbose

# Try clean build
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --clean
```

#### Configuration Errors
```bash
# Validate configuration
glovebox config show --validate

# Check profile validity
glovebox profile show glove80/v25.05

# Reset to defaults
glovebox config edit --reset
```

### Recovery Strategies

#### Cache Issues
```bash
# Clear problematic cache
glovebox cache clear

# Reset workspace
glovebox cache workspace delete problematic_workspace

# Disable cache temporarily
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --no-cache
```

#### Docker Issues
```bash
# Reset Docker environment
docker system prune -a

# Update Docker images
docker pull zmkfirmware/zmk-build-arm:3.5

# Use alternative build strategy
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --strategy moergo-nix
```

## Advanced Features

### Custom Build Matrices

For complex build configurations:

```bash
# Multi-board builds
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --boards "glove80_lh,glove80_rh"

# Custom shield configuration
glovebox firmware compile layout.json firmware/ \
  --profile corne/main \
  --shield corne_left,corne_right
```

### Environment Variables

Control builds with environment variables:

```bash
# Custom ZMK repository
export ZMK_REPOSITORY=https://github.com/my-org/zmk.git

# Custom build options
export ZMK_EXTRA_CFLAGS="-DCONFIG_ZMK_LOGGING_MINIMAL=y"

# Docker configuration
export DOCKER_BUILDKIT=1

# Build with environment
glovebox firmware compile layout.json firmware/ --profile glove80/v25.05
```

### Build Hooks

Execute custom scripts during build:

```bash
# Pre-build hook
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --pre-build-hook ./scripts/prepare.sh

# Post-build hook
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --post-build-hook ./scripts/validate.sh
```

## Batch Building

### Multiple Layouts

Build multiple layouts efficiently:

```bash
# Sequential builds
for layout in *.json; do
  glovebox firmware compile "$layout" "firmware/${layout%.json}/" \
    --profile glove80/v25.05
done

# Parallel builds (be careful with Docker resources)
for layout in *.json; do
  glovebox firmware compile "$layout" "firmware/${layout%.json}/" \
    --profile glove80/v25.05 &
done
wait
```

### Multiple Profiles

Test layouts across different keyboards:

```bash
# Build for multiple profiles
for profile in glove80/v25.05 corne/main lily58/main; do
  echo "Building for $profile..."
  glovebox firmware compile layout.json "firmware/$profile/" \
    --profile "$profile"
done
```

### Automated Builds

Create build scripts:

```bash
#!/bin/bash
# build_all.sh

set -e

LAYOUTS_DIR="layouts"
FIRMWARE_DIR="firmware"
PROFILE="glove80/v25.05"

echo "Building all layouts for $PROFILE..."

mkdir -p "$FIRMWARE_DIR"

for layout in "$LAYOUTS_DIR"/*.json; do
    name=$(basename "$layout" .json)
    echo "Building $name..."
    
    glovebox firmware compile "$layout" "$FIRMWARE_DIR/$name/" \
        --profile "$PROFILE" \
        --verbose
        
    echo "✓ Built $name"
done

echo "All builds completed!"
```

## Best Practices

### 1. Always Validate First
```bash
glovebox layout validate layout.json --profile glove80/v25.05 && \
glovebox firmware compile layout.json firmware/ --profile glove80/v25.05
```

### 2. Use Appropriate Timeouts
```bash
# Standard builds
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --timeout 300

# Complex layouts with many behaviors
glovebox firmware compile complex_layout.json firmware/ \
  --profile glove80/v25.05 \
  --timeout 600
```

### 3. Cache Management
```bash
# Warm cache for faster builds
glovebox cache workspace create zmk --profile glove80/v25.05

# Clean cache periodically
glovebox cache clear --older-than 7d
```

### 4. Error Recovery
```bash
# Always have fallback strategy
glovebox firmware compile layout.json firmware/ --profile glove80/v25.05 || \
glovebox firmware compile layout.json firmware/ --profile glove80/v25.05 --clean
```

### 5. Version Control
```bash
# Tag successful builds
git tag "firmware-$(date +%Y%m%d-%H%M%S)"

# Keep build logs
glovebox firmware compile layout.json firmware/ \
  --profile glove80/v25.05 \
  --verbose 2>&1 | tee "logs/build-$(date +%Y%m%d-%H%M%S).log"
```

---

*Firmware building is the core step in getting your layouts onto your keyboard. Understanding these commands and options will help you build reliable firmware efficiently.*