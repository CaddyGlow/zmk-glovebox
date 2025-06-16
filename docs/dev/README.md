# Developer Documentation

Welcome to the Glovebox developer documentation. This guide will help you understand the codebase architecture, development practices, and how to contribute effectively.

## Quick Start

### Prerequisites
- Python 3.11+
- Docker (for firmware building)
- Git

### Setup Development Environment
```bash
# Clone the repository
git clone https://github.com/your-org/glovebox.git
cd glovebox

# Install with development dependencies (recommended)
uv sync

# Or using pip
pip install -e ".[dev]"

# Set up pre-commit hooks
pre-commit install

# Run tests to verify setup
make test
```

### Essential Commands
```bash
# Code quality
make lint          # Run linting checks
make format        # Format code and fix issues
make test          # Run all tests
make coverage      # Run tests with coverage

# Development workflow
uv run pytest                    # Run tests
uv run ruff check . --fix        # Fix linting issues
uv run mypy glovebox/            # Type checking
```

## Architecture Overview

Glovebox uses **Domain-Driven Design** with clean boundaries between business domains:

```
glovebox/
├── layout/           # Layout processing (JSON→DTSI conversion)
├── firmware/         # Firmware building and flashing
├── compilation/      # Advanced build strategies & workspace management
├── config/           # Configuration system & profiles
├── adapters/         # External system interfaces
├── models/           # Shared data models
├── protocols/        # Interface definitions
└── cli/              # Command-line interface
```

### Key Principles
1. **Domain Ownership**: Each domain owns its models, services, and business logic
2. **Factory Functions**: Consistent creation patterns (`create_*_service()`)
3. **Protocol-Based Interfaces**: Type-safe abstractions with runtime checking
4. **Clean Imports**: No backward compatibility layers
5. **Service Layer**: Business logic in domain services

## Understanding the Domains

### Layout Domain (`glovebox/layout/`)
**Purpose**: Transform JSON layouts into ZMK files

```python
from glovebox.layout import create_layout_service, LayoutData

# Main service for layout operations
layout_service = create_layout_service()
result = layout_service.generate(profile, layout_data, output_prefix)
```

**Key Components**:
- `LayoutService`: Main layout operations (generate, validate, compile)
- `LayoutComponentService`: Layer extraction and merging operations
- `LayoutDisplayService`: Layout visualization and terminal display
- `ZmkFileContentGenerator`: ZMK file content generation

### Firmware Domain (`glovebox/firmware/`)
**Purpose**: Build and flash firmware

```python
from glovebox.firmware import create_build_service
from glovebox.firmware.flash import create_flash_service

# Build firmware
build_service = create_build_service()
result = build_service.compile(profile, keymap_file, config_file, options)

# Flash firmware
flash_service = create_flash_service()
result = flash_service.flash_device(device, firmware_file)
```

**Key Components**:
- `BuildService`: Firmware compilation using Docker
- **Flash Subdomain** (`glovebox/firmware/flash/`):
  - `FlashService`: Main flash operations
  - `DeviceDetector`: USB device detection and monitoring
  - `FlashOperations`: Low-level mount/unmount operations

### Compilation Domain (`glovebox/compilation/`)
**Purpose**: Direct compilation strategies with intelligent caching and workspace management

```python
from glovebox.compilation import create_compilation_service

# Direct strategy selection - user chooses via CLI
service = create_compilation_service(strategy="zmk_config")
result = service.compile(profile, keymap_file, config_file, options)
```

**Key Features**:
- **Direct Strategy Selection**: Users choose compilation strategy via CLI (no coordination layer)
- **Dynamic ZMK Config Generation**: Creates complete ZMK workspaces on-the-fly
- **Multi-Strategy Compilation**: Supports zmk_config, west, cmake, make, ninja, custom strategies
- **Generic Cache Integration**: Uses domain-agnostic cache system for workspace and dependency caching
- **Build Matrix Support**: GitHub Actions style build matrices with automatic split keyboard detection

### Configuration System (`glovebox/config/`)
**Purpose**: Type-safe modular configuration management

```python
from glovebox.config import create_keyboard_profile

# Full profile with firmware
profile = create_keyboard_profile("glove80", "v25.05")

# Keyboard-only profile
profile = create_keyboard_profile("glove80")
```

**Key Features**:
- **Modular YAML Structure**: Configuration files with includes and inheritance
- **Keyboard-Only Profile Support**: Minimal configurations for flashing
- **Multi-source Configuration**: Environment, global, local precedence
- **Type Safety**: Pydantic models with validation
- **Compilation Configuration**: Unified models for all compilation strategies

## Development Workflow

### Making Changes
1. **Create feature branch**: `git checkout -b feature/my-feature`
2. **Make changes**: Follow coding conventions and patterns
3. **Run quality checks**: `make lint && make test`
4. **Commit changes**: Use conventional commit format
5. **Submit PR**: Request review and merge to `dev`

### Adding New Features

#### Adding a New Keyboard
1. **Create modular configuration structure:**
   ```bash
   keyboards/
   ├── my_keyboard.yaml        # Main entry point with includes
   └── my_keyboard/
       ├── main.yaml           # Core keyboard definition
       ├── hardware.yaml       # Hardware specifications
       ├── firmwares.yaml      # Firmware variants
       ├── strategies.yaml     # Compilation methods
       ├── kconfig.yaml        # Kconfig options
       └── behaviors.yaml      # Behavior definitions
   ```
2. **Define compilation strategies, flash configuration, firmware variants**
3. **Test configuration loading:** `glovebox config list`
4. **Test compilation:** `glovebox firmware compile --profile my_keyboard/firmware_version`

#### Adding a New Service
1. Create service class following `*Service` naming convention
2. Implement corresponding protocol interface
3. Add factory function (`create_*_service()`)
4. Add comprehensive tests
5. Update domain `__init__.py` exports

#### Adding CLI Commands
1. Create command in appropriate `cli/commands/` module
2. Use `@with_profile()` decorator for profile-based commands
3. Follow consistent parameter patterns
4. Add help text and examples

### Testing Strategy

```bash
# Run all tests
pytest

# Run domain-specific tests
pytest tests/test_layout/
pytest tests/test_firmware/
pytest tests/test_compilation/

# Run with coverage
pytest --cov=glovebox --cov-report=html
```

**Test Organization**:
- **Unit tests**: Test individual components in isolation
- **Integration tests**: Test component interactions
- **CLI tests**: Test command-line interface functionality

## Code Conventions

### MANDATORY Requirements
- **Maximum 500 lines per file** (ENFORCED)
- **Maximum 50 lines per method** (ENFORCED)
- **All code MUST pass linting**: `ruff check . && ruff format .`
- **All code MUST pass type checking**: `mypy glovebox/`

### Naming Conventions
- **Adapter classes**: `*Adapter` (e.g., `DockerAdapter`)
- **Service classes**: `*Service` (e.g., `LayoutService`)
- **Protocol classes**: `*Protocol` (e.g., `FileAdapterProtocol`)
- **Factory functions**: `create_*` (e.g., `create_layout_service()`)

### Import Patterns
```python
# Domain-specific models from their domains
from glovebox.layout.models import LayoutData, LayoutBinding
from glovebox.firmware.flash.models import FlashResult

# Core models from models package
from glovebox.models.results import BuildResult

# Domain services from their domains
from glovebox.layout import create_layout_service
from glovebox.firmware import create_build_service
from glovebox.compilation import create_compilation_service

# Configuration from config package
from glovebox.config import create_keyboard_profile

# Generic cache system
from glovebox.core.cache import create_default_cache
```

## Debugging and Troubleshooting

### Debug Logging
```bash
# Debug levels (precedence: --debug > -vv > -v > config > default)
glovebox --debug [command]     # DEBUG + stack traces
glovebox -vv [command]         # DEBUG + stack traces  
glovebox -v [command]          # INFO + stack traces

# Log to file
glovebox --debug --log-file debug.log [command]

# Debug specific domains
glovebox --debug layout compile input.json output/     # Layout domain
glovebox --debug firmware compile keymap.keymap config.conf  # Firmware domain
glovebox --debug config list                          # Configuration domain
```

### Common Issues
- **Import errors**: Check domain boundaries and import patterns
- **Linting failures**: Run `ruff check . --fix` before committing
- **Type errors**: Use proper type annotations and protocols
- **Test failures**: Ensure proper mocking and isolation

## Documentation Guidelines

### When to Update Documentation
- Adding new domains or major components
- Changing public APIs or interfaces
- Adding new CLI commands or options
- Fixing bugs that affect documented behavior

### Documentation Structure
- **`docs/dev/`**: Developer-focused documentation
- **`docs/user/`**: End-user guides and tutorials
- **`docs/technical/`**: Technical specifications and API reference
- **`CLAUDE.md`**: LLM-specific guidance (keep under 400 lines)
- **`README.md`**: User-focused overview and quick start

## Further Reading

- **[Architecture Overview](architecture/overview.md)**: Detailed system architecture
- **[Domain Documentation](domains/)**: In-depth domain guides
- **[Development Guides](guides/)**: Specific development tasks
- **[Code Conventions](conventions/)**: Detailed coding standards
- **[Technical Reference](../technical/)**: API documentation and specifications

## Getting Help

- **Issues**: Report bugs and feature requests on GitHub Issues
- **Discussions**: Ask questions in GitHub Discussions
- **Code Review**: All changes require review before merging
- **Documentation**: Keep docs up-to-date with code changes