# System Architecture Overview

This document provides a comprehensive overview of Glovebox's architecture, design patterns, and organizational principles.

## Architectural Philosophy

Glovebox is built on **Domain-Driven Design** principles with a focus on:

1. **Clear Domain Boundaries**: Business logic organized by functional domains
2. **Service-Oriented Architecture**: Each domain provides services through well-defined interfaces
3. **Protocol-Based Design**: Type-safe interfaces with runtime checking
4. **Factory Functions**: Consistent object creation patterns
5. **Clean Dependencies**: Minimal coupling between domains

## High-Level Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   CLI Layer     │    │  User Configs   │    │   Keyboards     │
│                 │    │                 │    │                 │
│ • Commands      │    │ • Profiles      │    │ • YAML Configs  │
│ • Parameters    │    │ • Preferences   │    │ • Firmware Vars │
│ • Output        │    │ • Environment   │    │ • Templates     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Service Layer                               │
├─────────────────┬─────────────────┬─────────────────┬──────────┤
│  Layout Domain  │ Firmware Domain │Compilation Dom. │  Config  │
│                 │                 │                 │  Domain  │
│ • JSON→DTSI     │ • Build Service │ • Coordinators  │ • Profiles│
│ • Components    │ • Flash Service │ • Strategies    │ • Loading │
│ • Display       │ • Device Detect │ • Workspaces    │ • Validation│
│ • Behaviors     │ • USB Operations│ • Dynamic Gen   │ • Types   │
└─────────────────┴─────────────────┴─────────────────┴──────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Adapter Layer                               │
├─────────────────┬─────────────────┬─────────────────┬──────────┤
│  File Adapter   │ Docker Adapter  │  USB Adapter    │ Template │
│                 │                 │                 │ Adapter  │
│ • Read/Write    │ • Build Commands│ • Device Query  │ • Jinja2 │
│ • Path Ops      │ • Volume Mgmt   │ • Mount/Unmount │ • Render │
│ • Validation    │ • User Context  │ • Cross-Platform│ • Context│
└─────────────────┴─────────────────┴─────────────────┴──────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                   External Systems                              │
├─────────────────┬─────────────────┬─────────────────┬──────────┤
│   File System   │     Docker      │   USB Devices   │Templates │
│                 │                 │                 │          │
│ • Config Files  │ • ZMK Builders  │ • Block Devices │• Keymap  │
│ • Layouts       │ • Containers    │ • Mass Storage  │• Config  │
│ • Artifacts     │ • Images        │ • Device Events │• Build   │
└─────────────────┴─────────────────┴─────────────────┴──────────┘
```

## Domain Architecture

### Layout Domain (`glovebox/layout/`)

**Responsibility**: Transform JSON keyboard layouts into ZMK Device Tree Source files

```
Layout Domain
├── Models
│   ├── LayoutData           # Complete layout representation
│   ├── LayoutBinding        # Key binding definitions
│   ├── LayoutLayer          # Layer definitions
│   └── Behavior Models      # Macros, hold-taps, combos
├── Services
│   ├── LayoutService        # Main layout operations
│   ├── ComponentService     # Layer extraction/merging
│   └── DisplayService       # Terminal visualization
├── Generators
│   ├── ZmkFileGenerator     # DTSI file generation
│   └── BehaviorFormatter    # Behavior code formatting
└── Utilities
    ├── Template Context     # Build generation context
    └── Validation Utils     # Layout validation
```

**Key Responsibilities**:
- Parse and validate JSON layout files
- Extract and merge layout components (layers, behaviors)
- Generate ZMK-compatible `.keymap` and `.conf` files
- Format behaviors (macros, hold-taps, combos) for DTSI output
- Provide layout visualization in terminal

### Firmware Domain (`glovebox/firmware/`)

**Responsibility**: Build firmware binaries and flash them to devices

```
Firmware Domain
├── Build Services
│   ├── BuildService         # Main firmware compilation
│   ├── CompilerRegistry     # Available compilers
│   └── CompilerSelector     # Compiler selection logic
├── Flash Subdomain
│   ├── FlashService         # Device flashing operations
│   ├── DeviceDetector       # USB device discovery
│   ├── FlashOperations      # Mount/unmount operations
│   └── USBMonitor          # Cross-platform USB events
├── Compile Methods
│   ├── DockerCompiler       # Docker-based building
│   └── GenericDockerCompiler # Generic Docker builds
└── Models
    ├── BuildResult          # Compilation results
    ├── FlashResult          # Flash operation results
    └── BlockDevice          # USB device representation
```

**Key Responsibilities**:
- Compile ZMK firmware using Docker containers
- Detect and monitor USB devices across platforms
- Flash firmware to keyboard devices with retry logic
- Manage build artifacts and outputs
- Handle Docker volume permissions automatically

### Compilation Domain (`glovebox/compilation/`)

**Responsibility**: Direct compilation strategies with intelligent caching and workspace management

```
Compilation Domain
├── Services
│   ├── moergo_simple.py       # MoErgo Nix toolchain strategy
│   └── zmk_config_simple.py   # ZMK config builds (GitHub Actions style)
├── Cache System
│   ├── base_dependencies_cache.py  # Base dependency caching
│   └── cache_injector.py      # Cache dependency injection
├── Models
│   ├── build_matrix.py        # GitHub Actions build matrix
│   ├── compilation_config.py  # Unified compilation configuration
│   └── west_config.py         # West workspace configuration
└── Protocols
    └── compilation_protocols.py  # Type-safe interfaces
```

**Key Responsibilities**:
- Provide direct strategy selection via CLI (no coordination layer)
- Generate complete ZMK workspaces dynamically
- Manage intelligent caching using generic cache system
- Resolve GitHub Actions build matrices with automatic split keyboard detection
- Handle Docker user context and volume mapping
- Execute Docker-based compilation with unified configuration models
- Support multiple compilation strategies: zmk_config, west, cmake, make, ninja, custom

### Configuration Domain (`glovebox/config/`)

**Responsibility**: Type-safe configuration management and keyboard profiles

```
Configuration Domain
├── Profile System
│   ├── KeyboardProfile      # Unified keyboard+firmware config
│   ├── ProfileFactory       # Profile creation logic
│   └── ProfileCache         # Configuration caching
├── User Configuration
│   ├── UserConfig           # User preferences
│   ├── UserConfigData       # Pydantic validation model
│   └── ConfigSources        # Multi-source loading
├── Keyboard Configuration
│   ├── KeyboardConfig       # Keyboard definition model
│   ├── FirmwareConfig       # Firmware variant model
│   └── ConfigLoader         # YAML configuration loading
└── Models
    ├── BehaviorConfig       # Behavior definitions
    ├── DisplayConfig        # Display formatting
    └── ZmkConfig            # ZMK-specific settings
```

**Key Responsibilities**:
- Load and validate keyboard configurations from YAML
- Manage firmware variants and profiles
- Handle user preferences with environment precedence
- Provide type-safe configuration access
- Support keyboard-only profiles for minimal setups

## Cross-Cutting Concerns

### Generic Cache System

Glovebox includes a domain-agnostic caching system that can be used across all domains:

```python
from glovebox.core.cache import (
    create_filesystem_cache,
    create_memory_cache,
    create_default_cache
)

# Create cache managers
fs_cache = create_filesystem_cache(max_size_mb=500, default_ttl_hours=24)
memory_cache = create_memory_cache(max_size_mb=100, max_entries=1000)
default_cache = create_default_cache()  # Reasonable defaults

# Use in domain-specific services
from glovebox.compilation.cache import create_compilation_cache
compilation_cache = create_compilation_cache(cache_manager=fs_cache)
```

**Cache Features**:
- Multiple backends (filesystem, memory, future: Redis, SQLite)
- TTL support with automatic expiration
- Size-based and count-based eviction policies
- Cache hit/miss statistics and performance monitoring
- Domain-specific cache wrappers for specialized operations

### Adapter Layer

The adapter layer provides clean interfaces to external systems:

```python
# File operations
from glovebox.adapters import FileAdapter
file_adapter = FileAdapter()
content = file_adapter.read_file(path)

# Docker operations  
from glovebox.adapters import DockerAdapter
docker_adapter = DockerAdapter()
result = docker_adapter.run_build(image, command, volumes)

# USB device operations
from glovebox.adapters import USBAdapter
usb_adapter = USBAdapter()
devices = usb_adapter.list_devices(query)

# Template rendering
from glovebox.adapters import TemplateAdapter
template_adapter = TemplateAdapter()
output = template_adapter.render_template(template, context)
```

### Protocol System

All interfaces are defined as protocols for type safety:

```python
from typing import Protocol

class FileAdapterProtocol(Protocol):
    def read_file(self, path: Path) -> str: ...
    def write_file(self, path: Path, content: str) -> None: ...
    def check_exists(self, path: Path) -> bool: ...

class BaseServiceProtocol(Protocol):
    @property
    def name(self) -> str: ...
    @property 
    def version(self) -> str: ...
```

### Factory Functions

Consistent creation patterns across all domains:

```python
# Layout domain
from glovebox.layout import (
    create_layout_service,
    create_layout_component_service,
    create_layout_display_service
)

# Firmware domain
from glovebox.firmware import create_build_service
from glovebox.firmware.flash import create_flash_service

# Compilation domain
from glovebox.compilation import (
    create_compilation_service,
    create_zmk_config_service,
    create_west_service
)

# Configuration domain
from glovebox.config import create_keyboard_profile, create_user_config
```

## Design Patterns

### Service Layer Pattern

Each domain provides business logic through services:

```python
class LayoutService(BaseService):
    def __init__(
        self,
        file_adapter: FileAdapterProtocol,
        template_adapter: TemplateAdapterProtocol,
        behavior_service: BehaviorServiceProtocol,
    ):
        # Dependencies injected, not created
        
    def generate(
        self, 
        profile: KeyboardProfile, 
        layout_data: LayoutData, 
        output_prefix: str
    ) -> LayoutResult:
        # Business logic here
```

### Repository Pattern

Configuration loading follows repository pattern:

```python
def load_keyboard_config(keyboard_name: str) -> KeyboardConfig:
    """Load keyboard configuration with caching."""
    # Check cache first
    # Load from file system
    # Validate and return
```

### Strategy Pattern

Compilation uses direct strategy selection with unified configuration:

```python
from glovebox.compilation import create_compilation_service
from glovebox.compilation.models import ZmkCompilationConfig, MoergoCompilationConfig

# Direct strategy selection - user chooses via CLI
def compile_firmware(strategy: str, config: CompilationConfig, ...) -> CompilationResult:
    service = create_compilation_service(strategy)
    return service.compile(config, ...)

# Available strategies: "zmk_config", "moergo", "west", "cmake", "make", "ninja", "custom"
# Each strategy configured through unified CompilationConfig models
```

## Data Flow

### Typical Layout Processing Flow

```
1. JSON Layout File
   ↓ (CLI reads file)
2. LayoutData Model  
   ↓ (LayoutService.generate)
3. Behavior Analysis
   ↓ (BehaviorFormatter)
4. Template Context
   ↓ (TemplateAdapter.render)
5. ZMK Files (.keymap + .conf)
```

### Typical Firmware Build Flow

```
1. Keymap + Config Files
   ↓ (CLI validates inputs)
2. KeyboardProfile
   ↓ (BuildService.compile)
3. Docker Build Context
   ↓ (DockerAdapter.run_build)
4. Firmware Binary (.uf2)
```

### Typical Flash Flow

```
1. Firmware File + Profile
   ↓ (FlashService.flash_device)
2. Device Detection
   ↓ (DeviceDetector.find_devices)
3. Mount Operations
   ↓ (FlashOperations.mount_and_flash)
4. Flash Complete
```

## Error Handling

### Hierarchical Error Structure

```python
from glovebox.core.errors import (
    GloveboxError,           # Base error
    ConfigurationError,      # Config issues
    LayoutValidationError,   # Layout problems
    BuildError,              # Build failures
    FlashError               # Flash failures
)
```

### Error Context Propagation

Errors include context for debugging:

```python
try:
    result = service.process(data)
except ProcessingError as e:
    logger.error("Processing failed: %s", e)
    if verbose:
        print_stack_trace()
    raise UserFriendlyError("Failed to process layout") from e
```

## Performance Considerations

### Caching Strategy

- **Generic Cache System**: Domain-agnostic caching with multiple backends
- **Configuration Cache**: Keyboard configs cached after first load
- **Compilation Cache**: ZMK dependencies, workspace data, and build matrices
- **Template Cache**: Jinja2 templates cached for performance
- **Intelligent Invalidation**: Cache entries invalidated based on content changes

### Lazy Loading

- Models loaded only when needed
- Services created on-demand through factory functions
- Heavy operations deferred until required

### Resource Management

- Docker containers cleaned up after builds
- Temporary files removed automatically
- USB device handles properly closed

## Testing Architecture

### Test Organization

```
tests/
├── test_layout/         # Layout domain tests
├── test_firmware/       # Firmware domain tests  
├── test_compilation/    # Compilation domain tests
├── test_config/         # Configuration tests
├── test_adapters/       # Adapter tests
└── test_cli/           # CLI integration tests
```

### Test Types

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **Service Tests**: Test business logic in services
- **CLI Tests**: Test command-line interface

### Mocking Strategy

- Mock external dependencies (Docker, USB, File System)
- Use protocol-based mocking for type safety
- Provide test fixtures for common scenarios

## Security Considerations

### Input Validation

- All user inputs validated through Pydantic models
- File path validation prevents directory traversal
- JSON layout validation prevents malicious content

### Docker Security

- Docker user context properly managed
- No privileged container access required
- Build isolation through containers

### USB Device Access

- Device queries prevent unauthorized access
- Safe mount/unmount operations
- No root privileges required for device operations

## Future Architecture Considerations

### Planned Extensions

- **Plugin System**: Support for third-party keyboards and builders
- **Remote Builds**: Cloud-based firmware compilation
- **Keyboard Discovery**: Auto-detection of connected keyboards
- **Layout Sharing**: Community layout repository integration

### Scalability

- Current architecture supports adding new domains
- Service-oriented design enables independent scaling
- Protocol-based interfaces support implementation swapping