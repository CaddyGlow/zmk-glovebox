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
- **Domain-Driven Design**: Business logic organized by domains (layout, flash, behavior)
- **Service Layer**: Domain services with single responsibility 
- **Adapter Pattern**: External interfaces (Docker, USB, File, Template, Config)
- **Configuration System**: Type-safe profiles combining keyboard + firmware configs
- **Cross-Platform**: OS abstraction for USB device detection and flashing

The layout domain handles complex JSON→DTSI conversion with behaviors like macros, hold-taps, combos, and component extraction/merging.

## Active Development Plans

**CLI Output Format Enhancement** - See `docs/cli_output_format_implementation_plan.md` for detailed implementation plan and progress tracking of unified output format system with Rich syntax support.

**Generic Docker Compiler with ZMK West Workspace Support** - See `docs/generic_docker_compiler_zmk_west_workspace_implementation.md` for comprehensive implementation plan providing modern ZMK west workspace builds, multi-strategy compilation (west, cmake, make, ninja), intelligent workspace caching, and enhanced configuration flexibility while maintaining full backward compatibility.

**Dynamic ZMK Config Generation** - ✅ **COMPLETED** - Comprehensive on-the-fly ZMK config workspace generation system that eliminates the need for external repositories. Features automatic split keyboard detection, shield naming conventions, build.yaml generation, and full ZMK west workspace compatibility. Located in `glovebox/compilation/generation/` with complete test coverage.

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
   - Use single `with` statements with multiple contexts when possible

4. **MANDATORY PRE-COMMIT CHECKS**:
   ```bash
   pre-commit run --all-files
   pytest
   ```

5. **ZERO TOLERANCE for common linting violations**:
   - **SIM117**: Must use single with statement with multiple contexts
   - **UP035**: Must use modern typing (`dict` not `typing.Dict`)
   - **PTH123**: Must use `Path.open()` not `open()`
   - **B904**: Must use `raise ... from err` in except clauses
   - **N815**: No mixedCase variable names in class scope
   - **SIM102**: Use single if statement instead of nested if statements

**If you encounter ANY linting errors, you MUST fix them immediately before proceeding with other tasks.**

## Naming Conventions

**CRITICAL: These naming conventions are MANDATORY and must be followed consistently:**

### **Class Naming Standards**

1. **Adapter Classes**: Use `*Adapter` suffix (NO `Impl` suffix)
   ```python
   # ✅ CORRECT
   class DockerAdapter:
   class USBAdapter:
   class FileAdapter:
   class TemplateAdapter:
   
   # ❌ INCORRECT
   class DockerAdapterImpl:
   class JinjaTemplateAdapter:
   class FileSystemAdapter:
   ```

2. **Service Classes**: Use `*Service` suffix (NO `Impl` suffix)
   ```python
   # ✅ CORRECT
   class BuildService(BaseService):
   class LayoutService(BaseService):
   class FlashService:
   
   # ❌ INCORRECT
   class BuildServiceImpl:
   class BaseServiceImpl:
   ```

3. **Protocol Classes**: Use `*Protocol` suffix
   ```python
   # ✅ CORRECT
   class FileAdapterProtocol(Protocol):
   class BaseServiceProtocol(Protocol):
   
   # ❌ INCORRECT
   class BaseService(Protocol):  # Name collision with implementation
   ```

### **Function Naming Standards**

1. **Use Descriptive Verbs**: Function names must clearly indicate their purpose
   ```python
   # ✅ CORRECT - Descriptive function names
   def check_exists(path: Path) -> bool:
   def create_directory(path: Path) -> None:
   def mount_device(device: BlockDevice) -> list[str]:
   def unmount_device(device: BlockDevice) -> bool:
   
   # ❌ INCORRECT - Terse/unclear function names
   def exists(path: Path) -> bool:
   def mkdir(path: Path) -> None:
   def mount(device: BlockDevice) -> list[str]:
   def unmount(device: BlockDevice) -> bool:
   ```

2. **Consistent Verb Patterns**: Use standard verbs across the codebase
   - `check_*` for validation/existence checks
   - `create_*` for creation operations
   - `get_*` for retrieval operations
   - `*_device` suffix for device-specific operations

3. **Layout Domain Specific Standards**:
   ```python
   # ✅ CORRECT - Component operations
   def decompose_components()  # Split layout into files
   def compose_components()    # Combine files into layout
   
   # ✅ CORRECT - Display operations  
   def show()           # CLI display commands
   def format_*()       # Text formatting operations
   
   # ✅ CORRECT - File method patterns
   def generate_from_file()
   def decompose_components_from_file()
   def show_from_file()
   def validate_from_file()
   
   # ❌ INCORRECT - Old naming
   def extract_components()    # Use decompose_components
   def combine_components()    # Use compose_components
   def merge_components()      # Use compose_components
   def generate_display()      # Use show() for CLI, format_*() for text
   ```

### **Import and Export Standards**

1. **Factory Functions**: Always return protocol types
   ```python
   # ✅ CORRECT
   def create_file_adapter() -> FileAdapterProtocol:
       return FileAdapter()
   
   def create_build_service() -> BaseServiceProtocol:
       return BuildService("build", "1.0.0")
   ```

2. **Module Exports**: Export both protocols and implementations
   ```python
   # glovebox/adapters/__init__.py
   __all__ = [
       # Protocols
       "FileAdapterProtocol",
       "DockerAdapterProtocol",
       # Implementations
       "FileAdapter",
       "DockerAdapter",
       # Factory functions
       "create_file_adapter",
       "create_docker_adapter",
   ]
   ```

3. **Import Patterns**: Use consistent import structure
   ```python
   # ✅ CORRECT - Import from domain packages
   from glovebox.adapters import FileAdapter, create_file_adapter
   from glovebox.services import BaseServiceProtocol, BaseService
   
   # ❌ INCORRECT - No backward compatibility imports
   from glovebox.adapters import FileSystemAdapter  # Old name
   from glovebox.services import BaseServiceImpl     # Old name
   ```

### **Enforcement**

- **All new code** must follow these naming conventions
- **No exceptions** will be made for legacy compatibility
- **Breaking changes** to improve naming consistency are encouraged
- **Tests must be updated** when class/function names change

## Essential Commands

### Quick Commands

Use these simplified commands for common development tasks:

```bash
# Using make
make test           # Run all tests
make lint           # Run linting checks
make format         # Format code and fix linting issues
make coverage       # Run tests with coverage reporting
make setup          # Create virtual environment and install dependencies
make clean          # Clean build artifacts and coverage reports
make help           # Show available commands
```

You can also run the scripts directly:

```bash
# Using scripts
./scripts/test.sh
./scripts/lint.sh
./scripts/format.sh
./scripts/coverage.sh
./scripts/setup.sh
```

### Command Execution

If the virtual environment is not activated, prefix any Python command with `uv run` to ensure it runs with the correct dependencies:

```bash
# Run commands with uv
uv run pytest
uv run ruff check .
uv run mypy glovebox/
```

### Installation

```bash
# Development installation with development dependencies
uv sync 

# Normal installation 
uv sync --no-dev

# venv is normally created in .venv
source .venv/bin/activate

# if with devenv
source .devenv/state/venv/bin/activate

# Pre-commit setup
pre-commit install

# Add dependencies with uv to the project
uv add httpx 

# Add specific development dependencies with uv to the project
uv add --dev ruff            # Add linting/formatting
```

### Build and Run

```bash
# Run glovebox CLI directly
python -m glovebox.cli [command]
# or with uv:
uv run python -m glovebox.cli [command]

# Build a layout
glovebox layout compile my_layout.json output/my_layout --profile glove80/v25.05
# or with uv:
uv run glovebox layout compile my_layout.json output/my_layout --profile glove80/v25.05

# Build firmware
glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05

# Flash firmware
glovebox firmware flash firmware.uf2 --profile glove80/v25.05

# Flash firmware with wait mode (event-driven device detection)
glovebox firmware flash firmware.uf2 --wait --profile glove80/v25.05

# Custom wait configuration
glovebox firmware flash firmware.uf2 --wait --timeout 120 --poll-interval 1.0 --count 3
```

### Dynamic ZMK Config Generation

```bash
# Enable dynamic generation in keyboard configuration by setting config_repo_url: ""
# This automatically creates complete ZMK workspaces from glovebox layout files

# Build firmware using dynamic generation (Corne example)
glovebox firmware compile my_layout.keymap my_config.conf --profile corne/main

# The system automatically:
# - Detects split keyboards and creates left/right build targets
# - Generates build.yaml with appropriate targets
# - Creates west.yml for ZMK dependency management
# - Copies and renames files to match shield conventions (corne.keymap, corne.conf)
# - Creates complete workspace at ~/.glovebox/dynamic-zmk-config/corne/

# Workspace can be used with standard ZMK commands:
cd ~/.glovebox/dynamic-zmk-config/corne/
west init -l config
west update  
west build -b nice_nano_v2 -d build/left -- -DSHIELD=corne_left
west build -b nice_nano_v2 -d build/right -- -DSHIELD=corne_right
```

### Firmware Flash with Wait Mode

```bash
# Enable wait mode with default settings
glovebox firmware flash firmware.uf2 --wait --profile glove80/v25.05

# Custom wait configuration
glovebox firmware flash firmware.uf2 --wait --timeout 120 --poll-interval 1.0 --count 3

# Configure via user config for persistent settings
# ~/.config/glovebox/config.yaml:
firmware:
  flash:
    wait: true
    timeout: 120
    poll_interval: 0.5
    show_progress: true
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=glovebox

# Run with coverage and generate HTML report
pytest --cov=glovebox --cov-report=html

# Run with coverage and generate XML report (for CI tools)
pytest --cov=glovebox --cov-report=xml

# Run a specific test file
pytest tests/test_services/test_layout_service.py

# Run a specific test function
pytest tests/test_services/test_layout_service.py::test_function_name

# Run layout domain tests
pytest tests/test_layout/

# Run CLI tests
pytest tests/test_cli/test_command_execution.py
```

Note: The CLI tests have been simplified to focus on basic functionality and command structure verification. Layout domain tests have been reorganized into `tests/test_layout/` following consistent `test_layout_*.py` naming patterns.

### Linting and Formatting

```bash
# Format code
ruff format .

# Fix linting issues
ruff check . --fix

# Fix import ordering issues
ruff check . --select I --fix

# Apply unsafe automatic fixes (use with caution)
ruff check . --fix --unsafe-fixes

# Run type checking
mypy glovebox/

# Run all pre-commit hooks (includes ruff-check, ruff-format, and mypy)
pre-commit run --all-files
```

### Debug Logging and Verbose Output

Glovebox provides comprehensive debug tracing capabilities with multiple verbosity levels and automatic stack trace support:

```bash
# Verbose Flag Hierarchy (with precedence)
glovebox --debug [command]     # DEBUG level logging + stack traces (highest priority)
glovebox -vv [command]         # DEBUG level logging + stack traces  
glovebox -v [command]          # INFO level logging + stack traces
glovebox [command]             # User config level or WARNING (default)

# Log to file
glovebox --log-file debug.log [command]

# Combine debug and file logging
glovebox --debug --log-file debug.log [command]

# Examples with common commands
glovebox --debug status                                    # Debug keyboard detection
glovebox -vv layout compile input.json output/            # Debug layout generation
glovebox -v firmware compile keymap.keymap config.conf    # Info level firmware build
```

#### **Flag Precedence Rules**
The debug system follows strict precedence rules:
```
--debug > -vv > -v > user_config.log_level > WARNING (default)
```

#### **Stack Trace Behavior**
- **All verbose flags** (`-v`, `-vv`, `--verbose`, `--debug`) automatically show stack traces on errors
- **No verbose flags** = Clean error messages only (no stack traces)
- **Centralized implementation** via `print_stack_trace_if_verbose()` function

#### **Logging Levels and Output**
- **DEBUG (10)**: Full debug information, configuration loading details, internal operations
- **INFO (20)**: Important events, user-facing operations, progress updates  
- **WARNING (30)**: Recoverable issues, missing optional features
- **ERROR (40)**: Operation failures, validation errors
- **CRITICAL (50)**: System failures requiring immediate attention

#### **Use Cases**
- **Development**: Use `--debug` for comprehensive troubleshooting
- **User Support**: Use `-v` for informative output with stack traces
- **Production**: Use default level for clean, user-friendly messages
- **CI/CD**: Use `--log-file` for persistent debugging information

### LSP Tools

When using Claude Code, these Language Server Protocol tools are available to enhance code navigation and editing:

```
# Find symbol definition
mcp__language-server__definition

# Get diagnostics for a file
mcp__language-server__diagnostics

# Apply multiple edits to a file
mcp__language-server__edit_file

# Get type information and documentation for a symbol
mcp__language-server__hover

# Find all references to a symbol in the codebase
mcp__language-server__references

# Rename a symbol throughout the codebase
mcp__language-server__rename_symbol
```

## Project Architecture

Glovebox is a comprehensive tool for ZMK keyboard firmware management with a clean, modular architecture:

### Domain-Driven Structure

The codebase is organized into self-contained domains, each owning their models, services, and business logic:

#### Layout Domain (`glovebox/layout/`)
- **Purpose**: Keyboard layout processing, JSON→DTSI conversion, component operations, behavior formatting
- **Components**:
  - `LayoutService`: Main layout operations (generate, validate, compile)
  - `LayoutComponentService`: Layer extraction and merging operations
  - `LayoutDisplayService`: Layout visualization and terminal display
  - `ZmkFileContentGenerator`: ZMK file content generation
  - `BehaviorFormatterImpl`: Formats bindings and behaviors for DTSI output
  - `LayoutData`, `LayoutBinding`: Core layout models
- **Factory Functions**: `create_layout_service()`, `create_layout_display_service()`, `create_layout_component_service()`

#### Firmware Domain (`glovebox/firmware/`)
- **Purpose**: Firmware building, flashing, and device operations
- **Components**:
  - `BuildService`: Firmware compilation using Docker
  - **Flash Subdomain** (`glovebox/firmware/flash/`):
    - `FlashService`: Main flash operations (flash devices, list devices)
    - `DeviceDetector`: USB device detection and monitoring
    - `FlashOperations`: Low-level mount/unmount operations  
    - `FlashResult`: Flash operation results and device tracking
    - `BlockDevice`: USB device models and metadata
- **Factory Functions**: `create_build_service()`, `create_flash_service()`, `create_device_detector()`

#### Compilation Domain (`glovebox/compilation/`)
- **Purpose**: Advanced firmware compilation strategies, workspace management, and dynamic content generation
- **Components**:
  - **Services** (`glovebox/compilation/services/`):
    - `CompilationCoordinator`: Strategy orchestration and coordination
    - `ZmkConfigCompilationService`: ZMK config repository builds with GitHub Actions pattern
    - `WestCompilationService`: Traditional ZMK west workspace builds
  - **Generation** (`glovebox/compilation/generation/`):
    - `ZmkConfigContentGenerator`: Dynamic ZMK config workspace generation on-the-fly
    - Automatic split keyboard detection and build.yaml generation
    - Shield naming conventions and file management
  - **Configuration** (`glovebox/compilation/configuration/`):
    - `BuildMatrixResolver`: GitHub Actions build matrix resolution
    - `EnvironmentManager`: Environment variable template expansion
    - `VolumeManager`: Docker volume mapping management
  - **Workspace** (`glovebox/compilation/workspace/`):
    - `ZmkConfigWorkspaceManager`: ZMK config repository workspace management
    - `WestWorkspaceManager`: Traditional west workspace initialization
    - `CacheManager`: Intelligent workspace caching and cleanup
- **Key Features**:
  - **Dynamic ZMK Config Generation**: Creates complete ZMK workspaces without external repositories
  - **Multi-Strategy Compilation**: Supports zmk_config, west, cmake build strategies
  - **Intelligent Caching**: Workspace-aware caching with invalidation and cleanup
  - **Protocol-Based Architecture**: Type-safe interfaces with runtime checking
- **Factory Functions**: `create_compilation_coordinator()`, `create_zmk_config_service()`, `create_zmk_config_content_generator()`

#### Core Services (`glovebox/services/`)
- **Purpose**: Cross-domain services and base patterns
- **Components**:
  - `BehaviorService`: Behavior registry and management
  - `BaseService`: Common service patterns and interfaces

#### Adapters (`glovebox/adapters/`)
- **Purpose**: External system interfaces following adapter pattern
- **Components**:
  - `DockerAdapter`: Docker interaction for builds
  - `FileAdapter`: File system operations
  - `USBAdapter`: USB device detection and mounting
  - `TemplateAdapter`: Template rendering
  - `ConfigFileAdapter`: Configuration file loading and saving with type safety

#### Configuration System (`glovebox/config/`)
- **Purpose**: Type-safe configuration management, keyboard profiles, user settings
- **Components**:
  - `KeyboardProfile`: Unified keyboard + firmware configuration access
  - `UserConfig`: User preferences and environment settings
  - `UserConfigData`: Pydantic model for user settings validation
  - Configuration loading and caching with YAML support
- **Key Features**:
  - Multi-source configuration (environment variables, global config, local config)
  - Clear precedence rules and validation
  - Profile-based keyboard + firmware combinations
  - **Keyboard-Only Profile Support**: Full support for minimal keyboard configurations
    - `keymap` and `firmwares` sections are optional in keyboard configurations
    - Enables minimal keyboard configs with only core fields (keyboard, description, vendor, key_count, flash, build)
    - Keyboard-only profiles return empty behaviors and kconfig options for safe operation
    - Use case: Basic keyboard configurations for flashing operations without keymap generation
  - **Flexible Profile Creation**:
    - `create_keyboard_profile("keyboard_name")` - Creates keyboard-only profile
    - `create_keyboard_profile("keyboard_name", "firmware_version")` - Creates full profile
    - Automatic fallback to keyboard-only when firmware not found

#### Core Models (`glovebox/models/`)
- **Purpose**: Core data models shared across domains
- **Components**:
  - `config.py`: Configuration models (`KeyboardConfig`, `FirmwareConfig`, etc.)
  - `behavior.py`: Behavior and registry models (`SystemBehavior`, etc.)
  - `results.py`: Operation results (`BuildResult`, `LayoutResult`, etc.)
  - `build.py`: Build artifacts and output models
  - `options.py`: Service option models

#### Layout Utilities (`glovebox/layout/utils.py`)
- **Purpose**: Functional utilities for layout domain operations
- **Key Functions**:
  - `build_template_context()`: Build template context for DTSI generation
  - `generate_kconfig_conf()`: Generate kconfig configuration content
  - `generate_config_file()`: Configuration file generation
  - `generate_keymap_file()`: Keymap file generation with DTSI support

**Design**: Uses functional programming patterns for stateless operations, providing clean utility functions without unnecessary class abstractions.

### Domain Import Patterns

**IMPORTANT**: The codebase uses clean domain boundaries with no backward compatibility layers.

#### Correct Import Patterns:
```python
# Domain-specific models from their domains
from glovebox.layout.models import LayoutData, LayoutBinding
from glovebox.firmware.flash.models import FlashResult, BlockDevice

# Core models from models package
from glovebox.models.config import KeyboardConfig, FirmwareConfig
from glovebox.models.results import BuildResult, LayoutResult
from glovebox.models.behavior import SystemBehavior

# Domain services from their domains
from glovebox.layout import create_layout_service, create_layout_component_service
from glovebox.firmware import create_build_service
from glovebox.firmware.flash import create_flash_service

# Layout domain utilities
from glovebox.layout.behavior_formatter import BehaviorFormatterImpl
from glovebox.layout.generator import ZmkFileContentGenerator
from glovebox.layout.utils import build_template_context, generate_kconfig_conf

# Configuration from config package
from glovebox.config import create_keyboard_profile, KeyboardProfile
```


### Key Design Patterns

1. **Domain-Driven Design**: Business logic organized by domains with clear boundaries
2. **Factory Functions**: Consistent creation patterns for all services and components
3. **Protocol-Based Interfaces**: Type-safe abstractions with runtime checking
4. **Dependency Injection**: Services accept dependencies rather than creating them
5. **Domain Ownership**: Each domain owns its models, services, and business logic
6. **Clean Imports**: No backward compatibility layers - single source of truth for imports
7. **Simplicity First**: Functions over classes when state isn't needed

### Key Configuration Patterns

#### KeyboardProfile Pattern

The KeyboardProfile pattern is a central concept in the architecture:

1. **Creation**:
   ```python
   from glovebox.config.keyboard_profile import create_keyboard_profile

   # Full profile with firmware
   profile = create_keyboard_profile("glove80", "v25.05")
   
   # Keyboard-only profile (NEW: firmware_version=None)
   keyboard_profile = create_keyboard_profile("glove80")
   keyboard_profile = create_keyboard_profile("glove80", firmware_version=None)
   ```

2. **CLI Integration**:
   ```bash
   # Using profile parameter with firmware
   glovebox layout compile input.json output/ --profile glove80/v25.05
   
   # Using keyboard-only profile (NEW: no firmware part)
   glovebox status --profile glove80
   glovebox firmware flash firmware.uf2 --profile glove80
   ```

3. **Service Usage**:
   ```python
   # Service methods accept profile
   result = layout_service.generate(profile, json_data, target_prefix)
   ```

4. **Configuration Access**:
   ```python
   # Access keyboard configuration (always available)
   profile.keyboard_config.description
   profile.keyboard_config.vendor
   profile.keyboard_name
   
   # Access firmware configuration (may be None for keyboard-only profiles)
   if profile.firmware_config:
       firmware_version = profile.firmware_config.version
       build_options = profile.firmware_config.build_options
   
   # Safe access to optional components
   system_behaviors = profile.system_behaviors    # Returns [] for keyboard-only profiles
   kconfig_options = profile.kconfig_options      # Returns {} for keyboard-only profiles
   
   # Check profile type
   is_keyboard_only = profile.firmware_version is None
   has_firmware = profile.firmware_config is not None
   ```

5. **Optional Sections Support**:
   ```python
   # Minimal config example (no keymap, no firmwares)
   minimal_config = KeyboardConfig.model_validate({
       'keyboard': 'minimal_test',
       'description': 'Test minimal keyboard',
       'vendor': 'Test Vendor', 
       'key_count': 10,
       'flash': {...},  # Required
       'build': {...}   # Required
       # keymap and firmwares are optional
   })
   ```

#### Service Usage Patterns

Services follow consistent patterns for creation and usage:

1. **Service Creation**:
   ```python
   from glovebox.layout import create_layout_service
   from glovebox.config import create_keyboard_profile

   # Create profile and service
   profile = create_keyboard_profile("glove80", "v25.05")
   layout_service = create_layout_service()
   ```

2. **Service Operations**:
   ```python
   # Load and process layout data
   layout_data = LayoutData.model_validate(json_data)
   result = layout_service.generate(profile, layout_data, output_prefix)
   ```

3. **Component Operations**:
   ```python
   from glovebox.layout import create_layout_component_service
   
   component_service = create_layout_component_service()
   # Extract components
   result = component_service.extract_components(layout_data, output_dir)
   # Merge components
   merged_layout = component_service.combine_components(metadata, layers_dir)
   ```

### CLI Structure

All CLI commands follow a consistent pattern with profile-based parameter:

```
glovebox [command] [subcommand] [--profile KEYBOARD/FIRMWARE] [options]
```

For example:
- `glovebox layout compile my_layout.json output/my_keymap --profile glove80/v25.05`
- `glovebox firmware compile keymap.keymap config.conf --profile glove80/v25.05`
- `glovebox firmware flash firmware.uf2 --profile glove80/v25.05`
- `glovebox layout show my_layout.json --profile glove80/v25.05`
- `glovebox layout extract my_layout.json output/components`
- `glovebox layout merge input/components --output merged_layout.json`

#### Profile Parameter Implementation

**IMPORTANT: Use Consistent Profile Parameters Across All Commands**

All CLI commands that require keyboard profiles **MUST** use the standardized `ProfileOption` to eliminate code duplication and ensure consistency:

```python
# ✅ CORRECT - Use standardized ProfileOption
from glovebox.cli.helpers.parameters import ProfileOption

@my_app.command()
@with_profile(default_profile="glove80/v25.05")
def my_command(
    ctx: typer.Context,
    some_arg: str,
    profile: ProfileOption = None,  # Clean, reusable parameter
    other_option: bool = False,
) -> None:
    """My command with profile support."""
    # Profile is automatically processed by @with_profile decorator
    pass
```

```python
# ❌ INCORRECT - Don't repeat verbose profile definitions
@my_app.command()
def my_command(
    ctx: typer.Context,
    some_arg: str,
    profile: Annotated[  # 9 lines of repetitive code!
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Profile to use (e.g., 'glove80/v25.05'). Uses user config default if not specified.",
        ),
    ] = None,
    other_option: bool = False,
) -> None:
    pass
```

**Key Components:**

1. **Reusable Parameter Definition** (`glovebox/cli/helpers/parameters.py`):
   ```python
   # Single source of truth for profile parameter
   ProfileOption = Annotated[
       str | None,
       typer.Option(
           "--profile",
           "-p", 
           help="Profile to use (e.g., 'glove80/v25.05'). Uses user config default if not specified.",
       ),
   ]
   ```

2. **Profile Decorator** (`glovebox/cli/decorators/profile.py`):
   ```python
   @with_profile(default_profile="glove80/v25.05")
   def command_function(profile: ProfileOption = None):
       # Decorator automatically:
       # 1. Sets default profile if none provided
       # 2. Creates KeyboardProfile object
       # 3. Stores it in the Typer context
       # 4. Handles profile creation errors
   ```

3. **Usage in Commands** (Context Pattern - RECOMMENDED):
   ```python
   from glovebox.cli.helpers.parameters import ProfileOption
   from glovebox.cli.helpers.profile import get_keyboard_profile_from_context
   from glovebox.cli.decorators import with_profile
   
   @command_app.command()
   @handle_errors
   @with_profile(default_profile="glove80/v25.05")
   def my_command(
       ctx: typer.Context,
       profile: ProfileOption = None,
   ) -> None:
       # Access the created profile object from context
       keyboard_profile = get_keyboard_profile_from_context(ctx)
       # Also provides access to user_config via get_user_config_from_context(ctx)
   ```

4. **Profile Helper Functions** (`glovebox/cli/helpers/profile.py`):
   ```python
   # Recommended: Get keyboard profile from context (provides access to user_config too)
   def get_keyboard_profile_from_context(ctx: typer.Context) -> KeyboardProfile:
       """Get KeyboardProfile from Typer context."""
   
   # Alternative: Get keyboard profile from kwargs (if using **kwargs pattern)
   def get_keyboard_profile_from_kwargs(**kwargs: Any) -> KeyboardProfile:
       """Get KeyboardProfile from function kwargs."""
   ```

**Why Context Pattern is Recommended:**
- **Access to User Config**: Context provides both `keyboard_profile` and `user_config`
- **Cleaner Function Signatures**: No need for `**kwargs` in function parameters
- **Consistent Pattern**: All commands use the same simple one-liner
- **Better Error Handling**: Clear error messages when decorator is missing

**Benefits:**
- **DRY Principle**: Single definition instead of 9 lines per command
- **Consistency**: Same help text and behavior across all commands
- **Maintainability**: Change profile parameter behavior in one place
- **Type Safety**: Full IDE support and type checking
- **Error Handling**: Centralized profile creation error handling
- **User Config Access**: Easy access to user configuration alongside profile

**Commands Updated:**
- ✅ All `glovebox firmware` commands (compile, flash, list-devices)
- ✅ All `glovebox layout` commands (compile, decompose, compose, validate, show)  
- ✅ `glovebox status` command for keyboard-specific diagnostics

### OS Abstraction Layer for Flash Operations

Glovebox implements a clean OS abstraction layer for firmware flashing operations to support multiple platforms:

#### FlashOSProtocol Pattern

The flash operations use a protocol-based architecture for platform-specific operations:

1. **Protocol Definition**:
   ```python
   from glovebox.protocols.flash_os_protocol import FlashOSProtocol
   
   # Protocol defines interface for OS-specific operations
   class FlashOSProtocol(Protocol):
       def get_device_path(self, device_name: str) -> str: ...
       def mount_device(self, device: BlockDevice) -> list[str]: ...
       def unmount_device(self, device: BlockDevice) -> bool: ...
       def copy_firmware_file(self, firmware_file: Path, mount_point: str) -> bool: ...
       def sync_filesystem(self, mount_point: str) -> bool: ...
   ```

2. **Platform-Specific Implementations**:
   ```python
   from glovebox.flash.os_adapters import create_flash_os_adapter
   
   # Factory function creates appropriate adapter for current platform
   os_adapter = create_flash_os_adapter()
   # Returns: LinuxFlashOS, MacOSFlashOS, or StubFlashOS
   ```

3. **High-Level Operations**:
   ```python
   from glovebox.flash.flash_operations import create_flash_operations
   
   # High-level operations using OS abstraction
   flash_ops = create_flash_operations()
   success = flash_ops.mount_and_flash(device, firmware_file, max_retries=3)
   ```

4. **Integration with Services**:
   ```python
   from glovebox.adapters.usb_adapter import create_usb_adapter
   
   # USB adapter automatically uses OS abstraction
   usb_adapter = create_usb_adapter()
   result = usb_adapter.flash_device(device, firmware_file)
   ```

#### Platform Support

- **Linux**: Uses `udisksctl` for mounting/unmounting operations
- **macOS**: Uses `diskutil` for mounting/unmounting operations  
- **Windows**: Stub implementation (not yet supported)
- **Testing**: Mock implementations can be injected for testing

#### Key Benefits

1. **Platform Independence**: Core logic works on all supported platforms
2. **Testability**: OS-specific behavior can be mocked and tested independently
3. **Maintainability**: Platform-specific code is isolated and follows consistent interfaces
4. **Extensibility**: Easy to add support for new platforms

### Protocol Implementation Guidelines

When implementing Protocol interfaces:

1. **Use Protocol Classes**: All interfaces should be defined as Protocol classes in the `protocols` package
   - Prefer `TypeAdapterProtocol` naming over just `TypeAdapter` for clarity
   - Always mark protocols with `@runtime_checkable` decorator
   - Import protocols from the central `protocols` package

2. **Runtime Type Checking**: Use `isinstance()` for runtime type verification
   - Prefer `isinstance(obj, MyProtocol)` over custom validation logic
   - Use in tests to verify implementation compliance
   - Rely on mypy for static type checking during development

3. **Factory Functions**: Create factory functions that return protocol types
   - Return the protocol type, not the concrete implementation
   - Example: `def create_file_adapter() -> FileAdapterProtocol`

4. **Type Hints**: Consistently use protocol types in function signatures
   - Function parameters should use protocol types: `def process(adapter: FileAdapterProtocol)`
   - Return types should use protocol types when appropriate

### Maintainability Guidelines

This project is maintained by a small team (2-3 developers), so:

1. **Avoid Over-engineering**: Keep solutions as simple as possible
   - Prefer straightforward solutions over complex abstractions
   - Solve the problem at hand, not potential future problems
   - Only add complexity when there's a clear benefit

2. **Pragmatic Design**: Choose patterns that solve actual problems, not theoretical ones
   - Use design patterns when they simplify code, not for their own sake
   - Don't prematurely optimize or add flexibility that isn't needed yet
   - Prioritize maintainability over architectural purity

3. **Readability Over Cleverness**: Clear, explicit code is better than clever, complex code
   - Write code that's easy to read and understand at a glance
   - Avoid non-obvious language features unless truly necessary
   - Explicit is better than implicit (clear intent over concise code)

4. **Focused Changes**: Keep changes small and targeted rather than large refactors
   - Make incremental improvements that are easy to review
   - Test changes thoroughly before committing
   - Prefer clean breaks over maintaining legacy compatibility

5. **Comment Rationale**: Document WHY something is done a certain way, not just what it does
   - Explain complex logic or non-obvious design decisions
   - Include references to issues/tickets in comments for context
   - Document edge cases and limitations

6. **Optimize for Understanding**: Code should be easy for new developers to understand
   - Use descriptive variable names that explain purpose
   - Break complex logic into well-named helper functions
   - Follow consistent patterns across the codebase

7. **Use Standard Patterns**: Avoid exotic patterns that require specialized knowledge
   - Prefer common Python idioms that any Python developer would recognize
   - Document any necessary complex patterns clearly
   - Keep inheritance hierarchies shallow and understandable

### Logging Conventions

- Use appropriate logging levels:
  - `DEBUG`: Development/troubleshooting details
  - `INFO`: Important user-facing events
  - `WARNING`: Recoverable problems
  - `ERROR`: Failures that prevent operation completion
  - `CRITICAL`: System failures requiring immediate attention

- Always use lazy formatting (`%` style, not f-strings) in log calls:
  ```python
  logger.debug("Processing %d items: %s", len(items), items)
  ```

### Code Conventions

- Maximum 500 lines per file
- Maximum 50 lines per method
- Use comprehensive typing without complexity
- Document intent, not implementation
- Use pathlib for file operations
- Use modern typing when available
- **Follow naming conventions** (see Naming Conventions section above)
- Always lint/format before committing

### Common Linting Issues to Avoid

- **SIM117**: Use a single with statement with multiple contexts instead of nested with statements
- **UP035**: Use modern typing - `typing.Dict` is deprecated, use `dict` instead
- **PTH123**: Use `Path.open()` instead of built-in `open()`
- **B904**: Within except clauses, use `raise ... from err` to distinguish from errors in exception handling
- **N815**: Variable names in class scope should not be mixedCase
- **SIM102**: Use a single if statement instead of nested if statements
- **NB023**: Function definition should not bind loop variable

## Git Workflow

### Branch Strategy

- Main development branch is `dev`
- Feature branches should be created from `dev`
- Use meaningful branch names (e.g., `feature/new-keymap-format`, `fix/usb-detection-issue`)

### Commit Practices

- Commit regularly with small, focused changes
- Use descriptive commit messages following the conventional commits format:
  - `feat`: A new feature
  - `fix`: A bug fix
  - `refactor`: Code change that neither fixes a bug nor adds a feature
  - `docs`: Documentation only changes
  - `test`: Adding missing tests or correcting existing tests
  - `chore`: Changes to the build process or auxiliary tools
  - Example: `feat: add support for wireless keyboard detection`

### Before Working on Code

1. Always read and understand the model classes in `glovebox/models/` to understand the core data structures
2. Check the appropriate domain models (`glovebox/layout/models.py`, `glovebox/flash/models.py`) for domain-specific structures
3. Read the `docs/keymap_file_format.md` document to understand the layout file format

### Before Committing

1. Run the linter and fix any issues:
   ```bash
   ruff check .
   ruff format .
   ```

2. Run pre-commit hooks:
   ```bash
   pre-commit run --all-files
   ```

3. Run tests to ensure your changes don't break existing functionality:
   ```bash
   pytest
   ```

4. All new files must pass mypy type checking:
   ```bash
   mypy glovebox/
   ```

### Pull Request Process

1. Ensure all tests pass and code quality checks are successful
2. Request a review from at least one team member
3. After approval, squash commits for a clean history
4. Merge to `dev` branch:
   ```bash
   # Ensure you're on your feature branch
   git checkout feature/my-feature

   # Make sure your branch is up to date with dev
   git fetch
   git rebase origin/dev

   # Squash commits (interactive rebase)
   git rebase -i origin/dev

   # Push to remote (may need force push if you rebased)
   git push -f

   # Once PR is approved, merge to dev
   git checkout dev
   git merge feature/my-feature
   git push
   ```
