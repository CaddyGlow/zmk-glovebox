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

4. **MANDATORY EXCEPTION LOGGING PATTERN**:
   ```python
   # ✅ REQUIRED - Exception logging with debug-aware stack traces
   except Exception as e:
       exc_info = self.logger.isEnabledFor(logging.DEBUG)
       self.logger.error("Operation failed: %s", e, exc_info=exc_info)
   
   # ❌ INCORRECT - Missing debug-aware stack trace
   except Exception as e:
       self.logger.error("Operation failed: %s", e)
   ```
   - **MANDATORY for ALL exception handlers** that log errors/warnings
   - Stack traces appear ONLY when debug logging is enabled
   - Keeps production logs clean while enabling debugging
   - Can be one-lined: `exc_info=self.logger.isEnabledFor(logging.DEBUG)`

5. **MANDATORY PRE-COMMIT CHECKS**:
   ```bash
   pre-commit run --all-files
   pytest
   ```

**If you encounter ANY linting errors, you MUST fix them immediately before proceeding with other tasks.**

## CRITICAL: Pydantic Model Rules

**MANDATORY REQUIREMENTS - MUST BE FOLLOWED WITHOUT EXCEPTION:**

1. **ALL Pydantic models MUST inherit from GloveboxBaseModel**:
   ```python
   # ✅ CORRECT - Always inherit from GloveboxBaseModel
   from glovebox.models.base import GloveboxBaseModel
   
   class MyModel(GloveboxBaseModel):
       field: str
   ```

2. **NEVER use .to_dict() - ALWAYS use .model_dump()**:
   ```python
   # ✅ CORRECT - Use model_dump with proper parameters
   data = model.model_dump(by_alias=True, exclude_unset=True, mode="json")
   
   # ✅ CORRECT - Use the inherited to_dict() method (which calls model_dump correctly)
   data = model.to_dict()
   
   # ❌ INCORRECT - Never call model_dump without parameters
   data = model.model_dump()
   
   # ❌ INCORRECT - Never use deprecated .dict() method
   data = model.dict()
   ```

3. **ALWAYS use proper model validation parameters**:
   ```python
   # ✅ CORRECT - Use model_validate with proper mode
   model = MyModel.model_validate(data, mode="json")
   
   # ✅ CORRECT - Use model_validate_json for JSON strings
   model = MyModel.model_validate_json(json_string)
   
   # ❌ INCORRECT - Never use parse_obj or from_dict
   model = MyModel.parse_obj(data)  # Deprecated in Pydantic v2
   ```

4. **Special handling for whitespace preservation**:
   ```python
   # ✅ CORRECT - Override model_config for formatting classes
   class FormattingConfig(GloveboxBaseModel):
       model_config = ConfigDict(
           extra="allow",
           str_strip_whitespace=False,  # Preserve whitespace for formatting
           use_enum_values=True,
           validate_assignment=True,
       )
   ```

**These rules ensure consistent serialization behavior across ALL models with proper alias handling, unset field exclusion, and JSON-safe output.**

5. **MANDATORY TESTING REQUIREMENTS**:
   - **ALL public functions/methods/classes MUST have comprehensive tests**
   - **Minimum 90% code coverage** for all new code
   - **NO CODE can be merged without tests** - this is NON-NEGOTIABLE
   - ALL tests should pass mypy
   - See `docs/dev/testing.md` for complete testing standards and requirements

## CRITICAL: Test Isolation and Anti-Pollution Rules

**MANDATORY REQUIREMENTS - MUST BE FOLLOWED WITHOUT EXCEPTION:**

1. **NEVER write files to the current working directory in tests**:
   ```python
   # ✅ CORRECT - Always use tmp_path or isolated fixtures
   def test_file_creation(tmp_path):
       test_file = tmp_path / "test.json"
       test_file.write_text('{"test": "data"}')
   
   # ❌ INCORRECT - Never write to current directory
   def test_file_creation_bad():
       Path("test.json").write_text('{"test": "data"}')  # NEVER DO THIS
   ```

2. **ALWAYS use proper test isolation for configuration**:
   ```python
   # ✅ CORRECT - Use isolated_config fixture for any config-related tests
   def test_config_operation(isolated_config):
       config = UserConfig(cli_config_path=isolated_config.config_file)
       # Test operations are isolated to temp directory
   
   # ❌ INCORRECT - Never modify real user configuration
   def test_config_bad():
       config = UserConfig()  # Uses real ~/.glovebox/ directory
   ```

3. **MANDATORY use of isolation fixtures for CLI tests**:
   ```python
   # ✅ CORRECT - Use isolated_cli_environment for CLI command tests
   def test_cli_command(isolated_cli_environment, cli_runner):
       result = cli_runner.invoke(app, ["config", "list"])
       # All file operations isolated to temp directory
   
   # ❌ INCORRECT - CLI tests without isolation can pollute project
   def test_cli_bad(cli_runner):
       result = cli_runner.invoke(app, ["config", "export"])  # May write to current dir
   ```

4. **ENFORCE test file size limits**:
   - **Maximum 500 lines per test file** (ENFORCED)
   - Split large test files into domain-specific modules
   - Use shared fixtures in `conftest.py` files

5. **CLEANUP requirements**:
   ```python
   # ✅ CORRECT - Tests must clean up after themselves
   @pytest.fixture
   def temp_files(tmp_path):
       yield tmp_path
       # Automatic cleanup via tmp_path
   
   # ✅ CORRECT - Manual cleanup when needed
   def test_with_cleanup():
       try:
           # Test operations
           pass
       finally:
           # Explicit cleanup if needed
           pass
   ```

6. **FORBIDDEN practices in tests**:
   - Creating files in project root directory
   - Writing to `~/.glovebox/` or user config directories
   - Modifying global environment without proper restoration
   - Tests that depend on external file system state
   - Tests that write backup files to current directory

**Available Isolation Fixtures:**
- `isolated_config`: Complete configuration isolation with temp directories
- `isolated_cli_environment`: CLI command isolation with mocked environment
- `temp_config_dir`: Temporary configuration directory
- `mock_user_config`: Mocked user configuration that doesn't touch filesystem

**If you encounter ANY test pollution or isolation issues, you MUST fix them immediately before proceeding with other tasks.**

## New Feature: Keymap Version Management

**COMPLETED**: The keymap version management system is now fully implemented and operational.

### Architecture Components

1. **VersionManager** (`glovebox/layout/version_manager.py`):
   - Handles master layout imports and upgrades
   - Implements intelligent merge strategies preserving customizations
   - Stores master layouts in `~/.glovebox/masters/{keyboard}/{version}.json`
   - Tracks version metadata in YAML format

2. **FirmwareTracker** (`glovebox/layout/firmware_tracker.py`):
   - Links compiled firmware to layout files
   - Tracks build metadata: date, profile, hash, build ID
   - Enables verification of firmware-layout correspondence
   - Supports rollback and change tracking

3. **Enhanced Layout Models**:
   - Added version tracking fields: `version`, `base_version`, `base_layout`
   - Added firmware tracking: `last_firmware_build` metadata
   - Maintains backwards compatibility with existing layouts

### CLI Commands Added

```bash
# Import master layout versions
glovebox layout import-master ~/Downloads/master-v42.json v42 [--force]

# Upgrade custom layouts preserving all customizations
glovebox layout upgrade my-custom.json --to-master v42 [--output path] [--from-master v41]

# List available master versions
glovebox layout list-masters glove80

# Enhanced diff with DTSI comparison and JSON output
glovebox layout diff layout1.json layout2.json [--include-dtsi] [--json]

# Field manipulation commands
glovebox layout get-field layout.json "layers[0]"
glovebox layout set-field layout.json "title" "New Title"

# Layer management commands
glovebox layout add-layer layout.json "NewLayer" --position 5 [--import-from layer.json]
glovebox layout remove-layer layout.json "LayerName"
glovebox layout move-layer layout.json "LayerName" --position 3
glovebox layout export-layer layout.json "LayerName" --format bindings

# Patch and transform operations
glovebox layout patch layout.json diff.json --output patched.json
glovebox layout create-patch layout1.json layout2.json --output changes.patch
```

### Implementation Patterns

- **Simple Merge Strategy**: Preserves all customizations while updating base layers
- **DTSI Content Comparison**: Compares custom behaviors and device tree code
- **Firmware Linking**: Automatic tracking of layout-to-firmware relationships
- **Field Path Parsing**: Dot notation with array indexing (`layers[0].name`)
- **Pydantic Integration**: Uses `model_dump(mode="json")` for proper serialization
- **Layer Import/Export**: Multiple format support (bindings, layer object, full layout)

### Testing and Quality Assurance

- All new functionality includes comprehensive unit tests
- Integration tests cover end-to-end upgrade workflows
- Error handling with clear user feedback
- Logging with multiple verbosity levels
- Follows all existing code conventions and patterns

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
uv sync             # Install dependencies
uv run pytest      # Run tests
uv run ruff check . --fix  # Fix linting issues
uv run mypy glovebox/      # Type checking
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

# Keymap version management (NEW)
glovebox layout import-master master-v42.json v42
glovebox layout upgrade my-custom.json --to-master v42
glovebox layout diff layout1.json layout2.json --include-dtsi --json
```

## Project Architecture

### Domain-Driven Structure

The codebase is organized into self-contained domains:

#### Layout Domain (`glovebox/layout/`)
- **Purpose**: Keyboard layout processing, JSON→DTSI conversion, component operations, version management
- **Factory Functions**: `create_layout_service()`, `create_layout_component_service()`, `create_layout_display_service()`, `create_grid_layout_formatter()`, `create_zmk_file_generator()`, `create_behavior_registry()`
- **Models**: `LayoutData`, `LayoutBinding`, `LayoutLayer`, behavior models, bookmarks
- **Subdomains**:
  - `behavior/`: Behavior analysis, formatting, and models
  - `comparison/`: Layout comparison services
  - `diffing/`: Diff and patch operations
  - `editor/`: Layout editing operations
  - `layer/`: Layer management services
  - `utils/`: Field parsing, JSON operations, validation
- **Version Management**: `VersionManager`, `FirmwareTracker` (fully implemented)

#### Firmware Domain (`glovebox/firmware/`)
- **Purpose**: Firmware building and flashing operations
- **Key Components**: Method registry, build models, output handling
- **Models**: `BuildResult`, `FirmwareOutputFiles`, `OutputPaths`
- **Flash Subdomain** (`glovebox/firmware/flash/`):
  - **Factory Functions**: `create_flash_service()`, `create_device_detector()`, `create_usb_flasher()`, `create_firmware_flasher()`
  - **Services**: `FlashService`, `USBFlasher`
  - **Models**: `FlashResult`, `BlockDevice`
  - **Components**: Device detection, USB operations, OS adapters, wait services

#### Compilation Domain (`glovebox/compilation/`)
- **Purpose**: Direct compilation strategies with intelligent caching
- **Factory Functions**: `create_compilation_service(strategy)`, `create_zmk_west_service()`, `create_moergo_nix_service()`
- **Subdomains**:
  - `cache/`: **Shared cache coordination** with domain-specific factories, workspace cache service
  - `models/`: Build matrix, compilation config, west config
  - `protocols/`: Compilation protocols
  - `services/`: Strategy-specific services (ZMK West, MoErgo Nix)
- **Key Features**:
  - **Direct Strategy Selection**: Clean service selection pattern
  - **Build Matrix Support**: GitHub Actions style build matrices
  - **Shared Cache Integration**: Uses `create_compilation_cache_service()` for coordinated caching

#### Configuration System (`glovebox/config/`)
- **Purpose**: Type-safe configuration management, keyboard profiles, user settings
- **Factory Functions**: `create_keyboard_profile()`, `create_user_config()`
- **Key Components**: `keyboard_profile.py`, `profile.py`, `user_config.py`, `include_loader.py`
- **Models Subdomain**: Behavior, display, firmware, keyboard, user, ZMK models
- **Key Features**:
  - **Modular YAML Structure**: YAML includes for configuration composition
  - **Keyboard-Only Profile Support**: Minimal configurations for flashing operations
  - **Profile-based Combinations**: Keyboard + firmware or keyboard-only patterns

#### Core Models (`glovebox/models/`)
- **Purpose**: Cross-domain core models and base classes
- **Components**: `GloveboxBaseModel` base class, `DockerUserContext`, `BaseResult`

#### Adapters (`glovebox/adapters/`)
- **Purpose**: External system interfaces following adapter pattern
- **Factory Functions**: `create_docker_adapter()`, `create_file_adapter()`, `create_template_adapter()`, `create_usb_adapter()`
- **Components**: `DockerAdapter`, `FileAdapter`, `USBAdapter`, `TemplateAdapter`, `ConfigFileAdapter`

#### Core Infrastructure (`glovebox/core/`)
- **Purpose**: Core application infrastructure and shared services
- **Cache v2 Subdomain**: DiskCache-based system with **shared coordination** (`glovebox/core/cache_v2/`)
  - **Shared Coordination**: Single cache instances across domains with proper isolation
  - **Factory Functions**: `create_default_cache()`, `create_cache_from_user_config()`, `get_shared_cache_instance()`
  - **Domain Isolation**: Uses tags (compilation, metrics, layout, etc.) for namespace separation
  - **Test Safety**: `reset_shared_cache_instances()` for complete test isolation
  - **Cache Manager**: `DiskCacheManager` with SQLite backend for thread/process safety
- **Components**: Error handling, logging setup, startup services, version checking

#### MoErgo Domain (`glovebox/moergo/`)
- **Purpose**: MoErgo service integration and API client
- **Key Components**: Layout bookmark management, versioning
- **Client Subdomain**: MoErgo API client with auth, credentials, and models
- **Services**: `bookmark_service.py`, `versioning.py`

#### Supporting Infrastructure
- **Services** (`glovebox/services/`): `BaseService` and `BaseServiceProtocol` patterns
- **Protocols** (`glovebox/protocols/`): Runtime-checkable protocols for type safety
- **Utils** (`glovebox/utils/`): Process streaming, error utilities, diagnostics

### Key Design Patterns

1. **Domain-Driven Design**: Business logic organized by domains with clear boundaries
2. **Factory Functions**: Consistent creation patterns for all services and components
3. **Protocol-Based Interfaces**: Type-safe abstractions with runtime checking
4. **Domain Ownership**: Each domain owns its models, services, and business logic
5. **Clean Imports**: No backward compatibility layers - single source of truth for imports
6. **Shared Cache Coordination**: Single cache instances across domains with proper isolation

### Shared Cache Coordination System

**COMPLETED**: The cache system has been refactored to use shared coordination across all domains while maintaining proper isolation and following CLAUDE.md factory function patterns.

#### Architecture Overview

The shared cache coordination system eliminates multiple independent cache instances by:
- **Coordinating cache instances** across domains using a central registry
- **Domain isolation** through cache tags (compilation, metrics, layout, etc.)
- **CLAUDE.md compliance** using factory functions (no singletons)
- **Test safety** with automatic cache reset between tests

#### Core Components

1. **Cache Coordinator** (`glovebox/core/cache_v2/cache_coordinator.py`):
   ```python
   def get_shared_cache_instance(
       cache_root: Path,
       tag: str | None = None,
       enabled: bool = True,
       max_size_gb: int = 2,
       timeout: int = 30,
   ) -> CacheManager:
       """Get shared cache instance, creating if needed."""
   ```

2. **Updated Factory Functions**:
   ```python
   # Domain-agnostic cache creation with shared coordination
   cache = create_default_cache(tag="compilation")  # Shared instance
   cache2 = create_default_cache(tag="compilation") # Same instance
   cache3 = create_default_cache(tag="metrics")     # Different instance
   ```

3. **Domain-Specific Factories**:
   ```python
   # Compilation domain uses shared coordination
   from glovebox.compilation.cache import create_compilation_cache_service
   
   cache_manager, workspace_service = create_compilation_cache_service(user_config)
   ```

#### Cache Coordination Benefits

- **Single Cache Instances**: Same tag → same cache instance across all domains
- **Domain Isolation**: Different tags → separate cache instances with isolated namespaces
- **Memory Efficiency**: Eliminates duplicate cache managers and reduces memory usage
- **Thread/Process Safety**: DiskCache with SQLite backend supports concurrent access
- **Test Isolation**: `reset_shared_cache_instances()` ensures clean state between tests

#### Implementation Patterns

1. **Tag-Based Isolation**:
   ```python
   # Each domain gets its own isolated cache namespace
   compilation_cache = create_default_cache(tag="compilation")
   metrics_cache = create_default_cache(tag="metrics")
   layout_cache = create_default_cache(tag="layout")
   ```

2. **Service Integration**:
   ```python
   # Services use domain-specific cache factories
   def create_zmk_west_service() -> CompilationServiceProtocol:
       cache, workspace_service = create_compilation_cache_service(user_config)
       return create_zmk_west_service(docker_adapter, user_config, cache, workspace_service)
   ```

3. **Test Safety**:
   ```python
   # Automatic cache reset fixture (autouse=True)
   @pytest.fixture(autouse=True)
   def reset_shared_cache() -> Generator[None, None, None]:
       reset_shared_cache_instances()  # Before test
       yield
       reset_shared_cache_instances()  # After test
   ```

### CLI Structure

All CLI commands follow a consistent pattern with profile-based parameter:

```
glovebox [command] [subcommand] [--profile KEYBOARD/FIRMWARE] [options]
```

Examples:
- `glovebox layout compile my_layout.json output/my_keymap --profile glove80/v25.05`
- `glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05`
- `glovebox firmware flash firmware.uf2 --profile glove80/v25.05`

### Modular Configuration System

The configuration system now uses a modular YAML structure with includes:

```yaml
# keyboards/glove80.yaml (main config)
includes:
  - "glove80/main.yaml"

# keyboards/glove80/main.yaml
keyboard: "glove80"
description: "MoErgo Glove80 split ergonomic keyboard"
includes:
  - "hardware.yaml"     # Hardware specifications
  - "firmwares.yaml"    # Firmware variants
  - "strategies.yaml"   # Compilation strategies
  - "kconfig.yaml"      # Kconfig options
  - "behaviors.yaml"    # Behavior definitions
```

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

### Compilation Configuration

Compilation strategies are now configured through unified models:

```python
from glovebox.compilation.models import ZmkCompilationConfig, MoergoCompilationConfig

# ZMK compilation with west workspace
zmk_config = ZmkCompilationConfig(
    type="zmk_config",
    repository="zmkfirmware/zmk",
    branch="main",
    build_matrix=BuildMatrix(board=["nice_nano_v2"]),
    use_cache=True
)

# MoErgo compilation with Nix toolchain
moergo_config = MoergoCompilationConfig(
    type="moergo",
    repository="moergo-sc/zmk",
    branch="v25.05",
    build_matrix=BuildMatrix(board=["glove80_lh", "glove80_rh"])
)
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
from glovebox.compilation.models import CompilationConfig, BuildMatrix

# Core models from models package
from glovebox.models.base import GloveboxBaseModel
from glovebox.models.results import BaseResult

# Layout domain services
from glovebox.layout import (
    create_layout_service, 
    create_layout_component_service,
    create_layout_display_service,
    create_behavior_registry
)

# Firmware domain services
from glovebox.firmware.flash import (
    create_flash_service, 
    create_device_detector,
    create_usb_flasher
)

# Compilation domain services
from glovebox.compilation import (
    create_compilation_service,
    create_zmk_west_service,
    create_moergo_nix_service
)

# Version management and firmware tracking
from glovebox.layout.version_manager import create_version_manager
from glovebox.layout.firmware_tracker import create_firmware_tracker

# Configuration from config package
from glovebox.config import create_keyboard_profile, create_user_config

# MoErgo domain services
from glovebox.moergo.bookmark_service import create_bookmark_service
from glovebox.moergo.client import create_moergo_client

# Core infrastructure with shared cache coordination
from glovebox.core.cache_v2 import (
    create_default_cache, 
    create_cache_from_user_config,
    get_shared_cache_instance,
    reset_shared_cache_instances
)
from glovebox.adapters import create_docker_adapter, create_file_adapter
```

**IMPORTANT**: The codebase uses clean domain boundaries with no backward compatibility layers.

## CLI Architecture and Commands

### Modular CLI Structure

The CLI has been refactored into a modular structure with focused command modules under `glovebox/cli/commands/`:

```
glovebox/cli/commands/
├── __init__.py                 # Command registration
├── layout/                     # Layout management commands
│   ├── __init__.py            # Layout app registration
│   ├── compilation.py         # Compile, validate commands
│   ├── comparison.py          # Diff, create-patch commands
│   ├── component.py           # Decompose, compose commands
│   ├── display.py            # Show command
│   ├── editor.py             # Field editing commands
│   ├── layer.py              # Layer management commands
│   └── version.py            # Version management commands
├── config/                    # Configuration management
│   ├── __init__.py           # Config app registration
│   ├── edit.py               # Unified edit command
│   ├── management.py         # List, export, import commands
│   └── updates.py            # Version check commands
├── keyboard/                  # Keyboard information commands
│   ├── __init__.py           # Keyboard app registration
│   ├── info.py               # List, show commands
│   └── firmwares.py          # Firmware listing commands
├── firmware/                  # Firmware operations
├── moergo/                   # MoErgo integration
├── status.py                 # System status
├── cache.py                  # Cache management
└── config_legacy.py         # Legacy command compatibility
```

### Key CLI Design Principles

1. **Modular Organization**: Each command domain is a separate module under 500 lines
2. **Unified Interfaces**: Commands like `config edit` support multiple operations in one call
3. **Backward Compatibility**: Legacy commands maintained with deprecation warnings
4. **Clean Registration**: Each module registers its commands via `register_commands()` functions
5. **Consistent Patterns**: All commands follow the same structure and error handling

### Configuration Commands

#### Enhanced `config list` Command

The `config list` command now serves as the primary configuration viewing interface:

```bash
# Basic configuration listing
glovebox config list

# Show current values alongside defaults
glovebox config list --defaults

# Include field descriptions
glovebox config list --descriptions

# Show configuration sources
glovebox config list --sources

# Combine all information
glovebox config list --defaults --descriptions --sources
```

**Key Features:**
- Replaced the old `config options` command functionality
- Shows current configuration values in a table format
- Optional columns for defaults, descriptions, and sources
- Helpful usage guidance at the bottom

#### Unified `config edit` Command

The `config edit` command supports multiple operations in a single call:

```bash
# Multiple operations in one command
glovebox config edit \
  --get cache_strategy \
  --set emoji_mode=true \
  --add keyboard_paths=/new/path \
  --remove keyboard_paths=/old/path \
  --save
```

**Capabilities:**
- `--get`: Retrieve one or more configuration values
- `--set`: Set configuration values using key=value format
- `--add`: Add values to list-type configurations
- `--remove`: Remove values from list-type configurations
- `--save/--no-save`: Control whether changes are persisted

### Keyboard Commands

#### Dedicated Keyboard Module

Keyboard-related commands have been moved to a dedicated `keyboard` module:

```bash
# List available keyboards
glovebox keyboard list [--verbose] [--format json]

# Show keyboard details
glovebox keyboard show KEYBOARD_NAME [--verbose] [--format json]

# List firmware versions for a keyboard
glovebox keyboard firmwares KEYBOARD_NAME [--format json]
```

**Benefits:**
- Clean separation from configuration commands
- Focused interface for keyboard management
- Consistent output formatting across commands
- Tab completion for keyboard names

### Legacy Command Support

Legacy commands are maintained for backward compatibility but marked as deprecated:

```bash
# Legacy commands (deprecated but functional)
glovebox config keyboards       # → glovebox keyboard list
glovebox config show-keyboard   # → glovebox keyboard show
glovebox config firmwares       # → glovebox keyboard firmwares
```

**Deprecation Strategy:**
- Legacy commands show deprecation warnings
- Commands continue to work during transition period
- New commands provide enhanced functionality
- Documentation updated to promote new interface

### Command Registration Pattern

All command modules follow a consistent registration pattern:

```python
# In each command module
def register_commands(app: typer.Typer) -> None:
    """Register commands with the main app."""
    app.add_typer(command_app, name="command-name")

# In glovebox/cli/commands/__init__.py
def register_all_commands(app: typer.Typer) -> None:
    """Register all CLI commands with the main app."""
    register_layout_commands(app)
    register_firmware_commands(app)
    register_config_commands(app)
    register_keyboard_commands(app)
    register_status_commands(app)
    register_moergo_commands(app)
    app.add_typer(cache_app, name="cache")
```

This ensures consistent command discovery and registration across the entire CLI.
