# User Documentation

Welcome to the Glovebox user documentation. These guides will help you get started, configure keyboards, build firmware, and troubleshoot common issues.

## Getting Started

### Quick Start
1. **[Installation](getting-started.md#installation)** - Install Glovebox and dependencies
2. **[First Build](getting-started.md#first-build)** - Build your first layout and firmware
3. **[Flash Firmware](getting-started.md#flashing)** - Flash firmware to your keyboard

### Essential Concepts
- **Profiles** - Keyboard and firmware combinations (`glove80/v25.05`)
- **Layouts** - JSON files defining your keyboard layout
- **Firmware** - Compiled binary files (`.uf2`) that run on your keyboard
- **ZMK Files** - Device tree (`.keymap`) and configuration (`.conf`) files

## User Guides

### Basic Usage
- **[Getting Started](getting-started.md)** - Installation, first build, and basic usage
- **[Keyboard Profiles](keyboard-profiles.md)** - Understanding and managing keyboard profiles
- **[Layout Management](layout-editing.md)** - Creating, editing, and organizing keyboard layouts

### Firmware Operations
- **[Building Firmware](firmware-building.md)** - Compile ZMK firmware from layouts
- **[Flashing Firmware](firmware-flashing.md)** - Flash firmware to keyboard devices
- **[Device Detection](device-detection.md)** - USB device queries and troubleshooting

### Advanced Features
- **[Component Workflow](layout-components.md)** - Extract and merge layout components
- **[Dynamic Generation](dynamic-generation.md)** - On-the-fly ZMK workspace creation
- **[Docker Configuration](docker-configuration.md)** - Advanced Docker build settings

### Configuration
- **[User Configuration](user-configuration.md)** - Personal settings and preferences
- **[Custom Keyboards](custom-keyboards.md)** - Adding support for new keyboards
- **[Environment Setup](environment-setup.md)** - Development environment configuration

### Troubleshooting
- **[Common Issues](troubleshooting.md)** - Solutions to frequent problems
- **[Debug Logging](debug-logging.md)** - Using verbose output and debug modes
- **[Build Problems](build-troubleshooting.md)** - Resolving compilation issues
- **[Flash Problems](flash-troubleshooting.md)** - Fixing device detection and flashing issues

## Quick Reference

### Common Commands
```bash
# Build layout files
glovebox layout compile my_layout.json output/my_layout --profile glove80/v25.05

# Build firmware
glovebox firmware compile layout.keymap config.conf --profile glove80/v25.05

# Flash firmware
glovebox firmware flash firmware.uf2 --profile glove80/v25.05

# List configurations
glovebox config list

# Show system status
glovebox status
```

### Profile Examples
```bash
# Full profiles (keyboard + firmware)
--profile glove80/v25.05
--profile corne/main
--profile lily58/bluetooth

# Keyboard-only profiles (for flashing)
--profile glove80
--profile corne
```

### Debug Commands
```bash
# Debug levels (most to least verbose)
glovebox --debug [command]     # Full debug output
glovebox -vv [command]         # Debug with stack traces
glovebox -v [command]          # Info level with stack traces
glovebox [command]             # Normal output
```

## Supported Keyboards

### Fully Supported
- **Glove80** - MoErgo Glove80 split ergonomic keyboard
- **Corne** - Standard ZMK-compatible split keyboard

### Extensible Architecture
Glovebox is designed to easily support new keyboards. See [Custom Keyboards](custom-keyboards.md) for adding your keyboard.

## Getting Help

### Documentation
- **[Technical Reference](../technical/)** - Detailed specifications and API docs
- **[Developer Documentation](../dev/)** - Architecture and development guides

### Support Channels
- **GitHub Issues** - Bug reports and feature requests
- **GitHub Discussions** - Questions and community support
- **Examples** - Working examples in the repository

### Contributing
- **[Contributing Guide](../../CONTRIBUTING.md)** - How to contribute to Glovebox
- **[Development Setup](../dev/README.md)** - Setting up development environment

## What's New

See the [CHANGELOG](../../CHANGELOG.md) for recent updates and new features.

## Examples

The `examples/` directory contains working examples for:
- Sample keyboard layouts
- Configuration files
- Build scripts
- Common workflows