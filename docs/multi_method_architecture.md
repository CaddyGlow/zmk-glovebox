# Multi-Method Architecture Design

## Overview

This document outlines the architecture for supporting multiple compilation chains and flash methods in Glovebox. The design uses method-specific configuration models and a unified registry system for clean separation of concerns and type safety.

## CRITICAL: Code Convention Requirements

**MANDATORY REQUIREMENTS - MUST BE FOLLOWED WITHOUT EXCEPTION:**

All code implementing this architecture MUST strictly adhere to the conventions specified in `CLAUDE.md`:

1. **ALWAYS run linting before any code changes are considered complete**:
   ```bash
   ruff check . --fix
   ruff format .
   mypy glovebox/
   ```

2. **NEVER commit code that fails linting or type checking**
3. **FOLLOW PROJECT CONVENTIONS STRICTLY**:
   - Maximum 500 lines per file (ENFORCED)
   - Maximum 50 lines per method (ENFORCED)
   - Use comprehensive typing without complexity
   - Use pathlib for ALL file operations
   - Use modern typing (`dict` not `typing.Dict`, etc.)
   - Use `Path.open()` instead of built-in `open()`
   - Use lazy logging formatting (`%` style, not f-strings)

4. **NAMING CONVENTIONS ARE MANDATORY**:
   - **Adapter Classes**: Use `*Adapter` suffix (NO `Impl` suffix)
   - **Service Classes**: Use `*Service` suffix (NO `Impl` suffix)
   - **Protocol Classes**: Use `*Protocol` suffix
   - **Function Naming**: Use descriptive verbs (`check_available()`, `create_compiler()`, `flash_device()`)

**If you encounter ANY linting errors, you MUST fix them immediately before proceeding with other tasks.**

## Design Philosophy

- **Clean Configuration Models**: Each method has its own dedicated configuration type
- **Type Safety**: Strong typing with method-specific protocols
- **Extensibility**: Easy to add new methods without modifying existing code
- **Automatic Fallbacks**: Resilient method selection with fallback chains
- **Domain Separation**: Clear boundaries between compilation and flash domains

## Architecture Components

### 1. Method-Specific Configuration Models

Each compilation and flash method has its own dedicated configuration model for type safety and clarity.

#### Compilation Method Configurations

```python
# glovebox/config/compile_methods.py
from abc import ABC
from pathlib import Path
from pydantic import BaseModel, Field

class CompileMethodConfig(BaseModel, ABC):
    """Base configuration for compilation methods."""
    method_type: str
    fallback_methods: list[str] = Field(default_factory=list)

class DockerCompileConfig(CompileMethodConfig):
    """Docker-based compilation configuration."""
    method_type: str = "docker"
    image: str = "moergo-zmk-build:latest"
    repository: str = "moergo-sc/zmk"
    branch: str = "main"
    jobs: int | None = None
    
class LocalCompileConfig(CompileMethodConfig):
    """Local ZMK compilation configuration."""
    method_type: str = "local"
    zmk_path: Path
    toolchain_path: Path | None = None
    zephyr_base: Path | None = None
    jobs: int | None = None

class CrossCompileConfig(CompileMethodConfig):
    """Cross-compilation configuration."""
    method_type: str = "cross"
    target_arch: str  # "arm", "x86_64", etc.
    sysroot: Path
    toolchain_prefix: str  # "arm-none-eabi-"
    cmake_toolchain: Path | None = None

class QemuCompileConfig(CompileMethodConfig):
    """QEMU-based compilation for testing."""
    method_type: str = "qemu"
    qemu_target: str = "native_posix"
    test_runners: list[str] = Field(default_factory=list)
```

#### Flash Method Configurations

```python
# glovebox/config/flash_methods.py
class FlashMethodConfig(BaseModel, ABC):
    """Base configuration for flash methods."""
    method_type: str
    fallback_methods: list[str] = Field(default_factory=list)

class USBFlashConfig(FlashMethodConfig):
    """USB mounting flash configuration."""
    method_type: str = "usb"
    device_query: str
    mount_timeout: int = 30
    copy_timeout: int = 60
    sync_after_copy: bool = True

class DFUFlashConfig(FlashMethodConfig):
    """DFU-util flash configuration."""
    method_type: str = "dfu"
    vid: str
    pid: str
    interface: int = 0
    alt_setting: int = 0
    timeout: int = 30

class BootloaderFlashConfig(FlashMethodConfig):
    """Direct bootloader flash configuration."""
    method_type: str = "bootloader"
    protocol: str  # "uart", "spi", "i2c"
    port: str | None = None  # "/dev/ttyUSB0" for UART
    baud_rate: int = 115200
    reset_sequence: list[str] = Field(default_factory=list)

class WiFiFlashConfig(FlashMethodConfig):
    """Wireless flash configuration."""
    method_type: str = "wifi"
    host: str
    port: int = 8080
    protocol: str = "http"  # "http", "mqtt", "websocket"
    auth_token: str | None = None
```

### 2. Protocol Definitions

Method-specific protocols provide type-safe interfaces for each implementation.

```python
# glovebox/protocols/compile_protocols.py
@runtime_checkable
class CompilerProtocol(Protocol):
    """Generic compiler interface."""
    
    def compile(
        self, 
        keymap_file: Path, 
        config_file: Path, 
        output_dir: Path,
        config: CompileMethodConfig
    ) -> BuildResult:
        """Compile firmware using this method."""
        ...
    
    def check_available(self) -> bool:
        """Check if this compiler is available."""
        ...
    
    def validate_config(self, config: CompileMethodConfig) -> bool:
        """Validate method-specific configuration."""
        ...

@runtime_checkable  
class DockerCompilerProtocol(CompilerProtocol):
    """Docker-specific compiler interface."""
    
    def compile(
        self,
        keymap_file: Path,
        config_file: Path, 
        output_dir: Path,
        config: DockerCompileConfig  # Type-specific config
    ) -> BuildResult:
        ...
    
    def build_image(self, config: DockerCompileConfig) -> BuildResult:
        """Build Docker image for compilation."""
        ...

# glovebox/protocols/flash_protocols.py
@runtime_checkable
class FlasherProtocol(Protocol):
    """Generic flasher interface."""
    
    def flash_device(
        self,
        device: BlockDevice,
        firmware_file: Path,
        config: FlashMethodConfig
    ) -> FlashResult:
        """Flash device using this method."""
        ...
    
    def list_devices(self, config: FlashMethodConfig) -> list[BlockDevice]:
        """List compatible devices for this flash method."""
        ...

@runtime_checkable
class USBFlasherProtocol(FlasherProtocol):
    """USB-specific flasher interface."""
    
    def flash_device(
        self,
        device: BlockDevice, 
        firmware_file: Path,
        config: USBFlashConfig  # Type-specific config
    ) -> FlashResult:
        ...
    
    def mount_device(self, device: BlockDevice, config: USBFlashConfig) -> list[str]:
        """Mount USB device for flashing."""
        ...
```

### 3. Unified Method Registry

A generic registry system handles method registration and creation with type safety.

```python
# glovebox/firmware/method_registry.py
from typing import TypeVar, Generic, Union

ConfigType = TypeVar('ConfigType', bound='MethodConfig')
ProtocolType = TypeVar('ProtocolType')

class MethodRegistry(Generic[ConfigType, ProtocolType]):
    """Generic registry for method implementations."""
    
    def __init__(self):
        self._methods: dict[str, type[ProtocolType]] = {}
        self._config_types: dict[str, type[ConfigType]] = {}
    
    def register_method(
        self, 
        method_name: str, 
        implementation: type[ProtocolType],
        config_type: type[ConfigType]
    ) -> None:
        """Register a method implementation with its config type."""
        self._methods[method_name] = implementation
        self._config_types[method_name] = config_type
    
    def create_method(
        self, 
        method_name: str, 
        config: ConfigType,
        **dependencies
    ) -> ProtocolType:
        """Create method implementation with config validation."""
        if method_name not in self._methods:
            raise ValueError(f"Unknown method: {method_name}")
        
        # Validate config type matches expected type
        expected_config_type = self._config_types[method_name]
        if not isinstance(config, expected_config_type):
            raise TypeError(f"Expected {expected_config_type.__name__}, got {type(config).__name__}")
        
        implementation_class = self._methods[method_name]
        return implementation_class(config=config, **dependencies)
    
    def get_available_methods(self) -> list[str]:
        """Get list of available method names."""
        available = []
        for method_name, impl_class in self._methods.items():
            try:
                # Try to create instance to check availability
                temp_config = self._config_types[method_name]()
                temp_impl = impl_class(config=temp_config)
                if temp_impl.check_available():
                    available.append(method_name)
            except Exception:
                pass  # Method not available
        return available

# Create specific registries
CompilerRegistry = MethodRegistry[CompileMethodConfig, CompilerProtocol]
FlasherRegistry = MethodRegistry[FlashMethodConfig, FlasherProtocol]

# Global registry instances
compiler_registry = CompilerRegistry()
flasher_registry = FlasherRegistry()
```

### 4. Method Selection with Fallback Logic

Automatic method selection with fallback support for resilience.

```python
# glovebox/firmware/method_selector.py
def select_compiler_with_fallback(
    configs: list[CompileMethodConfig],
    **dependencies
) -> CompilerProtocol:
    """Select first available compiler from config list."""
    
    for config in configs:
        try:
            compiler = compiler_registry.create_method(
                config.method_type, 
                config, 
                **dependencies
            )
            if compiler.check_available():
                logger.info(f"Selected compiler: {config.method_type}")
                return compiler
        except Exception as e:
            logger.debug(f"Compiler {config.method_type} not available: {e}")
            continue
    
    available_methods = compiler_registry.get_available_methods()
    raise CompilerNotAvailableError(
        f"No available compilers from configs. Available methods: {available_methods}"
    )

def select_flasher_with_fallback(
    configs: list[FlashMethodConfig],
    **dependencies  
) -> FlasherProtocol:
    """Select first available flasher from config list."""
    
    for config in configs:
        try:
            flasher = flasher_registry.create_method(
                config.method_type,
                config,
                **dependencies
            )
            if flasher.check_available():
                logger.info(f"Selected flasher: {config.method_type}")
                return flasher
        except Exception as e:
            logger.debug(f"Flasher {config.method_type} not available: {e}")
            continue
    
    available_methods = flasher_registry.get_available_methods()
    raise FlasherNotAvailableError(
        f"No available flashers from configs. Available methods: {available_methods}"
    )
```

### 5. Updated Keyboard Configuration

Clean configuration model using method-specific types.

```python
# glovebox/config/models.py
from typing import Union
from glovebox.config.compile_methods import (
    DockerCompileConfig, LocalCompileConfig, CrossCompileConfig, QemuCompileConfig
)
from glovebox.config.flash_methods import (
    USBFlashConfig, DFUFlashConfig, BootloaderFlashConfig, WiFiFlashConfig
)

# Union types for method configs
CompileMethodConfigUnion = Union[
    DockerCompileConfig,
    LocalCompileConfig, 
    CrossCompileConfig,
    QemuCompileConfig
]

FlashMethodConfigUnion = Union[
    USBFlashConfig,
    DFUFlashConfig,
    BootloaderFlashConfig,
    WiFiFlashConfig
]

class KeyboardConfig(BaseModel):
    """Clean keyboard configuration with method-specific configs."""
    
    keyboard: str
    description: str
    vendor: str
    key_count: int = Field(gt=0)
    
    # Method-specific configurations
    compile_methods: list[CompileMethodConfigUnion] = Field(min_items=1)
    flash_methods: list[FlashMethodConfigUnion] = Field(min_items=1)
    
    # Optional sections
    firmwares: dict[str, FirmwareConfig] = Field(default_factory=dict)
    keymap: KeymapSection = Field(default_factory=KeymapSection)
```

## Implementation Status Tracking

**CRITICAL: All implementation progress MUST be tracked in this document.**

### Phase 1: Configuration Models
- [ ] Create `glovebox/config/compile_methods.py`
- [ ] Create `glovebox/config/flash_methods.py`
- [ ] Update `glovebox/config/models.py` with new KeyboardConfig
- [ ] Add validation and parsing logic
- [ ] **Linting Status**: ⚠️ MUST RUN `ruff check . --fix && mypy glovebox/` BEFORE COMMIT

### Phase 2: Protocol Definitions  
- [ ] Create `glovebox/protocols/compile_protocols.py`
- [ ] Create `glovebox/protocols/flash_protocols.py`
- [ ] Add `@runtime_checkable` decorators
- [ ] **Linting Status**: ⚠️ MUST RUN `ruff check . --fix && mypy glovebox/` BEFORE COMMIT

### Phase 3: Registry System
- [ ] Create `glovebox/firmware/method_registry.py`
- [ ] Create `glovebox/firmware/method_selector.py`
- [ ] Implement generic registry with type safety
- [ ] Add method registration functions
- [ ] **Linting Status**: ⚠️ MUST RUN `ruff check . --fix && mypy glovebox/` BEFORE COMMIT

### Phase 4: Method Implementations
- [ ] Create `glovebox/firmware/compile/` subdomain
- [ ] Create `glovebox/firmware/compile/methods.py` (< 500 lines)
- [ ] Extract Docker compilation from BuildService
- [ ] Implement LocalCompiler class
- [ ] Implement CrossCompiler class
- [ ] **Linting Status**: ⚠️ MUST RUN `ruff check . --fix && mypy glovebox/` BEFORE COMMIT

### Phase 5: Flash Method Implementations
- [ ] Create `glovebox/firmware/flash/flasher_methods.py` (< 500 lines)
- [ ] Extract USB flashing from FlashService
- [ ] Implement DFUFlasher class
- [ ] Implement BootloaderFlasher class
- [ ] **Linting Status**: ⚠️ MUST RUN `ruff check . --fix && mypy glovebox/` BEFORE COMMIT

### Phase 6: Service Integration
- [ ] Refactor BuildService to use method selection
- [ ] Refactor FlashService to use method selection
- [ ] Update factory functions
- [ ] **Linting Status**: ⚠️ MUST RUN `ruff check . --fix && mypy glovebox/` BEFORE COMMIT

### Phase 7: Testing
- [ ] Create unit tests for each method implementation
- [ ] Test fallback logic
- [ ] Test configuration validation
- [ ] **Linting Status**: ⚠️ MUST RUN `ruff check . --fix && mypy glovebox/` BEFORE COMMIT

### Phase 8: Documentation & CLI Integration
- [ ] Update CLI commands to support new configurations
- [ ] Add configuration examples
- [ ] Update user documentation
- [ ] **Linting Status**: ⚠️ MUST RUN `ruff check . --fix && mypy glovebox/` BEFORE COMMIT

## Configuration Examples

### Simple Docker + USB Configuration
```yaml
keyboard: glove80
description: "MoErgo Glove80"
vendor: "MoErgo"
key_count: 80

compile_methods:
  - method_type: docker
    image: "moergo-zmk-build:latest"
    repository: "moergo-sc/zmk"
    branch: "main"

flash_methods:
  - method_type: usb
    device_query: "vendor=Adafruit and serial~=GLV80-.* and removable=true"
    mount_timeout: 30
```

### Multi-Method with Fallbacks
```yaml
keyboard: custom_board
description: "Custom ZMK Board"
vendor: "Custom"
key_count: 60

compile_methods:
  - method_type: local
    zmk_path: /opt/zmk
    toolchain_path: /opt/zephyr-sdk
    jobs: 8
    fallback_methods: [docker]
  
  - method_type: docker
    image: "zmk-build:latest"
    repository: "zmkfirmware/zmk"
    branch: "main"

flash_methods:
  - method_type: dfu
    vid: "1234"
    pid: "5678"
    interface: 0
    fallback_methods: [usb, bootloader]
  
  - method_type: usb
    device_query: "vendor=Custom and removable=true"
  
  - method_type: bootloader
    protocol: uart
    port: "/dev/ttyUSB0"
    baud_rate: 115200
```

## Benefits

### 1. Type Safety & Clarity
- Each method has its own strongly-typed configuration
- No optional fields that only apply to some methods
- IDE provides accurate autocomplete for each method type
- Clear validation errors for missing/invalid config

### 2. Extensibility
- Easy to add new methods without modifying existing configs
- Each method can have completely different configuration needs
- No configuration pollution between methods

### 3. Configuration Validation
- Method-specific validation rules
- Can validate required dependencies (e.g., check if Docker is available for DockerCompileConfig)
- Clear error messages when configuration is invalid for a method

### 4. Maintainability
- Each method configuration is self-contained
- Easy to understand what each method needs
- No complex conditional logic based on method type

### 5. Implementation Simplicity
- Method implementations get exactly the config type they expect
- No need to extract relevant fields from generic config
- Clear separation of concerns

## REMEMBER: LINTING IS MANDATORY

**EVERY implementation task MUST include a linting check before being marked complete:**

```bash
# REQUIRED before any commit
ruff check . --fix
ruff format .
mypy glovebox/

# REQUIRED before any PR
pre-commit run --all-files
pytest
```

**NO EXCEPTIONS - Code that fails linting CANNOT be merged.**