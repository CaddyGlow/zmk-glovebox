# Configuration System

This document provides comprehensive reference for Glovebox's type-safe configuration system, including file formats, validation rules, profile management, and modular YAML structure.

## Overview

Glovebox uses a sophisticated configuration system built around:
- **Type-safe profiles** combining keyboard and firmware configurations
- **Modular YAML structure** with includes for composition
- **Pydantic models** for validation and serialization
- **Environment variable support** with proper precedence
- **User and system configuration** with clear override patterns

## Configuration Architecture

### Configuration Hierarchy

```
System Level
└── keyboards/
    ├── glove80.yaml              # Main keyboard config
    ├── glove80/
    │   ├── main.yaml            # Core configuration
    │   ├── hardware.yaml        # Hardware specifications
    │   ├── firmwares.yaml       # Firmware variants
    │   ├── strategies.yaml      # Compilation strategies
    │   ├── kconfig.yaml         # Kconfig options
    │   ├── behaviors.yaml       # Behavior definitions
    │   └── toolchain/
    │       └── default.nix      # Nix toolchain files

User Level
└── ~/.glovebox/
    ├── config.yaml              # User configuration
    ├── masters/                 # Master layout versions
    │   └── glove80/
    │       ├── v42.json
    │       └── v42.yaml         # Version metadata
    └── cache/                   # Build and workspace cache
```

### Profile Pattern

The `KeyboardProfile` is central to the configuration system, providing type-safe access to keyboard and firmware configurations.

```python
from glovebox.config import create_keyboard_profile

# Full profile with firmware
profile = create_keyboard_profile("glove80", "v25.05")

# Keyboard-only profile (firmware_version=None)
keyboard_profile = create_keyboard_profile("glove80")
```

## Keyboard Configuration Format

### Main Keyboard Configuration

```yaml
# keyboards/glove80.yaml
includes:
  - "glove80/main.yaml"

# keyboards/glove80/main.yaml
keyboard: "glove80"
description: "MoErgo Glove80 split ergonomic keyboard"
website: "https://moergo.com/collections/glove80-keyboards"

includes:
  - "hardware.yaml"
  - "firmwares.yaml"
  - "strategies.yaml"
  - "kconfig.yaml"
  - "behaviors.yaml"

# Layout formatting configuration
keymap:
  formatting:
    grid_layout: true
    key_width: 4
    spacing: 1
  
  # System behaviors available to this keyboard
  system_behaviors:
    - name: "&bt"
      description: "Bluetooth control"
      parameters: ["action", "profile"]
    - name: "&out"
      description: "Output selection"
      parameters: ["output"]

  # Default kconfig options
  kconfig_options:
    CONFIG_ZMK_SLEEP: {type: "bool", default: true}
    CONFIG_ZMK_IDLE_TIMEOUT: {type: "int", default: 30000}
```

### Hardware Configuration

```yaml
# keyboards/glove80/hardware.yaml
matrix_pins:
  rows: ["&pro_micro 21", "&pro_micro 20", "&pro_micro 19", "&pro_micro 18", "&pro_micro 15", "&pro_micro 14"]
  columns: ["&pro_micro 5", "&pro_micro 6", "&pro_micro 7", "&pro_micro 8", "&pro_micro 9"]

# Physical layout for display formatting
physical_layout:
  key_positions:
    # Left hand positions (0-39)
    left_hand: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39]
    # Right hand positions (40-79)
    right_hand: [40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79]

# USB identification
usb:
  vendor_id: "0x239A"
  product_id: "0x0029"
  manufacturer: "MoErgo"
  product: "Glove80"

# Flash configuration
flash:
  method: "usb"
  file_pattern: "*.uf2"
  mount_detection:
    volume_labels: ["GLV80LHBOOT", "GLV80RHBOOT"]
    vendor_names: ["MoErgo"]
```

### Firmware Configuration

```yaml
# keyboards/glove80/firmwares.yaml
firmwares:
  v25.05:
    version: "v25.05"
    description: "MoErgo ZMK v25.05 Release"
    changelog_url: "https://github.com/moergo-sc/zmk/releases/tag/v25.05"
    
    # Build configuration
    build:
      targets:
        - board: "glove80_lh"
          shield: null
          artifact_name: "glove80_left"
        - board: "glove80_rh"
          shield: null
          artifact_name: "glove80_right"
      
      parallel: true
      timeout: 600
    
    # Additional kconfig options specific to this firmware
    kconfig:
      CONFIG_ZMK_RGB_UNDERGLOW: {type: "bool", default: true}
      CONFIG_ZMK_RGB_UNDERGLOW_AUTO_OFF_IDLE: {type: "bool", default: true}
    
    # Additional system behaviors for this firmware
    system_behaviors:
      - name: "&rgb_ug"
        description: "RGB underglow control"
        parameters: ["command"]
    
    # Docker configuration for compilation
    docker:
      image: "moergo/zmk-dev:latest"
      user_mapping: true
      volumes:
        - type: "workspace"
          readonly: false
        - type: "cache" 
          readonly: false
    
    # Flash configuration overrides
    flash:
      wait_timeout: 30
      verify_flash: true

  main:
    version: "main"
    description: "Latest development version"
    
    build:
      targets:
        - board: "glove80_lh"
          shield: null
        - board: "glove80_rh"
          shield: null
    
    docker:
      image: "moergo/zmk-dev:main"
```

### Compilation Strategies

```yaml
# keyboards/glove80/strategies.yaml
compile:
  type: "moergo"
  repository: "moergo-sc/zmk"
  branch_map:
    v25.05: "v25.05"
    main: "main"
  
  # Build matrix configuration
  build_matrix:
    board: ["glove80_lh", "glove80_rh"]
    include:
      - board: "glove80_lh"
        artifact_name: "glove80_left"
      - board: "glove80_rh" 
        artifact_name: "glove80_right"
  
  # Docker configuration
  docker:
    base_image: "moergo/zmk-dev"
    user_mapping: true
    timeout: 600
  
  # Workspace configuration  
  workspace:
    cache_key_template: "moergo-{repository}-{branch}-{hash}"
    preserve_build_artifacts: true
    cleanup_on_success: false

# Alternative ZMK west strategy
compile_zmk:
  type: "zmk_west"
  repository: "zmkfirmware/zmk"
  branch: "main"
  
  build_matrix:
    board: ["nice_nano_v2"]
    shield: ["glove80_left", "glove80_right"]
  
  docker:
    base_image: "zmkfirmware/zmk-dev-arm"
```

### Behavior Definitions

```yaml
# keyboards/glove80/behaviors.yaml
behaviors:
  # Standard ZMK behaviors
  "&kp":
    description: "Key press"
    parameters: ["keycode"]
    formatter: "simple"
  
  "&mt":
    description: "Mod-tap"
    parameters: ["modifier", "keycode"]
    formatter: "mod_tap"
  
  "&lt":
    description: "Layer-tap"
    parameters: ["layer", "keycode"]
    formatter: "layer_tap"
  
  # Custom Glove80 behaviors
  "&magic":
    description: "Magic key functionality"
    parameters: ["action"]
    formatter: "magic"
    custom_defined: true
  
  "&lower":
    description: "Lower layer activation"
    parameters: []
    formatter: "simple"
    custom_defined: true

# Custom behavior formatters
formatters:
  mod_tap:
    template: "&mt {modifier} {keycode}"
    validation:
      modifier: ["LCTRL", "LALT", "LGUI", "LSHFT", "RCTRL", "RALT", "RGUI", "RSHFT"]
  
  layer_tap:
    template: "&lt {layer} {keycode}"
    validation:
      layer: {type: "int", min: 0, max: 15}
  
  magic:
    template: "&magic {action}"
    validation:
      action: ["0", "1", "2", "3"]
```

### Kconfig Options

```yaml
# keyboards/glove80/kconfig.yaml
kconfig_options:
  # Power management
  CONFIG_ZMK_SLEEP:
    type: "bool"
    default: true
    description: "Enable deep sleep support"
    category: "power"
  
  CONFIG_ZMK_IDLE_TIMEOUT:
    type: "int"
    default: 30000
    min: 1000
    max: 3600000
    description: "Idle timeout in milliseconds"
    category: "power"
  
  # Connectivity
  CONFIG_ZMK_BLE:
    type: "bool"
    default: true
    description: "Enable Bluetooth LE support"
    category: "connectivity"
  
  CONFIG_ZMK_USB:
    type: "bool" 
    default: true
    description: "Enable USB connectivity"
    category: "connectivity"
  
  # RGB underglow
  CONFIG_ZMK_RGB_UNDERGLOW:
    type: "bool"
    default: false
    description: "Enable RGB underglow"
    category: "display"
    depends_on: ["CONFIG_LED_STRIP"]
  
  CONFIG_ZMK_RGB_UNDERGLOW_AUTO_OFF_IDLE:
    type: "bool"
    default: true
    description: "Auto-disable RGB on idle"
    category: "display"
    depends_on: ["CONFIG_ZMK_RGB_UNDERGLOW"]

# Kconfig categories for organization
categories:
  power:
    title: "Power Management"
    description: "Sleep, idle, and power consumption settings"
  
  connectivity:
    title: "Connectivity"
    description: "Bluetooth, USB, and wireless settings"
  
  display:
    title: "Display & LEDs"
    description: "RGB, OLED, and visual feedback settings"
  
  input:
    title: "Input Processing"
    description: "Key scanning, debounce, and input handling"
```

## User Configuration Format

### Main User Configuration

```yaml
# ~/.glovebox/config.yaml
# Path configurations
keyboard-paths:
  - "~/.glovebox/keyboards"
  - "/usr/share/glovebox/keyboards"

cache-dir: "~/.glovebox/cache"
config-dir: "~/.glovebox"

# Behavior configurations
emoji-mode: false
cache-strategy: "aggressive"  # "aggressive", "conservative", "disabled"

# Build configurations
docker-user-mapping: true
parallel-builds: 4

# Display configurations
default-view-mode: "grid"    # "grid", "list", "compact"
key-width: 4

# CLI configurations
output-format: "human"       # "human", "json", "yaml"
theme: "auto"               # "auto", "light", "dark"

# Logging configuration
logging:
  level: "INFO"
  format: "human"           # "human", "json", "structured"
  
  handlers:
    console:
      type: "console"
      level: "INFO"
      format: "human"
    
    file:
      type: "file"
      level: "DEBUG"
      format: "structured"
      filename: "~/.glovebox/logs/glovebox.log"
      max_size: "10MB"
      backup_count: 3

# MoErgo service configuration (optional)
moergo:
  credentials:
    username: null            # Set via environment or prompt
    password: null            # Set via environment or prompt
  
  cognito:
    region: "us-east-1"
    user_pool_id: "us-east-1_XXXXXXXXX"
    client_id: "xxxxxxxxxxxxxxxxxxxxxxxxxx"
  
  api:
    base_url: "https://api.moergo.com"
    timeout: 30
    retry_attempts: 3

# Keyboard-specific overrides
keyboard_overrides:
  glove80:
    default-firmware: "v25.05"
    cache-strategy: "aggressive"
    build-timeout: 900
```

### Environment Variable Support

Configuration values can be overridden using environment variables with the `GLOVEBOX_` prefix:

```bash
# Override cache directory
export GLOVEBOX_CACHE_DIR="/tmp/glovebox-cache"

# Override emoji mode
export GLOVEBOX_EMOJI_MODE="true"

# Override logging level
export GLOVEBOX_LOGGING_LEVEL="DEBUG"

# Override MoErgo credentials
export GLOVEBOX_MOERGO_USERNAME="your-username"
export GLOVEBOX_MOERGO_PASSWORD="your-password"

# Override Docker settings
export GLOVEBOX_DOCKER_USER_MAPPING="false"
export GLOVEBOX_PARALLEL_BUILDS="8"
```

## Configuration Models

### KeyboardConfig

Main model for keyboard configuration.

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
    
    # Method configurations (optional)
    compile: CompileMethodConfigUnion | None = None
    flash: FlashMethodConfigUnion | None = None
```

### FirmwareConfig

Model for firmware-specific configuration.

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

Model for user configuration.

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

### KConfigOption

Model for individual Kconfig options.

```python
from glovebox.config.models import KConfigOption

class KConfigOption(GloveboxBaseModel):
    """Individual Kconfig option definition."""
    
    type: str  # "bool", "int", "string", "choice"
    default: ConfigValue | None = None
    description: str = ""
    category: str = "general"
    
    # Validation constraints
    min: int | None = None
    max: int | None = None
    choices: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list, alias="depends-on")
    
    # UI hints
    help_text: str = Field(default="", alias="help-text")
    advanced: bool = False
```

## Configuration Loading and Validation

### Include Processing

Glovebox supports modular configuration through YAML includes:

```python
from glovebox.config.include_loader import create_include_loader

include_loader = create_include_loader()

# Load configuration with includes resolved
config_data = include_loader.load_with_includes(config_path)
```

**Include resolution rules:**
1. Relative paths are resolved relative to the including file
2. Includes are processed recursively
3. Circular includes are detected and prevented
4. Later includes override earlier values for duplicate keys
5. Lists are merged (not replaced) across includes

### Configuration Factory Functions

```python
from glovebox.config import create_keyboard_profile, create_user_config

# Create keyboard profile
profile = create_keyboard_profile("glove80", "v25.05")

# Create keyboard-only profile
keyboard_profile = create_keyboard_profile("glove80")

# Create user configuration
user_config = create_user_config()

# Create user configuration with custom config file
user_config = create_user_config(config_file=Path("/custom/config.yaml"))
```

### Configuration Search Paths

Keyboard configurations are discovered through a search path hierarchy:

```python
def get_keyboard_search_paths() -> list[Path]:
    """Get search paths for keyboard configurations."""
    paths = []
    
    # User configuration paths from config
    user_config = create_user_config()
    for path in user_config.keyboard_paths:
        paths.append(Path(path).expanduser())
    
    # System installation paths
    paths.extend([
        Path("/usr/share/glovebox/keyboards"),
        Path("/usr/local/share/glovebox/keyboards"),
        Path.cwd() / "keyboards",
    ])
    
    return [p for p in paths if p.exists() and p.is_dir()]
```

## Configuration Validation

### Field Validation

```python
# KConfig option validation
@field_validator("type")
@classmethod
def validate_kconfig_type(cls, v: str) -> str:
    """Validate kconfig option type."""
    valid_types = {"bool", "int", "string", "choice", "hex"}
    if v not in valid_types:
        raise ValueError(f"Invalid kconfig type: {v}. Must be one of {valid_types}")
    return v

# Build target validation
@field_validator("targets")
@classmethod
def validate_build_targets(cls, v: list[BuildTarget]) -> list[BuildTarget]:
    """Validate build targets."""
    if not v:
        raise ValueError("At least one build target must be specified")
    
    # Validate unique artifact names
    artifact_names = [target.artifact_name for target in v if target.artifact_name]
    if len(artifact_names) != len(set(artifact_names)):
        raise ValueError("Build target artifact names must be unique")
    
    return v
```

### Cross-field Validation

```python
@model_validator(mode="after")
def validate_firmware_dependencies(self) -> "FirmwareConfig":
    """Validate firmware configuration dependencies."""
    # Check kconfig dependencies
    for option_name, option in self.kconfig.items():
        for dep in option.depends_on:
            if dep not in self.kconfig:
                raise ValueError(
                    f"Kconfig option {option_name} depends on {dep}, "
                    f"but {dep} is not defined"
                )
    
    # Validate Docker configuration if present
    if self.docker and not self.docker.image:
        raise ValueError("Docker configuration requires an image")
    
    return self
```

## Configuration Usage Examples

### Profile Creation and Usage

```python
from glovebox.config import create_keyboard_profile

# Create full profile
profile = create_keyboard_profile("glove80", "v25.05")

# Access configuration
print(f"Keyboard: {profile.keyboard_name}")
print(f"Firmware: {profile.firmware_version}")
print(f"Description: {profile.keyboard_config.description}")

# Access merged kconfig options
kconfig = profile.kconfig_options
sleep_enabled = kconfig.get("CONFIG_ZMK_SLEEP", {}).get("default", False)

# Access system behaviors
behaviors = profile.system_behaviors
bt_behavior = next((b for b in behaviors if b.name == "&bt"), None)

# Load keyboard-specific files
nix_toolchain = profile.load_toolchain_file("default.nix")
custom_config = profile.load_file("custom/settings.yaml")
```

### User Configuration Management

```python
from glovebox.config import create_user_config

# Load user configuration
user_config = create_user_config()

# Access configuration values
cache_dir = user_config.cache_dir
emoji_mode = user_config.emoji_mode
parallel_builds = user_config.parallel_builds

# Modify configuration
user_config.emoji_mode = True
user_config.parallel_builds = 8

# Save changes
user_config.save()

# Environment variable support
import os
os.environ["GLOVEBOX_EMOJI_MODE"] = "true"
user_config = create_user_config()  # Will use environment override
```

### Configuration Validation

```python
from pydantic import ValidationError

try:
    config = KeyboardConfig.model_validate(yaml_data)
except ValidationError as e:
    for error in e.errors():
        print(f"Configuration error at {error['loc']}: {error['msg']}")
```

### Dynamic Configuration

```python
# Get available keyboards
available_keyboards = get_available_keyboards()

# Get available firmwares for keyboard
available_firmwares = get_available_firmwares("glove80")

# Get default firmware
default_firmware = get_default_firmware("glove80")

# Create profile with defaults
profile = create_keyboard_profile("glove80", default_firmware)
```

This comprehensive configuration system provides type safety, validation, and flexibility while maintaining clear separation between keyboard-specific, firmware-specific, and user-specific settings.