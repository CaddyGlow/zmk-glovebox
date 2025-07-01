# API Reference

This document provides comprehensive API documentation for all public interfaces in Glovebox, organized by domain with complete function signatures, parameters, and usage examples.

## Layout Domain API

### Layout Service

Primary service for layout operations and JSON→DTSI conversion.

#### create_layout_service

```python
def create_layout_service() -> LayoutService
```

**Factory function for creating the main layout service.**

**Returns:**
- `LayoutService`: Configured layout service instance

**Example:**
```python
from glovebox.layout import create_layout_service

layout_service = create_layout_service()
```

#### LayoutService.compile

```python
def compile(
    self,
    input_file: Path,
    output_path: Path,
    profile: KeyboardProfile,
    validate_only: bool = False,
    skip_validation: bool = False,
    backup: bool = True,
) -> LayoutResult
```

**Compile JSON layout to ZMK keymap and config files.**

**Parameters:**
- `input_file` (Path): Path to input JSON layout file
- `output_path` (Path): Output directory or file path
- `profile` (KeyboardProfile): Keyboard profile for compilation
- `validate_only` (bool): Only validate, don't generate files
- `skip_validation` (bool): Skip validation during compilation
- `backup` (bool): Create backup of existing files

**Returns:**
- `LayoutResult`: Compilation result with success status and output files

**Raises:**
- `LayoutError`: If layout processing fails
- `ValidationError`: If layout validation fails
- `FileSystemError`: If file operations fail

**Example:**
```python
from glovebox.config import create_keyboard_profile

profile = create_keyboard_profile("glove80", "v25.05")
result = layout_service.compile(
    input_file=Path("my_layout.json"),
    output_path=Path("output/"),
    profile=profile,
    validate_only=False
)

if result.success:
    print(f"Generated files: {result.output_files}")
```

#### LayoutService.validate

```python
def validate(
    self,
    input_file: Path,
    profile: KeyboardProfile,
) -> LayoutResult
```

**Validate JSON layout without generating files.**

**Parameters:**
- `input_file` (Path): Path to JSON layout file
- `profile` (KeyboardProfile): Keyboard profile for validation

**Returns:**
- `LayoutResult`: Validation result with success status and any errors

### Layout Component Service

Service for layout decomposition and composition operations.

#### create_layout_component_service

```python
def create_layout_component_service() -> LayoutComponentService
```

**Factory function for creating layout component service.**

#### LayoutComponentService.decompose

```python
def decompose(
    self,
    input_file: Path,
    output_dir: Path,
    profile: KeyboardProfile,
    format_output: bool = True,
) -> dict[str, Any]
```

**Decompose layout into separate component files.**

**Parameters:**
- `input_file` (Path): Input JSON layout file
- `output_dir` (Path): Output directory for component files
- `profile` (KeyboardProfile): Keyboard profile
- `format_output` (bool): Apply formatting to output files

**Returns:**
- `dict[str, Any]`: Dictionary mapping component names to file paths

#### LayoutComponentService.compose

```python
def compose(
    self,
    input_dir: Path,
    output_file: Path,
    profile: KeyboardProfile,
) -> LayoutResult
```

**Compose component files into complete layout.**

**Parameters:**
- `input_dir` (Path): Directory containing component files
- `output_file` (Path): Output JSON layout file
- `profile` (KeyboardProfile): Keyboard profile

**Returns:**
- `LayoutResult`: Composition result

### Layout Editor Service

Service for programmatic layout editing operations.

#### create_layout_editor_service

```python
def create_layout_editor_service() -> LayoutEditorService
```

#### LayoutEditorService.get_field

```python
def get_field(
    self,
    layout_file: Path,
    field_path: str,
) -> Any
```

**Get field value from layout using dot notation.**

**Parameters:**
- `layout_file` (Path): Path to layout file
- `field_path` (str): Field path using dot notation (e.g., "layers[0].name")

**Returns:**
- `Any`: Field value

**Example:**
```python
editor = create_layout_editor_service()

# Get layer name
layer_name = editor.get_field(
    layout_file=Path("layout.json"),
    field_path="layers[0].name"
)

# Get config parameter
param_value = editor.get_field(
    layout_file=Path("layout.json"),
    field_path="config_parameters[0].value"
)
```

#### LayoutEditorService.set_field

```python
def set_field(
    self,
    layout_file: Path,
    field_path: str,
    value: Any,
    backup: bool = True,
) -> bool
```

**Set field value in layout.**

**Parameters:**
- `layout_file` (Path): Path to layout file
- `field_path` (str): Field path using dot notation
- `value` (Any): New field value
- `backup` (bool): Create backup before modification

**Returns:**
- `bool`: True if field was successfully set

### Layout Layer Service

Service for layer management operations.

#### create_layout_layer_service

```python
def create_layout_layer_service() -> LayoutLayerService
```

#### LayoutLayerService.add_layer

```python
def add_layer(
    self,
    layout_file: Path,
    layer_name: str,
    position: int | None = None,
    import_from: Path | None = None,
    backup: bool = True,
) -> bool
```

**Add new layer to layout.**

**Parameters:**
- `layout_file` (Path): Path to layout file
- `layer_name` (str): Name of new layer
- `position` (int | None): Position to insert layer (None for append)
- `import_from` (Path | None): Import layer data from file
- `backup` (bool): Create backup before modification

**Returns:**
- `bool`: True if layer was successfully added

#### LayoutLayerService.remove_layer

```python
def remove_layer(
    self,
    layout_file: Path,
    layer_name: str,
    backup: bool = True,
) -> bool
```

**Remove layer from layout.**

#### LayoutLayerService.move_layer

```python
def move_layer(
    self,
    layout_file: Path,
    layer_name: str,
    position: int,
    backup: bool = True,
) -> bool
```

**Move layer to new position.**

### Version Management

Service for layout version management and master layout imports.

#### create_version_manager

```python
def create_version_manager(user_config: UserConfig) -> VersionManager
```

**Factory function for version manager.**

#### VersionManager.import_master

```python
def import_master(
    self,
    layout_file: Path,
    version: str,
    keyboard: str,
    force: bool = False,
) -> bool
```

**Import master layout version.**

**Parameters:**
- `layout_file` (Path): Path to master layout file
- `version` (str): Version identifier
- `keyboard` (str): Keyboard name
- `force` (bool): Overwrite existing master version

**Returns:**
- `bool`: True if import was successful

#### VersionManager.upgrade_layout

```python
def upgrade_layout(
    self,
    layout_file: Path,
    to_master: str,
    output_path: Path | None = None,
    from_master: str | None = None,
) -> bool
```

**Upgrade custom layout to new master version.**

**Parameters:**
- `layout_file` (Path): Path to custom layout file
- `to_master` (str): Target master version
- `output_path` (Path | None): Output path (None for in-place)
- `from_master` (str | None): Source master version (auto-detect if None)

**Returns:**
- `bool`: True if upgrade was successful

#### VersionManager.list_masters

```python
def list_masters(
    self,
    keyboard: str,
) -> list[str]
```

**List available master versions for keyboard.**

**Parameters:**
- `keyboard` (str): Keyboard name

**Returns:**
- `list[str]`: List of available master versions

## Firmware Domain API

### Flash Service

Service for firmware flashing operations.

#### create_flash_service

```python
def create_flash_service() -> FlashService
```

**Factory function for flash service.**

#### FlashService.flash_firmware

```python
def flash_firmware(
    self,
    firmware_file: Path,
    device: BlockDevice | None = None,
    profile: KeyboardProfile | None = None,
    wait_for_device: bool = True,
    timeout: int = 60,
) -> FlashResult
```

**Flash firmware to keyboard device.**

**Parameters:**
- `firmware_file` (Path): Path to firmware .uf2 file
- `device` (BlockDevice | None): Target device (auto-detect if None)
- `profile` (KeyboardProfile | None): Keyboard profile
- `wait_for_device` (bool): Wait for device to appear
- `timeout` (int): Wait timeout in seconds

**Returns:**
- `FlashResult`: Flash operation result

**Example:**
```python
flash_service = create_flash_service()

result = flash_service.flash_firmware(
    firmware_file=Path("firmware.uf2"),
    wait_for_device=True,
    timeout=30
)

if result.success:
    print(f"Flashed {result.bytes_written} bytes to {result.device.description}")
```

### Device Detector

Service for USB device detection and monitoring.

#### create_device_detector

```python
def create_device_detector() -> DeviceDetector
```

#### DeviceDetector.detect_devices

```python
def detect_devices(
    self,
    filter_removable: bool = True,
    vendor_filter: str | None = None,
) -> list[BlockDevice]
```

**Detect available block devices.**

**Parameters:**
- `filter_removable` (bool): Only return removable devices
- `vendor_filter` (str | None): Filter by vendor name

**Returns:**
- `list[BlockDevice]`: List of detected devices

#### DeviceDetector.wait_for_device

```python
def wait_for_device(
    self,
    timeout: int = 60,
    device_filter: dict[str, str] | None = None,
) -> BlockDevice | None
```

**Wait for specific device to appear.**

**Parameters:**
- `timeout` (int): Wait timeout in seconds
- `device_filter` (dict[str, str] | None): Device filter criteria

**Returns:**
- `BlockDevice | None`: Detected device or None if timeout

## Compilation Domain API

### Compilation Service

Main service for firmware compilation operations.

#### create_compilation_service

```python
def create_compilation_service(strategy: str) -> CompilationServiceProtocol
```

**Factory function for compilation service with strategy selection.**

**Parameters:**
- `strategy` (str): Compilation strategy ("zmk_west" or "moergo_nix")

**Returns:**
- `CompilationServiceProtocol`: Configured compilation service

#### CompilationServiceProtocol.compile

```python
def compile(
    self,
    keymap_file: Path,
    config_file: Path,
    output_dir: Path,
    config: CompilationConfigUnion,
    keyboard_profile: KeyboardProfile,
    progress_callback: CompilationProgressCallback | None = None,
    json_file: Path | None = None,
) -> BuildResult
```

**Execute firmware compilation.**

**Parameters:**
- `keymap_file` (Path): Path to keymap file
- `config_file` (Path): Path to config file
- `output_dir` (Path): Output directory for build artifacts
- `config` (CompilationConfigUnion): Compilation configuration
- `keyboard_profile` (KeyboardProfile): Keyboard profile
- `progress_callback` (CompilationProgressCallback | None): Progress callback
- `json_file` (Path | None): Original JSON layout file for metadata

**Returns:**
- `BuildResult`: Compilation result with output files and metadata

#### CompilationServiceProtocol.compile_from_json

```python
def compile_from_json(
    self,
    json_file: Path,
    output_dir: Path,
    config: CompilationConfigUnion,
    keyboard_profile: KeyboardProfile,
    progress_callback: CompilationProgressCallback | None = None,
) -> BuildResult
```

**Compile firmware directly from JSON layout file.**

### ZMK West Service

Specialized service for ZMK west workspace compilation.

#### create_zmk_west_service

```python
def create_zmk_west_service() -> ZmkWestService
```

#### ZmkWestService.setup_workspace

```python
def setup_workspace(
    self,
    workspace_dir: Path,
    config: ZmkCompilationConfig,
) -> bool
```

**Set up ZMK west workspace.**

**Parameters:**
- `workspace_dir` (Path): Workspace directory
- `config` (ZmkCompilationConfig): ZMK compilation configuration

**Returns:**
- `bool`: True if workspace setup was successful

### MoErgo Nix Service

Specialized service for MoErgo Nix toolchain compilation.

#### create_moergo_nix_service

```python
def create_moergo_nix_service() -> MoergoNixService
```

## Configuration Domain API

### Keyboard Profile

Type-safe keyboard and firmware configuration management.

#### create_keyboard_profile

```python
def create_keyboard_profile(
    keyboard_name: str,
    firmware_version: str | None = None,
) -> KeyboardProfile
```

**Create keyboard profile with optional firmware version.**

**Parameters:**
- `keyboard_name` (str): Name of keyboard
- `firmware_version` (str | None): Firmware version (None for keyboard-only profile)

**Returns:**
- `KeyboardProfile`: Configured profile instance

**Raises:**
- `ConfigError`: If keyboard or firmware not found

**Example:**
```python
# Full profile with firmware
profile = create_keyboard_profile("glove80", "v25.05")

# Keyboard-only profile
profile = create_keyboard_profile("glove80")
```

#### KeyboardProfile.kconfig_options

```python
@property
def kconfig_options(self) -> dict[str, KConfigOption]
```

**Get combined kconfig options from keyboard and firmware.**

**Returns:**
- `dict[str, KConfigOption]`: Merged kconfig options

#### KeyboardProfile.system_behaviors

```python
@property
def system_behaviors(self) -> list[SystemBehavior]
```

**Get system behaviors for this profile.**

**Returns:**
- `list[SystemBehavior]`: Combined system behaviors

#### KeyboardProfile.load_file

```python
def load_file(self, relative_path: str) -> str | None
```

**Load file from keyboard's profile directory.**

**Parameters:**
- `relative_path` (str): Path relative to keyboard directory

**Returns:**
- `str | None`: File content or None if not found

### User Configuration

User-specific configuration management.

#### create_user_config

```python
def create_user_config(
    config_file: Path | None = None,
) -> UserConfig
```

**Create user configuration with optional custom config file.**

**Parameters:**
- `config_file` (Path | None): Path to config file (None for default)

**Returns:**
- `UserConfig`: User configuration instance

#### UserConfig.get

```python
def get(self, key: str, default: Any = None) -> Any
```

**Get configuration value.**

**Parameters:**
- `key` (str): Configuration key
- `default` (Any): Default value if key not found

**Returns:**
- `Any`: Configuration value

#### UserConfig.set

```python
def set(self, key: str, value: Any) -> None
```

**Set configuration value.**

#### UserConfig.save

```python
def save(self) -> None
```

**Save configuration to file.**

## Core Infrastructure API

### Cache Management

Shared cache coordination system.

#### create_default_cache

```python
def create_default_cache(
    tag: str | None = None,
    enabled: bool = True,
    max_size_gb: int = 2,
    timeout: int = 30,
) -> CacheManager
```

**Create default cache instance with shared coordination.**

**Parameters:**
- `tag` (str | None): Cache tag for domain isolation
- `enabled` (bool): Enable cache operations
- `max_size_gb` (int): Maximum cache size in GB
- `timeout` (int): Operation timeout in seconds

**Returns:**
- `CacheManager`: Cache manager instance

#### CacheManager.get

```python
def get(self, key: str, default: Any = None) -> Any
```

**Retrieve value from cache.**

#### CacheManager.set

```python
def set(self, key: str, value: Any, ttl: int | None = None) -> None
```

**Store value in cache.**

#### CacheManager.get_stats

```python
def get_stats(self) -> CacheStats
```

**Get cache performance statistics.**

### Error Handling

Structured error handling utilities.

#### create_error

```python
def create_error(
    error_type: type[E],
    message: str,
    *,
    cause: Exception | None = None,
    context: dict[str, Any] | None = None,
) -> E
```

**Create structured error with context information.**

**Parameters:**
- `error_type` (type[E]): Error class to create
- `message` (str): Error message
- `cause` (Exception | None): Underlying cause
- `context` (dict[str, Any] | None): Additional context

**Returns:**
- `E`: Configured error instance

## Adapter APIs

### Docker Adapter

Interface for Docker container operations.

#### create_docker_adapter

```python
def create_docker_adapter() -> DockerAdapter
```

#### DockerAdapter.run

```python
def run(
    self,
    image: str,
    command: list[str],
    volumes: list[tuple[str, str]] | None = None,
    environment: dict[str, str] | None = None,
    working_dir: str | None = None,
    user: str | None = None,
    remove: bool = True,
) -> tuple[int, str, str]
```

**Run command in Docker container.**

**Parameters:**
- `image` (str): Docker image name
- `command` (list[str]): Command to execute
- `volumes` (list[tuple[str, str]] | None): Volume mounts (host_path, container_path)
- `environment` (dict[str, str] | None): Environment variables
- `working_dir` (str | None): Working directory
- `user` (str | None): User specification
- `remove` (bool): Remove container after execution

**Returns:**
- `tuple[int, str, str]`: Exit code, stdout, stderr

### File Adapter

Interface for file system operations.

#### create_file_adapter

```python
def create_file_adapter() -> FileAdapter
```

#### FileAdapter.copy_file

```python
def copy_file(
    self,
    source: Path,
    destination: Path,
    preserve_metadata: bool = True,
) -> bool
```

**Copy file with optional metadata preservation.**

#### FileAdapter.ensure_directory

```python
def ensure_directory(
    self,
    directory: Path,
    mode: int = 0o755,
) -> bool
```

**Ensure directory exists with specified permissions.**

### USB Adapter

Interface for USB device operations.

#### create_usb_adapter

```python
def create_usb_adapter() -> USBAdapter
```

#### USBAdapter.list_devices

```python
def list_devices(
    self,
    vendor_filter: str | None = None,
    product_filter: str | None = None,
) -> list[dict[str, Any]]
```

**List USB devices with optional filtering.**

## Protocol Definitions

### Service Protocols

All service interfaces are defined as runtime-checkable protocols.

#### BaseServiceProtocol

```python
@runtime_checkable
class BaseServiceProtocol(Protocol):
    """Base protocol for all services."""
    
    def validate_config(self, config: Any) -> bool:
        """Validate service configuration."""
        ...
    
    def check_available(self) -> bool:
        """Check if service is available."""
        ...
```

#### TemplateServiceProtocol

```python
@runtime_checkable
class TemplateServiceProtocol(Protocol):
    """Protocol for template processing services."""
    
    def process_layout_data(self, layout: LayoutData) -> LayoutData:
        """Process templates in layout data."""
        ...
    
    def render_template(self, template: str, context: dict[str, Any]) -> str:
        """Render template with context."""
        ...
```

## Usage Patterns

### Error Handling

```python
from glovebox.core.errors import LayoutError, CompilationError

try:
    result = layout_service.compile(input_file, output_path, profile)
    if not result.success:
        logger.error("Compilation failed: %s", result.message)
except LayoutError as e:
    logger.error("Layout error: %s", e)
except Exception as e:
    logger.error("Unexpected error: %s", e, exc_info=True)
```

### Progress Callbacks

```python
def progress_callback(progress: CompilationProgress) -> None:
    print(f"Progress: {progress.percentage}% - {progress.current_phase}")

result = compilation_service.compile(
    keymap_file=keymap_path,
    config_file=config_path,
    output_dir=output_dir,
    config=compilation_config,
    keyboard_profile=profile,
    progress_callback=progress_callback
)
```

### Resource Management

```python
# Proper cache cleanup
cache_manager = create_default_cache(tag="compilation")
try:
    # Use cache operations
    result = cache_manager.get("key")
finally:
    cache_manager.close()

# Context manager pattern
with cache_manager:
    # Cache operations
    pass
```