# Glovebox User Documentation

Welcome to Glovebox, the comprehensive tool for ZMK keyboard firmware management. This documentation will help you get started with managing your keyboard layouts, building firmware, and flashing your keyboards.

## What is Glovebox?

Glovebox is a powerful command-line tool that transforms keyboard layouts through a multi-stage pipeline:

```
Layout Editor → JSON File → ZMK Files → Firmware → Flash
  (Design)    →  (.json)  → (.keymap + .conf) → (.uf2) → (Keyboard)
```

### Key Features

- **Layout Management**: Convert JSON layouts to ZMK keymap and config files
- **Firmware Building**: Compile firmware using Docker-based ZMK toolchains
- **Device Flashing**: Automatically detect and flash firmware to keyboards
- **Profile System**: Manage keyboard and firmware configurations
- **Library Integration**: Access and manage layout libraries (including MoErgo)
- **Version Management**: Track and upgrade layout versions
- **Intelligent Caching**: Fast builds with shared workspace caching

### Supported File Formats

- **`.json`** - Human-readable keyboard layout from Layout Editor
- **`.keymap`** - ZMK Device Tree Source Interface (DTSI) files defining keyboard behavior
- **`.conf`** - ZMK Kconfig options for firmware features  
- **`.uf2`** - Compiled firmware binary for flashing

## Quick Start

1. **[Installation](installation.md)** - Get Glovebox up and running
2. **[Getting Started](getting-started.md)** - Your first layout compilation
3. **[Configuration](configuration.md)** - Configure Glovebox for your setup
4. **[Keyboard Profiles](profiles.md)** - Set up your keyboard and firmware profiles

## User Guides

### Layout Management
- **[Layout Commands](layout-commands.md)** - Complete guide to layout operations
- **[Layout Editing](layout-editing.md)** - Edit layouts with field operations
- **[Layout Comparison](layout-comparison.md)** - Compare and diff layouts
- **[Version Management](version-management.md)** - Master layouts and upgrades

### Firmware Operations
- **[Firmware Building](firmware-building.md)** - Compile firmware from layouts
- **[Firmware Flashing](firmware-flashing.md)** - Flash firmware to keyboards
- **[Device Management](device-management.md)** - Manage connected keyboards

### Configuration & Profiles
- **[User Configuration](configuration.md)** - Configure Glovebox settings
- **[Keyboard Profiles](profiles.md)** - Manage keyboard and firmware profiles
- **[Cache Management](cache-management.md)** - Optimize build performance

### Integration & Libraries
- **[Library Management](library-management.md)** - Work with layout libraries
- **[MoErgo Integration](moergo-integration.md)** - Connect to MoErgo services
- **[Cloud Operations](cloud-operations.md)** - Upload and manage layouts

## Reference

- **[CLI Reference](cli-reference.md)** - Complete command reference
- **[Configuration Reference](configuration-reference.md)** - All configuration options
- **[Troubleshooting](troubleshooting.md)** - Common issues and solutions
- **[FAQ](faq.md)** - Frequently asked questions

## Examples and Workflows

- **[Common Workflows](workflows.md)** - Step-by-step workflow examples
- **[Layout Examples](examples.md)** - Sample layouts and configurations
- **[Advanced Usage](advanced.md)** - Power user features and tips

## Getting Help

If you need assistance:

1. Check the **[Troubleshooting Guide](troubleshooting.md)**
2. Review the **[FAQ](faq.md)**
3. Run `glovebox status` to check system diagnostics
4. Use `glovebox --help` or `glovebox COMMAND --help` for command help
5. Check the project repository for issues and discussions

---

*Glovebox is designed to make ZMK keyboard firmware management accessible and efficient for everyone, from beginners to advanced users.*