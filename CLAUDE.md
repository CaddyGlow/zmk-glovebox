# CLAUDE.md

This file provides comprehensive guidance to Claude Code (claude.ai/code) and other LLMs when working with code in this repository.

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

2. **NEVER use direct .model_dump() - ALWAYS use proper parameters or inherited methods**:
   ```python
   # ✅ CORRECT - Use model_dump with proper parameters
   data = model.model_dump(by_alias=True, exclude_unset=True, mode="json")
   
   # ✅ CORRECT - Use the inherited to_dict() method (recommended)
   data = model.to_dict()
   
   # ✅ CORRECT - Use to_dict_python() for Python objects
   data = model.to_dict_python()
   
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

5. **GloveboxBaseModel provides consistent defaults**:
   ```python
   # Built-in configuration in GloveboxBaseModel:
   model_config = ConfigDict(
       extra="allow",                    # Allow extra fields for flexibility
       str_strip_whitespace=True,        # Strip whitespace from strings
       use_enum_values=True,             # Use enum values in serialization
       validate_assignment=True,         # Validate assignment after creation
       validate_by_alias=True,           # Allow loading with alias and name
       validate_by_name=True,
   )
   ```

**These rules ensure consistent serialization behavior across ALL models with proper alias handling, unset field exclusion, and JSON-safe output.**

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
   
   # ✅ CORRECT - Cache reset fixture pattern
   @pytest.fixture(autouse=True)
   def reset_shared_cache() -> Generator[None, None, None]:
       reset_shared_cache_instances()  # Before test
       yield
       reset_shared_cache_instances()  # After test
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

7. **MANDATORY TESTING REQUIREMENTS**:
   - **ALL public functions/methods/classes MUST have comprehensive tests**
   - **Minimum 90% code coverage** for all new code
   - **NO CODE can be merged without tests** - this is NON-NEGOTIABLE
   - All tests should pass mypy type checking

**If you encounter ANY test pollution or isolation issues, you MUST fix them immediately before proceeding with other tasks.**

## CRITICAL: UI Theming and Visual Consistency

**MANDATORY REQUIREMENTS - MUST BE FOLLOWED WITHOUT EXCEPTION:**

### ASCII-First Interface Policy

1. **NO EMOJIS outside glovebox/cli/helpers/theme.py**:
   ```python
   # ❌ INCORRECT - Never use direct emojis in code
   print("✅ Success")
   console.print("🔧 Processing")
   
   # ✅ CORRECT - Always use theme helpers
   from glovebox.cli.helpers.theme import Icons, get_themed_console
   
   console = get_themed_console(icon_mode="text")  # ASCII mode
   icon = Icons.get_icon("SUCCESS", "text")  # Returns "✓"
   console.print_success("Operation completed")
   ```

2. **ASCII/Unicode Symbol Hierarchy** (in order of preference):
   - **ASCII Characters**: `*, +, -, |, >, <, ^, v` for basic indicators
   - **Unicode Symbols**: `✓, ✗, →, ←, ↑, ↓, ⚠, ℹ` for status and flow
   - **Box Drawing**: `┌─┐│└┘, ▌, ▍, █, ░` for frames and progress
   - **Geometric Shapes**: `●, ○, ■, □, ▲, ▼, ◆` for visual elements

3. **Professional Text Alternatives**:
   ```python
   # Status indicators
   SUCCESS = "✓"    # Check mark  
   ERROR = "✗"      # X mark
   WARNING = "⚠"    # Warning triangle
   INFO = "ℹ"       # Info symbol
   
   # Process indicators  
   LOADING = "..."  # Simple loading
   PROGRESS = "▌"   # Progress blocks
   BULLET = "•"     # List bullets
   ARROW = "→"      # Flow direction
   ```

### Color Scheme Enforcement

4. **NO HARDCODED COLORS outside theme.py**:
   ```python
   # ❌ INCORRECT - Never hardcode colors
   console.print("Error", style="red")
   table.add_column("Name", style="bold blue")
   
   # ✅ CORRECT - Always use theme colors
   from glovebox.cli.helpers.theme import Colors, get_themed_console
   
   console = get_themed_console()
   console.print_error("Error message")  # Auto-applies error styling
   table.add_column("Name", style=Colors.PRIMARY)
   ```

5. **Status-Based Color Mapping** (MANDATORY):
   ```python
   # Core status colors
   SUCCESS = "bold green"     # Operations that completed successfully  
   ERROR = "bold red"         # Operations that failed
   WARNING = "bold yellow"    # Warnings and cautions
   INFO = "bold blue"         # Informational messages
   
   # Operational states
   RUNNING = "bold cyan"      # Currently executing
   STOPPED = "dim red"        # Stopped/inactive
   PENDING = "yellow"         # Waiting to execute  
   AVAILABLE = "green"        # Available for use
   UNAVAILABLE = "red"        # Not available
   ```

### Rich Framework Integration

6. **MANDATORY Rich Framework Usage**:
   ```python
   # ✅ CORRECT - Use Rich components with theme integration
   from rich.table import Table
   from rich.panel import Panel
   from glovebox.cli.helpers.theme import TableStyles, PanelStyles
   
   # Create themed tables and panels
   table = TableStyles.create_basic_table("Devices", "DEVICE", "text")
   panel = PanelStyles.create_info_panel("Information", icon_mode="text")
   ```

7. **Theme Mode Support** (maintain backwards compatibility):
   ```python
   # Support three modes: emoji, nerdfont, text
   IconMode.EMOJI     # 🔧 (legacy support)
   IconMode.NERDFONT  # \uf2db (for terminals with nerd fonts)  
   IconMode.TEXT      # ✓ (DEFAULT - professional ASCII/Unicode)
   ```

### Enforcement Rules

8. **Single Source of Truth**: ALL visual elements MUST be defined in `glovebox/cli/helpers/theme.py`

9. **Consistency Patterns**:
   - Status messages → Use `console.print_success/error/warning/info()`
   - Tables → Use `TableStyles.create_*_table()` methods
   - Panels → Use `PanelStyles.create_*_panel()` methods  
   - Icons → Use `Icons.get_icon()` or `Icons.format_with_icon()`

10. **Testing Requirements**:
    - All theme components MUST have comprehensive tests
    - Test all icon modes (emoji, nerdfont, text)
    - Verify no hardcoded styling outside theme.py

**The default interface is ASCII/Unicode professional appearance. Emoji mode is preserved only for users who explicitly enable it through configuration.**

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

4. **Exception Naming**: Use descriptive error class names
   ```python
   # ✅ CORRECT - Specific exception types
   class KeymapError(GloveboxError):
   class ConfigurationError(GloveboxError):
   class FlashError(GloveboxError):
   
   # ❌ INCORRECT - Generic error names
   class Error(Exception):
   class MyError(Exception):
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

2. **Factory Function Pattern**: Use `create_*` prefix for all factory functions
   ```python
   # ✅ CORRECT - Factory function naming
   def create_layout_service() -> LayoutService:
   def create_flash_service() -> FlashService:
   def create_keyboard_profile() -> KeyboardProfile:
   
   # ❌ INCORRECT - Non-factory naming
   def get_layout_service() -> LayoutService:
   def make_flash_service() -> FlashService:
   ```

3. **Layout Domain Specific Standards**:
   ```python
   # ✅ CORRECT - Component operations
   def decompose_components()  # Split layout into files
   def compose_components()    # Combine files into layout
   
   # ✅ CORRECT - Display operations  
   def show()           # CLI display commands
   def format_*()       # Text formatting operations
   ```

### **Variable and Parameter Naming**

1. **Use descriptive names for complex objects**:
   ```python
   # ✅ CORRECT - Clear variable names
   user_config = create_user_config()
   layout_service = create_layout_service()
   keyboard_profile = create_keyboard_profile("glove80", "v25.05")
   
   # ❌ INCORRECT - Abbreviated names
   cfg = create_user_config()
   svc = create_layout_service()
   profile = create_keyboard_profile("glove80", "v25.05")
   ```

2. **Boolean variables should be questions**:
   ```python
   # ✅ CORRECT - Question-form booleans
   is_enabled: bool
   has_firmware: bool
   should_validate: bool
   
   # ❌ INCORRECT - Non-question booleans
   enabled: bool
   firmware: bool
   validate: bool
   ```

## Project Architecture

### Domain-Driven Structure

The codebase is organized into self-contained domains with clear boundaries:

#### Layout Domain (`glovebox/layout/`)
- **Purpose**: Keyboard layout processing, JSON→DTSI conversion, component operations, version management
- **Factory Functions**: `create_layout_service()`, `create_layout_component_service()`, `create_layout_display_service()`, `create_grid_layout_formatter()`, `create_zmk_file_generator()`, `create_behavior_registry()`
- **Models**: `LayoutData`, `LayoutBinding`, `LayoutLayer`, behavior models
- **Subdomains**:
  - `behavior/`: Behavior analysis, formatting, and models
  - `comparison/`: Layout comparison services
  - `diffing/`: Diff and patch operations
  - `editor/`: Layout editing operations
  - `layer/`: Layer management services
  - `utils/`: Field parsing, JSON operations, validation
- **Key Features**: Version management, firmware tracking, component decomposition

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
- **Factory Functions**: `create_keyboard_profile()`, `create_user_config()`, `create_include_loader()`
- **Key Components**: `keyboard_profile.py`, `profile.py`, `user_config.py`, `include_loader.py`
- **Models Subdomain**: Behavior, display, firmware, keyboard, user, ZMK models
- **Key Features**:
  - **Modular YAML Structure**: YAML includes for configuration composition
  - **Keyboard-Only Profile Support**: Minimal configurations for flashing operations
  - **Profile-based Combinations**: Keyboard + firmware or keyboard-only patterns

#### Core Models (`glovebox/models/`)
- **Purpose**: Cross-domain core models and base classes
- **Key Components**: 
  - `GloveboxBaseModel`: Base class for all Pydantic models
  - `DockerUserContext`: Docker execution context
  - `BaseResult`: Base result class with consistent patterns
  - `PreservingPath`: Path handling with serialization preservation

#### Adapters (`glovebox/adapters/`)
- **Purpose**: External system interfaces following adapter pattern
- **Factory Functions**: `create_docker_adapter()`, `create_file_adapter()`, `create_template_adapter()`, `create_usb_adapter()`, `create_config_file_adapter()`
- **Components**: `DockerAdapter`, `FileAdapter`, `USBAdapter`, `TemplateAdapter`, `ConfigFileAdapter`
- **Pattern**: Clean adapter pattern with protocol interfaces

#### Core Infrastructure (`glovebox/core/`)
- **Purpose**: Core application infrastructure and shared services
- **Cache Coordination** (`glovebox/core/cache/`):
  - **Shared Coordination**: Single cache instances across domains with proper isolation
  - **Factory Functions**: `create_default_cache()`, `create_cache_from_user_config()`, `get_shared_cache_instance()`
  - **Domain Isolation**: Uses tags (compilation, metrics, layout, etc.) for namespace separation
  - **Test Safety**: `reset_shared_cache_instances()` for complete test isolation
  - **Cache Manager**: `DiskCacheManager` with SQLite backend for thread/process safety
- **Components**: Error handling, logging setup, startup services, version checking, metrics

#### MoErgo Domain (`glovebox/moergo/`)
- **Purpose**: MoErgo service integration and API client
- **Key Components**: Layout versioning, credential management
- **Client Subdomain**: MoErgo API client with auth, credentials, and models
- **Services**: Authentication, layout client, utility client, firmware client

#### Supporting Infrastructure
- **Services** (`glovebox/services/`): `BaseService` and `BaseServiceProtocol` patterns
- **Protocols** (`glovebox/protocols/`): Runtime-checkable protocols for type safety
- **Utils** (`glovebox/utils/`): Process streaming, error utilities, diagnostics
- **Library** (`glovebox/library/`): Layout library management with fetchers and repository

### Key Design Patterns

1. **Domain-Driven Design**: Business logic organized by domains with clear boundaries
2. **Factory Functions**: Consistent creation patterns for all services and components
3. **Protocol-Based Interfaces**: Type-safe abstractions with runtime checking
4. **Domain Ownership**: Each domain owns its models, services, and business logic
5. **Clean Imports**: No backward compatibility layers - single source of truth for imports
6. **Shared Cache Coordination**: Single cache instances across domains with proper isolation
7. **Service Layer**: All business logic encapsulated in service classes inheriting from BaseService

### Shared Cache Coordination System

**COMPLETED**: The cache system uses shared coordination across all domains while maintaining proper isolation and following factory function patterns.

#### Architecture Overview

The shared cache coordination system eliminates multiple independent cache instances by:
- **Coordinating cache instances** across domains using a central registry
- **Domain isolation** through cache tags (compilation, metrics, layout, etc.)
- **Factory function compliance** using `create_*` functions (no singletons)
- **Test safety** with automatic cache reset between tests

#### Core Components

1. **Cache Coordinator** (`glovebox/core/cache/cache_coordinator.py`):
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
       return ZmkWestService(docker_adapter, user_config, cache, workspace_service)
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

#### Modular CLI Structure

The CLI has been refactored into a modular structure with focused command modules under `glovebox/cli/commands/`:

```
glovebox/cli/commands/
├── __init__.py                 # Command registration
├── layout/                     # Layout management commands
│   ├── __init__.py            # Layout app registration
│   ├── core.py                # Compile, validate, show commands
│   ├── comparison.py          # Diff, create-patch commands
│   ├── file_operations.py     # Split, merge commands
│   ├── edit.py                # Field editing commands
│   └── parsing.py             # Keymap parsing commands
├── config/                    # Configuration management
│   ├── __init__.py           # Config app registration
│   ├── edit.py               # Unified edit command
│   ├── management.py         # List, export, import commands
│   └── updates.py            # Version check commands
├── profile/                   # Profile management commands
│   ├── __init__.py           # Profile app registration
│   ├── info.py               # List, show commands
│   └── firmwares.py          # Firmware listing commands
├── firmware.py               # Firmware operations
├── moergo.py                 # MoErgo integration
├── status.py                 # System status
├── metrics.py                # Metrics commands
├── cache/                    # Cache management
│   ├── __init__.py           # Cache app registration
│   ├── show.py               # Cache information
│   ├── clear.py              # Cache cleanup
│   └── workspace.py          # Workspace management
├── library/                  # Library management
│   ├── __init__.py           # Library app registration
│   ├── fetch.py              # Fetch layouts
│   ├── search.py             # Search layouts
│   └── list_cmd.py           # List layouts
└── cloud.py                  # Cloud operations
```

#### CLI Design Principles

1. **Modular Organization**: Each command domain is a separate module under 500 lines
2. **Unified Interfaces**: Commands like `config edit` support multiple operations in one call
3. **Backward Compatibility**: Legacy commands maintained with deprecation warnings
4. **Clean Registration**: Each module registers its commands via `register_commands()` functions
5. **Consistent Patterns**: All commands follow the same structure and error handling
6. **Error Handling**: Use `@handle_errors` decorator for consistent error management

#### Command Registration Pattern

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
    register_profile_commands(app)
    register_status_commands(app)
    register_moergo_commands(app)
    app.add_typer(cache_app, name="cache")
```

This ensures consistent command discovery and registration across the entire CLI.

### Modular Configuration System

The configuration system uses a modular YAML structure with includes:

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

# Keyboard-only profile (firmware_version=None)
keyboard_profile = create_keyboard_profile("glove80")
```

**CLI Integration**:
```bash
# Using profile parameter with firmware
glovebox layout compile input.json output/ --profile glove80/v25.05

# Using keyboard-only profile (no firmware part)
glovebox status --profile glove80
glovebox firmware flash firmware.uf2 --profile glove80
```

### Compilation Configuration

Compilation strategies are configured through unified models:

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

# Enhanced layout operations
glovebox layout diff layout1.json layout2.json --include-dtsi --json
glovebox layout edit my_layout.json --set title="New Title" --save
```

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

# Configuration from config package
from glovebox.config import create_keyboard_profile, create_user_config

# MoErgo domain services
from glovebox.moergo.client import create_moergo_client

# Core infrastructure with shared cache coordination
from glovebox.core.cache import (
    create_default_cache, 
    create_cache_from_user_config,
    get_shared_cache_instance,
    reset_shared_cache_instances
)
from glovebox.adapters import create_docker_adapter, create_file_adapter

# CLI helpers and themes
from glovebox.cli.helpers.theme import Icons, get_themed_console, Colors
from glovebox.cli.decorators.error_handling import handle_errors
```

**IMPORTANT**: The codebase uses clean domain boundaries with no backward compatibility layers.

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

## Advanced Patterns and Anti-Patterns

### Factory Function Implementation

1. **Consistent Dependency Injection**:
   ```python
   # ✅ CORRECT - Explicit dependency injection
   def create_layout_service(
       file_adapter: FileAdapterProtocol,
       template_adapter: TemplateAdapterProtocol,
       behavior_registry: BehaviorRegistryProtocol,
       component_service: LayoutComponentService,
       layout_service: LayoutDisplayService,
       behavior_formatter: BehaviorFormatterImpl,
       dtsi_generator: ZmkFileContentGenerator,
       keymap_parser: ZmkKeymapParser | None = None,
   ) -> LayoutService:
       """Create a LayoutService instance with explicit dependency injection."""
   ```

2. **Factory Function Documentation**:
   ```python
   # ✅ CORRECT - Document dependencies and their factories
   def create_layout_service(
       # ... parameters
   ) -> LayoutService:
       """Create a LayoutService instance with explicit dependency injection.

       All dependencies are required to ensure proper dependency management.
       Use other factory functions to create the required dependencies:
       - create_file_adapter() for file_adapter
       - create_template_adapter() for template_adapter
       - create_behavior_registry() for behavior_registry
       """
   ```

### Error Handling Patterns

1. **Debug-Aware Exception Logging**:
   ```python
   # ✅ CORRECT - Use debug-aware exception logging
   def risky_operation(self):
       try:
           # Operation that might fail
           pass
       except Exception as e:
           exc_info = self.logger.isEnabledFor(logging.DEBUG)
           self.logger.error("Operation failed: %s", e, exc_info=exc_info)
           raise
   ```

2. **CLI Error Handling with Decorators**:
   ```python
   # ✅ CORRECT - Use handle_errors decorator for CLI commands
   from glovebox.cli.decorators.error_handling import handle_errors
   
   @handle_errors
   def my_cli_command():
       # Command implementation
       pass
   ```

### Service Layer Patterns

1. **BaseService Inheritance**:
   ```python
   # ✅ CORRECT - Inherit from BaseService
   class MyDomainService(BaseService):
       def __init__(self, dependency: SomeDependency):
           super().__init__("MyDomainService", "1.0.0")
           self.dependency = dependency
   ```

2. **Protocol Implementation**:
   ```python
   # ✅ CORRECT - Define protocols for type safety
   class MyServiceProtocol(Protocol):
       def perform_operation(self) -> bool: ...
   
   # ✅ CORRECT - Runtime checking for protocols
   def create_my_service() -> MyServiceProtocol:
       service = MyService()
       assert isinstance(service, MyServiceProtocol)
       return service
   ```

### Anti-Patterns to Avoid

1. **❌ NEVER use implementation suffixes for non-implementations**:
   ```python
   # ❌ INCORRECT - Don't use Impl suffix for main classes
   class LayoutServiceImpl:  # Should be LayoutService
       pass
   
   # ✅ CORRECT - Use Impl only for specific implementations
   class BehaviorFormatterImpl:  # Specific implementation of formatting
       pass
   ```

2. **❌ NEVER create services without factory functions**:
   ```python
   # ❌ INCORRECT - Direct instantiation without factory
   service = LayoutService(adapter, template, registry)
   
   # ✅ CORRECT - Use factory function
   service = create_layout_service(adapter, template, registry)
   ```

3. **❌ NEVER use global state or singletons**:
   ```python
   # ❌ INCORRECT - Singleton pattern
   class GlobalService:
       _instance = None
       
       def __new__(cls):
           if cls._instance is None:
               cls._instance = super().__new__(cls)
           return cls._instance
   
   # ✅ CORRECT - Use shared cache coordination instead
   cache = get_shared_cache_instance(cache_root, tag="my_domain")
   ```

4. **❌ NEVER bypass the theme system**:
   ```python
   # ❌ INCORRECT - Direct emoji or color usage
   print("🔧 Building...")
   console.print("Error", style="red")
   
   # ✅ CORRECT - Use theme system
   console = get_themed_console()
   icon = Icons.get_icon("BUILD", "text")
   console.print_error("Error message")
   ```

5. **❌ NEVER use bare exceptions**:
   ```python
   # ❌ INCORRECT - Bare exception catching
   try:
       operation()
   except:  # Never do this
       pass
   
   # ✅ CORRECT - Specific exception handling
   try:
       operation()
   except SpecificError as e:
       self.logger.error("Specific operation failed: %s", e)
   ```

### Performance Considerations

1. **Lazy Imports**: Use lazy imports for optional dependencies
2. **Cache Utilization**: Always use the shared cache system for expensive operations
3. **Streaming Operations**: Use streaming for large file operations
4. **Resource Cleanup**: Always use context managers or try/finally for resource cleanup

## Documentation Structure

For detailed information, refer to:

- **Developer Documentation**: `docs/dev/` - Architecture guides, domain documentation, coding conventions
- **User Documentation**: `docs/user/` - Getting started, tutorials, troubleshooting
- **Technical Reference**: `docs/technical/` - API reference, keymap format specification
- **Implementation Plans**: `docs/implementation/` - Current development plans and completed features

## Technology Stack

### Core Dependencies
- **Python**: 3.11+ (required minimum version)
- **Pydantic**: 2.11+ (data validation and serialization)
- **Typer**: 0.16+ (CLI framework)
- **Rich**: 13.3+ (terminal UI and formatting)
- **PyYAML**: 6.0+ (YAML configuration processing)
- **Jinja2**: 3.1+ (template engine for ZMK files)

### Key Libraries
- **Docker**: Required for firmware compilation
- **diskcache**: 5.6+ (intelligent caching system)
- **deepdiff**: 8.5+ (data comparison for layout diffs)
- **jsonpatch**: 1.33+ (JSON patching operations)
- **psutil**: 7.0+ (system process management)
- **pyudev**: 0.24+ (Linux USB device detection)
- **keyring**: 25.6+ (secure credential storage)
- **requests**: 2.32+ (HTTP client for MoErgo integration)

### Development Tools
- **uv**: Modern Python dependency manager (preferred)
- **ruff**: 0.11+ (linting and code formatting)
- **mypy**: 1.15+ (static type checking)
- **pytest**: 8.3+ (testing framework)
- **pre-commit**: 4.2+ (git hook management)

## Final Reminders

- **Always prioritize readability and maintainability over cleverness**
- **Follow the established patterns consistently across the codebase**
- **Use factory functions for all service creation**
- **Maintain proper test isolation with provided fixtures**
- **Leverage the theme system for all UI elements**
- **Document complex business logic thoroughly**
- **Keep domain boundaries clean and well-defined**

When in doubt, follow the patterns established in the existing codebase and prioritize simplicity and clarity over complex abstractions.