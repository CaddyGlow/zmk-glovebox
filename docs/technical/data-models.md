# Data Models Reference

This document provides comprehensive reference for all Pydantic data models used throughout Glovebox, including schemas, validation rules, and usage patterns.

## Base Model Architecture

### GloveboxBaseModel

All Glovebox models inherit from `GloveboxBaseModel`, which enforces consistent serialization behavior.

```python
from glovebox.models.base import GloveboxBaseModel

class GloveboxBaseModel(BaseModel):
    """Base model class for all Glovebox Pydantic models."""
    
    model_config = ConfigDict(
        extra="allow",                    # Allow extra fields for flexibility
        str_strip_whitespace=True,        # Strip whitespace from string fields
        use_enum_values=True,             # Use enum values in serialization
        validate_assignment=True,         # Validate assignment after model creation
        validate_by_alias=True,           # Allow loading with alias and name
        validate_by_name=True,
    )
```

#### Serialization Methods

**Consistent serialization with proper defaults:**
```python
# JSON-compatible serialization (recommended)
data = model.model_dump(by_alias=True, mode="json")
# or use convenience method
data = model.to_dict()

# Python-native serialization
data = model.to_dict_python()

# JSON string serialization
json_str = model.model_dump_json(by_alias=True)
```

**Key principles:**
- `by_alias=True` - Always use field aliases for external APIs
- `mode="json"` - JSON-compatible types (datetime → timestamp)
- `exclude_none=True` - Clean output without null values

## Layout Domain Models

### LayoutData

The core model representing complete keyboard layout data.

```python
from glovebox.layout.models import LayoutData

class LayoutData(LayoutMetadata):
    """Complete layout data model following Moergo API field names with aliases."""
    
    # User behavior definitions
    hold_taps: list[HoldTapBehavior] = Field(default_factory=list, alias="holdTaps")
    combos: list[ComboBehavior] = Field(default_factory=list)
    macros: list[MacroBehavior] = Field(default_factory=list)
    input_listeners: list[InputListener] | None = Field(default=None, alias="inputListeners")
    
    # Essential structure fields
    layers: list[LayerBindings] = Field(default_factory=list)
    
    # Custom code
    custom_defined_behaviors: str = Field(default="", alias="custom_defined_behaviors")
    custom_devicetree: str = Field(default="", alias="custom_devicetree")
```

#### Template Processing

LayoutData supports Jinja2 template processing:

```python
# Load with template processing
layout = LayoutData.load_with_templates(data)

# Manual template processing
resolved_layout = layout.process_templates()

# Export with resolved templates (no variables section)
flattened_data = layout.to_flattened_dict()
```

#### Field Validation

**Layer structure validation:**
```python
@field_validator("layers")
@classmethod
def validate_layers_structure(cls, v: list[LayerBindings]) -> list[LayerBindings]:
    """Validate layers structure with proper binding validation."""
    for i, layer in enumerate(v):
        if not isinstance(layer, list):
            raise ValueError(f"Layer {i} must be a list of bindings")
        
        for j, binding in enumerate(layer):
            if not isinstance(binding, LayoutBinding):
                raise ValueError(f"Layer {i}, binding {j} must be a LayoutBinding")
            if not binding.value:
                raise ValueError(f"Layer {i}, binding {j} missing 'value' field")
    
    return v
```

### LayoutBinding

Model for individual key bindings with support for nested parameters.

```python
from glovebox.layout.models import LayoutBinding, LayoutParam

class LayoutBinding(GloveboxBaseModel):
    """Model for individual key bindings."""
    
    value: str  # Behavior code (e.g., "&kp", "&mt")
    params: list[LayoutParam] = Field(default_factory=list)
    
    @property
    def behavior(self) -> str:
        """Get the behavior code."""
        return self.value
```

#### Parsing ZMK Behavior Strings

**Complex binding parsing with nested parameter support:**
```python
# Simple bindings
binding = LayoutBinding.from_str("&kp Q")
# Result: LayoutBinding(value="&kp", params=[LayoutParam(value="Q")])

# Multiple parameters
binding = LayoutBinding.from_str("&mt LCTRL A")
# Result: LayoutBinding(value="&mt", params=[LayoutParam(value="LCTRL"), LayoutParam(value="A")])

# Nested parameters
binding = LayoutBinding.from_str("&kp LC(X)")
# Result: LayoutBinding(value="&kp", params=[LayoutParam(value="LC", params=[LayoutParam(value="X")])])

# Complex modifier chains
binding = LayoutBinding.from_str("&sk LA(LC(LSHFT))")
# Result: LayoutBinding(value="&sk", params=[LayoutParam(value="LA", params=[LayoutParam(value="LC", params=[LayoutParam(value="LSHFT")])])])
```

### LayoutParam

Model for individual parameters within bindings.

```python
from glovebox.layout.models import LayoutParam

class LayoutParam(GloveboxBaseModel):
    """Model for individual binding parameters."""
    
    value: ParamValue  # str or int
    params: list["LayoutParam"] = Field(default_factory=list)  # Nested parameters
```

#### Type Aliases

```python
from glovebox.layout.models.types import (
    ConfigValue,      # str | int | bool
    LayerIndex,       # int
    TemplateNumeric,  # int | str (for template variables)
    LayerBindings,    # list[LayoutBinding]
    ConfigParamList,  # list[ConfigParameter]
    ParamValue,       # str | int
)
```

### Behavior Models

Specialized models for different ZMK behaviors.

#### HoldTapBehavior

```python
from glovebox.layout.models.behaviors import HoldTapBehavior

class HoldTapBehavior(GloveboxBaseModel):
    """Hold-tap behavior configuration."""
    
    name: str
    tap: str
    hold: str
    tapping_term_ms: int = Field(default=200, alias="tapping-term-ms")
    quick_tap_ms: int = Field(default=0, alias="quick-tap-ms")
    require_prior_idle_ms: int = Field(default=0, alias="require-prior-idle-ms")
    flavor: str = "tap-preferred"
    hold_trigger_key_positions: list[int] = Field(default_factory=list, alias="hold-trigger-key-positions")
    hold_trigger_on_release: bool = Field(default=False, alias="hold-trigger-on-release")
```

#### MacroBehavior

```python
from glovebox.layout.models.behaviors import MacroBehavior

class MacroBehavior(GloveboxBaseModel):
    """Macro behavior configuration."""
    
    name: str
    bindings: list[str]
    wait_ms: int = Field(default=0, alias="wait-ms")
    tap_ms: int = Field(default=0, alias="tap-ms")
```

#### ComboBehavior

```python
from glovebox.layout.models.behaviors import ComboBehavior

class ComboBehavior(GloveboxBaseModel):
    """Combo behavior configuration."""
    
    name: str
    key_positions: list[int] = Field(alias="key-positions")
    bindings: list[str]
    timeout_ms: int = Field(default=50, alias="timeout-ms")
    require_prior_idle_ms: int = Field(default=0, alias="require-prior-idle-ms")
    layers: list[int] = Field(default_factory=list)
```

### Metadata Models

#### LayoutMetadata

Base metadata for all layouts.

```python
from glovebox.layout.models.metadata import LayoutMetadata

class LayoutMetadata(GloveboxBaseModel):
    """Base metadata for layout data."""
    
    # Template variables (must be first for proper resolution)
    variables: dict[str, ConfigValue] = Field(default_factory=dict)
    
    # Core identification
    keyboard: str = ""
    firmware_api_version: str = Field(default="1", alias="firmwareApiVersion")
    locale: str = "en-US"
    uuid: str = ""
    parent_uuid: str | None = Field(default=None, alias="parentUuid")
    date: datetime | None = None
    creator: str = ""
    title: str = ""
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    
    # Version management (added for keymap master feature)
    version: str | None = None
    base_version: str | None = Field(default=None, alias="baseVersion")
    base_layout: str | None = Field(default=None, alias="baseLayout")
    last_firmware_build: dict[str, Any] | None = Field(default=None, alias="lastFirmwareBuild")
    
    # Layout structure
    layer_names: list[str] = Field(default_factory=list, alias="layerNames")
    config_parameters: list[ConfigParameter] = Field(default_factory=list, alias="configParameters")
```

## Configuration Domain Models

### KeyboardConfig

Main configuration model for keyboard definitions.

```python
from glovebox.config.models import KeyboardConfig

class KeyboardConfig(GloveboxBaseModel):
    """Configuration for a specific keyboard."""
    
    keyboard: str
    description: str = ""
    website: str = ""
    matrix_pins: list[str] = Field(default_factory=list, alias="matrix-pins")
    
    # Configuration sections
    keymap: KeymapSection
    firmwares: dict[str, FirmwareConfig] = Field(default_factory=dict)
    
    # Method configurations
    compile: CompileMethodConfigUnion | None = None
    flash: FlashMethodConfigUnion | None = None
```

### FirmwareConfig

Configuration for specific firmware versions.

```python
from glovebox.config.models import FirmwareConfig

class FirmwareConfig(GloveboxBaseModel):
    """Configuration for a specific firmware version."""
    
    version: str
    description: str = ""
    changelog_url: str = Field(default="", alias="changelog-url")
    
    # Build configuration
    build: BuildOptions = Field(default_factory=BuildOptions)
    kconfig: dict[str, KConfigOption] = Field(default_factory=dict)
    system_behaviors: list[SystemBehavior] = Field(default_factory=list, alias="system-behaviors")
    
    # Docker configuration
    docker: FirmwareDockerConfig | None = None
    
    # Flash configuration
    flash: FirmwareFlashConfig | None = None
```

### UserConfigData

User-specific configuration model.

```python
from glovebox.config.models import UserConfigData

class UserConfigData(GloveboxBaseModel):
    """User configuration data with validation."""
    
    # Path configurations
    keyboard_paths: list[str] = Field(default_factory=get_default_library_path, alias="keyboard-paths")
    cache_dir: str = Field(default="~/.glovebox/cache", alias="cache-dir")
    config_dir: str = Field(default="~/.glovebox", alias="config-dir")
    
    # Behavior configurations
    emoji_mode: bool = Field(default=False, alias="emoji-mode")
    cache_strategy: str = Field(default="aggressive", alias="cache-strategy")
    
    # Build configurations
    docker_user_mapping: bool = Field(default=True, alias="docker-user-mapping")
    parallel_builds: int = Field(default=1, alias="parallel-builds")
    
    # Display configurations
    default_view_mode: str = Field(default="grid", alias="default-view-mode")
    key_width: int = Field(default=4, alias="key-width")
    
    # Logging configuration
    logging: LoggingConfig = Field(default_factory=create_default_logging_config)
```

## Firmware Domain Models

### BlockDevice

Model for USB block devices used in flashing operations.

```python
from glovebox.firmware.flash.models import BlockDevice

@dataclass
class BlockDevice:
    """Represents a block device with its properties."""
    
    name: str
    device_node: str = ""
    size: int = 0
    type: str = "unknown"
    removable: bool = False
    model: str = ""
    vendor: str = ""
    serial: str = ""
    uuid: str = ""
    label: str = ""
    vendor_id: str = ""
    product_id: str = ""
    partitions: list[str] = field(default_factory=list)
    mountpoints: dict[str, str] = field(default_factory=dict)
    symlinks: set[str] = field(default_factory=set)
    raw: dict[str, str] = field(default_factory=dict)
    
    @property
    def path(self) -> str:
        """Return the device path."""
        return self.device_node
    
    @property
    def description(self) -> str:
        """Return a human-readable description of the device."""
        if self.label:
            return f"{self.label} ({self.name})"
        elif self.vendor and self.model:
            return f"{self.vendor} {self.model} ({self.name})"
        else:
            return self.name
```

#### Device Creation from Platform Sources

**From pyudev (Linux):**
```python
device = BlockDevice.from_pyudev_device(pyudev_device)
```

**From macOS disk utilities:**
```python
device = BlockDevice.from_macos_disk_info(disk_name, disk_info, usb_info, mounted_volumes)
```

### BuildResult

Result model for compilation operations.

```python
from glovebox.firmware.models import BuildResult

class BuildResult(BaseResult):
    """Result of a firmware build operation."""
    
    success: bool
    message: str = ""
    output_files: FirmwareOutputFiles | None = None
    build_log: str = ""
    duration: float = 0.0
    
    # Build metadata
    build_id: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)
    profile_name: str = ""
    strategy: str = ""
```

### FlashResult

Result model for firmware flashing operations.

```python
from glovebox.firmware.flash.models import FlashResult

class FlashResult(BaseResult):
    """Result of a firmware flash operation."""
    
    success: bool
    message: str = ""
    device: BlockDevice | None = None
    files_copied: list[str] = Field(default_factory=list)
    duration: float = 0.0
    bytes_written: int = 0
```

## Compilation Domain Models

### CompilationConfig

Base configuration for compilation strategies.

```python
from glovebox.compilation.models import CompilationConfig

class CompilationConfig(GloveboxBaseModel):
    """Base configuration for compilation strategies."""
    
    type: str  # Strategy identifier
    repository: str
    branch: str = "main"
    build_matrix: BuildMatrix = Field(default_factory=BuildMatrix)
    use_cache: bool = True
    docker: DockerUserConfig = Field(default_factory=DockerUserConfig)
    workspace: ZmkWorkspaceConfig = Field(default_factory=ZmkWorkspaceConfig)
```

### BuildMatrix

Build matrix configuration for multi-target builds.

```python
from glovebox.compilation.models import BuildMatrix, BuildTarget

class BuildMatrix(GloveboxBaseModel):
    """Build matrix configuration for GitHub Actions style builds."""
    
    board: list[str] = Field(default_factory=list)
    shield: list[str] = Field(default_factory=list)
    include: list[BuildTarget] = Field(default_factory=list)
    exclude: list[BuildTarget] = Field(default_factory=list)

class BuildTarget(GloveboxBaseModel):
    """Individual build target specification."""
    
    board: str
    shield: str | None = None
    artifact_name: str | None = Field(default=None, alias="artifact-name")
    cmake_args: str | None = Field(default=None, alias="cmake-args")
```

## Cache Domain Models

### CacheStats

Performance statistics for cache operations.

```python
from glovebox.core.cache.models import CacheStats

class CacheStats(GloveboxBaseModel):
    """Cache performance statistics."""
    
    hits: int = 0
    misses: int = 0
    total_keys: int = 0
    size_bytes: int = 0
    hit_rate: float = 0.0
    
    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate."""
        total = self.hits + self.misses
        return self.misses / total if total > 0 else 0.0
```

### CacheMetadata

Metadata for individual cache entries.

```python
from glovebox.core.cache.models import CacheMetadata

class CacheMetadata(GloveboxBaseModel):
    """Metadata for cache entries."""
    
    key: str
    size: int
    created: datetime
    accessed: datetime
    ttl: int | None = None
    tag: str | None = None
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        if self.ttl is None:
            return False
        return (datetime.now() - self.created).total_seconds() > self.ttl
```

## Results and Response Models

### BaseResult

Base class for all operation results.

```python
from glovebox.models.results import BaseResult

class BaseResult(GloveboxBaseModel):
    """Base class for operation results."""
    
    success: bool
    message: str = ""
    
    @property
    def failed(self) -> bool:
        """Check if operation failed."""
        return not self.success
```

## Validation Patterns

### Custom Validators

**Date validation with timestamp conversion:**
```python
@model_validator(mode="before")
@classmethod
def validate_data_structure(cls, data: Any, info: Any = None) -> Any:
    """Convert integer timestamps to datetime objects."""
    if not isinstance(data, dict):
        return data
    
    if "date" in data and isinstance(data["date"], int):
        from datetime import datetime
        data["date"] = datetime.fromtimestamp(data["date"])
    
    return data
```

**Field validation with proper error messages:**
```python
@field_validator("layers")
@classmethod
def validate_layers_structure(cls, v: list[LayerBindings]) -> list[LayerBindings]:
    """Validate layers structure with detailed error reporting."""
    for i, layer in enumerate(v):
        if not isinstance(layer, list):
            raise ValueError(f"Layer {i} must be a list of bindings")
        
        for j, binding in enumerate(layer):
            if not isinstance(binding, LayoutBinding):
                raise ValueError(f"Layer {i}, binding {j} must be a LayoutBinding")
    
    return v
```

### Serialization Customization

**Custom field ordering:**
```python
@model_serializer(mode="wrap")
def serialize_with_sorted_fields(self, serializer: Any, info: Any) -> dict[str, Any]:
    """Serialize with fields in a specific order."""
    data = serializer(self)
    
    # Define field order (variables must be first for template resolution)
    field_order = [
        "variables", "keyboard", "firmware_api_version", 
        "layers", "custom_defined_behaviors"
    ]
    
    # Create ordered dict
    ordered_data = {}
    for field in field_order:
        if field in data:
            ordered_data[field] = data[field]
    
    return ordered_data
```

## Usage Examples

### Loading and Validating Data

```python
# Load layout data with validation
layout_data = LayoutData.model_validate(json_data, mode="json")

# Load with template processing
layout_data = LayoutData.load_with_templates(json_data)

# Create keyboard profile
profile = create_keyboard_profile("glove80", "v25.05")
```

### Serialization and Export

```python
# Export with aliases for API compatibility
api_data = layout.model_dump(by_alias=True, mode="json")

# Export without template variables
flattened_data = layout.to_flattened_dict()

# Export user config
config_data = user_config.model_dump(by_alias=True, exclude_unset=True)
```

### Error Handling

```python
from pydantic import ValidationError

try:
    layout = LayoutData.model_validate(data)
except ValidationError as e:
    for error in e.errors():
        print(f"Field {error['loc']}: {error['msg']}")
```

## Schema Generation

All models support JSON Schema generation:

```python
# Generate JSON schema
schema = LayoutData.model_json_schema()

# Generate schema with specific serialization mode
schema = LayoutData.model_json_schema(mode="serialization")
```

This enables external integrations and API documentation generation.