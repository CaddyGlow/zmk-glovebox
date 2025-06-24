# API Reference

This section contains the complete API documentation for Glovebox, automatically generated from the source code docstrings.

## Overview

The Glovebox codebase is organized into several core domains:

### Layout Domain
- **[glovebox.layout](glovebox/layout/index.md)** - Keyboard layout processing and management
- **[glovebox.layout.models](glovebox/layout/models/index.md)** - Layout data models and validation
- **[glovebox.layout.behavior](glovebox/layout/behavior/index.md)** - ZMK behavior analysis and formatting

### Firmware Domain  
- **[glovebox.firmware](glovebox/firmware/index.md)** - Firmware building and compilation
- **[glovebox.firmware.flash](glovebox/firmware/flash/index.md)** - Device flashing operations

### Configuration Domain
- **[glovebox.config](glovebox/config/index.md)** - Configuration management and profiles
- **[glovebox.config.models](glovebox/config/models/index.md)** - Configuration data models

### Compilation Domain
- **[glovebox.compilation](glovebox/compilation/index.md)** - Build strategies and caching
- **[glovebox.compilation.models](glovebox/compilation/models/index.md)** - Compilation configuration models

### Core Infrastructure
- **[glovebox.core](glovebox/core/index.md)** - Core application infrastructure
- **[glovebox.adapters](glovebox/adapters/index.md)** - External system interfaces
- **[glovebox.models](glovebox/models/index.md)** - Base models and shared types
- **[glovebox.services](glovebox/services/index.md)** - Base service patterns
- **[glovebox.protocols](glovebox/protocols/index.md)** - Protocol definitions
- **[glovebox.utils](glovebox/utils/index.md)** - Utility functions and helpers

### CLI Interface
- **[glovebox.cli](glovebox/cli/index.md)** - Command-line interface
- **[glovebox.cli.commands](glovebox/cli/commands/index.md)** - CLI command implementations

### Metrics and Monitoring
- **[glovebox.metrics](glovebox/metrics/index.md)** - Performance metrics and monitoring

### MoErgo Integration
- **[glovebox.moergo](glovebox/moergo/index.md)** - MoErgo service integration
- **[glovebox.moergo.client](glovebox/moergo/client/index.md)** - MoErgo API client
- **[glovebox.moergo.bookmark_service](glovebox/moergo/bookmark_service.md)** - Layout bookmark management
- **[glovebox.moergo.versioning](glovebox/moergo/versioning.md)** - Layout versioning services

## Navigation

Use the navigation tree on the left to explore the complete API documentation. Each module includes:

- Class and function signatures
- Detailed docstrings
- Type annotations
- Source code links
- Cross-references between related components

## Docstring Style

The codebase uses Google-style docstrings with comprehensive type annotations. All public APIs are documented with:

- Parameter descriptions and types
- Return value descriptions
- Raised exceptions
- Usage examples where applicable