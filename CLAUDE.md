# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Glovebox** is a comprehensive tool for ZMK keyboard firmware management that transforms keyboard layouts through a multi-stage pipeline:

```
Layout Editor → JSON File → ZMK Files → Firmware → Flash
  (Design)    →  (.json)  → (.keymap + .conf) → (.uf2) → (Keyboard)
```

### Key File Formats:
- **`.json`** - Human-readable keyboard layout from Layout Editor
- **`.keymap`** - **ZMK Device Tree Source Interface (DTSI)** files defining keyboard behavior
- **`.conf`** - ZMK Kconfig options for firmware features  
- **`.uf2`** - Compiled firmware binary for flashing

### Core Architecture:
- **Domain-Driven Design**: Business logic organized by domains (layout, firmware, config, compilation)
- **Service Layer**: Domain services with single responsibility 
- **Adapter Pattern**: External interfaces (Docker, USB, File, Template, Config)
- **Configuration System**: Type-safe profiles combining keyboard + firmware configs
- **Cross-Platform**: OS abstraction for USB device detection and flashing

## CRITICAL: Code Convention Enforcement

**MANDATORY REQUIREMENTS - MUST BE FOLLOWED WITHOUT EXCEPTION:**

1. **ALWAYS run linting before any code changes are considered complete**:
   ```bash
   ruff check . --fix
   ruff format .
   mypy glovebox/
   ```

2. **NEVER commit code that fails linting or type checking**:
   - All code MUST pass `ruff check .` without warnings
   - All code MUST pass `mypy glovebox/` without errors
   - All code MUST be formatted with `ruff format .`

3. **FOLLOW PROJECT CONVENTIONS STRICTLY**:
   - Maximum 500 lines per file (ENFORCED)
   - Maximum 50 lines per method (ENFORCED)
   - Use comprehensive typing without complexity
   - Use pathlib for ALL file operations
   - Use modern typing (`dict` not `typing.Dict`, etc.)
   - Use `Path.open()` instead of built-in `open()`
   - Use lazy logging formatting (`%` style, not f-strings)

4. **MANDATORY PRE-COMMIT CHECKS**:
   ```bash
   pre-commit run --all-files
   pytest
   ```

**If you encounter ANY linting errors, you MUST fix them immediately before proceeding with other tasks.**

## Naming Conventions

**CRITICAL: These naming conventions are MANDATORY:**

### **Class Naming Standards**

1. **Adapter Classes**: Use `*Adapter` suffix (NO `Impl` suffix)
   ```python
   # ✅ CORRECT
   class DockerAdapter:
   class USBAdapter:
   class FileAdapter:
   ```

2. **Service Classes**: Use `*Service` suffix (NO `Impl` suffix)
   ```python
   # ✅ CORRECT
   class BuildService(BaseService):
   class LayoutService(BaseService):
   class FlashService:
   ```

3. **Protocol Classes**: Use `*Protocol` suffix
   ```python
   # ✅ CORRECT
   class FileAdapterProtocol(Protocol):
   class BaseServiceProtocol(Protocol):
   ```

### **Function Naming Standards**

1. **Use Descriptive Verbs**: Function names must clearly indicate their purpose
   ```python
   # ✅ CORRECT - Descriptive function names
   def check_exists(path: Path) -> bool:
   def create_directory(path: Path) -> None:
   def mount_device(device: BlockDevice) -> list[str]:
   
   # ❌ INCORRECT - Terse/unclear function names
   def exists(path: Path) -> bool:
   def mkdir(path: Path) -> None:
   ```

2. **Layout Domain Specific Standards**:
   ```python
   # ✅ CORRECT - Component operations
   def decompose_components()  # Split layout into files
   def compose_components()    # Combine files into layout
   
   # ✅ CORRECT - Display operations  
   def show()           # CLI display commands
   def format_*()       # Text formatting operations
   ```

## Essential Commands

### Quick Commands
```bash
# Using make
make test           # Run all tests
make lint           # Run linting checks
make format         # Format code and fix linting issues
make coverage       # Run tests with coverage reporting

# Using scripts or uv
./scripts/test.sh
uv run pytest
uv run ruff check . --fix
uv run mypy glovebox/
```

### Build and Run
```bash
# Run glovebox CLI directly
python -m glovebox.cli [command]
# or with uv:
uv run python -m glovebox.cli [command]

# Build a layout
glovebox layout compile my_layout.json output/my_layout --profile glove80/v25.05

# Build firmware
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05

# Flash firmware
glovebox firmware flash firmware.uf2 --profile glove80/v25.05
```

## Project Architecture

### Domain-Driven Structure

The codebase is organized into self-contained domains:

#### Layout Domain (`glovebox/layout/`)
- **Purpose**: Keyboard layout processing, JSON→DTSI conversion, component operations
- **Factory Functions**: `create_layout_service()`, `create_layout_component_service()`, `create_layout_display_service()`
- **Models**: `LayoutData`, `LayoutBinding`, `LayoutLayer`

#### Firmware Domain (`glovebox/firmware/`)
- **Purpose**: Firmware building and flashing operations
- **Factory Functions**: `create_build_service()`
- **Flash Subdomain** (`glovebox/firmware/flash/`):
  - `create_flash_service()`, `create_device_detector()`
  - Models: `FlashResult`, `BlockDevice`

#### Compilation Domain (`glovebox/compilation/`)
- **Purpose**: Advanced firmware compilation strategies, workspace management
- **Factory Functions**: `create_compilation_coordinator()`, `create_zmk_config_service()`, `create_west_service()`
- **Key Features**:
  - **Dynamic ZMK Config Generation**: Creates complete ZMK workspaces without external repositories
  - **Multi-Strategy Compilation**: Supports zmk_config, west, cmake build strategies

#### Configuration System (`glovebox/config/`)
- **Purpose**: Type-safe configuration management, keyboard profiles, user settings
- **Factory Functions**: `create_keyboard_profile()`, `create_user_config()`
- **Key Features**:
  - **Keyboard-Only Profile Support**: Minimal configurations for flashing operations
  - Profile-based keyboard + firmware combinations

#### Core Models (`glovebox/models/`)
- **Purpose**: Core data models shared across domains
- **Components**: Configuration models, behavior models, operation results

#### Adapters (`glovebox/adapters/`)
- **Purpose**: External system interfaces following adapter pattern
- **Components**: `DockerAdapter`, `FileAdapter`, `USBAdapter`, `TemplateAdapter`, `ConfigFileAdapter`

### Key Design Patterns

1. **Domain-Driven Design**: Business logic organized by domains with clear boundaries
2. **Factory Functions**: Consistent creation patterns for all services and components
3. **Protocol-Based Interfaces**: Type-safe abstractions with runtime checking
4. **Domain Ownership**: Each domain owns its models, services, and business logic
5. **Clean Imports**: No backward compatibility layers - single source of truth for imports

### CLI Structure

All CLI commands follow a consistent pattern with profile-based parameter:

```
glovebox [command] [subcommand] [--profile KEYBOARD/FIRMWARE] [options]
```

Examples:
- `glovebox layout compile my_layout.json output/my_keymap --profile glove80/v25.05`
- `glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05`
- `glovebox firmware flash firmware.uf2 --profile glove80/v25.05`

### KeyboardProfile Pattern

The KeyboardProfile pattern is central to the architecture:

```python
from glovebox.config import create_keyboard_profile

# Full profile with firmware
profile = create_keyboard_profile("glove80", "v25.05")

# Keyboard-only profile (NEW: firmware_version=None)
keyboard_profile = create_keyboard_profile("glove80")
```

**CLI Integration**:
```bash
# Using profile parameter with firmware
glovebox layout compile input.json output/ --profile glove80/v25.05

# Using keyboard-only profile (NEW: no firmware part)
glovebox status --profile glove80
glovebox firmware flash firmware.uf2 --profile glove80
```

## Maintainability Guidelines

This project is maintained by a small team (2-3 developers), so:

1. **Avoid Over-engineering**: Keep solutions as simple as possible
2. **Pragmatic Design**: Choose patterns that solve actual problems, not theoretical ones
3. **Readability Over Cleverness**: Clear, explicit code is better than clever, complex code
4. **Focused Changes**: Keep changes small and targeted rather than large refactors

## Git Workflow

### Branch Strategy
- Main development branch is `dev`
- Feature branches should be created from `dev`
- Use meaningful branch names (e.g., `feature/new-keymap-format`, `fix/usb-detection-issue`)

### Before Committing
1. Run the linter and fix any issues: `ruff check . && ruff format .`
2. Run pre-commit hooks: `pre-commit run --all-files`
3. Run tests: `pytest`
4. All new files must pass mypy type checking: `mypy glovebox/`

## Documentation Structure

For detailed information, refer to:

- **Developer Documentation**: `docs/dev/` - Architecture guides, domain documentation, coding conventions
- **User Documentation**: `docs/user/` - Getting started, tutorials, troubleshooting
- **Technical Reference**: `docs/technical/` - API reference, keymap format specification
- **Implementation Plans**: `docs/implementation/` - Current development plans and completed features

## Common Import Patterns

```python
# Domain-specific models from their domains
from glovebox.layout.models import LayoutData, LayoutBinding
from glovebox.firmware.flash.models import FlashResult, BlockDevice

# Core models from models package
from glovebox.models.results import BuildResult, LayoutResult

# Domain services from their domains
from glovebox.layout import create_layout_service, create_layout_component_service
from glovebox.firmware import create_build_service
from glovebox.firmware.flash import create_flash_service

# Configuration from config package
from glovebox.config import create_keyboard_profile, KeyboardProfile
```

**IMPORTANT**: The codebase uses clean domain boundaries with no backward compatibility layers.