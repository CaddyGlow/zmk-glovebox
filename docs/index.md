# Glovebox Documentation

**Glovebox** is a comprehensive tool for ZMK keyboard firmware management that transforms keyboard layouts through a multi-stage pipeline.

```
Layout Editor → JSON File → ZMK Files → Firmware → Flash
  (Design)    →  (.json)  → (.keymap + .conf) → (.uf2) → (Keyboard)
```

## Quick Start

Get started with Glovebox quickly:

- [Getting Started Guide](user/getting-started.md)
- [Keymap Version Management](user/keymap-version-management.md)

## User Guide

Complete user documentation:

- [User Documentation Overview](user/README.md)

## Developer Guide

Documentation for developers working on Glovebox:

- [Developer Overview](dev/README.md)
- [Architecture Overview](dev/architecture/overview.md)
- [Testing Guide](dev/testing.md)
- [Code Style Conventions](dev/conventions/code-style.md)
- [Shared Cache Coordination](dev/shared-cache-coordination.md)

### Domain Architecture

Core domains and their documentation:

- [Layout Domain](dev/domains/layout-domain.md)
- [Firmware Domain](dev/domains/firmware-domain.md)
- [Config Domain](dev/domains/config-domain.md)

## Technical Reference

Technical specifications and references:

- [Technical Overview](technical/README.md)
- [Keymap File Format](technical/keymap_file_format.md)
- [Caching System](technical/caching-system.md)

## Implementation Plans

Current and completed implementation plans:

- [Keymap Version Management](implementation/completed/keymap_version_management.md)
- [Firmware Command Refactoring](implementation/completed/firmware-command-refactoring.md)
- [Shared Cache Coordination System](implementation/completed/shared-cache-coordination-system.md)

## Pipeline Overview

Glovebox manages the complete ZMK firmware development pipeline:

1. **Layout Design**: Import layouts from layout editors or create manually
2. **JSON Processing**: Parse and validate keyboard layout JSON files
3. **ZMK Generation**: Convert layouts to ZMK keymap and configuration files
4. **Firmware Compilation**: Build firmware using Docker-based compilation strategies
5. **Device Flashing**: Flash compiled firmware to keyboard devices

## Key Features

- **Multi-domain Architecture**: Clean separation of layout, firmware, config, and compilation concerns
- **Version Management**: Track and upgrade keyboard layouts with preserved customizations
- **Flexible Compilation**: Support for multiple compilation strategies (ZMK West, MoErgo Nix)
- **Cross-platform Support**: Works on Linux, macOS, and Windows
- **Intelligent Caching**: Shared cache coordination system for efficient builds
- **Profile-based Configuration**: Keyboard and firmware profiles for consistent builds