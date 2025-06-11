# Configuration Domain Documentation

The Configuration domain provides type-safe configuration management, keyboard profiles, and user settings. It handles the complex configuration hierarchy that supports multiple keyboards, firmware variants, and user preferences.

## Overview

The Configuration domain is responsible for:
- **Keyboard Profiles**: Unified access to keyboard and firmware configurations
- **Configuration Loading**: YAML-based keyboard and firmware definitions
- **User Preferences**: Multi-source user configuration with precedence rules
- **Type Safety**: Pydantic-based validation and serialization
- **Configuration Discovery**: Automatic discovery of available keyboards and firmwares

## Domain Structure

```
glovebox/config/
├── __init__.py              # Domain exports and factory functions
├── keyboard_profile.py      # Keyboard profile management
├── profile.py              # KeyboardProfile class
├── user_config.py          # User configuration management
├── include_loader.py       # Configuration include system
├── compile_methods.py      # Compilation method configurations
├── flash_methods.py        # Flash method configurations
└── models/                 # Configuration data models
    ├── __init__.py
    ├── keyboard.py         # Keyboard configuration models
    ├── firmware.py         # Firmware configuration models
    ├── user.py            # User configuration models
    ├── behavior.py        # Behavior configuration models
    ├── display.py         # Display configuration models
    └── zmk.py            # ZMK-specific configuration models
```

## Core Models

### KeyboardConfig
Main keyboard configuration model:

```python
from glovebox.config.models import KeyboardConfig

class KeyboardConfig(BaseModel):
    """Keyboard configuration definition."""
    keyboard: str                           # Keyboard name
    description: str                        # Human-readable description
    vendor: str                            # Manufacturer
    key_count: Optional[int] = None        # Number of keys
    
    # Core configuration sections
    flash: FlashMethodConfig               # Flash configuration
    build: BuildOptions                    # Build configuration
    
    # Optional sections (support keyboard-only profiles)
    keymap: Optional[KeymapSection] = None # Keymap configuration
    firmwares: Optional[dict[str, FirmwareConfig]] = None  # Firmware variants
    
    # Additional sections
    display: Optional[DisplayConfig] = None # Display settings
    validation: Optional[ValidationLimits] = None  # Validation rules
```

### FirmwareConfig
Firmware variant configuration:

```python
class FirmwareConfig(BaseModel):
    """Firmware variant configuration."""
    description: str                        # Firmware description
    version: str                           # Firmware version
    branch: Optional[str] = None           # Git branch
    
    # Build overrides
    build_options: Optional[BuildOptions] = None    # Override build settings
    kconfig_options: Optional[dict[str, str]] = None  # Kconfig overrides
    system_behaviors: Optional[list[SystemBehavior]] = None  # Behavior overrides
    
    # Compilation settings
    config_repo_url: Optional[str] = None   # ZMK config repository
    workspace_path: Optional[str] = None    # Workspace directory
    compilation_strategy: Optional[str] = None  # Compilation method
```

### UserConfigData
User preferences and settings:

```python
from glovebox.config.models import UserConfigData

class UserConfigData(BaseModel):
    """User configuration data model."""
    # Default profile
    profile: Optional[str] = None           # Default keyboard/firmware profile
    
    # Paths
    keyboard_paths: list[str] = []          # Additional keyboard config paths
    output_dir: Optional[str] = None        # Default output directory
    
    # Logging
    log_level: str = "WARNING"              # Default log level
    log_file: Optional[str] = None          # Log file path
    
    # Firmware settings
    firmware: FirmwareUserConfig = FirmwareUserConfig()
    
    # Flash settings  
    flash: FlashUserConfig = FlashUserConfig()
```

### BuildOptions
Build configuration settings:

```python
class BuildOptions(BaseModel):
    """Build configuration options."""
    method: str                             # Build method (docker, cmake, etc.)
    
    # Docker settings
    docker_image: Optional[str] = None      # Docker image name
    docker_tag: Optional[str] = None        # Docker image tag
    
    # Repository settings
    repository: Optional[str] = None        # Git repository URL
    branch: Optional[str] = None           # Git branch
    
    # Build settings
    parallel_jobs: Optional[int] = None     # Number of parallel jobs
    clean_build: bool = False              # Clean before build
    
    # Docker user mapping
    enable_user_mapping: bool = True        # Enable --user flag
    detect_user_automatically: bool = True  # Auto-detect UID/GID
    manual_uid: Optional[int] = None        # Manual UID override
    manual_gid: Optional[int] = None        # Manual GID override
    manual_username: Optional[str] = None   # Manual username override
    host_home_dir: Optional[str] = None     # Host home directory
    container_home_dir: Optional[str] = None # Container home directory
    force_manual: bool = False             # Force manual settings
```

## Profile System

### KeyboardProfile
Unified access to keyboard and firmware configuration:

```python
from glovebox.config import create_keyboard_profile

# Full profile with firmware
profile = create_keyboard_profile("glove80", "v25.05")

# Keyboard-only profile (firmware_version=None)
profile = create_keyboard_profile("glove80")

# Profile properties
print(profile.keyboard_name)        # "glove80"
print(profile.firmware_version)     # "v25.05" or None
print(profile.keyboard_config.description)  # Keyboard description

# Safe access to optional components
if profile.firmware_config:
    print(profile.firmware_config.version)

# Always available (empty for keyboard-only profiles)
behaviors = profile.system_behaviors    # Returns [] for keyboard-only
kconfig = profile.kconfig_options      # Returns {} for keyboard-only
```

### Profile Factory Functions
Consistent profile creation:

```python
from glovebox.config.keyboard_profile import (
    create_keyboard_profile,
    create_keyboard_profile_with_includes,
    load_keyboard_config,
    get_available_keyboards,
    get_available_firmwares
)

# Create profile
profile = create_keyboard_profile("keyboard_name", "firmware_version")

# Create with include processing
profile = create_keyboard_profile_with_includes("keyboard_name", "firmware_version")

# Load raw keyboard config
keyboard_config = load_keyboard_config("keyboard_name")

# Discovery functions
keyboards = get_available_keyboards()
firmwares = get_available_firmwares("keyboard_name")
```

### Keyboard-Only Profile Support
Support for minimal keyboard configurations:

```python
# Minimal keyboard configuration (no keymap, no firmwares)
minimal_config = KeyboardConfig.model_validate({
    'keyboard': 'minimal_test',
    'description': 'Test minimal keyboard',
    'vendor': 'Test Vendor',
    'key_count': 10,
    'flash': {
        'method': 'mass_storage',
        'query': 'vendor=Custom',
        'usb_vid': 0x1234,
        'usb_pid': 0x5678
    },
    'build': {
        'method': 'docker',
        'docker_image': 'zmk-build',
        'repository': 'zmkfirmware/zmk',
        'branch': 'main'
    }
    # keymap and firmwares sections are optional
})

# Create keyboard-only profile
profile = create_keyboard_profile("minimal_test")  # No firmware version

# Safe operations for keyboard-only profiles
is_keyboard_only = profile.firmware_version is None
has_firmware = profile.firmware_config is not None
behaviors = profile.system_behaviors    # Returns empty list
kconfig = profile.kconfig_options      # Returns empty dict
```

## User Configuration

### UserConfig
Multi-source user configuration management:

```python
from glovebox.config import create_user_config

# Create user configuration with automatic source detection
user_config = create_user_config()

# Access configuration with type safety
profile = user_config._config.profile
log_level = user_config._config.log_level
keyboard_paths = user_config._config.keyboard_paths

# Set configuration values
user_config.set("profile", "glove80/v25.05")
user_config.set("log_level", "DEBUG")
user_config.set("firmware.flash.skip_existing", True)

# Save configuration
user_config.save()

# Get configuration with sources
config_with_sources = user_config.get_config_with_sources()
```

### Configuration Sources and Precedence
Multi-source configuration loading:

```
Precedence (highest to lowest):
1. Environment variables (GLOVEBOX_*)
2. Local config file (./glovebox.yaml)  
3. Global config file (~/.config/glovebox/config.yaml)
4. Default values
```

**Environment Variables**:
```bash
export GLOVEBOX_PROFILE="glove80/v25.05"
export GLOVEBOX_LOG_LEVEL="DEBUG"
export GLOVEBOX_FIRMWARE__FLASH__SKIP_EXISTING="true"
```

**Configuration Files**:
```yaml
# ~/.config/glovebox/config.yaml
profile: glove80/v25.05
log_level: INFO

firmware:
  flash:
    skip_existing: true
    timeout: 120
  docker:
    enable_user_mapping: true
    manual_uid: 1001

keyboard_paths:
  - /custom/keyboards
  - /shared/keyboards
```

## Configuration Loading

### Keyboard Configuration Discovery
Automatic discovery of keyboard configurations:

```python
from glovebox.config.keyboard_profile import get_available_keyboards

# Get all available keyboards
keyboards = get_available_keyboards()
# Returns: ["glove80", "corne", "lily58", ...]

# Get keyboards from custom paths
keyboards = get_available_keyboards(
    additional_paths=[Path("/custom/keyboards")]
)
```

### Configuration Validation
Type-safe configuration validation:

```python
from glovebox.config.models import KeyboardConfig
from pydantic import ValidationError

try:
    config = KeyboardConfig.model_validate(yaml_data)
except ValidationError as e:
    print(f"Configuration validation failed: {e}")
    for error in e.errors():
        print(f"  - {error['loc']}: {error['msg']}")
```

### Include System
Configuration include and inheritance:

```python
from glovebox.config.include_loader import load_config_with_includes

# Load configuration with include processing
config = load_config_with_includes(
    config_path=Path("keyboards/custom.yaml"),
    include_paths=[
        Path("keyboards/config/common/"),
        Path("keyboards/config/behaviors/")
    ]
)

# Configuration can include other files
# keyboards/custom.yaml:
# includes:
#   - common/default_includes.yaml
#   - behaviors/zmk_core.yaml
#   - behaviors/zmk_bluetooth.yaml
```

## Configuration Models

### Display Configuration
Layout display and formatting settings:

```python
from glovebox.config.models import DisplayConfig

class DisplayConfig(BaseModel):
    """Display configuration for layouts."""
    layout: VisualLayout                   # Visual layout definition
    formatting: DisplayFormatting          # Display formatting rules
    
class DisplayFormatting(BaseModel):
    """Display formatting configuration."""
    default_key_width: int = 8             # Default key display width
    key_gap: str = "  "                   # Gap between keys
    layer_separator: str = "\n\n"         # Separator between layers
    show_layer_names: bool = True          # Show layer names
    show_key_codes: bool = False          # Show raw key codes
```

### Behavior Configuration
Behavior definition and mapping:

```python
from glovebox.config.models import BehaviorConfig

class BehaviorConfig(BaseModel):
    """Behavior configuration definition."""
    system_behaviors: list[SystemBehavior] = []     # System behaviors
    behavior_mapping: dict[str, BehaviorMapping] = {} # Behavior mappings
    
class SystemBehavior(BaseModel):
    """System behavior definition."""
    name: str                              # Behavior name
    display_name: Optional[str] = None     # Display name
    description: Optional[str] = None      # Description
    params: list[SystemBehaviorParam] = [] # Parameters
```

### ZMK Configuration
ZMK-specific configuration settings:

```python
from glovebox.config.models import ZmkConfig

class ZmkConfig(BaseModel):
    """ZMK-specific configuration."""
    patterns: ZmkPatterns                  # ZMK patterns and validation
    compatible_strings: ZmkCompatibleStrings  # Compatible device strings
    validation_limits: ValidationLimits    # Validation constraints
    
class ValidationLimits(BaseModel):
    """Validation limits for ZMK."""
    max_layers: int = 32                   # Maximum layers
    max_behaviors: int = 1000              # Maximum behaviors
    max_combos: int = 500                  # Maximum combos
    max_macros: int = 100                  # Maximum macros
```

## Usage Patterns

### Basic Profile Usage

```python
from glovebox.config import create_keyboard_profile

# Create profile for specific keyboard and firmware
profile = create_keyboard_profile("glove80", "v25.05")

# Use in services
from glovebox.layout import create_layout_service
layout_service = create_layout_service()

result = layout_service.generate(
    profile=profile,
    layout_data=layout_data,
    output_prefix="output/my_layout"
)

# Access configuration properties
print(f"Building for {profile.keyboard_config.description}")
print(f"Using firmware {profile.firmware_config.version}")
```

### User Configuration Management

```python
from glovebox.config import create_user_config

# Load user configuration
user_config = create_user_config()

# Set default profile
user_config.set("profile", "glove80/v25.05")

# Configure firmware settings
user_config.set("firmware.flash.timeout", 120)
user_config.set("firmware.flash.skip_existing", True)

# Configure Docker settings
user_config.set("firmware.docker.enable_user_mapping", True)
user_config.set("firmware.docker.manual_uid", 1001)

# Save configuration
user_config.save()

# Access configuration
default_profile = user_config._config.profile
flash_timeout = user_config._config.firmware.flash.timeout
```

### Custom Keyboard Configuration

```python
# Define custom keyboard configuration
custom_keyboard = {
    'keyboard': 'my_custom_60',
    'description': 'Custom 60% keyboard',
    'vendor': 'Custom Keyboards',
    'key_count': 61,
    
    'flash': {
        'method': 'mass_storage',
        'query': 'vendor=Custom and removable=true',
        'usb_vid': 0x1234,
        'usb_pid': 0x5678
    },
    
    'build': {
        'method': 'docker',
        'docker_image': 'zmk-build:latest',
        'repository': 'zmkfirmware/zmk',
        'branch': 'main',
        'enable_user_mapping': True
    },
    
    'firmwares': {
        'stable': {
            'description': 'Stable firmware',
            'version': 'v1.0',
            'branch': 'main'
        },
        'beta': {
            'description': 'Beta firmware with new features',
            'version': 'v1.1-beta',
            'branch': 'beta',
            'kconfig_options': {
                'CONFIG_ZMK_RGB_UNDERGLOW': 'y'
            }
        }
    }
}

# Validate and save
from glovebox.config.models import KeyboardConfig
config = KeyboardConfig.model_validate(custom_keyboard)

# Save to file
import yaml
with open("keyboards/my_custom_60.yaml", "w") as f:
    yaml.dump(custom_keyboard, f)
```

### Configuration Discovery and Validation

```python
from glovebox.config.keyboard_profile import (
    get_available_keyboards,
    get_available_firmwares,
    load_keyboard_config
)

# Discover available configurations
keyboards = get_available_keyboards()
print(f"Available keyboards: {keyboards}")

for keyboard in keyboards:
    firmwares = get_available_firmwares(keyboard)
    print(f"{keyboard}: {firmwares}")

# Load and validate specific configuration
try:
    config = load_keyboard_config("glove80")
    print(f"Loaded {config.description}")
    print(f"Vendor: {config.vendor}")
    print(f"Available firmwares: {list(config.firmwares.keys())}")
except FileNotFoundError:
    print("Keyboard configuration not found")
except ValidationError as e:
    print(f"Configuration validation failed: {e}")
```

## Testing

### Unit Tests
Test configuration models and validation:

```python
def test_keyboard_config_validation():
    """Test keyboard configuration validation."""
    valid_config = {
        'keyboard': 'test',
        'description': 'Test keyboard',
        'vendor': 'Test Vendor',
        'flash': {...},
        'build': {...}
    }
    
    config = KeyboardConfig.model_validate(valid_config)
    assert config.keyboard == 'test'

def test_keyboard_only_profile():
    """Test keyboard-only profile support."""
    profile = create_keyboard_profile("test_keyboard")
    
    assert profile.firmware_version is None
    assert profile.firmware_config is None
    assert profile.system_behaviors == []
    assert profile.kconfig_options == {}
```

### Integration Tests
Test configuration loading and profile creation:

```python
def test_profile_creation_flow():
    """Test complete profile creation workflow."""
    # Test full profile
    profile = create_keyboard_profile("glove80", "v25.05")
    assert profile.keyboard_name == "glove80"
    assert profile.firmware_version == "v25.05"
    assert profile.firmware_config is not None
    
    # Test keyboard-only profile
    keyboard_only = create_keyboard_profile("glove80")
    assert keyboard_only.keyboard_name == "glove80"
    assert keyboard_only.firmware_version is None
    assert keyboard_only.firmware_config is None

def test_user_config_persistence():
    """Test user configuration save/load."""
    user_config = create_user_config()
    
    # Set configuration
    user_config.set("profile", "test/main")
    user_config.set("log_level", "DEBUG")
    
    # Save and reload
    user_config.save()
    reloaded = create_user_config()
    
    assert reloaded._config.profile == "test/main"
    assert reloaded._config.log_level == "DEBUG"
```

## Error Handling

### Configuration Errors
```python
from glovebox.core.errors import ConfigurationError

try:
    profile = create_keyboard_profile("nonexistent", "v1.0")
except FileNotFoundError as e:
    raise ConfigurationError(
        "Keyboard configuration not found",
        keyboard_name="nonexistent"
    ) from e

try:
    config = KeyboardConfig.model_validate(invalid_data)
except ValidationError as e:
    raise ConfigurationError(
        "Invalid keyboard configuration",
        validation_errors=e.errors()
    ) from e
```

### Profile Creation Errors
```python
from glovebox.core.errors import ProfileCreationError

try:
    profile = create_keyboard_profile("keyboard", "invalid_firmware")
except KeyError as e:
    raise ProfileCreationError(
        "Firmware version not found",
        keyboard_name="keyboard",
        firmware_version="invalid_firmware",
        available_firmwares=list(config.firmwares.keys())
    ) from e
```

## Performance Considerations

### Configuration Caching
- **Profile cache**: Keyboard profiles cached after creation
- **Config file cache**: YAML files cached after parsing
- **Include cache**: Processed includes cached to avoid reprocessing
- **Discovery cache**: Available keyboards/firmwares cached

### Lazy Loading
- **Firmware configs**: Only loaded when accessed
- **Include processing**: Deferred until needed
- **Validation**: Performed only when required

### Memory Management
- **Cache size limits**: Configuration caches have size limits
- **Cache invalidation**: Caches invalidated on file changes
- **Resource cleanup**: File handles properly closed

## Future Enhancements

### Planned Features
- **Configuration validation**: Enhanced validation with cross-references
- **Configuration templates**: Templates for common keyboard types
- **Remote configurations**: Support for remote configuration repositories
- **Configuration migration**: Automatic migration between schema versions

### Extension Points
- **Custom validators**: Plugin system for configuration validation
- **Configuration providers**: Alternative configuration sources
- **Profile transformers**: Profile transformation pipelines
- **Configuration UI**: Web-based configuration editor