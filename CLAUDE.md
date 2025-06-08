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

# Run CLI tests
pytest tests/test_cli/test_command_execution.py
```

Note: The CLI tests have been simplified to focus on basic functionality and command structure verification.

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

### Debug Logging

```bash
# Enable debug output
glovebox --debug [command]

# Log to file
glovebox --log-file debug.log [command]
```

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
  - `LayoutGenerator`: Layout formatting, view generation, and DTSI generation
  - `BehaviorFormatter`: Formats bindings and behaviors for DTSI output
  - `LayoutData`, `LayoutBinding`, `LayoutLayer`: Core layout models
- **Factory Functions**: `create_layout_service()`, `create_layout_display_service()`, `create_layout_generator()`

#### Flash Domain (`glovebox/flash/`)
- **Purpose**: Firmware flashing, USB device operations, cross-platform support
- **Components**:
  - `FlashService`: Main flash operations (flash devices, list devices)
  - `DeviceDetector`: USB device detection and monitoring
  - `FlashOperations`: Low-level mount/unmount operations  
  - `FlashResult`: Flash operation results and device tracking
  - `BlockDevice`: USB device models and metadata
- **Factory Functions**: `create_flash_service()`, `create_device_detector()`

#### Core Services (`glovebox/services/`)
- **Purpose**: Cross-domain services and base patterns
- **Components**:
  - `BuildService`: Firmware compilation using Docker
  - `BehaviorService`: Behavior registry and management
  - `BaseService`: Common service patterns and interfaces

- **Adapter Pattern**: External system interfaces
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

#### Core Models (`glovebox/models/`)
- **Purpose**: Core data models shared across domains
- **Components**:
  - `config.py`: Configuration models (`KeyboardConfig`, `FirmwareConfig`, etc.)
  - `behavior.py`: Behavior and registry models (`SystemBehavior`, etc.)
  - `results.py`: Operation results (`BuildResult`, `LayoutResult`, etc.)
  - `build.py`: Build artifacts and output models
  - `options.py`: Service option models

#### Generators (`glovebox/generators/`)
- **Purpose**: Multi-domain code generation utilities
- **Components**:
  - `DTSIGenerator`: Cross-domain DTSI file generation from layouts, behaviors, and configs
  
**Note**: Layout-specific formatting and DTSI generation has been moved to the layout domain (`glovebox/layout/generator.py`). The generators package now focuses on cross-domain utilities that serve multiple domains.

### Domain Import Patterns

**IMPORTANT**: The codebase uses clean domain boundaries with no backward compatibility layers.

#### Correct Import Patterns:
```python
# Domain-specific models from their domains
from glovebox.layout.models import LayoutData, LayoutBinding
from glovebox.flash.models import FlashResult, BlockDevice

# Core models from models package
from glovebox.models.config import KeyboardConfig, FirmwareConfig
from glovebox.models.results import BuildResult, LayoutResult
from glovebox.models.behavior import SystemBehavior

# Domain services from their domains
from glovebox.layout import create_layout_service, create_layout_generator
from glovebox.flash import create_flash_service

# Layout domain utilities
from glovebox.layout.generator import BehaviorFormatterImpl, DtsiLayoutGenerator

# Configuration from config package
from glovebox.config import create_keyboard_profile, KeyboardProfile
```

#### Forbidden Patterns:
```python
# ❌ NO backward compatibility imports
from glovebox.models import FlashResult  # FlashResult is in flash domain
from glovebox.models import LayoutData   # LayoutData is in layout domain
from glovebox.config.models import KeyboardConfig  # File removed
from glovebox.formatters import BehaviorFormatterImpl  # Moved to layout domain
from glovebox.generators import DTSIGenerator  # Layout-specific parts moved to layout domain
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
   from glovebox.config.keyboard_config import create_keyboard_profile

   profile = create_keyboard_profile("glove80", "v25.05")
   ```

2. **CLI Integration**:
   ```bash
   # Using profile parameter
   glovebox keymap compile input.json output/ --profile glove80/v25.05
   ```

3. **Service Usage**:
   ```python
   # Service methods accept profile
   result = layout_service.generate(profile, json_data, target_prefix)
   ```

4. **Configuration Access**:
   ```python
   # Access nested configuration
   profile.keyboard_config.description
   profile.firmware_config.version
   ```

#### ConfigFileAdapter Pattern

The ConfigFileAdapter pattern provides type-safe configuration file handling:

1. **Creation**:
   ```python
   from glovebox.adapters.config_file_adapter import create_config_file_adapter, create_keymap_config_adapter

   # For user configuration
   user_config_adapter = create_config_file_adapter()

   # For keymap configuration
   keymap_config_adapter = create_keymap_config_adapter()
   ```

2. **Loading Models**:
   ```python
   # Load and validate configuration
   config_data = config_adapter.load_model(file_path, UserConfigData)

   # Access typed properties
   print(config_data.default_keyboard)
   ```

3. **Saving Models**:
   ```python
   # Save with validation
   config_adapter.save_model(file_path, config_data)
   ```

4. **Type Safety**:
   ```python
   # Generic type parameter ensures type safety
   from typing import Generic, TypeVar
   from pydantic import BaseModel

   T = TypeVar("T", bound=BaseModel)

   class ConfigFileAdapter(Generic[T]):
       # Type-safe operations for specific model type
       def load_model(self, file_path: Path, model_class: type[T]) -> T:
           ...
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
